"use client";

interface Proposal {
  id: number;
  canonical_name: string;
  estimated_savings_pct: number;
  priority: string;
  confidence_score: number;
}

const PRIORITY_COLOR: Record<string, { bar: string; text: string }> = {
  HIGH:   { bar: "#f59e0b", text: "#fbbf24" },
  MEDIUM: { bar: "#06b6d4", text: "#22d3ee" },
  LOW:    { bar: "#475569", text: "#94a3b8" },
};

const MAX_SAVINGS = 30;
const BAR_H = 18;
const GAP = 10;
const LABEL_W = 110;
const CHART_W = 180;
const PADDING_TOP = 28;
const PADDING_BOTTOM = 20;

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

export function SavingsChart({ proposals }: { proposals: Proposal[] }) {
  const sorted = [...proposals]
    .sort((a, b) => b.estimated_savings_pct - a.estimated_savings_pct)
    .slice(0, 9);

  const svgH = PADDING_TOP + sorted.length * (BAR_H + GAP) + PADDING_BOTTOM;
  const totalW = LABEL_W + CHART_W + 46;

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 h-full">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold uppercase tracking-widest text-[var(--foreground-muted)]">
          Savings Potential
        </span>
        <span className="text-[10px] text-[var(--foreground-muted)] bg-white/5 border border-[var(--border)] rounded px-1.5 py-0.5">
          est. %
        </span>
      </div>

      <svg
        viewBox={`0 0 ${totalW} ${svgH}`}
        width="100%"
        style={{ display: "block", overflow: "visible" }}
      >
        {/* Scale lines */}
        {[0, 10, 20, 30].map((v) => {
          const x = LABEL_W + (v / MAX_SAVINGS) * CHART_W;
          return (
            <g key={v}>
              <line
                x1={x} y1={PADDING_TOP - 10}
                x2={x} y2={svgH - PADDING_BOTTOM}
                stroke="rgba(148,163,184,0.12)"
                strokeWidth="1"
              />
              <text
                x={x}
                y={PADDING_TOP - 13}
                textAnchor="middle"
                fontSize="8"
                fill="rgba(148,163,184,0.5)"
              >
                {v}%
              </text>
            </g>
          );
        })}

        {sorted.map((p, i) => {
          const y = PADDING_TOP + i * (BAR_H + GAP);
          const barW = (p.estimated_savings_pct / MAX_SAVINGS) * CHART_W;
          const colors = PRIORITY_COLOR[p.priority] ?? PRIORITY_COLOR.LOW;
          const opacity = 0.55 + (p.confidence_score / 100) * 0.45;

          return (
            <g key={p.id}>
              {/* Ingredient label */}
              <text
                x={LABEL_W - 8}
                y={y + BAR_H / 2 + 4}
                textAnchor="end"
                fontSize="9.5"
                fill="rgba(148,163,184,0.8)"
              >
                {truncate(p.canonical_name, 16)}
              </text>

              {/* Bar background track */}
              <rect
                x={LABEL_W}
                y={y}
                width={CHART_W}
                height={BAR_H}
                rx="4"
                fill="rgba(148,163,184,0.06)"
              />

              {/* Bar fill */}
              <rect
                x={LABEL_W}
                y={y}
                width={Math.max(barW, 4)}
                height={BAR_H}
                rx="4"
                fill={colors.bar}
                fillOpacity={opacity}
              />

              {/* Savings label */}
              <text
                x={LABEL_W + barW + 6}
                y={y + BAR_H / 2 + 4}
                fontSize="9"
                fill={colors.text}
                fontWeight="600"
              >
                +{p.estimated_savings_pct}%
              </text>
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="flex items-center gap-3 mt-1 flex-wrap">
        {(["HIGH", "MEDIUM", "LOW"] as const).map((p) => (
          <div key={p} className="flex items-center gap-1">
            <span
              className="inline-block h-2 w-3 rounded-sm"
              style={{ backgroundColor: PRIORITY_COLOR[p].bar, opacity: 0.8 }}
            />
            <span className="text-[9px] uppercase tracking-wider text-[var(--foreground-muted)]">{p}</span>
          </div>
        ))}
        <span className="text-[9px] text-[var(--foreground-muted)] ml-auto">
          bar opacity = confidence
        </span>
      </div>
    </div>
  );
}
