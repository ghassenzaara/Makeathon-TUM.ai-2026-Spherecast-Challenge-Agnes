"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight, CheckCircle2, AlertTriangle, TrendingUp,
  FileCheck, ShieldAlert, Loader2, Box, Zap, ChevronDown, X,
} from "lucide-react";
import { SavingsChart } from "./components/SavingsChart";
import { GaugeChart } from "./components/GaugeChart";
import { GalaxyCanvas } from "@/components/GalaxyCanvas";
import { HeroChatBar } from "@/components/HeroChatBar";
import { AgnesLogoMark, PrismaticOrb } from "@/app/components/AgnesLogo";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";

const ORB = "168,212,239";

/* ── Types ─────────────────────────────────────────────────────────────────── */

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

interface ChatMsg { role: "user" | "assistant"; content: string }

/* ── Shared chat sub-components ─────────────────────────────────────────────── */

function TypingDots() {
  return (
    <span className="flex items-center gap-1 py-0.5">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          style={{
            width: 7, height: 7, borderRadius: "50%",
            background: `rgba(${ORB},0.80)`,
            display: "inline-block",
            animation: `dotBounce 1.2s ease-in-out ${i * 0.2}s infinite`,
          }}
        />
      ))}
    </span>
  );
}

function ChatBubble({ msg, index, showOrb }: { msg: ChatMsg; index: number; showOrb: boolean }) {
  const isUser = msg.role === "user";
  const parts = msg.content.split(/(\[[PE]\d+\])/g);

  return (
    <motion.div
      initial={isUser ? { opacity: 0, x: 48, y: 16 } : { opacity: 0, x: -16, y: 12 }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      transition={{ type: "spring", stiffness: 380, damping: 30, delay: index === 0 ? 0.1 : 0 }}
      className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}
    >
      {/* Agnes orb — only on the last AI message */}
      {!isUser && showOrb && (
        <div className="shrink-0 mt-0.5"><PrismaticOrb size={28} /></div>
      )}
      {!isUser && !showOrb && <div className="shrink-0 w-7" />}

      {/* Bubble */}
      <div
        className="max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-relaxed"
        style={
          isUser
            ? { background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.10)", color: "rgba(255,255,255,0.90)", borderTopRightRadius: 4 }
            : { background: `rgba(${ORB},0.06)`, border: `1px solid rgba(${ORB},0.14)`, color: "rgba(226,232,240,0.95)", borderTopLeftRadius: 4, boxShadow: `0 0 24px rgba(${ORB},0.04)` }
        }
      >
        {parts.map((part, i) => {
          if (/^\[[PE]\d+\]$/.test(part)) {
            const isP = part.startsWith("[P");
            return (
              <span key={i} style={{
                display: "inline-flex", alignItems: "center", fontSize: "0.68rem", fontWeight: 600,
                padding: "1px 6px", borderRadius: 4, margin: "0 2px",
                background: isP ? `rgba(${ORB},0.15)` : "rgba(139,92,246,0.15)",
                color: isP ? `rgba(${ORB},1)` : "rgba(192,132,252,1)",
                border: isP ? `1px solid rgba(${ORB},0.35)` : "1px solid rgba(139,92,246,0.35)",
              }}>{part}</span>
            );
          }
          return part.split("\n").map((line, j, arr) => (
            <span key={`${i}-${j}`}>{line}{j < arr.length - 1 && <br />}</span>
          ));
        })}
      </div>
    </motion.div>
  );
}

/* ── Page ───────────────────────────────────────────────────────────────────── */

