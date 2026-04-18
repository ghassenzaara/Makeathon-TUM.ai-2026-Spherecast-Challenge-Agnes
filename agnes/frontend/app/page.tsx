"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  CheckCircle2, AlertTriangle, TrendingUp,
  ShieldAlert, FileCheck, Box, Zap, Activity,
  ExternalLink, ChevronDown, ChevronUp, Eye, ToggleLeft, ToggleRight,
} from "lucide-react";
import { AgnesOrb } from "./components/AgnesOrb";
import { Waveform } from "./components/Waveform";
import { TracingBorder } from "./components/TracingBorder";
import { SpotlightCard } from "./components/SpotlightCard";
import { ParetoChart } from "./components/ParetoChart";
import { fetchDashboardData } from "@/lib/api";
import type { Stats, Proposal } from "@/lib/types";


/* ─── Priority Sort ─── */
const PRIORITY_WEIGHT: Record<string, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 };

function sortByImpact(proposals: Proposal[]): Proposal[] {
  return [...proposals].sort((a, b) => {
    const wA = PRIORITY_WEIGHT[a.priority] || 0;
    const wB = PRIORITY_WEIGHT[b.priority] || 0;
    if (wA !== wB) return wB - wA;
    return b.estimated_savings_pct - a.estimated_savings_pct;
  });
}

/* ─── Framer Variants ─── */
const fadeInUp = {
  hidden: { opacity: 0, y: 14 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.06, duration: 0.4 },
  }),
};

/* ═══════════════════════════════════════
   DASHBOARD — Main Analysis View
   Order: Intro → Decision Logs → Charts
   ═══════════════════════════════════════ */
