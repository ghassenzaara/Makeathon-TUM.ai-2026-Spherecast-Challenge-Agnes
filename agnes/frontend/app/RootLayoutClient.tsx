"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { GalaxyBackground } from "./components/GalaxyBackground";
import { ChatWidget } from "./components/ChatWidget";
import { AuthGate } from "./components/AuthGate";

/* ─── Slim icon-based sidebar nav ─── */
function SideNav() {
  return (
    <nav className="flex flex-col items-center gap-1 py-6 px-2">
      {/* Logo — silver sphere placeholder */}
      <Link href="/" className="mb-6 group">
        <div
          className="h-8 w-8 rounded-full"
          style={{
            background: "radial-gradient(circle at 30% 30%, #f3f4f6, #737373, #171717)",
            boxShadow: "0 0 10px 2px rgba(160,160,160,0.2)",
          }}
        />
      </Link>

      <NavIcon href="/" label="Dashboard">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="7" height="7" rx="1"/>
          <rect x="14" y="3" width="7" height="7" rx="1"/>
          <rect x="3" y="14" width="7" height="7" rx="1"/>
          <rect x="14" y="14" width="7" height="7" rx="1"/>
        </svg>
      </NavIcon>

      <NavIcon href="/proposals/1" label="Proposals">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/>
          <path d="M14 2v6h6"/>
          <line x1="16" x2="8" y1="13" y2="13"/>
          <line x1="16" x2="8" y1="17" y2="17"/>
        </svg>
      </NavIcon>

      <NavIcon href="/chat" label="Chat">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="m3 21 1.9-5.7a8.5 8.5 0 1 1 3.8 3.8z"/>
        </svg>
      </NavIcon>

      <div className="flex-1" />

      <NavIcon href="#" label="Settings">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
          <circle cx="12" cy="12" r="3"/>
        </svg>
      </NavIcon>
    </nav>
  );
}

function NavIcon({ href, label, children }: { href: string; label: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      title={label}
      className="flex items-center justify-center w-10 h-10 rounded-xl text-[var(--foreground-muted)] hover:text-[var(--accent-blue)] hover:bg-white/[0.04] transition-all duration-200"
    >
      {children}
    </Link>
  );
}

export default function RootLayoutClient({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLoginPage = pathname === "/login";

  return (
    <>
      <GalaxyBackground />

      <AuthGate>
        {isLoginPage ? (
          /* Login page — full screen, no sidebar */
          <div className="relative z-10 min-h-screen">{children}</div>
        ) : (
          /* App shell — sidebar + main content */
          <div className="relative z-10 flex min-h-screen">
            <aside className="fixed left-0 top-0 z-50 flex h-screen w-14 flex-col border-r border-[var(--border)] bg-[var(--bg-surface-solid)]/80 backdrop-blur-md">
              <SideNav />
            </aside>
            <main className="ml-14 flex-1 min-h-screen">{children}</main>
          </div>
        )}
      </AuthGate>

      {/* Chat widget — only on app pages */}
      {!isLoginPage && <ChatWidget />}
    </>
  );
}
