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
    <div
      className="rounded-lg p-3 text-xs space-y-1 max-w-56 pointer-events-none border border-white/[0.1]"
      style={{
        background: "rgba(8, 10, 18, 0.95)",
        backdropFilter: "blur(12px)",
        color: "#e5e7eb",
      }}
    >
      <p className="font-semibold text-[var(--foreground)] truncate">
        {d.recommended_supplier_name || `Proposal #${d.id}`}
      </p>
      <p className="text-[var(--foreground-muted)]">
        Impact:{" "}
        <span className="text-emerald-400 font-medium">
          {d.impact_score?.toFixed(3)}
        </span>{" "}
        <span className="text-[var(--foreground-dim)]">
          (conf: {(d.impact_confidence * 100).toFixed(0)}%)
        </span>
      </p>
      <p className="text-[var(--foreground-muted)]">
        Compliance P:{" "}
        <span className="font-medium text-[var(--foreground)]">
          {d.compliance_probability?.toFixed(3)}
        </span>
      </p>
      <p className="text-[var(--foreground-muted)]">
        Savings:{" "}
        <span className="text-emerald-400 font-medium">
          {d.savings?.toFixed(1)}%
        </span>
        {" · "}Risk:{" "}
        <span className="text-red-400 font-medium">
          {d.risk_score?.toFixed(3)}
        </span>
      </p>
      <p className="text-[var(--foreground-muted)]">
        Utility:{" "}
        <span className="font-mono font-semibold text-[var(--foreground)]">
          {d.utility_score?.toFixed(3)}
        </span>
      </p>
      {d.flagged_low_confidence_high_impact && (
        <p className="text-red-400 font-semibold">
          ⚠ High impact, low confidence — review required
        </p>
      )}
      {d.is_pareto_optimal ? (
        <p className="text-amber-400 font-semibold">
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

interface SliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}

function SliderInput({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: SliderProps) {
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-center text-xs">
        <span className="text-[var(--foreground-muted)] font-medium">
          {label}
        </span>
        <span className="font-mono font-semibold text-[var(--foreground)] tabular-nums">
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

export function ParetoChart() {
  const router = useRouter();
  const [alpha, setAlpha] = useState(1.0);
  const [beta, setBeta] = useState(1.5);
  const [gamma, setGamma] = useState(0.8);
  const [data, setData] = useState<RerankPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchRerank = useCallback(
    async (a: number, b: number, g: number) => {
      setLoading(true);
      try {
        const points = await rerankProposals({ alpha: a, beta: b, gamma: g });
        setData(points);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    fetchRerank(alpha, beta, gamma);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const schedule = (a: number, b: number, g: number) => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => fetchRerank(a, b, g), 150);
  };

  const frontier = data.filter((d) => d.is_pareto_optimal);
  const dominated = data.filter((d) => !d.is_pareto_optimal);
  const flagged = data.filter((d) => d.flagged_low_confidence_high_impact);

  const handleClick = (point: { id?: number }) => {
    if (point?.id != null) router.push(`/proposals/${point.id}`);
  };

  function pointOpacity(conf: number): number {
    return Math.max(0.2, Math.min(0.95, conf));
  }

  return (
    <div className="p-5 space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-[var(--foreground)]">
            Pareto Frontier — Decision-Theoretic Ranking
          </h2>
          <p className="text-[11px] text-[var(--foreground-muted)] mt-0.5">
            X = evidence-weighted impact · opacity = confidence · red ring =
            high impact, low confidence
          </p>
        </div>
        {loading && (
          <span className="text-[10px] text-amber-400 font-medium animate-pulse uppercase tracking-wider">
            updating…
          </span>
        )}
      </div>

      {/* Sliders */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-white/[0.03] border border-white/[0.06] rounded-lg p-4">
        <SliderInput
          label="α  Savings weight"
          value={alpha}
          min={0}
          max={3}
          step={0.1}
          onChange={(v) => {
            setAlpha(v);
            schedule(v, beta, gamma);
          }}
        />
        <SliderInput
          label="β  Risk penalty"
          value={beta}
          min={0}
          max={3}
          step={0.1}
          onChange={(v) => {
            setBeta(v);
            schedule(alpha, v, gamma);
          }}
        />
        <SliderInput
          label="γ  Uncertainty penalty"
          value={gamma}
          min={0}
          max={3}
          step={0.1}
          onChange={(v) => {
            setGamma(v);
            schedule(alpha, beta, v);
          }}
        />
      </div>

      {/* Scatter chart */}
      <div className="h-[320px]">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 10, right: 24, bottom: 28, left: 10 }}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(255,255,255,0.05)"
            />
            <XAxis
              dataKey="impact_score"
              name="Impact"
              type="number"
              domain={[0, 0.9]}
              label={{
                value: "Evidence-Weighted Impact",
                position: "insideBottom",
                offset: -16,
                fontSize: 11,
                fill: "#6b7280",
              }}
              tick={{ fontSize: 10, fill: "#6b7280" }}
              axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
              tickLine={false}
            />
            <YAxis
              dataKey="compliance_probability"
              name="Compliance P"
              type="number"
              domain={[0, 1.05]}
              label={{
                value: "Compliance Probability",
                angle: -90,
                position: "insideLeft",
                offset: 14,
                fontSize: 11,
                fill: "#6b7280",
              }}
              tick={{ fontSize: 10, fill: "#6b7280" }}
              axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
              tickLine={false}
            />
            <Tooltip
              cursor={{
                strokeDasharray: "3 3",
                stroke: "rgba(255,255,255,0.15)",
              }}
              content={<CustomTooltip />}
            />
            <Scatter
              name="Dominated"
              data={dominated}
              onClick={handleClick}
              style={{ cursor: "pointer" }}
            >
              {dominated.map((entry) => (
                <Cell
                  key={`d-${entry.id}`}
                  fill="#475569"
                  opacity={pointOpacity(entry.impact_confidence)}
                  stroke={
                    entry.flagged_low_confidence_high_impact
                      ? "#ef4444"
                      : "none"
                  }
                  strokeWidth={entry.flagged_low_confidence_high_impact ? 2 : 0}
                />
              ))}
            </Scatter>
            <Scatter
              name="Frontier"
              data={frontier}
              onClick={handleClick}
              style={{ cursor: "pointer" }}
            >
              {frontier.map((entry) => (
                <Cell
                  key={`f-${entry.id}`}
                  fill="#f59e0b"
                  opacity={pointOpacity(entry.impact_confidence)}
                  stroke={
                    entry.flagged_low_confidence_high_impact
                      ? "#ef4444"
                      : "#d97706"
                  }
                  strokeWidth={entry.flagged_low_confidence_high_impact ? 3 : 2}
                />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      {data.length > 0 && (
        <div className="flex items-center gap-6 text-[11px] text-[var(--foreground-muted)] flex-wrap">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-400 border-2 border-amber-600" />
            {frontier.length} Pareto-optimal
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-slate-500 opacity-60" />
            {dominated.length} dominated
          </span>
          {flagged.length > 0 && (
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-full border-2 border-red-500" />
              {flagged.length} high-impact / low-confidence
            </span>
          )}
          <span className="text-[var(--foreground-dim)]">
            · opacity = confidence · click to view
          </span>
        </div>
      )}

      {data.length === 0 && !loading && (
        <p className="text-center text-xs text-[var(--foreground-dim)] py-4">
          Run Phase 1-3 pipeline first to populate proposals.
        </p>
      )}
    </div>
  );
}
