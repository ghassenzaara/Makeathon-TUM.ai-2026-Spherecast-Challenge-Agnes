"use client";

/**
 * TracingBorder — Spherecast-style illuminating border.
 * A spinning conic-gradient hidden behind a #0A0A0A inner mask,
 * leaving only a 1px moving glowing blue line tracing the edge.
 * 30s rotation duration via .animate-tracing-spin in globals.css.
 */
export function TracingBorder({
  children,
  className = "",
  active = true,
  borderRadius = 16,
  glowColor = "rgba(59, 130, 246, 0.8)",
}: {
  children: React.ReactNode;
  className?: string;
  active?: boolean;
  borderRadius?: number;
  glowColor?: string;
}) {
  return (
    <div
      className={`relative overflow-hidden ${className}`}
      style={{ borderRadius, padding: 1 }}
    >
      {/* Spinning conic gradient */}
      {active && (
        <div
          className="absolute animate-tracing-spin"
          style={{
            top: "50%",
            left: "50%",
            width: "200%",
            height: "200%",
            transform: "translate(-50%, -50%)",
            background: `conic-gradient(from 0deg, ${glowColor}, transparent 25%, transparent 50%, ${glowColor} 75%, transparent 100%)`,
          }}
        />
      )}

      {/* Static border fallback when inactive */}
      {!active && (
        <div
          className="absolute inset-0"
          style={{ background: "rgba(255,255,255,0.08)" }}
        />
      )}

      {/* Inner #0A0A0A mask — hides gradient, leaving 1px edge */}
      <div
        className="relative z-10"
        style={{
          borderRadius: borderRadius - 1,
          background: "#0A0A0A",
        }}
      >
        {children}
      </div>
    </div>
  );
}
