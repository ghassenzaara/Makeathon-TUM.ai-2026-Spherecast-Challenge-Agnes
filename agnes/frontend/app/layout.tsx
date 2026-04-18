import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agnes — AI Supply Chain Manager",
  description: "Phase 4 dashboard for sourcing consolidation proposals",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
            <Link href="/" className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-md bg-slate-900 text-white grid place-items-center font-mono text-sm font-bold">
                A
              </div>
              <div>
                <div className="text-sm font-semibold tracking-tight">Agnes</div>
                <div className="text-xs text-slate-500">AI Supply Chain Manager</div>
              </div>
            </Link>
            <nav className="flex items-center gap-1 text-sm">
              <Link
                href="/"
                className="rounded-md px-3 py-1.5 text-slate-700 hover:bg-slate-100"
              >
                Dashboard
              </Link>
              <Link
                href="/chat"
                className="rounded-md px-3 py-1.5 text-slate-700 hover:bg-slate-100"
              >
                Chat
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
