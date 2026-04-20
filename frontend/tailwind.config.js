/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        bricolage: ['"Bricolage Grotesque"', 'sans-serif'],
        dm: ['"DM Sans"', 'sans-serif'],
        jetbrains: ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        invite: '#30d158',
        reject: '#ff453a',
        accent: '#0a84ff',
        gold: '#ffd60a',
      },
      backdropBlur: {
        '3xl': '40px',
        '4xl': '60px',
      },
      borderColor: {
        glass: 'rgba(255,255,255,0.10)',
        'glass-top': 'rgba(255,255,255,0.22)',
      },
    },
  },
  plugins: [],
}
