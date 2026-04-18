"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, ArrowRight, X } from "lucide-react";
import { cn } from "@/lib/utils";

export function ChatTaskBar() {
  const [focused, setFocused] = useState(false);
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  function submit() {
    const q = query.trim();
    if (!q) return;
    router.push(`/chat?q=${encodeURIComponent(q)}`);
  }

  return (
    <div
      onClick={() => inputRef.current?.focus()}
      className={cn(
        "relative rounded-2xl border transition-all duration-300 cursor-text",
        "bg-[var(--surface)]/80 backdrop-blur-md",
        focused
          ? "border-cyan-500/50 shadow-[0_0_24px_rgba(6,182,212,0.12)]"
          : "border-[var(--border)] hover:border-cyan-500/25"
      )}
    >
      <div className="flex items-center gap-3 px-4 py-3">

        {/* Pulsing AI orb */}
        <div className="relative flex-shrink-0 h-7 w-7 flex items-center justify-center">
          <motion.span
            className="absolute inset-0 rounded-full bg-cyan-500/20"
            animate={{ scale: [1, 1.5, 1], opacity: [0.6, 0, 0.6] }}
            transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
          />
          <span className="relative flex items-center justify-center rounded-full bg-cyan-500/15 border border-cyan-500/30 h-7 w-7">
            <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
          </span>
        </div>

        {/* Input */}
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Ask Agnes about suppliers, compliance, savings opportunities…"
          className="flex-1 bg-transparent text-sm outline-none text-[var(--foreground)] placeholder:text-[var(--foreground-muted)]"
        />

        {/* Actions — only shown when there's text */}
        <AnimatePresence>
          {query.trim() && (
            <motion.div
              initial={{ opacity: 0, x: 8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 8 }}
              transition={{ duration: 0.15 }}
              className="flex items-center gap-2 flex-shrink-0"
            >
              <button
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => setQuery("")}
                className="text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors"
              >
                <X className="h-3.5 w-3.5" />
              </button>
              <button
                onMouseDown={(e) => e.preventDefault()}
                onClick={submit}
                className="flex items-center gap-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 transition-colors px-3 py-1.5 text-xs font-semibold text-white"
              >
                Ask <ArrowRight className="h-3 w-3" />
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
