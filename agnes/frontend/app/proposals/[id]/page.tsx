"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  ArrowLeft, CheckCircle2, AlertTriangle, XCircle,
  ExternalLink, ShieldAlert, FileText, Activity,
} from "lucide-react";
import { AgnesOrb } from "../../components/AgnesOrb";
import { TracingBorder } from "../../components/TracingBorder";
import { Waveform } from "../../components/Waveform";
import AgnesChat from "../../components/AgnesChat";
import { fetchProposalDetail } from "@/lib/api";

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

const fadeIn = {
  hidden: { opacity: 0, y: 14 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.08, duration: 0.4 },
  }),
};

export default function ProposalDetail() {
  const params = useParams();
  const router = useRouter();
  const [trail, setTrail] = useState<EvidenceTrail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    window.scrollTo(0, 0);
    async function loadData() {
      try {
        const data = await fetchProposalDetail(params.id as string);
        setTrail(data);
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
        <div className="flex flex-col items-center gap-4">
          <AgnesOrb state="thinking" size={56} />
          <span className="text-xs uppercase tracking-[0.2em] text-[var(--foreground-muted)]">Loading evidence trail…</span>
          <Waveform active={true} barCount={24} />
        </div>
      </div>
    );
  }

  if (error || !trail) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="glass-card p-8 text-center max-w-sm">
          <Activity className="h-8 w-8 mx-auto mb-3 text-[var(--foreground-dim)]" />
          <p className="text-sm text-[var(--foreground-muted)] mb-4">{error || "Something went wrong"}</p>
          <button
            onClick={() => router.back()}
            className="text-[var(--accent-blue)] text-sm font-medium hover:underline"
          >
            ← Go back
          </button>
        </div>
      </div>
    );
  }

  const confScore = trail.metrics.confidence_score;
  const confColor = confScore >= 75 ? "text-emerald-400" : confScore >= 50 ? "text-amber-400" : "text-fuchsia-400";

  return (
    <div className="max-w-4xl mx-auto px-6 py-6 space-y-6">

      {/* ── Header ── */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col md:flex-row items-start gap-4 justify-between">
        <div className="flex items-start gap-4 flex-1 min-w-0">
          <button
            onClick={() => router.back()}
            className="p-2 rounded-xl text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-white/[0.04] transition-all mt-0.5 shrink-0"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-xl font-bold text-[var(--foreground)] truncate">{trail.canonical_name}</h1>
              <span className="text-[10px] text-[var(--foreground-muted)] bg-white/[0.04] border border-[var(--border)] rounded-md px-2 py-0.5 shrink-0">
                ID: {trail.proposal_id}
              </span>
              <PriorityBadge priority={trail.metrics.priority} />
            </div>
            <p className="text-sm text-[var(--foreground-muted)] leading-relaxed">{trail.headline}</p>
          </div>
        </div>

        <button
          onClick={() => {
            document.getElementById("chat-section")?.scrollIntoView({ behavior: "smooth" });
          }}
          className="shrink-0 md:mt-1 px-4 py-2 text-sm font-semibold rounded-full bg-[var(--accent-blue)]/10 text-[var(--accent-blue)] border border-[var(--accent-blue)]/30 hover:bg-[var(--accent-blue)]/20 transition-all shadow-[0_0_15px_rgba(56,189,248,0.3)] hover:shadow-[0_0_25px_rgba(56,189,248,0.5)] whitespace-nowrap flex items-center gap-2 ml-14 md:ml-0"
        >
          Ask More <AgnesOrb state="idle" size={16} />
        </button>
      </motion.div>

      {/* ── Metrics Grid ── */}
      <motion.div
        className="grid grid-cols-2 md:grid-cols-4 gap-3"
        initial="hidden" animate="visible"
        variants={{ visible: { transition: { staggerChildren: 0.06 } } }}
      >
        <motion.div variants={fadeIn} custom={0}>
          <MetricTile label="Target Supplier" value={trail.recommended_supplier.name} accent="silver" />
        </motion.div>
        <motion.div variants={fadeIn} custom={1}>
          <MetricTile label="Est. Savings" value={`${trail.metrics.estimated_savings_pct.toFixed(1)}%`} accent="emerald" />
        </motion.div>
        <motion.div variants={fadeIn} custom={2}>
          <MetricTile label="Confidence" value={`${confScore.toFixed(0)}%`} accent={confScore >= 75 ? "emerald" : confScore >= 50 ? "amber" : "fuchsia"} />
        </motion.div>
        <motion.div variants={fadeIn} custom={3}>
          <MetricTile
            label="Verification"
            value={trail.verification_summary.passed ? "Passed" : "Issues Found"}
            accent={trail.verification_summary.passed ? "emerald" : "amber"}
            icon={trail.verification_summary.passed ? <CheckCircle2 className="h-3.5 w-3.5" /> : <ShieldAlert className="h-3.5 w-3.5" />}
          />
        </motion.div>
      </motion.div>

      {/* ── Coverage Bar ── */}
      <motion.div variants={fadeIn} custom={4} initial="hidden" animate="visible" className="glass-card p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-[var(--foreground-muted)]">Consolidation Coverage</span>
          <span className="text-xs font-medium text-[var(--foreground)]">{trail.metrics.members_served} / {trail.metrics.total_companies_in_group} companies</span>
        </div>
        <div className="h-2 rounded-full bg-white/[0.06] overflow-hidden">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-sky-500 to-cyan-400"
            initial={{ width: 0 }}
            animate={{ width: `${(trail.metrics.members_served / trail.metrics.total_companies_in_group) * 100}%` }}
            transition={{ duration: 1, delay: 0.3, ease: "easeOut" }}
            style={{ boxShadow: "0 0 8px rgba(56,189,248,0.3)" }}
          />
        </div>
      </motion.div>

      {/* ── Risk Factors ── */}
      {trail.risks?.length > 0 && (
        <motion.div variants={fadeIn} custom={5} initial="hidden" animate="visible">
          <div className="glass-card p-4 border-amber-500/15" style={{ borderColor: "rgba(245,158,11,0.12)" }}>
            <h3 className="text-[10px] font-semibold uppercase tracking-[0.15em] text-amber-400 flex items-center gap-2 mb-3">
              <AlertTriangle className="h-3.5 w-3.5" /> Risk Factors
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
        </motion.div>
      )}

      {/* ── Evidence Trail ── */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}>
        <h3 className="text-sm font-semibold text-[var(--foreground)] mb-3 flex items-center gap-2">
          <FileText className="h-4 w-4 text-[var(--accent-cyan)]" />
          Evidence Trail
          <span className="text-[10px] text-[var(--foreground-muted)] bg-white/[0.04] border border-[var(--border)] rounded-md px-2 py-0.5">
            {trail.claims.length} claims
          </span>
        </h3>
        <div className="space-y-3">
          {trail.claims.map((claim, idx) => {
            const isVerified = claim.status === "VERIFIED";
            return (
              <motion.div key={idx} variants={fadeIn} custom={idx} initial="hidden" animate="visible">
                {isVerified ? (
                  <div className="glass-card overflow-hidden">
                    <ClaimContent claim={claim} />
                  </div>
                ) : (
                  <TracingBorder
                    active={claim.status === "CONTRADICTED"}
                    borderRadius={16}
                    glowColor={claim.status === "CONTRADICTED" ? "rgba(217, 70, 239, 0.6)" : "rgba(56, 189, 248, 0.6)"}
                  >
                    <ClaimContent claim={claim} />
                  </TracingBorder>
                )}
              </motion.div>
            );
          })}
        </div>
      </motion.div>

      {/* ── Agnes Summary ── */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }}>
        <TracingBorder active={true} borderRadius={16}>
          <div className="p-5 flex items-start gap-4">
            <AgnesOrb state="idle" size={40} />
            <div>
              <h4 className="text-sm font-semibold text-[var(--foreground)] mb-1">Agnes Assessment</h4>
              <p className="text-[13px] leading-relaxed text-[var(--foreground-muted)]">
                {trail.verification_summary.passed ? (
                  <>
                    All verification checks <span className="text-emerald-400 font-medium">passed</span>. This proposal
                    for <span className="text-[var(--accent-blue)] font-medium">{trail.canonical_name}</span> via{" "}
                    <span className="text-[var(--foreground)] font-medium">{trail.recommended_supplier.name}</span> is
                    recommended for consolidation with <span className={confColor + " font-medium"}>{confScore}% confidence</span> and
                    an estimated <span className="text-emerald-400 font-medium">+{trail.metrics.estimated_savings_pct.toFixed(1)}%</span> savings.
                  </>
                ) : (
                  <>
                    Some verification checks <span className="text-amber-400 font-medium">require review</span>.
                    While <span className="text-[var(--accent-blue)] font-medium">{trail.canonical_name}</span> shows
                    potential for consolidation, {trail.risks.length > 0 ? `${trail.risks.length} risk factor(s) were identified` : "further analysis is needed"}.
                    Confidence: <span className={confColor + " font-medium"}>{confScore}%</span>.
                  </>
                )}
              </p>
            </div>
          </div>
        </TracingBorder>
      </motion.div>

      {/* ── Per-Proposal Chat (Evidence-Trail Context) ── */}
      <motion.div
        id="chat-section"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.7, duration: 0.5 }}
      >
        <AgnesChat proposalId={trail.proposal_id} compact />
      </motion.div>
    </div>
  );
}


