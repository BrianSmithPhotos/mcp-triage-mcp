"use client";

import { useState } from "react";
import Link from "next/link";
import { ChatMessage, sendChat } from "@/lib/api";

function isVisible(message: ChatMessage) {
  return message.role === "user" || (message.role === "assistant" && !!message.content);
}

export default function ChatPage() {
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!input.trim()) return;
    const userMessage: ChatMessage = { role: "user", content: input };
    const nextHistory = [...history, userMessage];
    setHistory(nextHistory);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const result = await sendChat(nextHistory);
      setHistory([...nextHistory, ...result.messages]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col flex-1 items-center bg-zinc-50 font-sans dark:bg-black px-8 py-16">
      <div className="flex w-full max-w-2xl flex-col gap-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Planner Chat</h1>
          <Link href="/" className="text-sm underline">
            Back
          </Link>
        </div>

        <div className="flex flex-col gap-3 min-h-[300px]">
          {history.filter(isVisible).map((m, i) => (
            <div
              key={i}
              className={`rounded-lg px-4 py-2 max-w-[80%] ${
                m.role === "user"
                  ? "self-end bg-foreground text-background"
                  : "self-start bg-zinc-200 dark:bg-zinc-800"
              }`}
            >
              {m.content}
            </div>
          ))}
        </div>

        {error && <p className="text-red-600">{error}</p>}

        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder="Ask about your Planner tasks..."
            className="flex-1 rounded-full border border-black/[.15] px-4 py-2 dark:border-white/[.15] dark:bg-zinc-900"
          />
          <button
            onClick={submit}
            disabled={loading}
            className="h-11 rounded-full bg-foreground px-6 text-background disabled:opacity-50"
          >
            {loading ? "..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
