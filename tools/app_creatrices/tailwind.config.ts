import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { nuit: "#070f1c", nuit2: "#0d1728", carte: "#111d31", argent: "#c9d1dc", argent2: "#8b96a8", accent: "#7aa7ff", of: "#59b6ff", mym: "#ff7aa2" },
      fontFamily: { sf: ["-apple-system", "BlinkMacSystemFont", "SF Pro Display", "Inter", "Segoe UI", "Roboto", "sans-serif"] },
      boxShadow: { carte: "0 10px 30px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.06)" },
    },
  },
  plugins: [],
};
export default config;
