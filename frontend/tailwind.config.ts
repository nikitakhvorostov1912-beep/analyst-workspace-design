import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-plex-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-plex-mono)", "monospace"],
      },
      colors: {
        // Legacy aliases (backward compatibility — текущий код)
        bg: "var(--bg-0)",
        "bg-elevated": "var(--bg-1)",
        fg: "var(--fg-1)",
        "fg-muted": "var(--fg-3)",
        border: "var(--bd-2)",
        accent: "var(--accent)",

        // Granular tokens (Phase 11.2+ компоненты используют)
        "bg-0": "var(--bg-0)",
        "bg-1": "var(--bg-1)",
        "bg-2": "var(--bg-2)",
        "bg-3": "var(--bg-3)",
        "fg-1": "var(--fg-1)",
        "fg-2": "var(--fg-2)",
        "fg-3": "var(--fg-3)",
        "fg-4": "var(--fg-4)",
        "bd-1": "var(--bd-1)",
        "bd-2": "var(--bd-2)",
        "bd-3": "var(--bd-3)",

        // Accent variants
        "accent-08": "var(--accent-08)",
        "accent-12": "var(--accent-12)",
        "accent-20": "var(--accent-20)",

        // Semantic
        success: "var(--success)",
        "success-12": "var(--success-12)",
        "success-20": "var(--success-20)",
        warning: "var(--warning)",
        "warning-12": "var(--warning-12)",
        "warning-20": "var(--warning-20)",
        error: "var(--error)",
        "error-12": "var(--error-12)",
        "error-20": "var(--error-20)",
      },
      transitionDuration: {
        micro: "150ms",
        normal: "200ms",
        large: "300ms",
      },
      transitionTimingFunction: {
        "design-ease": "cubic-bezier(0.4, 0, 0.2, 1)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.95)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "dialog-in": {
          "0%": { opacity: "0", transform: "scale(0.96)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
        "status-pulse": {
          "0%, 100%": { boxShadow: "0 0 0 0 currentColor", opacity: "1" },
          "50%": { boxShadow: "0 0 0 4px transparent", opacity: "0.85" },
        },
        "skeleton-pulse": {
          "0%, 100%": { opacity: "0.35" },
          "50%": { opacity: "0.6" },
        },
      },
      animation: {
        "fade-up": "fade-up 200ms cubic-bezier(0.4, 0, 0.2, 1)",
        "fade-in": "fade-in 200ms cubic-bezier(0.4, 0, 0.2, 1)",
        "scale-in": "scale-in 150ms cubic-bezier(0.4, 0, 0.2, 1)",
        "dialog-in": "dialog-in 200ms cubic-bezier(0.4, 0, 0.2, 1)",
        blink: "blink 0.9s infinite",
        "status-pulse": "status-pulse 2s infinite",
        "skeleton-pulse": "skeleton-pulse 1.5s cubic-bezier(0.4, 0, 0.2, 1) infinite",
      },
    },
  },
  plugins: [],
};

export default config;
