import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f2f7f5",
          100: "#dcece5",
          200: "#b9d9cb",
          300: "#8ec0aa",
          400: "#5fa084",
          500: "#3f8268",
          600: "#2f6853",
          700: "#275444",
          800: "#214439",
          900: "#1b3830",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
      },
    },
  },
  plugins: [],
};

export default config;
