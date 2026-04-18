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
} from "lucide-react";

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
        if (!res.ok) throw new Error(res.status === 404 ? "Proposal not found" : "Failed to load");
        setTrail(await res.json());
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Unexpected error");
      } finally {
        setLoading(false);
      }
    }
    if (params.id) loadData();
  }, [params.id]);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-cyan-500" />
      </div>
    );
  }

  if (error || !trail) {
    return (
      <div className="text-center py-16">
        <p className="text-[var(--foreground-muted)] mb-4">{error || "Something went wrong"}</p>
        <button onClick={() => router.back()} className="text-cyan-400 font-medium hover:underline">
          Go back
        </button>
      </div>
    );
  }

  return (
    <div className="px-6 py-8">
    <div className="space-y-6 animate-fade-in max-w-4xl mx-auto">

      {/* Back + title */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="p-2 rounded-full text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-white/5 transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)] flex items-center gap-3">
            {trail.canonical_name}
            <span className="text-xs font-normal text-[var(--foreground-muted)] bg-white/5 border border-[var(--border)] px-2.5 py-0.5 rounded-full">
              ID: {trail.proposal_id}
            </span>
          </h1>
        </div>
      </div>

      {/* Summary card */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-sm font-semibold text-[var(--foreground)] mb-3">Consolidation Summary</h2>
        <p className="text-sm text-[var(--foreground-muted)] leading-relaxed mb-6">{trail.headline}</p>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MetricTile label="Target Supplier" value={trail.recommended_supplier.name} color="default" />
          <MetricTile label="Est. Savings" value={`${trail.metrics.estimated_savings_pct.toFixed(1)}%`} color="emerald" />
          <MetricTile label="Confidence" value={`${trail.metrics.confidence_score.toFixed(0)}%`} color="cyan" />
          <MetricTile
            label="Agent Verification"
            value={trail.verification_summary.passed ? "Passed" : "Issues Found"}
            color={trail.verification_summary.passed ? "emerald" : "amber"}
            icon={trail.verification_summary.passed
              ? <CheckCircle2 className="h-3.5 w-3.5" />
              : <ShieldAlert className="h-3.5 w-3.5" />}
          />
        </div>
      </div>

      {/* Risk factors */}
      {trail.risks?.length > 0 && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-5">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-amber-400 flex items-center gap-2 mb-3">
            <AlertTriangle className="h-4 w-4" /> Risk Factors
          </h3>
          <ul className="space-y-2">
            {trail.risks.map((risk, i) => (
              <li key={i} className="text-sm text-amber-300/80 flex items-start gap-2">
                <span className="mt-1.5 block h-1.5 w-1.5 rounded-full bg-amber-500 shrink-0" />
                {risk}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Evidence trail */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold uppercase tracking-widest text-[var(--foreground-muted)]">
          Evidence Trail
        </h3>
        {trail.claims.map((claim, idx) => (
          <div
            key={idx}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden"
          >
            {/* Claim header */}
            <div className="px-5 py-3 border-b border-[var(--border)] flex items-start justify-between gap-4 bg-white/[0.02]">
              <p className="text-sm font-medium text-[var(--foreground)]">{claim.claim}</p>
              <ClaimStatus status={claim.status} />
            </div>

            {/* Citations */}
            {claim.citations.length > 0 ? (
              <div className="p-5 space-y-4">
                {claim.citations.map((cite, cidx) => (
                  <div key={cidx} className="flex gap-3">
                    <FileText className="h-4 w-4 text-[var(--foreground-muted)] mt-0.5 shrink-0" />
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 mb-2">
                        <span className="text-sm font-medium text-[var(--foreground)]">{cite.label}</span>
                        {cite.url && (
                          <a
                            href={cite.url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-cyan-400 hover:underline"
                          >
                            Source <ExternalLink className="h-3 w-3" />
                          </a>
                        )}
                        <span className="text-[10px] uppercase tracking-wider font-semibold text-[var(--foreground-muted)] bg-white/5 border border-[var(--border)] px-2 py-0.5 rounded">
                          {(cite.confidence * 100).toFixed(0)}% confidence
                        </span>
                      </div>
                      <blockquote className="text-sm text-[var(--foreground-muted)] leading-relaxed border-l-2 border-cyan-500/40 pl-3 italic">
                        &quot;{cite.snippet}&quot;
                      </blockquote>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="px-5 py-4 text-sm text-[var(--foreground-muted)] italic">
                No direct citations found for this claim.
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
    </div>
  );
}

/* ── Sub-components ── */

function MetricTile({
  label, value, color, icon,
}: {
  label: string;
  value: string;
  color: "default" | "emerald" | "cyan" | "amber";
  icon?: React.ReactNode;
}) {
  const styles = {
    default: "text-[var(--foreground)]",
    emerald: "text-emerald-400",
    cyan:    "text-cyan-400",
    amber:   "text-amber-400",
  };
  return (
    <div className="rounded-lg border border-[var(--border)] bg-white/[0.02] p-4">
      <div className="text-[10px] uppercase tracking-widest font-medium text-[var(--foreground-muted)] mb-1">{label}</div>
      <div className={`font-semibold text-lg flex items-center gap-1.5 truncate ${styles[color]}`}>
        {icon}{value}
      </div>
    </div>
  );
}

function ClaimStatus({ status }: { status: string }) {
  if (status === "VERIFIED")
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-400 shrink-0">
        <CheckCircle2 className="h-4 w-4" /> Verified
      </span>
    );
  if (status === "CONTRADICTED")
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold text-fuchsia-400 shrink-0">
        <XCircle className="h-4 w-4" /> Contradicted
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-400 shrink-0">
      <AlertTriangle className="h-4 w-4" /> Unverified
    </span>
  );
}
