import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { ThemeProvider } from "./providers";
import { ThemeToggle } from "./components/ThemeToggle";
import { CrystalBallOrb, AgnesWordmark } from "./components/AgnesLogo";

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
            <div className="mx-auto flex max-w-7xl items-center px-6 py-4 relative">

              {/* Left — nav links */}
              <nav className="flex items-center gap-1 text-sm">
                <Link
                  href="/"
                  className="rounded-md px-3 py-1.5 text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-white/5 transition-colors"
                >
                  Dashboard
                </Link>
                <Link
                  href="/chat"
                  className="rounded-md px-3 py-1.5 text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-white/5 transition-colors"
                >
                  Chat
                </Link>
              </nav>

              {/* Center — logo (absolutely centered) */}
              <Link
                href="/"
                className="absolute left-1/2 -translate-x-1/2 flex items-center gap-2.5 group"
              >
                <CrystalBallOrb size={38} />
                <div>
                  <AgnesWordmark />
                  <div className="text-[11px] uppercase tracking-widest text-[var(--foreground-muted)] mt-0.5">
                    Supply Chain AI
                  </div>
                </div>
              </Link>

              {/* Right — theme toggle */}
              <div className="ml-auto">
                <ThemeToggle />
              </div>
            </div>
          </header>

          <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
        </ThemeProvider>
      </body>
    </html>
  );
}
