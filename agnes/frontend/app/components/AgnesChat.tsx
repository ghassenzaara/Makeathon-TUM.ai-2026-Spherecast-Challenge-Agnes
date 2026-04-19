"use client";

import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { Send, ExternalLink } from "lucide-react";
import { AgnesOrb } from "./AgnesOrb";
import { TracingBorder } from "./TracingBorder";
import { sendChatMessage } from "@/lib/api";
import type { Citation } from "@/lib/types";

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}

interface AgnesChatProps {
  proposalId?: number;
  initialGreeting?: string;
  compact?: boolean;
}

export default function AgnesChat({
  proposalId,
  initialGreeting,
  compact = false,
}: AgnesChatProps) {
  const defaultGreeting = proposalId
    ? `I'm Agnes. Ask me anything about Proposal #${proposalId} — its evidence trail, supplier, risks, or savings.`
    : "Hello! I am Agnes, your AI Supply Chain Manager. Ask me anything about your supply chain data, consolidation proposals, or ingredient substitutions.";

  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: initialGreeting || defaultGreeting },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (messages.length > 1) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { role: "user", content: input };
    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setInput("");
    setIsLoading(true);

    try {
      const { answer, citations } = await sendChatMessage(
        nextMessages.map((m) => ({ role: m.role, content: m.content })),
        proposalId
      );
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: answer, citations },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "Error: Could not reach the chat agent. Is the backend running?",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const containerHeight = compact
    ? "h-[560px] w-full"
    : "h-[calc(100vh-8rem)] max-w-4xl w-full";

  return (
    <div
      className={`flex flex-col mx-auto rounded-2xl border border-white/[0.08] bg-[var(--bg-card)]/80 backdrop-blur-xl overflow-hidden ${containerHeight}`}
    >
      {/* Header */}
      <div className="border-b border-white/[0.06] px-5 py-4 flex items-center gap-3">
        <AgnesOrb state={isLoading ? "thinking" : "idle"} size={32} />
        <div>
          <h2 className="text-sm font-semibold text-[var(--foreground)]">
            Agnes Chat
            {proposalId && (
              <span className="ml-2 text-[10px] uppercase tracking-wider text-blue-400/80">
                Proposal #{proposalId}
              </span>
            )}
          </h2>
          <p className="text-[10px] uppercase tracking-wider text-[var(--foreground-muted)]">
            {proposalId ? "Evidence-trail context" : "RAG & supply-chain memory"}
          </p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {messages.map((msg, i) => {
          const isAssistant = msg.role === "assistant";
          const isLastAssistant =
            isAssistant && i === messages.length - 1 && !isLoading;

          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
              className={`flex ${isAssistant ? "justify-start" : "justify-end"}`}
            >
              {isAssistant ? (
                <div className="flex flex-col gap-2 max-w-[85%]">
                  <TracingBorder active={isLastAssistant} borderRadius={14}>
                    <div className="px-4 py-3">
                      <p className="text-[13px] leading-relaxed text-[var(--foreground)] whitespace-pre-wrap">
                        {msg.content}
                      </p>
                    </div>
                  </TracingBorder>
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pl-1">
                      {msg.citations.map((cit, idx) =>
                        cit.url ? (
                          <a
                            key={idx}
                            href={cit.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-500/10 hover:bg-blue-500/20 text-blue-300 text-[10px] rounded-md border border-blue-500/20 transition-colors"
                          >
                            <span className="font-semibold">
                              [{cit.doc_id}]
                            </span>
                            {cit.label}
                            <ExternalLink className="h-2.5 w-2.5" />
                          </a>
                        ) : (
                          <span
                            key={idx}
                            className="inline-flex items-center gap-1 px-2 py-0.5 bg-white/[0.04] text-[var(--foreground-muted)] text-[10px] rounded-md border border-white/[0.08]"
                          >
                            <span className="font-semibold">
                              [{cit.doc_id}]
                            </span>
                            {cit.label}
                          </span>
                        )
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="px-4 py-3 max-w-[80%] rounded-xl bg-white/[0.06] border border-white/[0.08]">
                  <p className="text-[13px] leading-relaxed text-[var(--foreground)] whitespace-pre-wrap">
                    {msg.content}
                  </p>
                </div>
              )}
            </motion.div>
          );
        })}

        {isLoading && (
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
                      transition={{
                        duration: 1,
                        delay: i * 0.2,
                        repeat: Infinity,
                      }}
                    />
                  ))}
                </div>
                <span className="text-[11px] text-[var(--foreground-muted)]">
                  Agnes is thinking…
                </span>
              </div>
            </TracingBorder>
          </motion.div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-5 py-4 border-t border-white/[0.06]">
        <form onSubmit={handleSubmit} className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              proposalId
                ? "Ask about this proposal's evidence…"
                : "Ask about consolidation, suppliers, risks…"
            }
            className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-2.5 text-sm text-[var(--foreground)] placeholder:text-[var(--foreground-dim)] focus:outline-none focus:border-white/[0.15] focus:bg-white/[0.06] transition-all"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="p-2.5 rounded-xl bg-white/[0.06] border border-white/[0.08] text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-white/[0.1] disabled:opacity-30 transition-all"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
