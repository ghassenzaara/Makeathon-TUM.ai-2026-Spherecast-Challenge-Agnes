"use client";

import { useRef, type ReactNode } from "react";
import { motion, useMotionValue, useMotionTemplate } from "framer-motion";

interface SpotlightCardProps {
  children: ReactNode;
  className?: string;
  /** Spotlight radius in pixels */
  spotlightSize?: number;
  /** Spotlight color — default icy blue */
  spotlightColor?: string;
}

/**
 * SpotlightCard — Spherecast-style frosted glass card with a mouse-tracking
 * icy blue glowing orb that illuminates borders and background on hover.
 *
 * PERFORMANCE: Uses Framer Motion's useMotionValue + useMotionTemplate.
 * Mouse coordinates are stored in MotionValues which update the DOM directly
 * via CSS variables — ZERO React re-renders on mouse move.
 */
export function SpotlightCard({
  children,
  className = "",
  spotlightSize = 320,
  spotlightColor = "rgba(154, 200, 255, 0.18)",
}: SpotlightCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);

  /* ── MotionValues — no re-renders ── */
  const mouseX = useMotionValue(-spotlightSize);
  const mouseY = useMotionValue(-spotlightSize);
  const opacity = useMotionValue(0);

  /* ── Radial gradient that follows cursor ── */
  const spotlightBg = useMotionTemplate`
    radial-gradient(${spotlightSize}px circle at ${mouseX}px ${mouseY}px, ${spotlightColor}, transparent 80%)
  `;

  /* Border glow — tighter, more visible on edges */
  const borderGlow = useMotionTemplate`
    radial-gradient(${spotlightSize * 0.6}px circle at ${mouseX}px ${mouseY}px, rgba(154, 200, 255, 0.4), transparent 70%)
  `;

  function handleMouseMove(e: React.MouseEvent) {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    mouseX.set(e.clientX - rect.left);
    mouseY.set(e.clientY - rect.top);
  }

  function handleMouseEnter() {
    opacity.set(1);
  }

  function handleMouseLeave() {
    opacity.set(0);
  }

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`group relative overflow-hidden rounded-2xl ${className}`}
      /* Outer wrapper — the actual card border */
      style={{
        padding: 1,
        background: "rgba(255, 255, 255, 0.06)",
      }}
    >
      {/* ── Border glow layer — sits behind the inner mask, visible only at the 1px edge ── */}
      <motion.div
        className="absolute inset-0 rounded-2xl pointer-events-none"
        style={{
          background: borderGlow,
          opacity,
        }}
      />

      {/* ── Inner card mask — hides the glow everywhere except the 1px border gap ── */}
      <div
        className="relative rounded-[15px] overflow-hidden"
        style={{
          background: "#0e1216",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
        }}
      >
        {/* ── Spotlight layer — the inner radial glow behind content ── */}
        <motion.div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: spotlightBg,
            opacity,
          }}
        />

        {/* ── Frosted glass base tint ── */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: "rgba(255, 255, 255, 0.02)",
          }}
        />

        {/* ── Content ── */}
        <div className="relative z-10">{children}</div>
      </div>
    </div>
  );
}
