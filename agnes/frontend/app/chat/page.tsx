"use client";

import { useState, useRef, useEffect } from "react";
import { Send, User, Bot, Loader2 } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hello! I'm Agnes, your AI Supply Chain Manager. Ask me about consolidation proposals, ingredient substitutions, or compliance constraints.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [...messages, userMessage].map((m) => ({
            role: m.role,
            content: m.content,
          })),
        }),
      });

      if (!response.ok) throw new Error("Chat request failed");
      const data = await response.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer || "No response." },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Could not reach the chat agent — is the backend running on port 8000?",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="px-6 py-8">
    <div className="flex flex-col h-[calc(100vh-9rem)] max-w-3xl mx-auto rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden animate-fade-in">

      {/* Header */}
      <div className="border-b border-[var(--border)] px-5 py-4 flex items-center gap-3 bg-white/[0.02]">
        <div className="h-9 w-9 rounded-lg bg-cyan-500 text-slate-950 flex items-center justify-center glow-cyan">
          <Bot className="h-5 w-5" />
        </div>
        <div>
          <div className="text-sm font-semibold text-[var(--foreground)]">Agnes Chat</div>
          <div className="text-xs text-[var(--foreground-muted)]">RAG-grounded supply chain Q&amp;A</div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5 bg-[var(--background)]/30">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
          >
            <div
              className={`shrink-0 h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold ${
                msg.role === "user"
                  ? "bg-slate-700 text-white dark:bg-slate-600"
                  : "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
              }`}
            >
              {msg.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
            </div>
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-slate-800 text-slate-100 rounded-tr-sm dark:bg-slate-700"
                  : "bg-[var(--surface)] border border-[var(--border)] text-[var(--foreground)] rounded-tl-sm"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-3">
            <div className="shrink-0 h-8 w-8 rounded-full bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 flex items-center justify-center">
              <Bot className="h-4 w-4" />
            </div>
            <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-2 text-sm text-[var(--foreground-muted)]">
              <Loader2 className="h-4 w-4 animate-spin text-cyan-500" /> Thinking…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-[var(--border)] bg-[var(--surface)]">
        <form onSubmit={handleSubmit} className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about consolidation, compliance, or suppliers…"
            disabled={isLoading}
            className="w-full rounded-full border border-[var(--border)] bg-[var(--background)] pl-5 pr-12 py-3 text-sm text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500/50 transition-colors"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="absolute right-2 p-2 rounded-full bg-cyan-500 text-slate-950 hover:bg-cyan-400 disabled:opacity-40 disabled:hover:bg-cyan-500 transition-colors"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
    </div>
  );
}