export default function Dashboard() {
  /* Dashboard data */
  const [stats, setStats]         = useState<Stats | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading]     = useState(true);

  /* Chat overlay */
  const [chatMode, setChatMode]       = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [isThinking, setIsThinking]   = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const [statsRes, propsRes] = await Promise.all([
          fetch("http://127.0.0.1:8000/api/stats"),
          fetch("http://127.0.0.1:8000/api/proposals"),
        ]);
        if (statsRes.ok) setStats(await statsRes.json());
        if (propsRes.ok) setProposals(await propsRes.json());
      } catch { /* backend offline */ }
      finally { setLoading(false); }
    }
    loadData();
  }, []);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, isThinking]);

  /* Hits the API and appends AI response */
  const fetchChat = useCallback(async (history: ChatMsg[]) => {
    setIsThinking(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setChatMessages(prev => [...prev, { role: "assistant", content: data.answer || "No response." }]);
    } catch {
      setChatMessages(prev => [...prev, {
        role: "assistant",
        content: "Could not reach the agent — is the backend running on port 8000?",
      }]);
    } finally {
      setIsThinking(false);
    }
  }, []);

  /* Called from hero chip/enter — opens overlay */
  function handleHeroSubmit(q: string) {
    const first: ChatMsg = { role: "user", content: q };
    setChatMessages([first]);
    setChatMode(true);
    fetchChat([first]);
  }

  /* Called from input inside overlay — continues conversation */
  function handleChatContinue(q: string) {
    const msg: ChatMsg = { role: "user", content: q };
    setChatMessages(prev => {
      const next = [...prev, msg];
      fetchChat(next);
      return next;
    });
  }

  const highPriority = proposals.filter((p) => p.priority === "HIGH");

  return (
    <>
      {/* Galaxy background (fixed) */}
      <GalaxyCanvas />

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section className="relative flex min-h-[calc(100vh-73px)] flex-col items-center justify-center gap-8 px-6">
        <div className="text-center space-y-3">
          <h1 className="text-4xl sm:text-5xl font-bold text-white leading-tight">
            What can I help you source?
          </h1>
        </div>

        {/* Only rendered when NOT in chat mode — layoutId flies to overlay */}
        {!chatMode && (
          <HeroChatBar layoutId="agnes-chatbar" onSubmit={handleHeroSubmit} />
        )}

        <div className="absolute bottom-8 flex flex-col items-center gap-1 text-white/20 select-none pointer-events-none">
          <ChevronDown className="h-5 w-5 animate-bounce" />
        </div>
      </section>

      {/* ── Dashboard ─────────────────────────────────────────────────────── */}
      <div className="relative bg-[var(--background)]">
        <div className="absolute -top-24 inset-x-0 h-24 pointer-events-none"
          style={{ background: "linear-gradient(to bottom, transparent, var(--background))" }} />

        <div className="mx-auto max-w-7xl px-6 py-10 space-y-6 animate-fade-in">

          <div>
            <h2 className="text-xl font-bold tracking-tight text-[var(--foreground)]">Command Center</h2>
            <p className="text-sm text-[var(--foreground-muted)] mt-1">
              AI-generated sourcing consolidation proposals — Agnes Phase 4
            </p>
          </div>

          {/* Loading skeletons */}
          {loading && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-11 rounded-xl" />)}
              </div>
              <Skeleton className="h-56 rounded-xl" />
            </div>
          )}

          {/* Stat tiles */}
          {stats && (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatTile label="Total Proposals" value={stats.proposal_count.toString()} accent="cyan"    icon={<Box className="h-6 w-6" />} />
              <StatTile label="Avg Est. Savings" value={`${stats.avg_savings_pct}%`}    accent="emerald" icon={<TrendingUp className="h-6 w-6" />} />
              <StatTile label="Agent Verified"   value={stats.verified_count.toString()} accent="violet" icon={<CheckCircle2 className="h-6 w-6" />} />
              <StatTile label="High Priority"    value={(stats.by_priority["HIGH"] || 0).toString()} accent="amber" icon={<AlertTriangle className="h-6 w-6" />} />
            </div>
          )}

          {/* Charts */}
          {stats && proposals.length > 0 && (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
              <div className="lg:col-span-3"><SavingsChart proposals={proposals} /></div>
              <div className="lg:col-span-2"><GaugeChart value={stats.avg_confidence} label="AI Confidence" /></div>
            </div>
          )}

          {/* Command alerts */}
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
                  <Link key={p.id} href={`/proposals/${p.id}`}
                    className="flex items-center justify-between rounded-lg border border-amber-500/20 bg-[var(--surface)] px-4 py-3 hover:border-amber-500/50 transition-colors group"
                  >
                    <div>
                      <div className="text-sm font-semibold text-[var(--foreground)] truncate max-w-[160px]">{p.canonical_name}</div>
                      <div className="text-xs text-amber-400 mt-0.5">{p.recommended_supplier_name} · +{p.estimated_savings_pct}%</div>
                    </div>
                    <ArrowRight className="h-4 w-4 text-[var(--foreground-muted)] group-hover:text-amber-400 transition-colors shrink-0" />
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Proposals table — shadcn Table */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
            <div className="border-b border-[var(--border)] px-6 py-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-[var(--foreground)] flex items-center gap-2">
                <Zap className="h-4 w-4 text-cyan-500" /> Sourcing Proposals
              </h2>
              <span className="text-xs text-[var(--foreground-muted)]">{proposals.length} total</span>
            </div>

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ingredient</TableHead>
                  <TableHead>Supplier</TableHead>
                  <TableHead>Savings</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead>Compliance</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead className="text-right">Detail</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {proposals.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell>
                      <div className="font-medium text-[var(--foreground)]">{p.canonical_name}</div>
                      <div className="text-xs text-[var(--foreground-muted)] mt-0.5">
                        {p.members_served} of {p.total_companies_in_group} companies
                      </div>
                    </TableCell>
                    <TableCell className="text-[var(--foreground)]">{p.recommended_supplier_name}</TableCell>
                    <TableCell>
                      <span className="font-semibold text-emerald-400">+{p.estimated_savings_pct}%</span>
                    </TableCell>
                    <TableCell><ConfidenceBar score={p.confidence_score} /></TableCell>
                    <TableCell>
                      {(p.compliance_status === "PASSED" || p.compliance_status === "ALL_PASS")
                        ? <Badge variant="emerald"><FileCheck className="h-3 w-3" /> Passed</Badge>
                        : <Badge variant="fuchsia"><ShieldAlert className="h-3 w-3" /> Review</Badge>}
                    </TableCell>
                    <TableCell>
                      <Badge variant={p.priority === "HIGH" ? "amber" : p.priority === "MEDIUM" ? "cyan" : "default"}>
                        {p.priority}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Link href={`/proposals/${p.id}`}
                        className="inline-flex items-center justify-center h-8 w-8 rounded-md text-[var(--foreground-muted)] hover:text-cyan-400 hover:bg-cyan-500/10 transition-colors"
                      >
                        <ArrowRight className="h-4 w-4" />
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
                {proposals.length === 0 && !loading && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-16 text-[var(--foreground-muted)] text-sm">
                      No proposals found — run Phase 1–3 first.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>

        </div>
      </div>

      {/* ── Chat overlay — AnimatePresence + layoutId transition ─────────── */}
      <AnimatePresence>
        {chatMode && (
          <motion.div
            key="chat-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="fixed inset-0 z-[60] flex flex-col"
            style={{ background: "rgba(5,8,15,0.94)", backdropFilter: "blur(22px)" }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-6 py-4 shrink-0"
              style={{ borderBottom: `1px solid rgba(${ORB},0.10)` }}
            >
              <AgnesLogoMark />
              <button
                onClick={() => setChatMode(false)}
                className="h-8 w-8 flex items-center justify-center rounded-full transition-colors"
                style={{ color: "rgba(255,255,255,0.40)", border: "1px solid rgba(255,255,255,0.08)" }}
                onMouseEnter={e => (e.currentTarget.style.color = "rgba(255,255,255,0.80)")}
                onMouseLeave={e => (e.currentTarget.style.color = "rgba(255,255,255,0.40)")}
                title="Back to dashboard"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Messages */}
            <ScrollArea className="flex-1 px-6 py-6">
              <div className="max-w-3xl mx-auto space-y-5">
                {chatMessages.map((msg, i) => {
                  const isLastAssistant =
                    msg.role === "assistant" &&
                    !chatMessages.slice(i + 1).some((m) => m.role === "assistant");
                  return <ChatBubble key={i} msg={msg} index={i} showOrb={isLastAssistant} />;
                })}

                {/* Prismatic orb thinking indicator */}
                <AnimatePresence>
                  {isThinking && (
                    <motion.div
                      key="thinking"
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 6 }}
                      transition={{ duration: 0.2 }}
                      className="flex gap-3"
                    >
                      {/* Orb with pulsing glow ring */}
                      <div className="relative shrink-0 mt-0.5">
                        <PrismaticOrb size={28} />
                        <motion.div
                          className="absolute -inset-3 rounded-full pointer-events-none"
                          animate={{
                            boxShadow: [
                              `0 0 0px 0px rgba(${ORB},0)`,
                              `0 0 18px 6px rgba(${ORB},0.28)`,
                              `0 0 0px 0px rgba(${ORB},0)`,
                            ],
                          }}
                          transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
                        />
                      </div>

                      <div
                        className="rounded-2xl px-4 py-3"
                        style={{
                          background: `rgba(${ORB},0.06)`,
                          border: `1px solid rgba(${ORB},0.14)`,
                          borderTopLeftRadius: 4,
                        }}
                      >
                        <TypingDots />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                <div ref={chatBottomRef} />
              </div>
            </ScrollArea>

            {/* Input bar at bottom — same layoutId → Framer Motion animates from hero */}
            <div
              className="px-6 pb-6 pt-4 shrink-0"
              style={{ borderTop: `1px solid rgba(${ORB},0.08)` }}
            >
              <div className="max-w-3xl mx-auto">
                <HeroChatBar
                  layoutId="agnes-chatbar"
                  onSubmit={handleChatContinue}
                  hideChips
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

/* ── Sub-components ──────────────────────────────────────────────────────────── */

function StatTile({ label, value, accent, icon }: {
  label: string; value: string;
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
      <div className={`flex items-center justify-center ${panel[accent]}`} style={{ width: "42%" }}>{icon}</div>
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
