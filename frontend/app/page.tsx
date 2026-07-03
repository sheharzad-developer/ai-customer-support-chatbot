"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Chat from "@/components/Chat";
import Sidebar from "@/components/Sidebar";
import { useAuth } from "@/components/AuthProvider";

export default function HomePage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [activeConversationId, setActiveConversationId] = useState<string | null>(
    null
  );
  // Bumped whenever a new conversation is created, so the sidebar refreshes.
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <main className="flex min-h-screen items-center justify-center text-slate-400">
        Loading…
      </main>
    );
  }

  return (
    <main className="flex h-screen overflow-hidden">
      <Sidebar
        activeConversationId={activeConversationId}
        onSelect={setActiveConversationId}
        reloadKey={reloadKey}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <h1 className="text-sm font-semibold">AI Support Chatbot</h1>
        </header>
        <div className="flex-1 overflow-hidden">
          <Chat
            conversationId={activeConversationId}
            onConversationStarted={(id) => {
              setActiveConversationId(id);
              setReloadKey((k) => k + 1);
            }}
          />
        </div>
      </div>
    </main>
  );
}
