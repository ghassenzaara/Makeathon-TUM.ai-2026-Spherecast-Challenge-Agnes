/* ═══════════════════════════════════════
   lib/types.ts — Single source of truth
   for all Agnes dashboard data shapes.
   ═══════════════════════════════════════ */

export interface Stats {
  proposal_count: number;
  verified_count: number;
  avg_confidence: number;
  avg_savings_pct: number;
  by_priority: Record<string, number>;
  by_compliance: Record<string, number>;
}

export interface Proposal {
  id: number;
  ingredient_group_id: number;
  recommended_supplier_id: number;
  recommended_supplier_name: string;
  companies_consolidated: string[];
  members_served: number;
  total_companies_in_group: number;
  estimated_savings_pct: number;
  compliance_status: string;
  confidence_score: number;
  priority: string;
  verification_passed: boolean;
  canonical_name: string;
}

/** The shape returned by fetchDashboardData() */
export interface DashboardData {
  stats: Stats | null;
  proposals: Proposal[];
}
