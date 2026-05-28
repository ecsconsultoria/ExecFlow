/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './app/templates/**/*.html',
    './app/static/js/**/*.js',
  ],
  safelist: [
    {
      pattern: /(bg|text|border|hover:bg|hover:border|dark:bg|dark:text|dark:border)-(slate|blue|green|amber|red|emerald|sky|violet|cyan|teal|orange|yellow|rose|fuchsia|purple|indigo|lime|pink)-(50|100|200|300|400|500|600|700|800|900)(\/(10|20|30|50))?/,
    },
  ],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: '#3b82f6', dark: '#2563eb' },
      },
    },
  },
  plugins: [],
};
