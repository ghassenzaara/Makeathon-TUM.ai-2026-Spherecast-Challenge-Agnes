"use client";

import { motion } from "framer-motion";

interface WaveformProps {
  active?: boolean;
  barCount?: number;
}

export function Waveform({ active = false, barCount = 24 }: WaveformProps) {
  return (
    <div className="flex items-end justify-center gap-[2px] h-5">
      {Array.from({ length: barCount }).map((_, i) => {
        const center = barCount / 2;
        const distFromCenter = Math.abs(i - center) / center;
        const maxH = 1 - distFromCenter * 0.6;

        return (
          <motion.div
            key={i}
            className="w-[2px] rounded-full bg-blue-500/60"
            animate={
              active
                ? {
                    height: [
                      `${maxH * 20}%`,
                      `${maxH * 90}%`,
                      `${maxH * 40}%`,
                      `${maxH * 75}%`,
                      `${maxH * 20}%`,
                    ],
                    opacity: [0.4, 0.9, 0.5, 0.8, 0.4],
                  }
                : { height: "15%", opacity: 0.2 }
            }
            transition={
              active
                ? {
                    duration: 0.8 + Math.random() * 0.6,
                    repeat: Infinity,
                    ease: "easeInOut",
                    delay: i * 0.03,
                  }
                : { duration: 0.3 }
            }
          />
        );
      })}
    </div>
  );
}
