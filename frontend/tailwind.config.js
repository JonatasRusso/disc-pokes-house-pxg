/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#5865F2",
          dark: "#4752C4",
        },
      },
    },
  },
  plugins: [],
};
