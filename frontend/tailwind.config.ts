import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          green: "#A8E063",
          dark: "#0E1116",
        },
      },
    },
  },
  plugins: [],
};
export default config;
