"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowUp, Mic, SlidersHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";

const ORB = "168,212,239";

const SUGGESTIONS = [
  "Top savings opportunities",
  "Compliance risks",
  "High priority suppliers",
  "Consolidation proposals",
];

interface HeroChatBarProps {
  /** If provided, called instead of routing to /chat */
  onSubmit?: (q: string) => void;
  /** Framer Motion layoutId for shared-layout transitions */
  layoutId?: string;
  /** Hide suggestion chips (used in chat overlay) */
  hideChips?: boolean;
}

export function HeroChatBar({
  onSubmit,
  layoutId = "agnes-chatbar",
  hideChips = false,
}: HeroChatBarProps) {
  const [query, setQuery]     = useState("");
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const router = useRouter();

  function submit(q: string = query) {
    const trimmed = q.trim();
    if (!trimmed) return;
    if (onSubmit) {
      onSubmit(trimmed);
      setQuery("");
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    } else {
      router.push(`/chat?q=${encodeURIComponent(trimmed)}`);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function autoResize(el: HTMLTextAreaElement) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }

  return (
    <div className="w-full max-w-[840px] mx-auto flex flex-col items-center gap-4">

      {/* Input card — layoutId enables Framer Motion shared-layout animation */}
      <motion.div
        layoutId={layoutId}
        layout
        className={cn(
          "w-full rounded-3xl border cursor-text",
          "bg-white/6 backdrop-blur-xl",
        )}
        style={{
          borderColor: focused ? `rgba(${ORB},0.45)` : "rgba(255,255,255,0.10)",
          boxShadow: focused
            ? `0 0 40px rgba(${ORB},0.18), 0 8px 32px rgba(0,0,0,0.40)`
            : "0 8px 32px rgba(0,0,0,0.35)",
        }}
        onClick={() => textareaRef.current?.focus()}
        transition={{ type: "spring", stiffness: 280, damping: 32 }}
      >
        {/* Textarea */}
        <div className="px-6 pt-5 pb-3">
          <textarea
            ref={textareaRef}
            value={query}
            rows={1}
            onChange={(e) => { setQuery(e.target.value); autoResize(e.target); }}
            onKeyDown={handleKeyDown}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder="Ask Agnes about suppliers, compliance, savings…"
            className="w-full bg-transparent resize-none outline-none text-base text-white placeholder:text-white/35 leading-relaxed"
            style={{ minHeight: "30px", maxHeight: "200px" }}
          />
        </div>

        {/* Bottom toolbar */}
        <div className="flex items-center justify-between px-4 pb-4 pt-1 gap-3">

          {/* Left — Focus scope */}
          <button
            disabled
            title="Select a focus area — coming soon"
            className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors select-none cursor-not-allowed"
            style={{
              color: `rgba(${ORB},0.65)`,
              border: `1px solid rgba(${ORB},0.18)`,
              background: `rgba(${ORB},0.06)`,
            }}
          >
            <SlidersHorizontal className="h-3 w-3" />
            Focus scope
          </button>

          {/* Right — mic + send */}
          <div className="flex items-center gap-2">
            <button
              disabled
              title="Voice input — coming soon"
              className="flex items-center justify-center h-8 w-8 rounded-full transition-colors cursor-not-allowed"
              style={{
                color: `rgba(${ORB},0.50)`,
                border: `1px solid rgba(${ORB},0.15)`,
                background: `rgba(${ORB},0.05)`,
              }}
            >
              <Mic className="h-3.5 w-3.5" />
            </button>

            <AnimatePresence>
              {query.trim() && (
                <motion.button
                  initial={{ scale: 0.7, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0.7, opacity: 0 }}
                  transition={{ duration: 0.15 }}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => submit()}
                  className="flex items-center justify-center h-8 w-8 rounded-full transition-colors"
                  style={{
                    background: `rgba(${ORB},0.90)`,
                    boxShadow: `0 0 14px rgba(${ORB},0.45)`,
                  }}
                >
                  <ArrowUp className="h-4 w-4 text-[#06091a]" />
                </motion.button>
              )}
            </AnimatePresence>
          </div>
        </div>
      </motion.div>

      {/* Suggestion chips — hidden in chat overlay */}
      <AnimatePresence>
        {!hideChips && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
            className="flex flex-wrap justify-center gap-2"
          >
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => submit(s)}
                className="rounded-full px-4 py-2 text-sm transition-all duration-200"
                style={{
                  color: `rgba(${ORB},0.60)`,
                  border: `1px solid rgba(${ORB},0.15)`,
                  background: `rgba(${ORB},0.05)`,
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLButtonElement).style.color = `rgba(${ORB},1)`;
                  (e.currentTarget as HTMLButtonElement).style.borderColor = `rgba(${ORB},0.40)`;
                  (e.currentTarget as HTMLButtonElement).style.background = `rgba(${ORB},0.12)`;
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLButtonElement).style.color = `rgba(${ORB},0.60)`;
                  (e.currentTarget as HTMLButtonElement).style.borderColor = `rgba(${ORB},0.15)`;
                  (e.currentTarget as HTMLButtonElement).style.background = `rgba(${ORB},0.05)`;
                }}
              >
                {s}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
