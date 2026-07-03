"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import {
  deleteConversation,
  listConversations,
  type Conversation,
} from "@/lib/api";

interface SidebarProps {
  activeConversationId: string | null;
  onSelect: (id: string | null) => void;
  reloadKey: number;
}

export default function Sidebar({
  activeConversationId,
  onSelect,
  reloadKey,
}: SidebarProps) {
  const { user, logout } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);

  const load = useCallback(async () => {
    try {
      setConversations(await listConversations());
    } catch {
      setConversations([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, reloadKey]);

  async function handleDelete(id: string) {
    try {
      await deleteConversation(id);
      if (id === activeConversationId) onSelect(null); // leave the deleted chat
      await load();
    } catch {
      /* ignore */
    }
  }

  return (
    <aside className="flex h-full w-64 flex-col border-r border-slate-200 bg-slate-50">
      {/* New chat */}
      <div className="p-3">
        <button
          onClick={() => onSelect(null)}
          className="w-full rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          + New chat
        </button>
      </div>

      {/* History */}
      <div className="flex-1 overflow-y-auto px-2">
        <div className="px-2 py-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
          History
        </div>
        {conversations.length === 0 && (
          <div className="px-2 py-2 text-xs text-slate-400">
            No conversations yet.
          </div>
        )}
        <ul className="space-y-1">
          {conversations.map((c) => (
            <li key={c.id} className="group relative">
              <button
                onClick={() => onSelect(c.id)}
                className={`w-full truncate rounded-lg py-2 pl-2 pr-8 text-left text-sm ${
                  c.id === activeConversationId
                    ? "bg-slate-200 text-slate-900"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
                title={c.title}
              >
                {c.title || "Untitled"}
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleDelete(c.id);
                }}
                className="absolute right-1 top-1/2 -translate-y-1/2 rounded p-1 text-slate-400 opacity-0 hover:bg-slate-200 hover:text-red-600 focus:opacity-100 group-hover:opacity-100"
                title="Delete conversation"
                aria-label="Delete conversation"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-4 w-4"
                >
                  <path d="M3 6h18" />
                  <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                  <path d="M10 11v6" />
                  <path d="M14 11v6" />
                </svg>
              </button>
            </li>
          ))}
        </ul>
      </div>

      {/* Profile card */}
      {user && (
        <div className="border-t border-slate-200 p-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-900 text-sm font-semibold text-white">
              {user.email.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium text-slate-800">
                {user.email}
              </div>
              <div className="text-xs text-slate-400">
                {user.is_admin ? "Admin" : "Member"}
              </div>
            </div>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs">
            {user.is_admin ? (
              <Link href="/admin" className="text-slate-600 hover:text-slate-900">
                Admin dashboard
              </Link>
            ) : (
              <span />
            )}
            <button
              onClick={logout}
              className="text-slate-600 hover:text-slate-900"
            >
              Sign out
            </button>
          </div>
        </div>
      )}
    </aside>
  );
}
