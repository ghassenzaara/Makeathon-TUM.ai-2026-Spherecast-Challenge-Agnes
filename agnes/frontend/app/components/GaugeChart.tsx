"use client";

interface GaugeChartProps {
  value: number;   // 0–100
  label?: string;
}

function arcPath(cx: number, cy: number, r: number, value: number): string {
  const v = Math.min(Math.max(value / 100, 0), 0.9999);
  const endAngle = (1 - v) * Math.PI;
  const endX = cx + r * Math.cos(endAngle);
  const endY = cy - r * Math.sin(endAngle);
  return `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${endX.toFixed(2)} ${endY.toFixed(2)}`;
}

function trackPath(cx: number, cy: number, r: number): string {
  return `M ${cx - r} ${cy} A ${r} ${r} 0 1 1 ${cx + r} ${cy}`;
}

function rating(v: number) {
  if (v >= 75) return { label: "HIGH CONFIDENCE",   color: "#22d3ee" };
  if (v >= 50) return { label: "MEDIUM CONFIDENCE", color: "#f59e0b" };
  return             { label: "LOW CONFIDENCE",    color: "#d946ef" };
}

function arcColor(v: number) {
  if (v >= 75) return "#06b6d4";
  if (v >= 50) return "#f59e0b";
  return "#d946ef";
}

export function GaugeChart({ value, label = "AI Confidence" }: GaugeChartProps) {
  const cx = 130;
  const cy = 125;
  const rTrack = 80;
  const sw = 14;
  const { label: ratingLabel, color: ratingColor } = rating(value);
  const color = arcColor(value);

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4" style={{ overflow: "hidden" }}>
      <span className="block text-xs font-semibold uppercase tracking-widest text-[var(--foreground-muted)] mb-3">
        {label}
      </span>

      <svg
        viewBox="0 0 260 165"
        style={{ display: "block", width: "100%", aspectRatio: "260/165", overflow: "hidden" }}
      >
        {/* Grey track — full semicircle */}
        <path
          d={trackPath(cx, cy, rTrack)}
          fill="none"
          stroke="rgba(148,163,184,0.13)"
          strokeWidth={sw}
          strokeLinecap="round"
        />

        {/* Value arc — CSS drop-shadow stays clipped to the element's own box */}
        {value > 0 && (
          <path
            d={arcPath(cx, cy, rTrack, value)}
            fill="none"
            stroke={color}
            strokeWidth={sw}
            strokeLinecap="round"
            style={{ filter: `drop-shadow(0 0 5px ${color}cc)` }}
          />
        )}

        {/* Tick marks */}
        {[0, 0.25, 0.5, 0.75, 1].map((t) => {
          const angle = (1 - t) * Math.PI;
          const x1 = cx + (rTrack + 6)  * Math.cos(angle);
          const y1 = cy - (rTrack + 6)  * Math.sin(angle);
          const x2 = cx + (rTrack + 13) * Math.cos(angle);
          const y2 = cy - (rTrack + 13) * Math.sin(angle);
          return (
            <line key={t}
              x1={x1.toFixed(1)} y1={y1.toFixed(1)}
              x2={x2.toFixed(1)} y2={y2.toFixed(1)}
              stroke="rgba(148,163,184,0.25)" strokeWidth="1.5"
            />
          );
        })}

        {/* Tick labels */}
        {([
          { t: 0,   txt: "0"   },
          { t: 0.5, txt: "50"  },
          { t: 1,   txt: "100" },
        ] as const).map(({ t, txt }) => {
          const angle = (1 - t) * Math.PI;
          const lx = cx + (rTrack + 24) * Math.cos(angle);
          const ly = cy - (rTrack + 24) * Math.sin(angle);
          return (
            <text key={t}
              x={lx.toFixed(1)} y={ly.toFixed(1)}
              textAnchor="middle" dominantBaseline="middle"
              fontSize="9" fill="rgba(148,163,184,0.4)"
            >
              {txt}
            </text>
          );
        })}

        {/* Big percentage */}
        <text
          x={cx} y={cy - 8}
          textAnchor="middle" dominantBaseline="middle"
          fontSize="34" fontWeight="700"
          fill={color}
          style={{ filter: `drop-shadow(0 0 6px ${color}88)` }}
        >
          {value.toFixed(0)}%
        </text>

        {/* Rating label */}
        <text
          x={cx} y={cy + 18}
          textAnchor="middle"
          fontSize="9" fontWeight="600"
          fill={ratingColor} letterSpacing="0.08em"
        >
          {ratingLabel}
        </text>

        {/* Footer */}
        <text
          x={cx} y={cy + 34}
          textAnchor="middle"
          fontSize="7.5" fill="rgba(148,163,184,0.38)"
        >
          avg. across all proposals
        </text>
      </svg>
    </div>
  );
}
