import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Legacy names kept (remapped to the boarding-pass palette) so existing
        // utility classes keep working; navy/teal/coral/perf are the new ones.
        surface: "var(--paper)",
        "surface-2": "var(--card)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        accent: "var(--teal)",
        "accent-soft": "var(--teal-soft)",
        line: "var(--line)",
        navy: "var(--navy)",
        teal: "var(--teal)",
        coral: "var(--coral)",
        perf: "var(--perf)",
      },
      borderRadius: { bento: "var(--radius)", "bento-sm": "var(--radius-sm)" },
      fontFamily: { display: "var(--font-display)", mono: "var(--font-mono)" },
      boxShadow: { ticket: "var(--shadow-ticket)" },
      keyframes: {
        "ticket-in": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: { "ticket-in": "ticket-in 0.5s cubic-bezier(0.16, 1, 0.3, 1) both" },
    },
  },
  plugins: [],
} satisfies Config;
