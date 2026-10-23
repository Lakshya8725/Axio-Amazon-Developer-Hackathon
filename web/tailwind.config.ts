import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#07080c",
        panel: "#10141c",
        mute: "#93a0b4",
        faint: "#6d7b90",
        glow: "#7ee7ff",
        good: "#5ee0a0",
        warn: "#f0c36a",
        bad: "#ff8d9a",
      },
      boxShadow: {
        panel: "0 24px 60px rgba(0, 0, 0, 0.32)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
