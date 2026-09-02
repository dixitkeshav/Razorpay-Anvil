/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Plus Jakarta Sans", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        anvil: {
          blue: "#0D5CFF",
          "blue-dark": "#003DB3",
          "blue-soft": "#EEF4FF",
          accent: "#22C55E",
          success: "#16A34A",
          "success-soft": "#ECFDF3",
          warning: "#F59E0B",
          "warning-soft": "#FFFAEB",
          danger: "#EF4444",
          "danger-soft": "#FEF2F2",
          ink: "#111827",
          "ink-soft": "#667085",
          "ink-muted": "#98A2B3",
          surface: "#F8FAFC",
          border: "#E5E7EB",
          "border-strong": "#D0D5DD",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(16, 24, 40, 0.03), 0 1px 4px rgba(16, 24, 40, 0.02)",
      },
      borderRadius: {
        sm: "6px",
        md: "10px",
        lg: "14px",
      },
    },
  },
  plugins: [],
};
