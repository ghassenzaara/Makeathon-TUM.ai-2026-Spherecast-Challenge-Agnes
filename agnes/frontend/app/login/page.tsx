"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { AgnesOrb } from "../components/AgnesOrb";
import { Waveform } from "../components/Waveform";
import { Eye, EyeOff, ArrowRight } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setError("Please fill in all fields.");
      return;
    }
    setError("");
    setLoading(true);

    // Simulate auth — replace with real backend later
    await new Promise((r) => setTimeout(r, 1200));
    localStorage.setItem("agnes_auth", "true");
    router.push("/");
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="w-full max-w-sm"
      >
        {/* ── Agnes Orb + Branding ── */}
        <div className="flex flex-col items-center mb-8">
          <AgnesOrb state={loading ? "thinking" : "idle"} size={64} />
          <motion.h1
            className="mt-5 text-xl font-semibold text-gray-100 tracking-tight"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            Agnes
          </motion.h1>
          <motion.p
            className="mt-1 text-[11px] uppercase tracking-[0.2em] text-gray-500"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
          >
            AI Supply Chain Command Center
          </motion.p>
          {loading && (
            <div className="mt-3">
              <Waveform active={true} barCount={24} />
            </div>
          )}
        </div>

        {/* ── Login Card ── */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.5 }}
          className="rounded-2xl overflow-hidden"
          style={{
            padding: 1,
            background: "rgba(255, 255, 255, 0.06)",
          }}
        >
          <div
            className="rounded-[15px] p-6"
            style={{
              background: "#0e1216",
              backdropFilter: "blur(12px)",
              WebkitBackdropFilter: "blur(12px)",
            }}
          >
            <form onSubmit={handleLogin} className="space-y-4">
              {/* Email */}
              <div>
                <label className="block text-[10px] font-semibold uppercase tracking-[0.15em] text-gray-500 mb-1.5">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="agent@spherecast.ai"
                  className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-2.5 text-sm text-gray-100 placeholder:text-gray-600 focus:outline-none focus:border-blue-500/30 focus:bg-white/[0.06] transition-all"
                  disabled={loading}
                  autoFocus
                />
              </div>

              {/* Password */}
              <div>
                <label className="block text-[10px] font-semibold uppercase tracking-[0.15em] text-gray-500 mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPass ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl px-4 py-2.5 pr-10 text-sm text-gray-100 placeholder:text-gray-600 focus:outline-none focus:border-blue-500/30 focus:bg-white/[0.06] transition-all"
                    disabled={loading}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPass(!showPass)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
                    tabIndex={-1}
                  >
                    {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              {/* Error */}
              {error && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-[11px] text-red-400"
                >
                  {error}
                </motion.p>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 bg-blue-500/10 border border-blue-500/20 text-blue-400 hover:bg-blue-500/20 hover:border-blue-500/30 disabled:opacity-40 rounded-xl px-4 py-2.5 text-sm font-medium transition-all duration-200"
              >
                {loading ? "Authenticating..." : "Sign In"}
                {!loading && <ArrowRight className="h-4 w-4" />}
              </button>
            </form>

            {/* Divider */}
            <div className="flex items-center gap-3 my-4">
              <div className="flex-1 h-px bg-white/[0.06]" />
              <span className="text-[9px] uppercase tracking-[0.15em] text-gray-600">or</span>
              <div className="flex-1 h-px bg-white/[0.06]" />
            </div>

            {/* Demo access */}
            <button
              type="button"
              onClick={() => {
                localStorage.setItem("agnes_auth", "true");
                router.push("/");
              }}
              className="w-full text-center text-[11px] text-gray-500 hover:text-gray-300 transition-colors py-1"
            >
              Continue as Demo User →
            </button>
          </div>
        </motion.div>

        {/* Footer */}
        <p className="text-center text-[10px] text-gray-600 mt-6">
          Spherecast · Makeathon TUM.ai 2026
        </p>
      </motion.div>
    </div>
  );
}
