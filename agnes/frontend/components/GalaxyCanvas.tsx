"use client";

import { useEffect, useRef } from "react";

interface Star {
  x: number; y: number; r: number;
  opacity: number; speed: number; drift: number; phase: number;
}

export function GalaxyCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let stars: Star[] = [];
    let t = 0;

    function resize() {
      canvas!.width  = window.innerWidth;
      canvas!.height = window.innerHeight;
      initStars();
    }

    function initStars() {
      const count = Math.floor((canvas!.width * canvas!.height) / 6000);
      stars = Array.from({ length: Math.min(count, 220) }, () => ({
        x:       Math.random() * canvas!.width,
        y:       Math.random() * canvas!.height,
        r:       Math.random() * 1.8 + 0.35,
        opacity: Math.random() * 0.10 + 0.90,   // 0.90–1.00 base — doubled brightness
        speed:   Math.random() * 0.10 + 0.02,
        drift:   (Math.random() - 0.5) * 0.08,
        phase:   Math.random() * Math.PI * 2,
      }));
    }

    function draw() {
      const w = canvas!.width, h = canvas!.height;
      ctx!.clearRect(0, 0, w, h);

      // Deep navy base — Spherecast palette
      const bg = ctx!.createLinearGradient(0, 0, w, h);
      bg.addColorStop(0,   "#060914");
      bg.addColorStop(0.5, "#080d1a");
      bg.addColorStop(1,   "#05080f");
      ctx!.fillStyle = bg;
      ctx!.fillRect(0, 0, w, h);

      // Nebula layers — slow drift
      const s  = Math.sin(t * 0.00025);
      const s2 = Math.cos(t * 0.00018);
      const nebulae = [
        // Spherecast sky-blue tones
        { cx: w * 0.18 + s  * 55, cy: h * 0.28 + s2 * 35, r: w * 0.38, color: "rgba(95,163,212,0.07)"  },
        { cx: w * 0.82 + s2 * 45, cy: h * 0.65 + s  * 50, r: w * 0.42, color: "rgba(168,212,239,0.055)" },
        { cx: w * 0.52 + s  * 70, cy: h * 0.12 + s2 * 25, r: w * 0.30, color: "rgba(232,245,253,0.04)"  },
        // Faint prismatic accent — violet
        { cx: w * 0.70 + s2 * 35, cy: h * 0.18 + s  * 45, r: w * 0.28, color: "rgba(139,92,246,0.03)"   },
        // Warm near-white core
        { cx: w * 0.35 + s  * 40, cy: h * 0.55 + s2 * 30, r: w * 0.22, color: "rgba(248,252,255,0.035)" },
      ];

      nebulae.forEach(({ cx, cy, r, color }) => {
        const grad = ctx!.createRadialGradient(cx, cy, 0, cx, cy, r);
        grad.addColorStop(0, color);
        grad.addColorStop(1, "transparent");
        ctx!.fillStyle = grad;
        ctx!.fillRect(0, 0, w, h);
      });

      // Global heartbeat — wall-clock locked to 6 000 ms so it stays in phase
      // with the CSS orbPulse / agnesGlow animations (same 6 s period).
      const masterPhase = (Date.now() % 6000) / 6000;           // 0 → 1 every 6 s
      const heartbeat   = (Math.sin(masterPhase * Math.PI * 2 - Math.PI / 2) + 1) / 2; // 0 → 1

      // Global multiplier: dims to 0.70, brightens to 1.05 at the peak breath
      const globalBright = 0.85 + 0.50 * heartbeat;

      // Stars — individual twinkle × global breath
      stars.forEach((star) => {
        const twinkle = 0.22 + 0.78 * ((Math.sin(t * star.speed * 0.018 + star.phase) + 1) / 2);
        const alpha   = Math.min(star.opacity * twinkle * globalBright, 1.0);

        const hue = 195 + Math.sin(star.phase) * 30;

        // Core — pure white pinpoint
        ctx!.beginPath();
        ctx!.arc(star.x, star.y, star.r, 0, Math.PI * 2);
        ctx!.fillStyle = `hsla(${hue}, 10%, 100%, ${alpha})`;
        ctx!.fill();

        const large = star.r > 1.2;
        const pulse  = 0.85 + 0.45 * heartbeat; // heartbeat multiplier kept in sync

        // Layer 1 — tight hot glow
        const r1 = star.r * (large ? 14 : 10);
        ctx!.beginPath();
        ctx!.arc(star.x, star.y, r1, 0, Math.PI * 2);
        ctx!.fillStyle = `hsla(${hue}, 50%, 99%, ${Math.min(alpha * 0.92 * pulse, 0.92)})`;
        ctx!.fill();

        // Layer 2 — mid bloom
        const r2 = r1 * 2.2;
        ctx!.beginPath();
        ctx!.arc(star.x, star.y, r2, 0, Math.PI * 2);
        ctx!.fillStyle = `hsla(${hue}, 55%, 98%, ${Math.min(alpha * 0.60 * pulse, 0.70)})`;
        ctx!.fill();

        // Layer 3 — wide corona
        const r3 = r2 * 2.5;
        ctx!.beginPath();
        ctx!.arc(star.x, star.y, r3, 0, Math.PI * 2);
        ctx!.fillStyle = `hsla(${hue}, 60%, 97%, ${alpha * 0.28 * pulse})`;
        ctx!.fill();

        // Layer 4 — faint super-wide halo (big stars only)
        if (large) {
          const r4 = r3 * 2;
          ctx!.beginPath();
          ctx!.arc(star.x, star.y, r4, 0, Math.PI * 2);
          ctx!.fillStyle = `hsla(${hue}, 65%, 97%, ${alpha * 0.10 * pulse})`;
          ctx!.fill();
        }

        star.y += star.speed * 0.055;
        star.x += star.drift * 0.04;
        if (star.y > h + 2)    { star.y = -2; star.x = Math.random() * w; }
        if (star.x < -2)        star.x = w + 2;
        if (star.x > w + 2)    star.x = -2;
      });

      t++;
      animId = requestAnimationFrame(draw);
    }

    resize();
    draw();
    window.addEventListener("resize", resize);
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "fixed",
        inset: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        zIndex: 0,
      }}
    />
  );
}
