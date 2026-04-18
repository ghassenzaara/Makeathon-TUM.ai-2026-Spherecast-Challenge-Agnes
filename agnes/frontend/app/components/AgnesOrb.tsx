"use client";

import { motion, AnimatePresence } from "framer-motion";

type OrbState = "idle" | "thinking" | "complete";

interface AgnesOrbProps {
  state?: OrbState;
  size?: number;
}

/**
 * Agnes Logo — Silver/Grey metallic sphere.
 * Idle: anti-gravity levitation (slow float up/down).
 * Thinking: HEAVY spin (rotate: 360, linear, infinite) + outward grey pulse rings.
 */
export function AgnesOrb({ state = "idle", size = 48 }: AgnesOrbProps) {
  const sphereSize = size * 0.7;

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>

      {/* Thinking: outward grey/white pulse rings */}
      <AnimatePresence>
        {state === "thinking" && (
          <>
            {[0, 1, 2].map((i) => (
              <motion.div
                key={`pulse-${i}`}
                className="absolute inset-0 rounded-full"
                style={{ border: "1px solid rgba(200, 200, 200, 0.15)" }}
                initial={{ scale: 1, opacity: 0.5 }}
                animate={{ scale: 2.8, opacity: 0 }}
                exit={{ opacity: 0 }}
                transition={{
                  duration: 2,
                  delay: i * 0.6,
                  repeat: Infinity,
                  ease: "easeOut",
                }}
              />
            ))}
          </>
        )}
      </AnimatePresence>

      {/* Ambient glow */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: size * 1.4,
          height: size * 1.4,
          background: "radial-gradient(circle, rgba(160,160,160,0.1) 0%, transparent 70%)",
        }}
        animate={
          state === "thinking"
            ? { scale: [1, 1.4, 1], opacity: [0.2, 0.6, 0.2] }
            : { scale: [1, 1.1, 1], opacity: [0.2, 0.4, 0.2] }
        }
        transition={{
          duration: state === "thinking" ? 0.8 : 3,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />

      {/* Anti-gravity levitation */}
      <motion.div
        animate={
          state === "idle"
            ? { y: [0, -4, 0, 4, 0] }
            : state === "thinking"
            ? { y: [0, -2, 0, 2, 0] }
            : { y: 0 }
        }
        transition={{
          duration: state === "idle" ? 4 : 1.5,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      >
        {/* HEAVY spin wrapper — continuous 360 rotation when thinking */}
        <motion.div
          animate={state === "thinking" ? { rotate: 360 } : { rotate: 0 }}
          transition={
            state === "thinking"
              ? { duration: 2, repeat: Infinity, ease: "linear" }
              : { duration: 0 }
          }
        >
          {/* Core metallic sphere */}
          <div
            className="rounded-full relative overflow-hidden"
            style={{
              width: sphereSize,
              height: sphereSize,
              background: "radial-gradient(circle at 30% 30%, #f3f4f6, #737373, #171717)",
              boxShadow:
                state === "thinking"
                  ? "0 0 24px 8px rgba(180,180,180,0.3), 0 0 48px 16px rgba(120,120,120,0.1)"
                  : "0 0 10px 3px rgba(120,120,120,0.15), 0 0 20px 6px rgba(80,80,80,0.06)",
            }}
          >
            {/* Crescent specular highlight */}
            <div
              className="absolute"
              style={{
                top: "12%",
                left: "15%",
                width: "40%",
                height: "25%",
                background: "rgba(255,255,255,0.5)",
                filter: "blur(3px)",
                borderRadius: "50%",
                transform: "rotate(-25deg)",
              }}
            />
            {/* Sparkle */}
            <motion.div
              className="absolute rounded-full bg-white"
              style={{ top: "22%", left: "58%", width: "7%", height: "7%" }}
              animate={{ opacity: [0.2, 0.9, 0.2] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
            {/* Bottom reflection */}
            <div
              className="absolute"
              style={{
                bottom: "8%",
                right: "18%",
                width: "22%",
                height: "12%",
                background: "rgba(200,200,200,0.12)",
                filter: "blur(2px)",
                borderRadius: "50%",
              }}
            />
          </div>
        </motion.div>
      </motion.div>

      {/* Complete flash */}
      <AnimatePresence>
        {state === "complete" && (
          <motion.div
            className="absolute inset-0 rounded-full bg-emerald-500/15"
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1.8, opacity: [0, 0.5, 0] }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.8 }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

export function AgnesOrbMini({ size = 34, state = "idle" as OrbState }: { size?: number; state?: OrbState }) {
  return <AgnesOrb state={state} size={size} />;
}
