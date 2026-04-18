"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ExternalLink,
  ShieldAlert,
  Loader2,
  FileText,
  TrendingUp,
  AlertCircle,
} from "lucide-react";
import AgnesChat from "../../components/AgnesChat";

interface Citation {
  label: string;
  url: string;
  scraped_at: string;
  confidence: number;
  snippet: string;
}

interface Claim {
  claim: string;
  status: string;
  citations: Citation[];
}

interface SignalItem {
  label: string;
  value: number;
  confidence: number;
  source_type: string;
  importance: number;
}

interface ScoreBreakdown {
  value: number;
  confidence: number;
  coverage: number;
  source_distribution: Record<string, number>;
  drivers: SignalItem[];
  weak_signals: SignalItem[];
  uncertainty_sources: string[];
}

interface EvidenceTrail {
  proposal_id: number;
  canonical_name: string;
  recommended_supplier: {
    id: number;
    name: string;
  };
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

const SOURCE_COLORS: Record<string, string> = {
  ontology: "bg-violet-500",
  deterministic: "bg-blue-500",
  llm: "bg-amber-500",
  embedding: "bg-slate-400",
};

function SourceBar({ distribution }: { distribution: Record<string, number> }) {
  const entries = Object.entries(distribution).filter(([, v]) => v > 0);
  if (!entries.length) return null;
  return (
    <div className="space-y-1">
      <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">Source distribution</p>
      <div className="flex h-2 w-full rounded-full overflow-hidden gap-px">
        {entries.map(([src, frac]) => (
          <div
            key={src}
            className={`${SOURCE_COLORS[src] ?? "bg-slate-300"}`}
            style={{ width: `${(frac * 100).toFixed(1)}%` }}
            title={`${src}: ${(frac * 100).toFixed(0)}%`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5">
        {entries.map(([src, frac]) => (
          <span key={src} className="flex items-center gap-1 text-[10px] text-slate-500">
            <span className={`inline-block h-2 w-2 rounded-sm ${SOURCE_COLORS[src] ?? "bg-slate-300"}`} />
            {src} {(frac * 100).toFixed(0)}%
          </span>
        ))}
      </div>
    </div>
  );
}

function CoverageMeter({ coverage }: { coverage: number }) {
  const pct = Math.round(coverage * 100);
  const color = pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[10px] font-medium text-slate-500 uppercase tracking-wider">
        <span>Signal coverage</span>
        <span className={pct >= 70 ? "text-emerald-600" : pct >= 40 ? "text-amber-600" : "text-red-600"}>
          {pct}%
        </span>
      </div>
      <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function ProposalDetail() {
  const params = useParams();
  const router = useRouter();
  const [trail, setTrail] = useState<EvidenceTrail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadData() {
      try {
        const res = await fetch(`http://127.0.0.1:8000/api/proposals/${params.id}`);
        if (!res.ok) {
          if (res.status === 404) throw new Error("Proposal not found");
          throw new Error("Failed to fetch proposal details");
        }
        setTrail(await res.json());
      } catch (err: unknown) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("An unexpected error occurred");
        }
      } finally {
        setLoading(false);
      }
    }
    if (params.id) loadData();
  }, [params.id]);

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error || !trail) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-500 mb-4">{error || "Something went wrong"}</p>
        <button onClick={() => router.back()} className="text-indigo-600 font-medium hover:underline">
          Go back
        </button>
      </div>
    );
  }

  const bd = trail.score_breakdown;
  const cb = trail.compliance_breakdown;

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-4xl mx-auto">
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="p-2 rounded-full hover:bg-slate-100 text-slate-500 transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-3">
            {trail.canonical_name}
            <span className="text-sm font-normal text-slate-500 bg-slate-100 px-2.5 py-0.5 rounded-full">
              ID: {trail.proposal_id}
            </span>
            {trail.flagged_low_confidence_high_impact && (
              <span className="text-xs font-semibold text-red-600 bg-red-50 border border-red-200 px-2 py-0.5 rounded-full flex items-center gap-1">
                <AlertCircle className="h-3 w-3" /> High impact · Low confidence
              </span>
            )}
          </h1>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Consolidation Summary</h2>
        <p className="text-slate-700 leading-relaxed mb-6">{trail.headline}</p>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-lg bg-slate-50 border border-slate-100">
            <div className="text-xs font-medium text-slate-500 mb-1">Target Supplier</div>
            <div className="font-semibold text-slate-900 truncate" title={trail.recommended_supplier.name}>
              {trail.recommended_supplier.name}
            </div>
          </div>
          <div className="p-4 rounded-lg bg-emerald-50 border border-emerald-100">
            <div className="text-xs font-medium text-emerald-600 mb-1">Est. Savings</div>
            <div className="font-semibold text-emerald-700 text-xl">
              {trail.metrics.estimated_savings_pct.toFixed(1)}%
            </div>
          </div>
          <div className="p-4 rounded-lg bg-blue-50 border border-blue-100">
            <div className="text-xs font-medium text-blue-600 mb-1">Impact Score</div>
            <div className="font-semibold text-blue-700 text-xl">
              {trail.impact_score.toFixed(3)}
            </div>
          </div>
          <div className={`p-4 rounded-lg border ${
            trail.verification_summary.passed
              ? "bg-emerald-50 border-emerald-100"
              : "bg-amber-50 border-amber-100"
          }`}>
            <div className={`text-xs font-medium mb-1 ${
              trail.verification_summary.passed ? "text-emerald-600" : "text-amber-600"
            }`}>
              Agent Verification
            </div>
            <div className={`font-semibold flex items-center gap-1.5 ${
              trail.verification_summary.passed ? "text-emerald-700" : "text-amber-700"
            }`}>
              {trail.verification_summary.passed ? (
                <><CheckCircle2 className="h-4 w-4" /> Passed</>
              ) : (
                <><ShieldAlert className="h-4 w-4" /> Issues Found</>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Uncertainty-aware score breakdown */}
      {bd && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-5">
          <h2 className="text-lg font-semibold text-slate-900">Score Breakdown</h2>

          {/* Value ± uncertainty band */}
          <div className="flex items-end gap-4">
            <div>
              <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider mb-1">
                Composite score
              </p>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold text-slate-900">
                  {(bd.value * 100).toFixed(0)}
                  <span className="text-lg font-normal text-slate-500">%</span>
                </span>
                <span className="text-sm text-slate-400">
                  ± {((1 - bd.confidence) * 100).toFixed(0)}% uncertainty band
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Confidence: <span className="font-medium text-slate-600">{(bd.confidence * 100).toFixed(0)}%</span>
              </p>
            </div>

            {/* Compliance breakdown pills */}
            {cb && (
              <div className="ml-auto flex gap-2 flex-wrap justify-end">
                {cb.compliant != null && (
                  <span className="px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold border border-emerald-200">
                    ✓ {cb.compliant} compliant
                  </span>
                )}
                {cb.non_compliant != null && cb.non_compliant > 0 && (
                  <span className="px-2.5 py-1 rounded-full bg-red-50 text-red-700 text-xs font-semibold border border-red-200">
                    ✗ {cb.non_compliant} non-compliant
                  </span>
                )}
                {cb.unknown != null && cb.unknown > 0 && (
                  <span className="px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 text-xs font-semibold border border-amber-200">
                    ? {cb.unknown} unknown
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Coverage bar + source distribution */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <CoverageMeter coverage={bd.coverage} />
            <SourceBar distribution={bd.source_distribution} />
          </div>

          {/* Main drivers */}
          {bd.drivers.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-700 flex items-center gap-1.5 mb-2">
                <TrendingUp className="h-3.5 w-3.5 text-emerald-500" />
                Main drivers (top contributing signals)
              </p>
              <div className="space-y-2">
                {bd.drivers.map((s, i) => (
                  <div key={i} className="flex items-center gap-3 text-xs">
                    <span className="font-medium text-slate-800 w-36 shrink-0 truncate">{s.label}</span>
                    <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-emerald-400 rounded-full"
                        style={{ width: `${(s.value * 100).toFixed(0)}%` }}
                      />
                    </div>
                    <span className="text-slate-500 w-10 text-right">{(s.value * 100).toFixed(0)}%</span>
                    <span className="text-slate-400 w-16 text-right">
                      conf {(s.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Weak signals / uncertainty sources */}
          {(bd.weak_signals.length > 0 || bd.uncertainty_sources.length > 0) && (
            <div className="rounded-lg bg-amber-50 border border-amber-100 p-4 space-y-2">
              {bd.weak_signals.length > 0 && (
                <>
                  <p className="text-xs font-semibold text-amber-800 flex items-center gap-1.5">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    Weak signals (high-importance, low-confidence)
                  </p>
                  <ul className="space-y-1">
                    {bd.weak_signals.map((s, i) => (
                      <li key={i} className="text-xs text-amber-700 flex items-center gap-2">
                        <span className="h-1.5 w-1.5 rounded-full bg-amber-500 shrink-0" />
                        {s.label}
                        <span className="text-amber-500">
                          (conf {(s.confidence * 100).toFixed(0)}% · imp {(s.importance * 100).toFixed(0)}%)
                        </span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {bd.uncertainty_sources.length > 0 && (
                <>
                  <p className="text-xs font-semibold text-amber-800 mt-2">Uncertainty sources</p>
                  <ul className="space-y-1">
                    {bd.uncertainty_sources.map((src, i) => (
                      <li key={i} className="text-xs text-amber-700 flex items-start gap-2">
                        <span className="h-1.5 w-1.5 rounded-full bg-amber-400 shrink-0 mt-1" />
                        {src}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {trail.risks && trail.risks.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-6 shadow-sm">
          <h3 className="text-sm font-semibold text-amber-900 flex items-center gap-2 mb-3">
            <AlertTriangle className="h-4 w-4" />
            Identified Risk Factors
          </h3>
          <ul className="space-y-2">
            {trail.risks.map((risk, i) => (
              <li key={i} className="text-sm text-amber-800 flex items-start gap-2">
                <span className="mt-1 block h-1.5 w-1.5 rounded-full bg-amber-500 shrink-0" />
                {risk}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-slate-900">Evidence Trail</h3>
        {trail.claims.map((claim, idx) => (
          <div key={idx} className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
            <div className="bg-slate-50 px-5 py-3 border-b border-slate-200 flex items-start justify-between gap-4">
              <div className="font-medium text-slate-800 text-sm">{claim.claim}</div>
              <div className="shrink-0">
                {claim.status === "VERIFIED" && (
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600">
                    <CheckCircle2 className="h-4 w-4" /> Verified
                  </span>
                )}
                {claim.status === "CONTRADICTED" && (
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-red-600">
                    <XCircle className="h-4 w-4" /> Contradicted
                  </span>
                )}
                {claim.status === "UNVERIFIED" && (
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-600">
                    <AlertTriangle className="h-4 w-4" /> Unverified
                  </span>
                )}
              </div>
            </div>

            {claim.citations.length > 0 ? (
              <div className="p-5 space-y-4">
                {claim.citations.map((cite, cidx) => (
                  <div key={cidx} className="flex gap-4">
                    <div className="mt-0.5 text-slate-400">
                      <FileText className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <span className="font-medium text-sm text-slate-900">{cite.label}</span>
                        {cite.url && (
                          <a href={cite.url} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline inline-flex items-center gap-1 text-xs">
                            Source <ExternalLink className="h-3 w-3" />
                          </a>
                        )}
                        <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-sm">
                          Confidence: {(cite.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p className="text-sm text-slate-600 leading-relaxed bg-slate-50 border border-slate-100 rounded-md p-3">
                        &quot;{cite.snippet}&quot;
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-5 text-sm text-slate-500 italic">
                No direct citations found for this claim.
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-12 pt-8 border-t border-slate-200">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Chat with Agnes</h3>
        <AgnesChat
          proposalId={trail.proposal_id}
          initialGreeting="Ask me anything about this proposal — why this supplier, what's missing, what would change my confidence."
          compact={true}
        />
      </div>
    </div>
  );
}
