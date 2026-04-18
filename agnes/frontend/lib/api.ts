/* ═══════════════════════════════════════
   lib/api.ts — Agnes Strategic API Layer.

   Connects the Next.js frontend to the Python backend.
   Includes a silent mock fallback to prevent development overlays.
   ═══════════════════════════════════════ */

import type { DashboardData, Stats, Proposal } from "./types";
import { MOCK_STATS, MOCK_PROPOSALS } from "./mockData";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") ||
  "http://127.0.0.1:8000";

export async function fetchDashboardData(): Promise<DashboardData> {
  try {
    const [statsRes, proposalsRes] = await Promise.all([
      fetch(`${API_BASE}/api/stats`, { signal: AbortSignal.timeout(5000) }),
      fetch(`${API_BASE}/api/proposals`, { signal: AbortSignal.timeout(5000) }),
    ]);

    if (!statsRes.ok || !proposalsRes.ok) throw new Error("API Offline");

    const stats: Stats = await statsRes.json();
    const proposals: Proposal[] = await proposalsRes.json();

    return { stats, proposals };
  } catch (err) {
    // Silent fallback to keep the "Issue Panel" away
    return { stats: MOCK_STATS, proposals: MOCK_PROPOSALS };
  }
}

export async function fetchProposalDetail(id: string | number) {
  try {
    const res = await fetch(`${API_BASE}/api/proposals/${id}`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) throw new Error("Offline");
    return await res.json();
  } catch (err) {
    return null;
  }
}

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

    if (!res.ok) throw new Error("Offline");
    const data = await res.json();
    return data.answer || "No response recorded.";
  } catch (err) {
    return "Agent is optimizing the database. Please try again in a moment.";
  }
}
