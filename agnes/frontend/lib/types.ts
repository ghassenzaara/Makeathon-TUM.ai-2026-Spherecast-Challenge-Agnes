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
  // Probabilistic / multi-objective fields from backend
  compliance_probability: number;
  evidence_strength: number;
  risk_score: number;
  utility_score: number;
  pareto_rank: number | null;
  is_pareto_optimal: boolean;
  dominated_by: number[];
  impact_score: number;
  substitution_risk: number;
  reliability_variance: number;
  flagged_low_confidence_high_impact: boolean;
  score_breakdown: Record<string, unknown> | null;
  compliance_breakdown: Record<string, number> | null;
}

/** The shape returned by fetchDashboardData() */
export interface DashboardData {
  stats: Stats | null;
  proposals: Proposal[];
}

// ── Chat types ──────────────────────────────────────────────────────────────

/** RAG citation returned by /api/chat */
export interface RagCitation {
  doc_id: string;
  label: string;
  url: string;
  kind: string;
}

/** Chat response envelope */
export interface ChatResponse {
  answer: string;
  citations?: RagCitation[];
}

// ── Rerank / Pareto types ───────────────────────────────────────────────────

/** Single point returned by /api/proposals/rerank */
export interface RerankPoint {
  id: number;
  utility_score: number;
  rank: number;
  savings: number;
  compliance_probability: number;
  risk_score: number;
  substitution_risk: number;
  reliability_variance: number;
  is_pareto_optimal: boolean;
  dominated_by: number[];
  recommended_supplier_name: string;
  canonical_name: string;
  companies_consolidated: number;
  impact_score: number;
  impact_confidence: number;
  flagged_low_confidence_high_impact: boolean;
}

/** 5-weight vector sent to /api/proposals/rerank */
export interface RerankWeights {
  alpha: number;
  beta: number;
  gamma: number;
  delta: number;
  epsilon: number;
}

// ── Evidence Trail types ────────────────────────────────────────────────────

export interface EvidenceCitation {
  label: string;
  url: string;
  scraped_at: string;
  confidence: number;
  snippet: string;
}

export interface Claim {
  claim: string;
  status: string;
  citations: EvidenceCitation[];
}

export interface SignalItem {
  label: string;
  value: number;
  confidence: number;
  source_type: string;
  importance: number;
}

export interface ScoreBreakdown {
  value: number;
  confidence: number;
  coverage: number;
  source_distribution: Record<string, number>;
  drivers: SignalItem[];
  weak_signals: SignalItem[];
  uncertainty_sources: string[];
}

export interface EvidenceTrail {
  proposal_id: number;
  canonical_name: string;
  recommended_supplier: { id: number; name: string };
  headline: string;
  metrics: {
    companies_consolidated: number;
    total_companies_in_group: number;
    members_served: number;
    estimated_savings_pct: number;
    confidence_score: number;
    priority: string;
    compliance_status: string;
  };
  claims: Claim[];
  risks: string[];
  verification_summary: {
    counts: Record<string, number>;
    passed: boolean;
    all_verified: boolean;
  };
  score_breakdown: ScoreBreakdown | null;
  compliance_breakdown: Record<string, number> | null;
  impact_score: number;
  flagged_low_confidence_high_impact: boolean;
}