/* ═══ Sub-Components ═══ */

function ClaimContent({ claim }: { claim: Claim }) {
  return (
    <>
      <div className="px-5 py-3 border-b border-white/[0.04] flex items-start justify-between gap-4 bg-white/[0.01]">
        <p className="text-sm font-medium text-[var(--foreground)]">{claim.claim}</p>
        <ClaimStatus status={claim.status} />
      </div>
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
                      className="inline-flex items-center gap-1 text-xs text-[var(--accent-blue)] hover:underline"
                    >
                      Source <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-[var(--foreground-muted)] bg-white/[0.04] border border-[var(--border)] px-2 py-0.5 rounded">
                    {(cite.confidence * 100).toFixed(0)}% confidence
                  </span>
                </div>
                <blockquote className="text-sm text-[var(--foreground-muted)] leading-relaxed border-l-2 border-sky-500/30 pl-3 italic">
                  &quot;{cite.snippet}&quot;
                </blockquote>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="px-5 py-4 text-sm text-[var(--foreground-muted)] italic">No direct citations found for this claim.</p>
      )}
    </>
  );
}

function MetricTile({ label, value, accent, icon }: {
  label: string; value: string; accent: string; icon?: React.ReactNode;
}) {
  const colors: Record<string, string> = {
    silver:  "text-gray-300",
    emerald: "text-emerald-400",
    cyan:    "text-cyan-400",
    amber:   "text-amber-400",
    fuchsia: "text-fuchsia-400",
  };
  return (
    <div className="glass-card p-4">
      <div className="text-[9px] uppercase tracking-[0.12em] font-medium text-[var(--foreground-muted)] mb-1">{label}</div>
      <div className={`font-semibold text-lg flex items-center gap-1.5 truncate ${colors[accent] ?? colors.silver}`}>
        {icon}{value}
      </div>
    </div>
  );
}

function PriorityBadge({ priority }: { priority: string }) {
  const s: Record<string, string> = {
    HIGH: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    MEDIUM: "bg-sky-500/10 text-sky-400 border-sky-500/20",
    LOW: "bg-slate-500/10 text-slate-400 border-slate-500/20",
  };
  return <span className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-medium border shrink-0 ${s[priority] ?? s.LOW}`}>{priority}</span>;
}

function ClaimStatus({ status }: { status: string }) {
  if (status === "VERIFIED")
    return <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-400 shrink-0"><CheckCircle2 className="h-4 w-4" /> Verified</span>;
  if (status === "CONTRADICTED")
    return <span className="inline-flex items-center gap-1 text-xs font-semibold text-fuchsia-400 shrink-0"><XCircle className="h-4 w-4" /> Contradicted</span>;
  return <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-400 shrink-0"><AlertTriangle className="h-4 w-4" /> Unverified</span>;
}
