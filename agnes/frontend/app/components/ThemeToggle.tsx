"use client";

import { Sun, Moon } from "lucide-react";
import { useTheme } from "../providers";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button
      onClick={toggle}
      aria-label="Toggle theme"
      className="rounded-md p-2 text-slate-400 hover:text-slate-200 hover:bg-white/10 dark:hover:bg-white/5 transition-colors"
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}
