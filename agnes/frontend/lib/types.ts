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
  companies_consolidated: number;
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

/** RAG citation returned by /api/chat */
export interface Citation {
  doc_id: string;
  label: string;
  url: string;
  kind: string;
}

/** Chat response envelope */
export interface ChatResponse {
  answer: string;
  citations?: Citation[];
}

/** Single point returned by /api/proposals/rerank */
export interface RerankPoint {
  id: number;
  utility_score: number;
  rank: number;
  savings: number;
  compliance_probability: number;
  risk_score: number;
  is_pareto_optimal: boolean;
  dominated_by: number[];
  recommended_supplier_name: string;
  impact_score: number;
  impact_confidence: number;
  flagged_low_confidence_high_impact: boolean;
}

export interface RerankWeights {
  alpha: number;
  beta: number;
  gamma: number;
}
