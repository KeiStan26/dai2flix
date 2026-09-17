/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        netflix: {
          red: '#E50914',
          darkRed: '#B81D24',
          black: '#141414',
          dark: '#181818',
          card: '#202020',
          hover: '#2a2a2a',
          light: '#808080',
        },
      },
      fontFamily: {
        sans: ['"Netflix Sans"', 'Helvetica Neue', 'Segoe UI', 'Roboto', 'Ubuntu', 'sans-serif'],
      },
      boxShadow: {
        'netflix-card': '0 8px 24px rgba(0, 0, 0, 0.75)',
        'netflix-hero': 'inset 0 0 100px 50px rgba(0, 0, 0, 0.8)',
      },
    },
  },
  plugins: [],
}
