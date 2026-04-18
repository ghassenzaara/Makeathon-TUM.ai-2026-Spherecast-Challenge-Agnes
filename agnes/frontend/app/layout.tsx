import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { AgnesLogoMark } from "./components/AgnesLogo";

export const metadata: Metadata = {
  title: "Agnes — AI Supply Chain Manager",
  description: "AI-powered sourcing consolidation command center",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[var(--background)] text-[var(--foreground)] antialiased">
        <header className="sticky top-0 z-50 border-b border-white/[0.06] bg-transparent backdrop-blur-md">
          <div className="flex items-center justify-between px-20 py-3">

            {/* Left — logo */}
            <Link href="/" className="flex items-center">
              <AgnesLogoMark />
            </Link>

            {/* Right — Log In: glassy orb-blue pill */}
            <button
              disabled
              className="relative rounded-full px-5 py-1.5 text-sm font-medium transition-all cursor-not-allowed overflow-hidden"
              style={{
                color: "#a8d4ef",
                border: "1px solid rgba(163,198,236,0.22)",
                background: "linear-gradient(135deg, rgba(163,198,236,0.08) 0%, rgba(92,127,199,0.06) 100%)",
                boxShadow: "0 0 10px 1px rgba(163,198,236,0.08), inset 0 1px 0 rgba(255,255,255,0.06)",
                backdropFilter: "blur(8px)",
              }}
            >
              Log In
            </button>

          </div>
        </header>

        <main className="relative z-10">{children}</main>
      </body>
    </html>
  );
}
