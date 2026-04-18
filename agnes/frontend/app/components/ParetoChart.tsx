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

interface RerankPoint {
  id: number;
  utility_score: number;
  rank: number;
  savings: number;
  compliance_probability: number;
  risk_score: number;
  is_pareto_optimal: boolean;
  dominated_by: number[];
  recommended_supplier_name: string;
  impact_score: number;
  impact_confidence: number;
  flagged_low_confidence_high_impact: boolean;
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: RerankPoint }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-xl text-xs space-y-1 max-w-56 pointer-events-none">
      <p className="font-semibold text-slate-900 truncate">{d.recommended_supplier_name || `Proposal #${d.id}`}</p>
      <p className="text-slate-500">
        Impact: <span className="text-emerald-600 font-medium">{d.impact_score?.toFixed(3)}</span>
        {" "}
        <span className="text-slate-400">(conf: {(d.impact_confidence * 100).toFixed(0)}%)</span>
      </p>
      <p className="text-slate-500">
        Compliance P: <span className="font-medium text-slate-800">{d.compliance_probability?.toFixed(3)}</span>
      </p>
      <p className="text-slate-500">
        Savings: <span className="text-emerald-600 font-medium">{d.savings?.toFixed(1)}%</span>
        {" · "}Risk: <span className="text-red-500 font-medium">{d.risk_score?.toFixed(3)}</span>
      </p>
      <p className="text-slate-500">
        Utility: <span className="font-mono font-semibold text-slate-800">{d.utility_score?.toFixed(3)}</span>
      </p>
      {d.flagged_low_confidence_high_impact && (
        <p className="text-red-600 font-semibold">⚠ High impact, low confidence — review required</p>
      )}
      {d.is_pareto_optimal ? (
        <p className="text-amber-600 font-semibold">★ Pareto Optimal (rank #{d.rank})</p>
      ) : (
        <p className="text-slate-400">
          Dominated by {d.dominated_by?.length ?? 0} proposal(s)
        </p>
      )}
      <p className="text-slate-300 mt-1">Click to view details</p>
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

function SliderInput({ label, value, min, max, step, onChange }: SliderProps) {
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-center text-xs">
        <span className="text-slate-600 font-medium">{label}</span>
        <span className="font-mono font-semibold text-slate-800 tabular-nums">{value.toFixed(1)}</span>
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

  const fetchRerank = useCallback(async (a: number, b: number, g: number) => {
    setLoading(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/proposals/rerank", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alpha: a, beta: b, gamma: g }),
      });
      if (res.ok) setData(await res.json());
    } catch {
      // API not yet running — silently skip
    } finally {
      setLoading(false);
    }
  }, []);

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

  // Encode confidence as opacity: low confidence → translucent
  function pointOpacity(conf: number): number {
    return Math.max(0.2, Math.min(0.95, conf));
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-6 space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">
            Pareto Frontier — Decision-Theoretic Ranking
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            X-axis: evidence-weighted impact · opacity encodes confidence · red ring = high impact, low confidence
          </p>
        </div>
        {loading && (
          <span className="text-xs text-amber-500 font-medium animate-pulse">updating…</span>
        )}
      </div>

      {/* Sliders */}
      <div className="grid grid-cols-3 gap-6 bg-slate-50 rounded-lg p-4">
        <SliderInput
          label="α  Savings weight"
          value={alpha}
          min={0}
          max={3}
          step={0.1}
          onChange={(v) => { setAlpha(v); schedule(v, beta, gamma); }}
        />
        <SliderInput
          label="β  Risk penalty"
          value={beta}
          min={0}
          max={3}
          step={0.1}
          onChange={(v) => { setBeta(v); schedule(alpha, v, gamma); }}
        />
        <SliderInput
          label="γ  Uncertainty penalty"
          value={gamma}
          min={0}
          max={3}
          step={0.1}
          onChange={(v) => { setGamma(v); schedule(alpha, beta, v); }}
        />
      </div>

      {/* Scatter chart */}
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 10, right: 24, bottom: 28, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis
              dataKey="impact_score"
              name="Impact"
              type="number"
              domain={[0, 0.9]}
              label={{ value: "Evidence-Weighted Impact", position: "insideBottom", offset: -16, fontSize: 11, fill: "#94a3b8" }}
              tick={{ fontSize: 10, fill: "#94a3b8" }}
            />
            <YAxis
              dataKey="compliance_probability"
              name="Compliance P"
              type="number"
              domain={[0, 1.05]}
              label={{ value: "Compliance Probability", angle: -90, position: "insideLeft", offset: 14, fontSize: 11, fill: "#94a3b8" }}
              tick={{ fontSize: 10, fill: "#94a3b8" }}
            />
            <Tooltip
              cursor={{ strokeDasharray: "3 3", stroke: "#cbd5e1" }}
              content={<CustomTooltip />}
            />
            {/* Dominated proposals — opacity encodes confidence */}
            <Scatter
              name="Dominated"
              data={dominated}
              onClick={handleClick}
              style={{ cursor: "pointer" }}
            >
              {dominated.map((entry) => (
                <Cell
                  key={`d-${entry.id}`}
                  fill="#94a3b8"
                  opacity={pointOpacity(entry.impact_confidence)}
                  stroke={entry.flagged_low_confidence_high_impact ? "#ef4444" : "none"}
                  strokeWidth={entry.flagged_low_confidence_high_impact ? 2 : 0}
                />
              ))}
            </Scatter>
            {/* Pareto-optimal proposals — opacity encodes confidence */}
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
                  stroke={entry.flagged_low_confidence_high_impact ? "#ef4444" : "#d97706"}
                  strokeWidth={entry.flagged_low_confidence_high_impact ? 3 : 2}
                />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      {data.length > 0 && (
        <div className="flex items-center gap-6 text-xs text-slate-500 flex-wrap">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-full bg-amber-400 border-2 border-amber-600" />
            {frontier.length} Pareto-optimal
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-full bg-slate-400 opacity-60" />
            {dominated.length} dominated
          </span>
          {flagged.length > 0 && (
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 rounded-full bg-white border-2 border-red-500" />
              {flagged.length} high-impact / low-confidence
            </span>
          )}
          <span className="text-slate-300">· opacity = confidence · click to view</span>
        </div>
      )}

      {data.length === 0 && !loading && (
        <p className="text-center text-xs text-slate-400 py-4">
          Run Phase 1-3 pipeline first to populate proposals.
        </p>
      )}
    </div>
  );
}
