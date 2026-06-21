import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        accent: "var(--accent)",
        "accent-soft": "var(--accent-soft)",
        line: "var(--line)",
      },
      borderRadius: { bento: "var(--radius)" },
      fontFamily: { display: "var(--font-display)", mono: "var(--font-mono)" },
    },
  },
  plugins: [],
} satisfies Config;
