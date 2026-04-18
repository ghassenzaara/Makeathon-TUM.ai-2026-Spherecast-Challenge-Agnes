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
  FileText
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
            <div className="text-xs font-medium text-blue-600 mb-1">Confidence Score</div>
            <div className="font-semibold text-blue-700 text-xl">
              {trail.metrics.confidence_score.toFixed(0)}%
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
