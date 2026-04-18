/* ═══════════════════════════════════════
   lib/api.ts — Agnes Strategic API Layer.

   Connects the Next.js frontend to the Python backend.
   Base URL is managed via NEXT_PUBLIC_API_URL.
   ═══════════════════════════════════════ */

import type { DashboardData, Stats, Proposal } from "./types";

/** Base URL — set via .env.local or defaults to localhost:8000 */
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") ||
  "http://127.0.0.1:8000";

/**
 * Fetches dashboard stats and proposals in parallel.
 * Throws on failure to ensure error states are caught by components.
 */
export async function fetchDashboardData(): Promise<DashboardData> {
  const [statsRes, proposalsRes] = await Promise.all([
    fetch(`${API_BASE}/api/stats`, { signal: AbortSignal.timeout(8000) }),
    fetch(`${API_BASE}/api/proposals`, { signal: AbortSignal.timeout(8000) }),
  ]);

  if (!statsRes.ok || !proposalsRes.ok) {
    throw new Error(`API Error: Stats=${statsRes.status}, Proposals=${proposalsRes.status}`);
  }

  const stats: Stats = await statsRes.json();
  const proposals: Proposal[] = await proposalsRes.json();

  return { stats, proposals };
}

/**
 * Fetches a single proposal's evidence trail by ID.
 */
export async function fetchProposalDetail(id: string | number) {
  const res = await fetch(`${API_BASE}/api/proposals/${id}`, {
    signal: AbortSignal.timeout(8000),
  });
  if (!res.ok) {
    if (res.status === 404) throw new Error("Proposal not found.");
    throw new Error(`API Error: ${res.status}`);
  }
  return await res.json();
}

/**
 * Sends a chat message to the Agnes agent.
 */
export async function sendChatMessage(
  messages: { role: string; content: string }[]
): Promise<string> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
    signal: AbortSignal.timeout(20000),
  });

  if (!res.ok) throw new Error(`Agent offline (Status ${res.status})`);
  
  const data = await res.json();
  return data.answer || "No response recorded.";
}
