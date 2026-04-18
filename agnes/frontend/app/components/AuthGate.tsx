"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

/**
 * AuthGate — redirects to /login if not authenticated.
 * Wraps children and only renders them when auth is confirmed.
 * Skips check on /login route itself.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // Skip auth check on login page
    if (pathname === "/login") {
      setReady(true);
      return;
    }

    const isAuth = localStorage.getItem("agnes_auth") === "true";
    if (!isAuth) {
      router.replace("/login");
    } else {
      setReady(true);
    }
  }, [pathname, router]);

  if (!ready) return null;
  return <>{children}</>;
}
