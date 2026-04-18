"use client";

import { useState, useRef, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowUp } from "lucide-react";
import { PrismaticOrb } from "@/app/components/AgnesLogo";

const ORB = "168,212,239";

interface Message {
  role: "user" | "assistant";
  content: string;
}

// Render text with [P12] / [E47] citation tags as styled badges
function MessageContent({ text }: { text: string }) {
  const parts = text.split(/(\[[PE]\d+\])/g);
  return (
    <span>
      {parts.map((part, i) => {
        if (/^\[[PE]\d+\]$/.test(part)) {
          const isProposal = part.startsWith("[P");
          return (
            <span
              key={i}
              style={{
                display: "inline-flex",
                alignItems: "center",
                fontSize: "0.68rem",
                fontWeight: 600,
                padding: "1px 6px",
                borderRadius: "4px",
                margin: "0 2px",
                background: isProposal
                  ? `rgba(${ORB},0.15)`
                  : "rgba(139,92,246,0.15)",
                color: isProposal ? `rgba(${ORB},1)` : "rgba(192,132,252,1)",
                border: isProposal
                  ? `1px solid rgba(${ORB},0.35)`
                  : "1px solid rgba(139,92,246,0.35)",
              }}
            >
              {part}
            </span>
          );
        }
        // Split on newlines so we preserve paragraph breaks
        return part.split("\n").map((line, j, arr) => (
          <span key={`${i}-${j}`}>
            {line}
            {j < arr.length - 1 && <br />}
          </span>
        ));
      })}
    </span>
  );
}

// Animated 3-dot typing indicator
function TypingDots() {
  return (
    <span className="flex items-center gap-1 py-0.5">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            background: `rgba(${ORB},0.80)`,
            display: "inline-block",
            animation: `dotBounce 1.2s ease-in-out ${i * 0.2}s infinite`,
          }}
        />
      ))}
    </span>
  );
}

function ChatPageInner() {
  const searchParams = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hello! I'm Agnes, your AI supply chain manager. Ask me about consolidation proposals, ingredient substitutions, or compliance constraints.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const didAutoSubmit = useRef(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const sendMessage = useCallback(async (text: string, history: Message[]) => {
    const userMessage: Message = { role: "user", content: text };
    const nextHistory = [...history, userMessage];
    setMessages(nextHistory);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: nextHistory.map((m) => ({ role: m.role, content: m.content })),
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
  }, []);

  // Auto-submit the ?q= param once on mount
  useEffect(() => {
    const q = searchParams.get("q");
    if (q && !didAutoSubmit.current) {
      didAutoSubmit.current = true;
      sendMessage(q, messages);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    sendMessage(input.trim(), messages);
  };

  return (
    <div className="px-6 py-8">
      <div
        className="flex flex-col h-[calc(100vh-9rem)] max-w-3xl mx-auto rounded-2xl overflow-hidden animate-fade-in"
        style={{
          border: `1px solid rgba(${ORB},0.12)`,
          background: "rgba(8,13,26,0.85)",
          backdropFilter: "blur(16px)",
        }}
      >
        {/* Header */}
        <div
          className="px-5 py-4 flex items-center gap-3"
          style={{ borderBottom: `1px solid rgba(${ORB},0.10)` }}
        >
          <PrismaticOrb size={34} />
          <div>
            <div className="text-sm font-semibold" style={{ color: `rgba(${ORB},1)` }}>
              Agnes
            </div>
            <div className="text-xs text-white/40">RAG-grounded supply chain Q&amp;A</div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
            >
              {/* Agnes orb — only on the last AI message */}
              {msg.role === "assistant" && (
                (() => {
                  const isLast = !messages.slice(i + 1).some((m) => m.role === "assistant");
                  return isLast
                    ? <div className="shrink-0 mt-0.5"><PrismaticOrb size={28} /></div>
                    : <div className="shrink-0 w-7" />;
                })()
              )}

              {/* Bubble */}
              <div
                className="max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-relaxed"
                style={
                  msg.role === "user"
                    ? {
                        background: "rgba(255,255,255,0.07)",
                        border: "1px solid rgba(255,255,255,0.10)",
                        color: "rgba(255,255,255,0.90)",
                        borderTopRightRadius: 4,
                      }
                    : {
                        background: `rgba(${ORB},0.06)`,
                        border: `1px solid rgba(${ORB},0.14)`,
                        color: "rgba(226,232,240,0.95)",
                        borderTopLeftRadius: 4,
                        boxShadow: `0 0 24px rgba(${ORB},0.04)`,
                      }
                }
              >
                <MessageContent text={msg.content} />
              </div>
            </div>
          ))}

          {/* Typing indicator */}
          {isLoading && (
            <div className="flex gap-3">
              <div className="shrink-0 mt-0.5">
                <PrismaticOrb size={28} />
              </div>
              <div
                className="rounded-2xl px-4 py-3"
                style={{
                  background: `rgba(${ORB},0.06)`,
                  border: `1px solid rgba(${ORB},0.14)`,
                  borderTopLeftRadius: 4,
                }}
              >
                <TypingDots />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div
          className="p-4"
          style={{ borderTop: `1px solid rgba(${ORB},0.10)` }}
        >
          <form onSubmit={handleSubmit} className="relative flex items-center">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about consolidation, compliance, or suppliers…"
              disabled={isLoading}
              className="w-full rounded-full pl-5 pr-12 py-3 text-sm outline-none transition-all"
              style={{
                background: "rgba(255,255,255,0.04)",
                border: `1px solid rgba(${ORB},0.18)`,
                color: "rgba(226,232,240,0.95)",
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = `rgba(${ORB},0.45)`;
                e.currentTarget.style.boxShadow = `0 0 20px rgba(${ORB},0.10)`;
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = `rgba(${ORB},0.18)`;
                e.currentTarget.style.boxShadow = "none";
              }}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="absolute right-2 flex items-center justify-center h-8 w-8 rounded-full transition-all disabled:opacity-30"
              style={{
                background: `rgba(${ORB},0.90)`,
                boxShadow: input.trim() ? `0 0 14px rgba(${ORB},0.45)` : "none",
              }}
            >
              <ArrowUp className="h-4 w-4 text-[#06091a]" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense>
      <ChatPageInner />
    </Suspense>
  );
}
