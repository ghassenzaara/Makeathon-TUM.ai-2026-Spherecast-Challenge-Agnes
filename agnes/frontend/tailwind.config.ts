import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        void: "#030303",
        surface: "rgba(8, 10, 18, 0.72)",
        "surface-solid": "#080a12",
        elevated: "rgba(14, 18, 32, 0.85)",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.5s ease-out both",
        "fade-in-up": "fadeInUp 0.6s ease-out both",
        "slide-in-left": "slideInLeft 0.4s ease-out both",
        "slide-in-right": "slideInRight 0.4s ease-out both",
        "glow-breathe": "glowBreathe 3s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        fadeInUp: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideInLeft: {
          "0%": { opacity: "0", transform: "translateX(-16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        slideInRight: {
          "0%": { opacity: "0", transform: "translateX(16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        glowBreathe: {
          "0%, 100%": { boxShadow: "0 0 16px 2px rgba(56, 189, 248, 0.1)" },
          "50%": { boxShadow: "0 0 24px 4px rgba(56, 189, 248, 0.2)" },
        },
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
};
export default config;
