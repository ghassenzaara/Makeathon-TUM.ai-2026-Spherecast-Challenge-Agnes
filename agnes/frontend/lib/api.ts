/* ═══════════════════════════════════════
   lib/api.ts — Bulletproof data fetcher.

   Reads from NEXT_PUBLIC_API_URL.
   If the real backend is online → returns live data.
   If it's offline/erroring → console.warns and
   gracefully returns mock data so the UI NEVER crashes.

   page.tsx just calls fetchDashboardData() blindly.
   ═══════════════════════════════════════ */

import type { DashboardData, Stats, Proposal } from "./types";
import { MOCK_STATS, MOCK_PROPOSALS } from "./mockData";

/** Base URL — set via .env.local or defaults to localhost:8000 */
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") ||
  "http://127.0.0.1:8000";

/**
 * Fetches both /api/stats and /api/proposals in parallel.
 * If either request fails, the entire result falls back to mock data.
 */
export async function fetchDashboardData(): Promise<DashboardData> {
  try {
    const [statsRes, proposalsRes] = await Promise.all([
      fetch(`${API_BASE}/api/stats`, { signal: AbortSignal.timeout(5000) }),
      fetch(`${API_BASE}/api/proposals`, { signal: AbortSignal.timeout(5000) }),
    ]);

    if (!statsRes.ok || !proposalsRes.ok) {
      throw new Error(
        `API returned non-200: stats=${statsRes.status}, proposals=${proposalsRes.status}`
      );
    }

    const stats: Stats = await statsRes.json();
    const proposals: Proposal[] = await proposalsRes.json();

    console.log(
      `✅ Agnes API: ${proposals.length} proposals loaded from ${API_BASE}`
    );

    return { stats, proposals };
  } catch (err) {
    console.warn(
      "⚠️ Agnes API unreachable — falling back to mock data.",
      err instanceof Error ? err.message : err
    );
    return { stats: MOCK_STATS, proposals: MOCK_PROPOSALS };
  }
}

/**
 * Fetches a single proposal's evidence trail by ID.
 * Falls back to null (the detail page handles the error state).
 */
export async function fetchProposalDetail(id: string | number) {
  try {
    const res = await fetch(`${API_BASE}/api/proposals/${id}`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) throw new Error(`Status ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(
      `⚠️ Agnes API: Could not load proposal ${id}.`,
      err instanceof Error ? err.message : err
    );
    return null;
  }
}

/**
 * Sends a chat message to the Agnes agent.
 * Falls back to a friendly offline message.
 */
export async function sendChatMessage(
  messages: { role: string; content: string }[]
): Promise<string> {
  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) throw new Error(`Status ${res.status}`);
    const data = await res.json();
    return data.answer || "No response from agent.";
  } catch (err) {
    console.warn(
      "⚠️ Agnes Chat unreachable.",
      err instanceof Error ? err.message : err
    );
    return "I'm currently offline. Please ensure the backend is running on " + API_BASE;
  }
}
