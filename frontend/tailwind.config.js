/** @type {import("tailwindcss").Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Manrope", "ui-sans-serif", "system-ui"],
        display: ["Space Grotesk", "ui-sans-serif", "system-ui"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      colors: {
        // Cream / brown light palette — strict single system
        paper: "#F4EBDA",      // page background
        card: "#FDF8EE",       // surfaces / cards
        sand: "#EEE1CB",       // subtle fills, chips
        hover: "#E7D8BD",      // hover fills
        line: "#DECBAA",       // borders / dividers
        coffee: {
          light: "#A07C55",
          DEFAULT: "#7B5836",  // primary brown
          deep: "#5A3E28",
        },
        espresso: "#3A2A1C",   // headings / strongest text
        cocoa: "#4E3A2A",      // body text
        muted: "#93795C",      // secondary text
        // warm status accents that live inside the palette
        olive: "#5E7A46",      // success
        terracotta: "#B14A34", // danger
        ochre: "#B27C24",      // warning
      },
      boxShadow: {
        soft: "0 1px 2px rgba(90, 62, 40, 0.06), 0 4px 16px rgba(90, 62, 40, 0.06)",
        lift: "0 6px 24px rgba(90, 62, 40, 0.12)",
      },
    },
  },
  plugins: [],
};
