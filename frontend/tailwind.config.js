/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0f2ff',
          100: '#e0e4ff',
          200: '#c1c9ff',
          300: '#9aa5ff',
          400: '#6d7aff',
          500: '#4949FF',
          600: '#000E9C',
          700: '#000b7a',
          800: '#000858',
          900: '#000536',
        },
        accent: {
          50: '#f0f2ff',
          100: '#e0e4ff',
          200: '#c1c9ff',
          300: '#9aa5ff',
          400: '#6d7aff',
          500: '#4949FF',
          600: '#3333cc',
          700: '#2626a3',
          800: '#1a1a7a',
          900: '#0d0d52',
        },
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
