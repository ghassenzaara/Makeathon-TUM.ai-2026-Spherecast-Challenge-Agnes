"use client";

/**
 * Prismatic animated orb — translated from the CSS/HTML spec.
 * Size prop scales all layers proportionally.
 */
export function PrismaticOrb({ size = 28 }: { size?: number }) {
  const layerBase: React.CSSProperties = {
    position: "absolute",
    top: "-50%",
    left: "-50%",
    width: "200%",
    height: "200%",
    borderRadius: "40%",
    opacity: 0.15,
  };

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        position: "relative",
        overflow: "hidden",
        flexShrink: 0,
        background:
          "radial-gradient(circle at 50% 50%, rgb(205,230,255) 0%, rgb(163,198,236) 45%, rgb(130,169,218) 70%, rgb(92,127,199) 100%)",
        boxShadow: "0 0 6px 2px rgba(187,218,247,0.22)",
        animation: "orbPulse 6s ease-in-out infinite",
      }}
    >
      {/* Inner highlight — glowing core */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          background:
            "radial-gradient(circle at 35% 35%, rgba(255,255,255,0.62) 0%, rgba(255,255,255,0) 60%)",
        }}
      />
      {/* Rotating texture layer 1 */}
      <div
        style={{
          ...layerBase,
          background:
            "linear-gradient(rgba(255,255,255,0.5) 0%, rgba(255,255,255,0) 100%), linear-gradient(90deg, #bbdafb, #cde6ff)",
          animation: "rotateTexture 25s linear infinite",
        }}
      />
      {/* Rotating texture layer 2 — opposite direction */}
      <div
        style={{
          ...layerBase,
          background:
            "linear-gradient(rgba(255,255,255,0.5) 0%, rgba(255,255,255,0) 100%), linear-gradient(210deg, #bbdafb, #cde6ff)",
          animation: "rotateTexture 15s linear reverse infinite",
        }}
      />
    </div>
  );
}

/** Header logo: orb + AGNES wordmark in matching orb blue */
export function AgnesLogoMark() {
  return (
    <div className="flex items-center gap-2.5 select-none">
      <PrismaticOrb size={30} />
      <span
        style={{
          fontWeight: 700,
          fontSize: "1.1rem",
          letterSpacing: "0.06em",
          color: "#a8d4ef",
          animation: "agnesGlow 6s ease-in-out infinite",
        }}
      >
        Agnes
      </span>
    </div>
  );
}

/* Keep old exports so existing imports don't break */
export function CrystalBallOrb({ size = 32 }: { size?: number }) {
  return <PrismaticOrb size={size} />;
}

export function AgnesWordmark() {
  return (
    <span
      style={{
        fontWeight: 700,
        fontSize: "1rem",
        letterSpacing: "0.15em",
        color: "#a8d4ef",
      }}
    >
      AGNES
    </span>
  );
}