export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [orbState, setOrbState] = useState<"idle" | "thinking" | "complete">("thinking");
  const [whatIf, setWhatIf] = useState(false);

  // Sorting, Filtering, and Pagination state
  const [sortBy, setSortBy] = useState<"impact" | "savings" | "confidence" | "name">("impact");
  const [filterPriority, setFilterPriority] = useState<"ALL" | "HIGH" | "MEDIUM" | "LOW">("ALL");
  const [filterCompliance, setFilterCompliance] = useState<"ALL" | "ALL_PASS" | "PARTIAL" | "REVIEW_NEEDED">("ALL");
  const [displayedCount, setDisplayedCount] = useState(10);
  const [showScrollTop, setShowScrollTop] = useState(false);

  useEffect(() => {
    const handleScroll = () => setShowScrollTop(window.scrollY > 300);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    setDisplayedCount(10);
  }, [sortBy, filterPriority, filterCompliance]);

  const scrollToTop = () => window.scrollTo({ top: 0, behavior: "smooth" });

  useEffect(() => {
    async function loadData() {
      try {
        setOrbState("thinking");
        const data = await fetchDashboardData();
        setStats(data.stats);
        setProposals(data.proposals);
        setOrbState("complete");
      } catch (err) {
        console.error("Dashboard Load Error:", err);
      } finally {
        setTimeout(() => setOrbState("idle"), 1200);
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const processedProposals = proposals
    .filter(p => filterPriority === "ALL" || p.priority === filterPriority)
    .filter(p => filterCompliance === "ALL" || p.compliance_status === filterCompliance || (filterCompliance === "ALL_PASS" && p.compliance_status === "PASSED"))
    .sort((a, b) => {
      if (sortBy === "impact") {
        const wA = PRIORITY_WEIGHT[a.priority] || 0;
        const wB = PRIORITY_WEIGHT[b.priority] || 0;
        if (wA !== wB) return wB - wA;
        return b.estimated_savings_pct - a.estimated_savings_pct;
      }
      if (sortBy === "savings") return b.estimated_savings_pct - a.estimated_savings_pct;
      if (sortBy === "confidence") return b.confidence_score - a.confidence_score;
      if (sortBy === "name") return a.canonical_name.localeCompare(b.canonical_name);
      return 0;
    });

  const highCount = processedProposals.filter((p) => p.priority === "HIGH").length;
  const displayedProposals = processedProposals.slice(0, displayedCount);

  const savingsChart = [...proposals]
    .sort((a, b) => a.id - b.id)
    .map((p) => ({
      name: p.canonical_name.length > 12 ? p.canonical_name.slice(0, 11) + "…" : p.canonical_name,
      savings: whatIf ? p.estimated_savings_pct * 0.15 : p.estimated_savings_pct,
      confidence: p.confidence_score,
    }));

  /* ── Loading: spinning sphere ── */
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-6">
          <AgnesOrb state="thinking" size={72} />
          <div className="flex flex-col items-center gap-2">
            <span className="text-xs uppercase tracking-[0.2em] text-gray-500">
              Agnes is analyzing your supply chain
            </span>
            <Waveform active={true} barCount={32} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="px-6 py-6 max-w-5xl mx-auto space-y-6">

      {/* ═══ 1. INTRO: Proactive Strategic Summary ═══ */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <SpotlightCard>
          <TracingBorder active={orbState === "thinking"}>
            <div className="p-5 flex items-start gap-4">
              <AgnesOrb state={orbState} size={44} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2">
                  <h2 className="text-sm font-semibold text-gray-100">Strategic Summary</h2>
                  <StatusIndicator active={orbState === "idle"} />
                </div>
                {stats ? (
                  <p className="text-[13px] leading-relaxed text-gray-400">
                    Agnes identified <span className="text-blue-400 font-medium">{stats.proposal_count} consolidation opportunities</span> across
                    your supply chain. <span className="text-emerald-400 font-medium">{stats.verified_count} proposals</span> are fully verified
                    with an average saving of <span className="text-emerald-400 font-medium">{stats.avg_savings_pct}%</span>.
                    {" "}<span className="text-amber-400 font-medium">{stats.by_priority["HIGH"] || 0} high-priority alerts</span> require immediate attention
                    — {stats.by_compliance["REVIEW_NEEDED"] ? `${stats.by_compliance["REVIEW_NEEDED"]} have compliance conflicts detected.` : "all compliance checks passed."}
                  </p>
                ) : (
                  <p className="text-[13px] text-gray-500">Start the backend to see AI-generated insights.</p>
                )}
                <div className="mt-3 opacity-50">
                  <Waveform active={orbState === "thinking"} barCount={40} />
                </div>
              </div>
            </div>
          </TracingBorder>
        </SpotlightCard>
      </motion.div>

      {/* ── Stat Tiles ── */}
      {stats && (
        <motion.div
          className="grid grid-cols-2 gap-3 lg:grid-cols-4"
          initial="hidden" animate="visible"
          variants={{ visible: { transition: { staggerChildren: 0.06 } } }}
        >
          {[
            { label: "Proposals", val: stats.proposal_count.toString(), icon: <Box className="h-3.5 w-3.5" /> },
            { label: "Avg Savings", val: `${stats.avg_savings_pct}%`, icon: <TrendingUp className="h-3.5 w-3.5" /> },
            { label: "Verified", val: stats.verified_count.toString(), icon: <CheckCircle2 className="h-3.5 w-3.5" /> },
            { label: "High Priority", val: (stats.by_priority["HIGH"] || 0).toString(), icon: <AlertTriangle className="h-3.5 w-3.5" /> },
          ].map((t, i) => (
            <motion.div key={t.label} variants={fadeInUp} custom={i}>
              <SpotlightCard>
                <div className="px-4 py-3 flex flex-col items-center justify-center gap-1.5 text-center">
                  <div className="rounded-lg p-1.5 border border-gray-700 bg-gray-800/50 text-gray-400">{t.icon}</div>
                  <p className="text-2xl font-bold text-gray-100 leading-none">{t.val}</p>
                  <p className="text-[9px] uppercase tracking-[0.12em] text-gray-500">{t.label}</p>
                </div>
              </SpotlightCard>
            </motion.div>
          ))}
        </motion.div>
      )}

      {/* ═══ 2. DECISION LOGS — Prioritized, critical at top ═══ */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-4 gap-3">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold text-gray-100 flex items-center gap-2">
              <Zap className="h-4 w-4 text-blue-400" />
              Decision Log
            </h2>
            <span className="text-[10px] text-gray-500 bg-white/[0.03] border border-[var(--border)] rounded-md px-2 py-0.5">
              {processedProposals.length} entries
            </span>
          </div>
          
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <div className="flex items-center gap-1.5 bg-gray-800/50 border border-gray-700/50 rounded-lg p-1">
              <span className="text-[10px] text-gray-500 pl-2 uppercase tracking-wider">Sort:</span>
              <select 
                value={sortBy} 
                onChange={(e) => setSortBy(e.target.value as any)}
                className="bg-transparent text-gray-300 text-xs outline-none border-none cursor-pointer py-1 pr-2"
              >
                <option value="impact">Highest Impact</option>
                <option value="savings">Top Savings</option>
                <option value="confidence">Highest Confidence</option>
                <option value="name">Alphabetical</option>
              </select>
            </div>
            
            <div className="flex items-center gap-1.5 bg-gray-800/50 border border-gray-700/50 rounded-lg p-1">
              <span className="text-[10px] text-gray-500 pl-2 uppercase tracking-wider">Priority:</span>
              <select 
                value={filterPriority} 
                onChange={(e) => setFilterPriority(e.target.value as any)}
                className="bg-transparent text-gray-300 text-xs outline-none border-none cursor-pointer py-1 pr-2"
              >
                <option value="ALL">All Priorities</option>
                <option value="HIGH">High Only</option>
                <option value="MEDIUM">Medium Only</option>
                <option value="LOW">Low Only</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5 bg-gray-800/50 border border-gray-700/50 rounded-lg p-1">
              <span className="text-[10px] text-gray-500 pl-2 uppercase tracking-wider">Status:</span>
              <select 
                value={filterCompliance} 
                onChange={(e) => setFilterCompliance(e.target.value as any)}
                className="bg-transparent text-gray-300 text-xs outline-none border-none cursor-pointer py-1 pr-2"
              >
                <option value="ALL">All Statuses</option>
                <option value="ALL_PASS">Passed</option>
                <option value="PARTIAL">Partial</option>
                <option value="REVIEW_NEEDED">Review Needed</option>
              </select>
            </div>
          </div>
        </div>
        <div className="space-y-3">
          <AnimatePresence>
            {displayedProposals.map((p, i) => (
              <motion.div key={p.id} variants={fadeInUp} custom={i} initial="hidden" animate="visible" layout>
                <ProposalCard proposal={p} isCritical={p.priority === "HIGH"} isTop={i < 2} />
              </motion.div>
            ))}
          </AnimatePresence>
          {processedProposals.length === 0 && (
            <div className="card-solid p-12 text-center">
              <Activity className="h-8 w-8 mx-auto mb-3 text-gray-600" />
              <p className="text-sm text-gray-500">No proposals match the current filters.</p>
            </div>
          )}
          {displayedCount < processedProposals.length && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="pt-2 pb-4 text-center">
              <button
                onClick={() => setDisplayedCount(prev => prev + 10)}
                className="px-6 py-2.5 rounded-full border border-white/[0.08] bg-white/[0.03] text-xs font-medium text-gray-400 hover:text-white hover:bg-white/[0.08] transition-all"
              >
                Show More ({processedProposals.length - displayedCount} remaining)
              </button>
            </motion.div>
          )}
        </div>
      </motion.div>

      {/* ═══ 3. PARETO FRONTIER — Decision-Theoretic Ranking ═══ */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.5 }}
      >
        <SpotlightCard>
          <ParetoChart />
        </SpotlightCard>
      </motion.div>

      {/* ═══ 4. CHARTS — Savings Distribution ═══ */}
      {savingsChart.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.5 }}
        >
        <SpotlightCard>
          <div className="p-5">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-gray-500">
              {whatIf ? "Impact: Ignoring Proposals" : "Savings Distribution"}
            </span>
            <span className="text-[10px] text-gray-600 bg-white/[0.03] border border-[var(--border)] rounded px-1.5 py-0.5">est. %</span>
          </div>

          {/* What-If Toggle */}
          <button
            onClick={() => setWhatIf(!whatIf)}
            className="flex items-center gap-2 mb-4 text-[10px] uppercase tracking-wider text-gray-500 hover:text-gray-300 transition-colors"
          >
            {whatIf
              ? <ToggleRight className="h-4 w-4 text-red-400" />
              : <ToggleLeft className="h-4 w-4 text-gray-600" />
            }
            <span className={whatIf ? "text-red-400 font-medium" : ""}>What-If: Ignore proposals</span>
          </button>

          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={savingsChart} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={whatIf ? "#ef4444" : "#3b82f6"} stopOpacity={0.25} />
                    <stop offset="95%" stopColor={whatIf ? "#ef4444" : "#3b82f6"} stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="name" tick={{ fill: "#6b7280", fontSize: 9 }} axisLine={{ stroke: "rgba(255,255,255,0.06)" }} tickLine={false} />
                <YAxis tick={{ fill: "#6b7280", fontSize: 9 }} axisLine={{ stroke: "rgba(255,255,255,0.06)" }} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    background: "#0A0A0A",
                    border: "1px solid rgba(255,255,255,0.1)",
                    borderRadius: "8px",
                    fontSize: "11px",
                    color: "#e5e7eb",
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="savings"
                  stroke={whatIf ? "#ef4444" : "#3b82f6"}
                  strokeWidth={2}
                  fill="url(#areaGrad)"
                  dot={{ r: 3, fill: whatIf ? "#ef4444" : "#3b82f6", stroke: "#030303", strokeWidth: 2 }}
                  activeDot={{ r: 5, fill: whatIf ? "#ef4444" : "#3b82f6" }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          {whatIf && (
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-[11px] text-red-400 mt-2 text-center">
              ⚠ Ignoring all proposals loses ~{stats ? (stats.avg_savings_pct * 0.85).toFixed(1) : "—"}% potential savings
            </motion.p>
          )}
          </div>
        </SpotlightCard>
        </motion.div>
      )}

      {/* ── Compliance Breakdown ── */}
      {stats && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6, duration: 0.5 }}
        >
        <SpotlightCard>
          <div className="p-5 space-y-3">
            <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-gray-500">Compliance Breakdown</span>
            {Object.entries(stats.by_compliance).map(([status, count]) => (
              <div key={status} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={`h-2 w-2 rounded-full ${status === "ALL_PASS" ? "bg-emerald-500" : status === "PARTIAL" ? "bg-amber-500" : "bg-gray-500"}`} />
                  <span className="text-xs text-gray-400">{status.replace(/_/g, " ")}</span>
                </div>
                <span className="text-sm font-semibold text-gray-200">{count}</span>
              </div>
            ))}
          </div>
        </SpotlightCard>
        </motion.div>
      )}

      {/* Scroll to Top Button */}
      <AnimatePresence>
        {showScrollTop && (
          <motion.button
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            onClick={scrollToTop}
            className="fixed bottom-8 left-8 p-3 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 hover:bg-blue-500/20 transition-all z-50 shadow-lg backdrop-blur-md"
            aria-label="Scroll to top"
          >
            <ChevronUp className="h-5 w-5" />
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}


/* ═══════════════════════════════════════
   SUB-COMPONENTS
   ═══════════════════════════════════════ */

function StatusIndicator({ active }: { active: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={`h-1.5 w-1.5 rounded-full ${active ? "bg-emerald-500" : "bg-gray-500 status-pulse"}`} />
      <span className="text-[10px] uppercase tracking-wider text-gray-600">{active ? "Live" : "Analyzing"}</span>
    </div>
  );
}

/* ── Proposal Card — Critical cards get TracingBorder ── */
function ProposalCard({ proposal: p, isCritical, isTop }: { proposal: Proposal; isCritical: boolean; isTop: boolean }) {
  const [expanded, setExpanded] = useState(false);

  const cardInner = (
    <>
      <Link href={`/proposals/${p.id}`} className="block group">
        <div className={isTop ? "p-5" : "p-4"}>
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                <PriorityBadge priority={p.priority} />
                <ComplianceBadge status={p.compliance_status} />
                <ConfidenceBadge score={p.confidence_score} />
              </div>
              <h3 className={`font-semibold text-gray-100 truncate ${isTop ? "text-base" : "text-sm"}`}>
                {p.canonical_name}
              </h3>
              <p className="text-xs text-gray-500 mt-1">
                {p.recommended_supplier_name} · {p.members_served} of {p.total_companies_in_group} companies
              </p>
            </div>
            <div className="flex flex-col items-end gap-1.5 shrink-0" title="Estimated cost savings percentage">
              <div className="text-right flex flex-col items-end">
                <span className={`font-bold text-emerald-400 leading-none ${isTop ? "text-xl" : "text-lg"}`}>+{p.estimated_savings_pct}%</span>
                <span className="text-[9px] text-gray-500 uppercase tracking-widest mt-1">Est. Savings</span>
              </div>
              <div title="AI Confidence Score: the probability that this consolidation is compliant and viable" className="flex flex-col items-end mt-1">
                <ConfidenceBar score={p.confidence_score} />
                <span className="text-[9px] text-gray-500 uppercase tracking-widest mt-1">Confidence</span>
              </div>
            </div>
          </div>
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/[0.04]">
            <div className="flex -space-x-1.5">
              {Array.from({ length: Math.min(4, p.companies_consolidated) }).map((_, i) => {
                const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
                const colors = [
                  "bg-blue-500/20 text-blue-400 border-blue-500/30",
                  "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
                  "bg-amber-500/20 text-amber-400 border-amber-500/30",
                  "bg-purple-500/20 text-purple-400 border-purple-500/30",
                  "bg-rose-500/20 text-rose-400 border-rose-500/30",
                  "bg-cyan-500/20 text-cyan-400 border-cyan-500/30"
                ];
                const hash = p.id * 17 + i * 31;
                const letter = letters[hash % letters.length];
                const colorClass = colors[hash % colors.length];
                
                return (
                  <div key={i} className={`h-6 w-6 rounded-full flex items-center justify-center text-[10px] font-bold border ${colorClass} shadow-sm backdrop-blur-sm z-${10 - i}`}>
                    {letter}
                  </div>
                );
              })}
              {p.companies_consolidated > 4 && (
                <div className="h-6 w-6 rounded-full bg-white/[0.04] border border-white/[0.08] flex items-center justify-center text-[9px] text-gray-500 z-0 backdrop-blur-sm">
                  +{p.companies_consolidated - 4}
                </div>
              )}
            </div>
            <span className="text-[10px] text-gray-600 group-hover:text-blue-400 transition-colors flex items-center gap-1">
              View evidence <ExternalLink className="h-3 w-3" />
            </span>
          </div>
        </div>
      </Link>

      {/* Logic Trace (expandable) */}
      <button
        onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
        className="w-full flex items-center justify-center gap-1.5 py-2 border-t border-white/[0.04] text-[10px] uppercase tracking-wider text-gray-600 hover:text-blue-400 hover:bg-white/[0.02] transition-all"
      >
        <Eye className="h-3 w-3" /> Logic Trace
        {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25 }} className="overflow-hidden">
            <div className="px-4 pb-4 space-y-2 text-[11px] text-gray-500">
              <div className="flex gap-2"><span className="text-blue-400 shrink-0">→</span><span>Semantic match: &quot;{p.canonical_name}&quot; identified across {p.total_companies_in_group} companies via SKU normalization</span></div>
              <div className="flex gap-2"><span className="text-emerald-400 shrink-0">→</span><span>Supplier &quot;{p.recommended_supplier_name}&quot; covers {p.members_served} companies ({((p.members_served / p.total_companies_in_group) * 100).toFixed(0)}% reach)</span></div>
              <div className="flex gap-2"><span className={`shrink-0 ${p.compliance_status === "ALL_PASS" ? "text-emerald-400" : "text-amber-400"}`}>→</span><span>Compliance: {p.compliance_status.replace(/_/g, " ")} — Confidence {p.confidence_score}%</span></div>
              <div className="flex gap-2"><span className="text-blue-400 shrink-0">→</span><span>Estimated volume discount: +{p.estimated_savings_pct}% savings from consolidation leverage</span></div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );

  if (isCritical) {
    return (
      <SpotlightCard>
        {cardInner}
      </SpotlightCard>
    );
  }

  return (
    <SpotlightCard>
      {cardInner}
    </SpotlightCard>
  );
}

