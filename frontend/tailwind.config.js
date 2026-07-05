/** @type {import("tailwindcss").Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Google Sans Flex", "system-ui", "sans-serif"],
        display: ["Google Sans Flex", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      colors: {
        paper: "rgb(var(--color-paper) / <alpha-value>)",
        card: "rgb(var(--color-card) / <alpha-value>)",
        sand: "rgb(var(--color-sand) / <alpha-value>)",
        hover: "rgb(var(--color-hover) / <alpha-value>)",
        line: "rgb(var(--color-line) / <alpha-value>)",
        coffee: {
          light: "rgb(var(--color-coffee-light) / <alpha-value>)",
          DEFAULT: "rgb(var(--color-coffee) / <alpha-value>)",
          deep: "rgb(var(--color-coffee-deep) / <alpha-value>)",
        },
        espresso: "rgb(var(--color-espresso) / <alpha-value>)",
        cocoa: "rgb(var(--color-cocoa) / <alpha-value>)",
        muted: "rgb(var(--color-muted) / <alpha-value>)",
        olive: "rgb(var(--color-olive) / <alpha-value>)",
        terracotta: "rgb(var(--color-terracotta) / <alpha-value>)",
        ochre: "rgb(var(--color-ochre) / <alpha-value>)",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(90, 62, 40, 0.06), 0 4px 16px rgba(90, 62, 40, 0.06)",
        lift: "0 6px 24px rgba(90, 62, 40, 0.12)",
      },
    },
  },
  plugins: [],
};
