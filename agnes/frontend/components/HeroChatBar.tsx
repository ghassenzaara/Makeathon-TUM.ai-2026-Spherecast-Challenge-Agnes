"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowUp, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

const SUGGESTIONS = [
  "Top savings opportunities",
  "Compliance risks",
  "High priority suppliers",
  "Consolidation proposals",
];

export function HeroChatBar() {
  const [query, setQuery]   = useState("");
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const router = useRouter();

  function submit(q: string = query) {
    const trimmed = q.trim();
    if (!trimmed) return;
    router.push(`/chat?q=${encodeURIComponent(trimmed)}`);
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
    <div className="w-full max-w-2xl mx-auto flex flex-col items-center gap-4">

      {/* Input card */}
      <div
        className={cn(
          "w-full rounded-3xl border transition-all duration-300",
          "bg-white/6 backdrop-blur-xl",
          focused
            ? "border-cyan-400/40 shadow-[0_0_40px_rgba(95,163,212,0.18),0_8px_32px_rgba(0,0,0,0.4)]"
            : "border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.35)]"
        )}
        onClick={() => textareaRef.current?.focus()}
      >
        {/* Text area */}
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
        <div className="flex items-center justify-between px-5 pb-4 pt-1">
          <span className="flex items-center gap-1.5 text-xs text-white/20 select-none">
            <Sparkles className="h-3 w-3 text-cyan-400/40" />
            Ask anything
          </span>

          <AnimatePresence>
            {query.trim() && (
              <motion.button
                initial={{ scale: 0.7, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.7, opacity: 0 }}
                transition={{ duration: 0.15 }}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => submit()}
                className="flex items-center justify-center h-9 w-9 rounded-full bg-cyan-500 hover:bg-cyan-400 transition-colors shadow-[0_0_16px_rgba(6,182,212,0.5)]"
              >
                <ArrowUp className="h-4 w-4 text-white" />
              </motion.button>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Suggestion chips */}
      <div className="flex flex-wrap justify-center gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => submit(s)}
            className="rounded-full border border-white/10 bg-white/5 backdrop-blur-sm px-4 py-2 text-sm text-white/50 hover:text-white/90 hover:border-cyan-400/35 hover:bg-cyan-500/10 transition-all duration-200"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
