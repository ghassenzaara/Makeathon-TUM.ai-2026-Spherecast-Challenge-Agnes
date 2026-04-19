"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, ArrowLeft, ExternalLink } from "lucide-react";
import Link from "next/link";
import { AgnesOrb } from "../components/AgnesOrb";
import { TracingBorder } from "../components/TracingBorder";
import { Waveform } from "../components/Waveform";
import { sendChatMessage } from "@/lib/api";
import type { RagCitation } from "@/lib/types";

interface Message {
  role: "user" | "agnes";
  content: string;
  timestamp?: string;
  citations?: RagCitation[];
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "agnes",
      content:
        "Hello — I'm Agnes, your AI Supply Chain Manager. I can analyze consolidation proposals, check compliance constraints, and recommend suppliers. What would you like to explore?",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
  ]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || thinking) return;

    const userMsg = input.trim();
    const ts = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg, timestamp: ts }]);
    setThinking(true);

    try {
      const history = [...messages, { role: "user", content: userMsg }].map((m) => ({
        role: m.role === "agnes" ? "assistant" : m.role,
        content: m.content,
      }));

      const response = await sendChatMessage(history);
      const rTs = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

      setMessages((prev) => [
        ...prev,
        {
          role: "agnes",
          content: response.answer,
          timestamp: rTs,
          citations: response.citations,
        },
      ]);
    } finally {
      setThinking(false);
    }
  }

  return (
    <div className="flex flex-col h-screen max-h-screen">
      {/* ── Header ── */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border)] bg-[var(--bg-surface-solid)]/60 backdrop-blur-md">
        <div className="flex items-center gap-4">
          <Link href="/" className="p-2 rounded-xl text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-white/[0.04] transition-all">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="flex items-center gap-3">
            <AgnesOrb state={thinking ? "thinking" : "idle"} size={36} />
            <div>
              <h1 className="text-sm font-semibold text-[var(--foreground)]">Agnes</h1>
              <p className="text-[10px] uppercase tracking-[0.15em] text-[var(--foreground-muted)]">
                {thinking ? "Analyzing your question…" : "Supply Chain Intelligence"}
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`h-1.5 w-1.5 rounded-full ${thinking ? "bg-amber-400 status-pulse" : "bg-emerald-500"}`} />
          <span className="text-[10px] uppercase tracking-wider text-[var(--foreground-dim)]">
            {thinking ? "Processing" : "Online"}
          </span>
        </div>
      </div>

      {/* ── Messages ── */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-2xl mx-auto space-y-5">
          {messages.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
            >
              {/* Avatar */}
              {msg.role === "agnes" ? (
                <div className="shrink-0 mt-1"><AgnesOrb state="idle" size={32} /></div>
              ) : (
                <div className="shrink-0 mt-1 h-8 w-8 rounded-full bg-white/[0.08] border border-white/[0.1] flex items-center justify-center text-[11px] font-semibold text-[var(--foreground-muted)]">
                  You
                </div>
              )}

              {/* Bubble + Citations */}
              <div className={`max-w-[75%] space-y-2 ${msg.role === "user" ? "text-right" : ""}`}>
                {msg.role === "agnes" ? (
                  <TracingBorder active={i === messages.length - 1 && !thinking} borderRadius={14}>
                    <div className="px-4 py-3">
                      <p className="text-[13px] leading-relaxed text-[var(--foreground)]">{msg.content}</p>
                    </div>
                  </TracingBorder>
                ) : (
                  <div className="rounded-xl bg-white/[0.06] border border-white/[0.08] px-4 py-3 inline-block text-left">
                    <p className="text-[13px] leading-relaxed text-[var(--foreground)]">{msg.content}</p>
                  </div>
                )}

                {/* Citations */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {msg.citations.map((c, ci) => (
                      <a
                        key={ci}
                        href={c.url || "#"}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-[10px] text-[var(--accent-blue)] bg-blue-500/10 border border-blue-500/20 rounded px-1.5 py-0.5 hover:bg-blue-500/20 transition-colors"
                      >
                        <ExternalLink className="h-2.5 w-2.5" />
                        {c.label || c.doc_id}
                      </a>
                    ))}
                  </div>
                )}

                {msg.timestamp && (
                  <p className={`text-[9px] text-[var(--foreground-dim)] ${msg.role === "user" ? "text-right" : ""}`}>
                    {msg.timestamp}
                  </p>
                )}
              </div>
            </motion.div>
          ))}

          {/* Thinking indicator */}
          <AnimatePresence>
            {thinking && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -5 }}
                className="flex gap-3"
              >
                <div className="shrink-0 mt-1"><AgnesOrb state="thinking" size={32} /></div>
                <TracingBorder active={true} borderRadius={14}>
                  <div className="px-4 py-3 flex items-center gap-3">
                    <div className="flex gap-1">
                      {[0, 1, 2].map((i) => (
                        <motion.div
                          key={i}
                          className="h-1.5 w-1.5 rounded-full bg-gray-400"
                          animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.2, 0.8] }}
                          transition={{ duration: 1, delay: i * 0.2, repeat: Infinity }}
                        />
                      ))}
                    </div>
                    <span className="text-[11px] text-[var(--foreground-muted)]">Agnes is analyzing…</span>
                  </div>
                </TracingBorder>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* ── Input Bar ── */}
      <div className="border-t border-[var(--border)] bg-[var(--bg-surface-solid)]/60 backdrop-blur-md px-6 py-4">
        <div className="max-w-2xl mx-auto">
          <div className="mb-2 opacity-50">
            <Waveform active={thinking} barCount={48} />
          </div>
          <form onSubmit={handleSend} className="flex items-center gap-3">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about suppliers, consolidation, compliance, risks…"
              disabled={thinking}
              className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-xl px-5 py-3 text-sm text-[var(--foreground)] placeholder:text-[var(--foreground-dim)] focus:outline-none focus:border-white/[0.15] focus:bg-white/[0.06] transition-all disabled:opacity-40"
            />
            <button
              type="submit"
              disabled={!input.trim() || thinking}
              className="p-3 rounded-xl text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-all disabled:opacity-30"
              style={{
                background: "radial-gradient(circle at 30% 30%, #d4d4d8, #525252, #171717)",
                boxShadow: "0 0 12px 2px rgba(160,160,160,0.1)",
              }}
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