function ConfidenceBadge({ score }: { score: number }) {
  const c = score > 75 ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" :
            score > 50 ? "text-amber-400 bg-amber-500/10 border-amber-500/20" :
            "text-gray-400 bg-gray-500/10 border-gray-500/20";
  return <span className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-medium border ${c}`}>{score}%</span>;
}

function ConfidenceBar({ score }: { score: number }) {
  const c = score > 75 ? "bg-emerald-500" : score > 50 ? "bg-amber-500" : "bg-gray-500";
  return (
    <div className="h-1 w-14 rounded-full bg-white/[0.06] overflow-hidden">
      <motion.div className={`h-full rounded-full ${c}`} initial={{ width: 0 }} animate={{ width: `${score}%` }} transition={{ duration: 0.8, delay: 0.2 }} />
    </div>
  );
}

function ComplianceBadge({ status }: { status: string }) {
  if (status === "PASSED" || status === "ALL_PASS")
    return <span className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><FileCheck className="h-2.5 w-2.5" /> Pass</span>;
  if (status === "PARTIAL")
    return <span className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20"><AlertTriangle className="h-2.5 w-2.5" /> Partial</span>;
  return <span className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium bg-gray-500/10 text-gray-400 border border-gray-500/20"><ShieldAlert className="h-2.5 w-2.5" /> Review</span>;
}

function PriorityBadge({ priority }: { priority: string }) {
  const s: Record<string, string> = {
    HIGH: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    MEDIUM: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    LOW: "bg-gray-500/10 text-gray-500 border-gray-600/20",
  };
  return <span className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-medium border ${s[priority] ?? s.LOW}`}>{priority}</span>;
}
