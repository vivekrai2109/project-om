import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#09111f",
        mist: "#d7e9ff",
        horizon: "#6ed4ff",
        ember: "#ff8f5c",
        moss: "#8fe388",
      },
      boxShadow: {
        panel: "0 30px 80px rgba(6, 18, 35, 0.28)",
      },
    },
  },
  plugins: [],
};

export default config;
