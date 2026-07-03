export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "rag_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface User {
  id: string;
  email: string;
  is_admin: boolean;
  created_at: string;
}

export interface Citation {
  document_id: string;
  document_title: string;
  chunk_index: number;
  snippet: string;
}

export interface DocumentItem {
  id: string;
  title: string;
  source: string;
  content_type: string;
  chunk_count: number;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: ConversationMessage[];
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function login(email: string, password: string): Promise<string> {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  const data = await handle<{ access_token: string }>(res);
  return data.access_token;
}

export async function register(email: string, password: string): Promise<User> {
  const res = await fetch(`${API_URL}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handle<User>(res);
}

export async function fetchMe(): Promise<User> {
  const res = await fetch(`${API_URL}/api/auth/me`, { headers: authHeaders() });
  return handle<User>(res);
}

export async function listConversations(): Promise<Conversation[]> {
  const res = await fetch(`${API_URL}/api/chat/conversations`, {
    headers: authHeaders(),
  });
  return handle<Conversation[]>(res);
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const res = await fetch(`${API_URL}/api/chat/conversations/${id}`, {
    headers: authHeaders(),
  });
  return handle<ConversationDetail>(res);
}

export async function deleteConversation(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/chat/conversations/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to delete conversation");
}

export async function listDocuments(): Promise<DocumentItem[]> {
  const res = await fetch(`${API_URL}/api/documents`, { headers: authHeaders() });
  return handle<DocumentItem[]>(res);
}

export async function uploadDocument(
  file: File,
  title?: string
): Promise<DocumentItem> {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);
  const res = await fetch(`${API_URL}/api/documents`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  return handle<DocumentItem>(res);
}

export async function deleteDocument(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/documents/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to delete document");
}

/**
 * Send a chat message and stream the response via SSE.
 * Callbacks fire as events arrive.
 */
export async function streamChat(
  message: string,
  conversationId: string | null,
  handlers: {
    onMeta?: (conversationId: string) => void;
    onToken?: (text: string) => void;
    onCitations?: (citations: Citation[]) => void;
    onError?: (message: string) => void;
    onDone?: () => void;
  }
): Promise<void> {
  const res = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });

  if (!res.ok || !res.body) {
    throw new Error(`Chat request failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      let event = "message";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      const parsed = JSON.parse(data);
      switch (event) {
        case "meta":
          handlers.onMeta?.(parsed.conversation_id);
          break;
        case "token":
          handlers.onToken?.(parsed.text);
          break;
        case "citations":
          handlers.onCitations?.(parsed.citations);
          break;
        case "error":
          handlers.onError?.(parsed.message);
          break;
        case "done":
          handlers.onDone?.();
          break;
      }
    }
  }
}
