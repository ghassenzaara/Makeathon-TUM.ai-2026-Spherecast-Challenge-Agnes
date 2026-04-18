"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  TrendingUp,
  FileCheck,
  ShieldAlert,
  Loader2,
  Box,
  Zap,
  ChevronDown,
} from "lucide-react";
import { SavingsChart } from "./components/SavingsChart";
import { GaugeChart } from "./components/GaugeChart";
import { GalaxyCanvas } from "@/components/GalaxyCanvas";
import { HeroChatBar } from "@/components/HeroChatBar";
import { Card } from "@/components/ui/card";

interface Stats {
  proposal_count: number;
  verified_count: number;
  avg_confidence: number;
  avg_savings_pct: number;
  by_priority: Record<string, number>;
  by_compliance: Record<string, number>;
}

interface Proposal {
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

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [statsRes, propsRes] = await Promise.all([
          fetch("http://127.0.0.1:8000/api/stats"),
          fetch("http://127.0.0.1:8000/api/proposals"),
        ]);
        if (statsRes.ok) setStats(await statsRes.json());
        if (propsRes.ok) setProposals(await propsRes.json());
      } catch {
        // backend offline — show empty state
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const highPriority = proposals.filter((p) => p.priority === "HIGH");

  return (
    <>
      {/* ── Galaxy background (fixed, behind everything) ── */}
      <GalaxyCanvas />

      {/* ── Hero section — full viewport height, transparent ── */}
      <section className="relative flex min-h-[calc(100vh-73px)] flex-col items-center justify-center gap-8 px-6">
        {/* Greeting */}
        <div className="text-center space-y-3">
          <h1 className="text-4xl sm:text-5xl font-bold text-white leading-tight">
            What can I help you source?
          </h1>
        </div>

        {/* Big Gemini-style chat bar */}
        <HeroChatBar />

        {/* Scroll hint */}
        <div className="absolute bottom-8 flex flex-col items-center gap-1 text-white/20 select-none pointer-events-none">
          <ChevronDown className="h-5 w-5 animate-bounce" />
        </div>
      </section>

      {/* ── Dashboard — solid bg, scrolls in below hero ── */}
      <div className="relative bg-[var(--background)]">
        {/* Fade from galaxy to solid */}
        <div
          className="absolute -top-24 inset-x-0 h-24 pointer-events-none"
          style={{
            background: "linear-gradient(to bottom, transparent, var(--background))",
          }}
        />

        <div className="mx-auto max-w-7xl px-6 py-10 space-y-6 animate-fade-in">

          {/* Page label */}
          <div>
            <h2 className="text-xl font-bold tracking-tight text-[var(--foreground)]">
              Command Center
            </h2>
            <p className="text-sm text-[var(--foreground-muted)] mt-1">
              AI-generated sourcing consolidation proposals — Agnes Phase 4
            </p>
          </div>

          {loading && (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-8 w-8 animate-spin text-cyan-500" />
            </div>
          )}

          {/* ── Row 1: stat tiles ── */}
          {stats && (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatTile label="Total Proposals" value={stats.proposal_count.toString()} accent="cyan"    icon={<Box className="h-6 w-6" />} />
              <StatTile label="Avg Est. Savings" value={`${stats.avg_savings_pct}%`}   accent="emerald" icon={<TrendingUp className="h-6 w-6" />} />
              <StatTile label="Agent Verified"   value={stats.verified_count.toString()} accent="violet" icon={<CheckCircle2 className="h-6 w-6" />} />
              <StatTile label="High Priority"    value={(stats.by_priority["HIGH"] || 0).toString()} accent="amber" icon={<AlertTriangle className="h-6 w-6" />} />
            </div>
          )}

          {/* ── Row 2: charts ── */}
          {stats && proposals.length > 0 && (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
              <div className="lg:col-span-3">
                <SavingsChart proposals={proposals} />
              </div>
              <div className="lg:col-span-2">
                <GaugeChart value={stats.avg_confidence} label="AI Confidence" />
              </div>
            </div>
          )}

          {/* ── Command alerts strip ── */}
          {highPriority.length > 0 && (
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-400" />
                </span>
                <span className="text-xs font-semibold uppercase tracking-widest text-amber-400">
                  Command Alerts — {highPriority.length} high-priority
                </span>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {highPriority.slice(0, 6).map((p) => (
                  <Link
                    key={p.id}
                    href={`/proposals/${p.id}`}
                    className="flex items-center justify-between rounded-lg border border-amber-500/20 bg-[var(--surface)] px-4 py-3 hover:border-amber-500/50 transition-colors group"
                  >
                    <div>
                      <div className="text-sm font-semibold text-[var(--foreground)] truncate max-w-[160px]">
                        {p.canonical_name}
                      </div>
                      <div className="text-xs text-amber-400 mt-0.5">
                        {p.recommended_supplier_name} · +{p.estimated_savings_pct}%
                      </div>
                    </div>
                    <ArrowRight className="h-4 w-4 text-[var(--foreground-muted)] group-hover:text-amber-400 transition-colors shrink-0" />
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* ── Proposals table ── */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
            <div className="border-b border-[var(--border)] px-6 py-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-[var(--foreground)] flex items-center gap-2">
                <Zap className="h-4 w-4 text-cyan-500" />
                Sourcing Proposals
              </h2>
              <span className="text-xs text-[var(--foreground-muted)]">
                {proposals.length} total
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-[var(--foreground-muted)] text-xs uppercase tracking-wider">
                    <th className="px-6 py-3 font-medium">Ingredient</th>
                    <th className="px-6 py-3 font-medium">Supplier</th>
                    <th className="px-6 py-3 font-medium">Savings</th>
                    <th className="px-6 py-3 font-medium">Confidence</th>
                    <th className="px-6 py-3 font-medium">Compliance</th>
                    <th className="px-6 py-3 font-medium">Priority</th>
                    <th className="px-6 py-3 font-medium text-right">Detail</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {proposals.map((p) => (
                    <tr key={p.id} className="hover:bg-white/5 transition-colors group">
                      <td className="px-6 py-4">
                        <div className="font-medium text-[var(--foreground)]">{p.canonical_name}</div>
                        <div className="text-xs text-[var(--foreground-muted)] mt-0.5">
                          {p.members_served} of {p.total_companies_in_group} companies
                        </div>
                      </td>
                      <td className="px-6 py-4 text-[var(--foreground)]">{p.recommended_supplier_name}</td>
                      <td className="px-6 py-4">
                        <span className="font-semibold text-emerald-400">+{p.estimated_savings_pct}%</span>
                      </td>
                      <td className="px-6 py-4"><ConfidenceBar score={p.confidence_score} /></td>
                      <td className="px-6 py-4"><ComplianceBadge status={p.compliance_status} /></td>
                      <td className="px-6 py-4"><PriorityBadge priority={p.priority} /></td>
                      <td className="px-6 py-4 text-right">
                        <Link
                          href={`/proposals/${p.id}`}
                          className="inline-flex items-center justify-center h-8 w-8 rounded-md text-[var(--foreground-muted)] hover:text-cyan-400 hover:bg-cyan-500/10 transition-colors"
                        >
                          <ArrowRight className="h-4 w-4" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                  {proposals.length === 0 && !loading && (
                    <tr>
                      <td colSpan={7} className="px-6 py-16 text-center text-[var(--foreground-muted)] text-sm">
                        No proposals found — run Phase 1–3 first.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

        </div>
      </div>
    </>
  );
}

/* ── Sub-components ── */

function StatTile({
  label, value, accent, icon,
}: {
  label: string;
  value: string;
  accent: "cyan" | "emerald" | "violet" | "amber";
  icon: React.ReactNode;
}) {
  const panel = {
    cyan:    "bg-cyan-500/10 border-r border-cyan-500/20 text-cyan-400",
    emerald: "bg-emerald-500/10 border-r border-emerald-500/20 text-emerald-400",
    violet:  "bg-violet-500/10 border-r border-violet-500/20 text-violet-400",
    amber:   "bg-amber-500/10 border-r border-amber-500/20 text-amber-400",
  };
  return (
    <Card className="flex items-stretch overflow-hidden h-11">
      <div className={`flex items-center justify-center ${panel[accent]}`} style={{ width: "42%" }}>
        {icon}
      </div>
      <div className="flex flex-col justify-center px-3">
        <p className="text-xl font-bold text-[var(--foreground)] leading-none">{value}</p>
        <p className="text-[8px] uppercase tracking-wider text-[var(--foreground-muted)] mt-0.5">{label}</p>
      </div>
    </Card>
  );
}

function ConfidenceBar({ score }: { score: number }) {
  const color = score > 75 ? "bg-emerald-500" : score > 50 ? "bg-amber-500" : "bg-fuchsia-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 rounded-full bg-[var(--border)] overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs text-[var(--foreground-muted)]">{score}%</span>
    </div>
  );
}

function ComplianceBadge({ status }: { status: string }) {
  if (status === "PASSED" || status === "ALL_PASS")
    return (
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
        <FileCheck className="h-3 w-3" /> Passed
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-fuchsia-500/10 text-fuchsia-400 border border-fuchsia-500/20">
      <ShieldAlert className="h-3 w-3" /> Review
    </span>
  );
}

function PriorityBadge({ priority }: { priority: string }) {
  const styles: Record<string, string> = {
    HIGH:   "bg-amber-500/10 text-amber-400 border-amber-500/20",
    MEDIUM: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
    LOW:    "bg-slate-500/10 text-slate-400 border-slate-500/20",
  };
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium border ${styles[priority] ?? styles.LOW}`}>
      {priority}
    </span>
  );
}
