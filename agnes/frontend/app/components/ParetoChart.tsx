"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceArea,
} from "recharts";
import { rerankProposals } from "@/lib/api";
import type { RerankPoint } from "@/lib/types";

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: RerankPoint }>;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;

  return (
    <div className="rounded-lg p-3 shadow-xl text-xs space-y-1 max-w-60 pointer-events-none" style={{ background: "#0e1216", border: "1px solid rgba(255,255,255,0.08)" }}>
      <p className="font-semibold text-gray-100 truncate">
        {d.recommended_supplier_name || `Proposal #${d.id}`}
      </p>
      <p className="text-gray-500 truncate">{d.canonical_name}</p>
      <p className="text-gray-400">
        Impact:{" "}
        <span className="text-emerald-600 font-medium">
          {d.impact_score?.toFixed(3)}
        </span>{" "}
        <span className="text-slate-400">
          (conf: {(d.impact_confidence * 100).toFixed(0)}%)
        </span>
      </p>
      <p className="text-gray-400">
        Compliance P:{" "}
        <span className="font-medium text-slate-800">
          {d.compliance_probability?.toFixed(3)}
        </span>
      </p>
      <p className="text-gray-400">
        Savings:{" "}
        <span className="text-emerald-600 font-medium">
          {d.savings?.toFixed(1)}%
        </span>
        {" · "}Comp. risk:{" "}
        <span className="text-red-500 font-medium">
          {(1 - d.compliance_probability).toFixed(3)}
        </span>
      </p>
      <p className="text-gray-400">
        Subst. risk:{" "}
        <span className="text-orange-500 font-medium">
          {d.substitution_risk?.toFixed(3)}
        </span>
        {" · "}Rel. var:{" "}
        <span className="text-purple-500 font-medium">
          {d.reliability_variance?.toFixed(3)}
        </span>
      </p>
      <p className="text-gray-400">
        Companies:{" "}
        <span className="font-medium text-slate-800">
          {d.companies_consolidated}
        </span>
        {" · "}Utility:{" "}
        <span className="font-mono font-semibold text-slate-800">
          {d.utility_score?.toFixed(3)}
        </span>
      </p>
      {d.flagged_low_confidence_high_impact && (
        <p className="text-red-600 font-semibold">
          ⚠ High impact, low confidence — review required
        </p>
      )}
      {d.is_pareto_optimal ? (
        <p className="text-amber-600 font-semibold">
          ★ Pareto Optimal (rank #{d.rank})
        </p>
      ) : (
        <p className="text-[var(--foreground-dim)]">
          Dominated by {d.dominated_by?.length ?? 0} proposal(s)
        </p>
      )}
      <p className="text-[var(--foreground-dim)] mt-1">Click to view details</p>
    </div>
  );
}

function SliderInput({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-center text-xs">
        <span className="text-gray-400 font-medium">{label}</span>
        <span className="font-mono font-semibold text-gray-200 tabular-nums">
          {value.toFixed(1)}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-1.5 rounded-full accent-amber-500 cursor-pointer"
      />
    </div>
  );
}

function dotRadius(count: number): number {
  return Math.max(5, Math.min(14, 4 + (count ?? 2) * 0.5));
}
function dotOpacity(conf: number): number {
  return Math.max(0.2, Math.min(0.95, conf));
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function DominatedDot(props: any) {
  const { cx, cy, payload } = props as { cx: number; cy: number; payload: RerankPoint };
  if (cx == null || cy == null) return null;
  const r = dotRadius(payload.companies_consolidated);
  const op = dotOpacity(payload.impact_confidence);
  return (
    <circle
      cx={cx}
      cy={cy}
      r={r}
      fill="#94a3b8"
      fillOpacity={op}
      stroke={payload.flagged_low_confidence_high_impact ? "#ef4444" : "none"}
      strokeWidth={payload.flagged_low_confidence_high_impact ? 2 : 0}
    />
  );
}

function makeFrontierDot(kneeId: number | null) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return function FrontierDot(props: any) {
    const { cx, cy, payload } = props as { cx: number; cy: number; payload: RerankPoint };
    if (cx == null || cy == null) return null;
    const r = dotRadius(payload.companies_consolidated);
    const op = dotOpacity(payload.impact_confidence);
    const isKnee = payload.id === kneeId;
    const isFlagged = payload.flagged_low_confidence_high_impact;
    const label = payload.recommended_supplier_name?.split(" ")[0] ?? "";

    return (
      <g>
        {isKnee && (
          <circle
            cx={cx}
            cy={cy}
            r={r + 6}
            fill="none"
            stroke="#22c55e"
            strokeWidth={2}
            strokeDasharray="4 3"
            opacity={0.9}
          />
        )}
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="#f59e0b"
          fillOpacity={op}
          stroke={isFlagged ? "#ef4444" : "#d97706"}
          strokeWidth={isFlagged ? 3 : 1.5}
        />
        {label && (
          <text x={cx + r + 3} y={cy + 4} fontSize={9} fill="#78716c" fontWeight={600} pointerEvents="none">
            {label}
          </text>
        )}
      </g>
    );
  };
}

