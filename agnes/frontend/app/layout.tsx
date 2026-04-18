import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { ThemeProvider } from "./providers";
import { ThemeToggle } from "./components/ThemeToggle";

export const metadata: Metadata = {
  title: "Agnes — AI Supply Chain Manager",
  description: "AI-powered sourcing consolidation command center",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-[var(--background)] text-[var(--foreground)] antialiased transition-colors duration-200">
        <ThemeProvider>
          <header className="sticky top-0 z-50 border-b border-[var(--border)] bg-[var(--surface)] backdrop-blur">
            <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">

              {/* Logo */}
              <Link href="/" className="flex items-center gap-3 group">
                <div className="h-8 w-8 rounded-md bg-cyan-500 text-slate-950 grid place-items-center font-mono text-sm font-bold shadow-lg glow-cyan">
                  A
                </div>
                <div>
                  <div className="text-sm font-bold tracking-tight text-[var(--foreground)]">Agnes</div>
                  <div className="text-[10px] uppercase tracking-widest text-[var(--foreground-muted)]">Supply Chain AI</div>
                </div>
              </Link>

              {/* Nav */}
              <nav className="flex items-center gap-1 text-sm">
                <Link
                  href="/"
                  className="rounded-md px-3 py-1.5 text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-white/5 dark:hover:bg-white/5 transition-colors"
                >
                  Dashboard
                </Link>
                <Link
                  href="/chat"
                  className="rounded-md px-3 py-1.5 text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-white/5 dark:hover:bg-white/5 transition-colors"
                >
                  Chat
                </Link>
                <div className="ml-2 h-4 w-px bg-[var(--border)]" />
                <ThemeToggle />
              </nav>
            </div>
          </header>

          <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
        </ThemeProvider>
      </body>
    </html>
  );
}
