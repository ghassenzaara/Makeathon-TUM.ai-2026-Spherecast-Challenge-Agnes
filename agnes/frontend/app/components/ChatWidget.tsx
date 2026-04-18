"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { X, Send, ExternalLink } from "lucide-react";
import { AgnesOrb } from "./AgnesOrb";
import { TracingBorder } from "./TracingBorder";
import { sendChatMessage } from "@/lib/api";

interface Message {
  role: "user" | "agnes";
  content: string;
}

export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  async function handleSend() {
    if (!input.trim()) return;
    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setThinking(true);

    try {
      const { answer } = await sendChatMessage([...messages, { role: "user", content: userMsg }]);
      setMessages((prev) => [...prev, { role: "agnes", content: answer }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "agnes", content: err instanceof Error ? err.message : "Agent offline. Ensure the backend is running." },
      ]);
    } finally {
      setThinking(false);
    }
  }

  return (
    <>
      {/* ── Floating Action Button ── */}
      <motion.button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex items-center justify-center w-14 h-14 aspect-square rounded-full cursor-pointer"
        style={{
          background: "radial-gradient(circle at 30% 30%, #d4d4d8, #525252, #171717)",
          boxShadow: "0 0 24px 6px rgba(100,80,220,0.2), 0 4px 12px rgba(0,0,0,0.4)",
        }}
        whileHover={{ scale: 1.1, boxShadow: "0 0 32px 8px rgba(100,80,220,0.3)" }}
        whileTap={{ scale: 0.95 }}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: open ? 0 : 1, y: open ? 20 : 0, pointerEvents: open ? "none" as const : "auto" as const }}
        transition={{ duration: 0.3 }}
      >
        <AgnesOrb state="idle" size={40} transparent={true} />
      </motion.button>

      {/* ── Side Panel Overlay ── */}
      <AnimatePresence>
        {open && (
          <>
            {/* Backdrop */}
            <motion.div
              className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
            />

            {/* Panel */}
            <motion.div
              className="fixed top-0 right-0 z-50 h-full w-full max-w-md flex flex-col border-l border-white/[0.06]"
              style={{ background: "rgba(8, 10, 18, 0.95)", backdropFilter: "blur(24px)" }}
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 28, stiffness: 300 }}
            >
              {/* Header */}
              <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
                <div className="flex items-center gap-3">
                  <AgnesOrb state={thinking ? "thinking" : "idle"} size={32} />
                  <div>
                    <h3 className="text-sm font-semibold text-[var(--foreground)]">Agnes</h3>
                    <p className="text-[10px] uppercase tracking-wider text-[var(--foreground-muted)]">
                      {thinking ? "Analyzing…" : "Supply Chain AI"}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Link
                    href="/chat"
                    onClick={() => setOpen(false)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium text-[var(--foreground-muted)] hover:text-[var(--foreground)] bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.06] transition-all"
                  >
                    Open Full View <ExternalLink className="h-3 w-3" />
                  </Link>
                  <button
                    onClick={() => setOpen(false)}
                    className="p-1.5 rounded-lg text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-white/[0.06] transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* Messages */}
              <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
                {messages.length === 0 && (
                  <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
                    <AgnesOrb state="idle" size={56} />
                    <div>
                      <p className="text-sm font-medium text-[var(--foreground)]">Ask Agnes anything</p>
                      <p className="text-xs text-[var(--foreground-muted)] mt-1">
                        Try: &ldquo;What are the high priority alerts?&rdquo;
                      </p>
                    </div>
                  </div>
                )}
                {messages.map((msg, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                    className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    {msg.role === "agnes" ? (
                      <TracingBorder active={i === messages.length - 1} borderRadius={14}>
                        <div className="px-4 py-3 max-w-[320px]">
                          <p className="text-[13px] leading-relaxed text-[var(--foreground)]">
                            {msg.content}
                          </p>
                        </div>
                      </TracingBorder>
                    ) : (
                      <div className="px-4 py-3 max-w-[280px] rounded-xl bg-white/[0.06] border border-white/[0.08]">
                        <p className="text-[13px] leading-relaxed text-[var(--foreground)]">
                          {msg.content}
                        </p>
                      </div>
                    )}
                  </motion.div>
                ))}

                {/* Thinking indicator */}
                {thinking && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex justify-start"
                  >
                    <TracingBorder active={true} borderRadius={14}>
                      <div className="px-4 py-3 flex items-center gap-2">
                        <div className="flex gap-1">
                          {[0, 1, 2].map((i) => (
                            <motion.div
                              key={i}
                              className="h-1.5 w-1.5 rounded-full bg-gray-400"
                              animate={{ opacity: [0.3, 1, 0.3] }}
                              transition={{ duration: 1, delay: i * 0.2, repeat: Infinity }}
                            />
                          ))}
                        </div>
                        <span className="text-[11px] text-[var(--foreground-muted)]">Agnes is thinking…</span>
                      </div>
                    </TracingBorder>
                  </motion.div>
                )}
              </div>

              {/* Input */}
              <div className="px-5 py-4 border-t border-white/[0.06]">
                <form
                  onSubmit={(e) => { e.preventDefault(); handleSend(); }}
                  className="flex items-center gap-2"
                >
                  <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask about suppliers, risks, savings…"
                    className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-2.5 text-sm text-[var(--foreground)] placeholder:text-[var(--foreground-dim)] focus:outline-none focus:border-white/[0.15] focus:bg-white/[0.06] transition-all"
                    disabled={thinking}
                  />
                  <button
                    type="submit"
                    disabled={thinking || !input.trim()}
                    className="p-2.5 rounded-xl bg-white/[0.06] border border-white/[0.08] text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-white/[0.1] disabled:opacity-30 transition-all"
                  >
                    <Send className="h-4 w-4" />
                  </button>
                </form>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
