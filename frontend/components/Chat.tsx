"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { getConversation, streamChat, type Citation } from "@/lib/api";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}

interface ChatProps {
  conversationId: string | null;
  onConversationStarted: (id: string) => void;
}

export default function Chat({ conversationId, onConversationStarted }: ChatProps) {
  const { user } = useAuth();
  const userInitial = user?.email.charAt(0).toUpperCase() ?? "U";
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  // Tracks a conversation we just created locally, so the loader below does not
  // re-fetch (and wipe) the messages we already have on screen.
  const startedLocallyRef = useRef<string | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Load history when a different, existing conversation is selected.
  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!conversationId) {
        setMessages([]);
        return;
      }
      if (conversationId === startedLocallyRef.current) return;
      try {
        const convo = await getConversation(conversationId);
        if (cancelled) return;
        setMessages(
          convo.messages.map((m) => ({
            role: m.role,
            content: m.content,
            citations: m.citations,
          }))
        );
      } catch {
        if (!cancelled) setMessages([]);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  async function send() {
    const question = input.trim();
    if (!question || streaming) return;
    setInput("");
    setStreaming(true);

    setMessages((prev) => [
      ...prev,
      { role: "user", content: question },
      { role: "assistant", content: "" },
    ]);

    const appendToAssistant = (text: string) =>
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          ...next[next.length - 1],
          content: next[next.length - 1].content + text,
        };
        return next;
      });

    try {
      await streamChat(question, conversationId, {
        onMeta: (id) => {
          if (!conversationId) {
            startedLocallyRef.current = id;
            onConversationStarted(id);
          }
        },
        onToken: (t) => appendToAssistant(t),
        onCitations: (citations) =>
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = { ...next[next.length - 1], citations };
            return next;
          }),
        onError: (msg) => appendToAssistant(`\n\n⚠️ ${msg}`),
      });
    } catch (err) {
      appendToAssistant(
        `\n\n⚠️ ${err instanceof Error ? err.message : "Request failed"}`
      );
    } finally {
      setStreaming(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="mt-20 text-center text-slate-400">
            Ask a question to get started.
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} userInitial={userInitial} />
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-slate-200 bg-white p-4">
        <div className="mx-auto flex max-w-3xl gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            rows={1}
            placeholder="Type your question…"
            className="flex-1 resize-none rounded-xl border border-slate-300 px-4 py-2 text-sm outline-none focus:border-slate-500"
          />
          <button
            onClick={send}
            disabled={streaming || !input.trim()}
            className="rounded-xl bg-slate-900 px-5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {streaming ? "…" : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({
  message,
  userInitial,
}: {
  message: ChatMessage;
  userInitial: string;
}) {
  const isUser = message.role === "user";
  return (
    <div
      className={`mx-auto flex max-w-3xl items-end gap-2 ${
        isUser ? "flex-row-reverse" : "flex-row"
      }`}
    >
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white ${
          isUser ? "bg-slate-900" : "bg-emerald-600"
        }`}
        aria-hidden
      >
        {isUser ? userInitial : "AI"}
      </div>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm ${
          isUser
            ? "bg-slate-900 text-white"
            : "bg-white text-slate-800 ring-1 ring-slate-200"
        }`}
      >
        <div className="whitespace-pre-wrap">
          {message.content || (isUser ? "" : "…")}
        </div>
      </div>
    </div>
  );
}