export function ParetoChart() {
  const router = useRouter();
  const [alpha, setAlpha] = useState(1.0);
  const [beta, setBeta] = useState(1.5);
  const [gamma, setGamma] = useState(1.0);
  const [delta, setDelta] = useState(0.5);
  const [epsilon, setEpsilon] = useState(0.8);
  const [data, setData] = useState<RerankPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchRerank = useCallback(async (a: number, b: number, g: number, d_val: number, e_val: number) => {
    setLoading(true);
    try {
      const result = await rerankProposals({ alpha: a, beta: b, gamma: g, delta: d_val, epsilon: e_val });
      setData(result);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRerank(alpha, beta, gamma, delta, epsilon);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const schedule = (a: number, b: number, g: number, d_val: number, e_val: number) => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => fetchRerank(a, b, g, d_val, e_val), 150);
  };

  const frontier = data.filter((d) => d.is_pareto_optimal);
  const dominated = data.filter((d) => !d.is_pareto_optimal);
  const flagged = data.filter((d) => d.flagged_low_confidence_high_impact);

  const kneePoint =
    frontier.length > 0
      ? frontier.reduce((best, d) => (d.utility_score > best.utility_score ? d : best), frontier[0])
      : null;

  const sortedFrontier = [...frontier].sort((a, b) => a.impact_score - b.impact_score);
  const FrontierDot = makeFrontierDot(kneePoint?.id ?? null);

  const handleClick = (point: { id?: number }) => {
    if (point?.id != null) router.push(`/proposals/${point.id}`);
  };

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-sm font-semibold text-gray-100 flex items-center gap-2">
            Pareto Frontier — Decision-Theoretic Ranking
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            X: evidence-weighted impact · Y: β/γ/δ/ε composite risk · dot size = companies consolidated · opacity = confidence · green dashes = knee point
          </p>
        </div>
        {loading && (
          <span className="text-xs text-amber-500 font-medium animate-pulse">updating…</span>
        )}
      </div>

      {/* Sliders */}
      <div className="grid grid-cols-5 gap-4 bg-white/[0.03] border border-white/[0.06] rounded-lg p-4">
        <SliderInput label="α Savings" value={alpha} min={0} max={3} step={0.1}
          onChange={(v) => { setAlpha(v); schedule(v, beta, gamma, delta, epsilon); }} />
        <SliderInput label="β Compl. Risk" value={beta} min={0} max={3} step={0.1}
          onChange={(v) => { setBeta(v); schedule(alpha, v, gamma, delta, epsilon); }} />
        <SliderInput label="γ Subst. Risk" value={gamma} min={0} max={3} step={0.1}
          onChange={(v) => { setGamma(v); schedule(alpha, beta, v, delta, epsilon); }} />
        <SliderInput label="δ Supplier Var" value={delta} min={0} max={3} step={0.1}
          onChange={(v) => { setDelta(v); schedule(alpha, beta, gamma, v, epsilon); }} />
        <SliderInput label="ε Uncertainty" value={epsilon} min={0} max={3} step={0.1}
          onChange={(v) => { setEpsilon(v); schedule(alpha, beta, gamma, delta, v); }} />
      </div>

      {/* Chart */}
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 10, right: 60, bottom: 28, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />

            <ReferenceArea x1={0} x2={0.45} y1={0.5} y2={1} fill="#ef4444" fillOpacity={0.05} />
            <ReferenceArea x1={0.45} x2={0.9} y1={0.5} y2={1} fill="#f59e0b" fillOpacity={0.06} />
            <ReferenceArea x1={0} x2={0.45} y1={0} y2={0.5} fill="#94a3b8" fillOpacity={0.04} />
            <ReferenceArea x1={0.45} x2={0.9} y1={0} y2={0.5} fill="#22c55e" fillOpacity={0.05} />

            <XAxis
              dataKey="impact_score"
              name="Impact"
              type="number"
              domain={[0, 0.9]}
              label={{ value: "Evidence-Weighted Impact →", position: "insideBottom", offset: -16, fontSize: 11, fill: "#94a3b8" }}
              tick={{ fontSize: 10, fill: "#94a3b8" }}
            />
            <YAxis
              dataKey="risk_score"
              name="Risk"
              type="number"
              domain={[0, 1]}
              label={{ value: "Multi-Objective Risk ↑", angle: -90, position: "insideLeft", offset: 14, fontSize: 11, fill: "#94a3b8" }}
              tick={{ fontSize: 10, fill: "#94a3b8" }}
            />
            <Tooltip
              cursor={{ strokeDasharray: "3 3", stroke: "rgba(255,255,255,0.15)" }}
              content={<CustomTooltip />}
            />

            <Scatter name="Dominated" data={dominated} onClick={handleClick} style={{ cursor: "pointer" }} shape={<DominatedDot />}>
              {dominated.map((entry) => <Cell key={`d-${entry.id}`} />)}
            </Scatter>

            <Scatter
              name="Frontier"
              data={sortedFrontier}
              onClick={handleClick}
              style={{ cursor: "pointer" }}
              shape={<FrontierDot />}
              line={{ stroke: "#f59e0b", strokeWidth: 1.5, strokeDasharray: "4 3", strokeOpacity: 0.55 }}
              lineJointType="stepAfter"
            >
              {sortedFrontier.map((entry) => <Cell key={`f-${entry.id}`} />)}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      {/* Quadrant key */}
      <div className="grid grid-cols-4 gap-2 text-xs text-center">
        <div className="rounded bg-white/[0.03] border border-white/[0.06] px-2 py-1 text-gray-500">
          <span className="font-medium">↙ Marginal</span><br />
          <span className="text-gray-600">low impact · low risk</span>
        </div>
        <div className="rounded bg-emerald-500/10 border border-emerald-500/20 px-2 py-1 text-emerald-400">
          <span className="font-medium">↘ Ideal</span><br />
          <span className="text-emerald-500">high impact · low risk</span>
        </div>
        <div className="rounded bg-amber-500/10 border border-amber-500/20 px-2 py-1 text-amber-400">
          <span className="font-medium">↗ Review</span><br />
          <span className="text-amber-500">high impact · high risk</span>
        </div>
        <div className="rounded bg-red-500/10 border border-red-500/20 px-2 py-1 text-red-400">
          <span className="font-medium">↖ Eliminate</span><br />
          <span className="text-red-500">low impact · high risk</span>
        </div>
      </div>

      {/* Legend */}
      {data.length > 0 && (
        <div className="flex items-center gap-6 text-xs text-gray-500 flex-wrap">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-400 border-2 border-amber-600" />
            {frontier.length} Pareto-optimal
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-gray-500 opacity-60" />
            {dominated.length} dominated
          </span>
          {flagged.length > 0 && (
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 rounded-full border-2 border-red-500" style={{ background: "transparent" }} />
              {flagged.length} high-impact / low-confidence
            </span>
          )}
          {kneePoint && (
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 rounded-full border-2 border-green-500" style={{ borderStyle: "dashed", background: "transparent" }} />
              knee: {kneePoint.recommended_supplier_name?.split(" ")[0]}
            </span>
          )}
          <span className="text-gray-600">
            · dot size = companies · opacity = confidence · click to view
          </span>
        </div>
      )}

      {data.length === 0 && !loading && (
        <p className="text-center text-xs text-gray-600 py-4">
          Run Phase 1–3 pipeline first to populate proposals.
        </p>
      )}
    </div>
  );
}
