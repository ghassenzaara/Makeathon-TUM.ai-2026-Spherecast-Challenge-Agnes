"use client";

export function CrystalBallOrb({ size = 32 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <defs>
        {/* Spherecast-style gradient — white core fading to soft sky blue at rim */}
        <radialGradient id="orbFill" cx="38%" cy="30%" r="68%" gradientUnits="userSpaceOnUse">
          <stop offset="0%"  stopColor="#ffffff" stopOpacity="1"   />
          <stop offset="20%" stopColor="#e8f5fd" stopOpacity="1"   />
          <stop offset="48%" stopColor="#a8d4ef" stopOpacity="1"   />
          <stop offset="75%" stopColor="#5fa3d4" stopOpacity="1"   />
          <stop offset="100%" stopColor="#3a80b8" stopOpacity="1"  />
        </radialGradient>

        {/* Outer glow filter */}
        <filter id="orbGlow" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="1.8" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>

        {/* Particle glow */}
        <filter id="dotGlow" x="-100%" y="-100%" width="300%" height="300%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="0.6" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>

      {/* Outer halo ring */}
      <circle cx="16" cy="16" r="15" stroke="#7abde0" strokeWidth="0.6" strokeOpacity="0.5" />

      {/* Main orb */}
      <circle cx="16" cy="16" r="13" fill="url(#orbFill)" filter="url(#orbGlow)" />

      {/* Crescent shine highlight — top-left */}
      <ellipse
        cx="11.5"
        cy="10"
        rx="4.5"
        ry="2.8"
        fill="white"
        fillOpacity="0.38"
        transform="rotate(-28 11.5 10)"
      />

      {/* Secondary smaller shine */}
      <ellipse
        cx="9.5"
        cy="8"
        rx="1.8"
        ry="1.1"
        fill="white"
        fillOpacity="0.55"
        transform="rotate(-28 9.5 8)"
      />

      {/* Floating mystery particles */}
      <circle cx="20" cy="19" r="1.1" fill="#ffffff" fillOpacity="0.55" filter="url(#dotGlow)" />
      <circle cx="14" cy="21" r="0.75" fill="#c8e8f8" fillOpacity="0.5"  filter="url(#dotGlow)" />
      <circle cx="22" cy="13" r="0.55" fill="white"   fillOpacity="0.7"  filter="url(#dotGlow)" />

      {/* Inner depth ring */}
      <circle cx="16" cy="16" r="9" stroke="#5fa3d4" strokeWidth="0.4" strokeOpacity="0.2" fill="none" />
    </svg>
  );
}

export function AgnesWordmark() {
  return (
    <div className="flex items-baseline gap-[0.5px] text-base font-bold tracking-tight leading-none select-none">
      {/* A */}
      <span className="text-[var(--foreground)]">A</span>

      {/* g — the crystal ball letter */}
      <span className="relative inline-flex items-center justify-center mx-[1px]">
        {/* glowing orb ring behind the "g" bowl */}
        <span
          className="absolute rounded-full"
          style={{
            width: "0.78em",
            height: "0.78em",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -55%)",
            background: "radial-gradient(circle at 38% 33%, rgba(255,255,255,0.35), rgba(95,163,212,0.22) 55%, transparent 78%)",
            boxShadow: "0 0 5px 1.5px rgba(95,163,212,0.35)",
            border: "0.5px solid rgba(122,189,224,0.35)",
            pointerEvents: "none",
          }}
        />
        <span
          className="relative"
          style={{
            color: "#5fa3d4",
            textShadow: "0 0 8px rgba(95,163,212,0.8), 0 0 16px rgba(95,163,212,0.35)",
          }}
        >
          g
        </span>
      </span>

      {/* nes */}
      <span className="text-[var(--foreground)]">nes</span>
    </div>
  );
}
