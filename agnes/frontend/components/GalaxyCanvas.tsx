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
      const count = Math.min(Math.floor((canvas!.width * canvas!.height) / 4500), 280);
      stars = Array.from({ length: count }, () => ({
        x:       Math.random() * canvas!.width,
        y:       Math.random() * canvas!.height,
        r:       Math.random() * 1.2 + 0.25,
        opacity: Math.random() * 0.40 + 0.45,
        speed:   0.0006,
        drift:   0,
        phase:   Math.random() * Math.PI * 2,
      }));
    }

    function draw() {
      const w = canvas!.width, h = canvas!.height;
      ctx!.clearRect(0, 0, w, h);

      // Deep navy base
      const bg = ctx!.createLinearGradient(0, 0, w, h);
      bg.addColorStop(0,   "#060914");
      bg.addColorStop(0.5, "#080d1a");
      bg.addColorStop(1,   "#05080f");
      ctx!.fillStyle = bg;
      ctx!.fillRect(0, 0, w, h);

      // Nebula clouds — slow drift
      const s  = Math.sin(t * 0.00025);
      const s2 = Math.cos(t * 0.00018);
      const nebulae = [
        { cx: w * 0.18 + s  * 55, cy: h * 0.28 + s2 * 35, r: w * 0.38, color: "rgba(95,163,212,0.07)"   },
        { cx: w * 0.82 + s2 * 45, cy: h * 0.65 + s  * 50, r: w * 0.42, color: "rgba(168,212,239,0.055)" },
        { cx: w * 0.52 + s  * 70, cy: h * 0.12 + s2 * 25, r: w * 0.30, color: "rgba(232,245,253,0.04)"  },
        { cx: w * 0.70 + s2 * 35, cy: h * 0.18 + s  * 45, r: w * 0.28, color: "rgba(139,92,246,0.03)"   },
        { cx: w * 0.35 + s  * 40, cy: h * 0.55 + s2 * 30, r: w * 0.22, color: "rgba(248,252,255,0.035)" },
      ];
      nebulae.forEach(({ cx, cy, r, color }) => {
        const grad = ctx!.createRadialGradient(cx, cy, 0, cx, cy, r);
        grad.addColorStop(0, color);
        grad.addColorStop(1, "transparent");
        ctx!.fillStyle = grad;
        ctx!.fillRect(0, 0, w, h);
      });

      // Heartbeat — locked to 6 s (matches CSS orbPulse / agnesGlow)
      const masterPhase = (Date.now() % 6000) / 6000;
      const heartbeat   = (Math.sin(masterPhase * Math.PI * 2 - Math.PI / 2) + 1) / 2;
      // Wider breath range so the sync with the logo is clearly felt
      const globalBright = 0.45 + 0.55 * heartbeat; // 0.45 dim → 1.0 full

      // Slow galactic rotation offset — the whole field gently swirls
      const galacticAngle = t * 0.0000008; // one full rotation every ~2 hours

      stars.forEach((star) => {
        // Rotate each star slightly around the canvas centre for galaxy swirl
        const cx = canvas!.width  / 2;
        const cy = canvas!.height / 2;
        const dx = star.x - cx;
        const dy = star.y - cy;
        // Depth-weighted rotation: stars further from centre move a touch faster
        const dist  = Math.sqrt(dx * dx + dy * dy);
        const angle = galacticAngle * (0.5 + dist / (Math.max(cx, cy) * 2));
        const cos   = Math.cos(angle);
        const sin   = Math.sin(angle);
        star.x = cx + dx * cos - dy * sin;
        star.y = cy + dx * sin + dy * cos;

        star.y += star.speed;
        if (star.y > h + 2) { star.y = -2; star.x = Math.random() * canvas!.width; }

        // Individual twinkle synced to breath — trough aligns with logo dim
        const twinkle = 0.35 + 0.65 * ((Math.sin(t * star.speed * 8 + star.phase) + 1) / 2);
        const alpha   = Math.min(star.opacity * twinkle * globalBright, 0.92);
        const hue     = 200 + Math.sin(star.phase) * 25;

        // Core pinpoint
        ctx!.beginPath();
        ctx!.arc(star.x, star.y, star.r, 0, Math.PI * 2);
        ctx!.fillStyle = `hsla(${hue}, 40%, 96%, ${alpha})`;
        ctx!.fill();

        // Glow halo — radius kept tight, scales slightly with heartbeat
        const glowR = star.r * (star.r > 1.0 ? 4.0 : 3.0);
        ctx!.beginPath();
        ctx!.arc(star.x, star.y, glowR, 0, Math.PI * 2);
        ctx!.fillStyle = `hsla(${hue}, 55%, 97%, ${alpha * 0.24})`;
        ctx!.fill();
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
