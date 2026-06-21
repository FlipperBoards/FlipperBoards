/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"Courier New"', 'Courier', 'monospace'],
        display: ['"Share Tech Mono"', '"Courier New"', 'monospace'],
      },
      animation: {
        'flip-down': 'flipDown 0.15s ease-in forwards',
        'flip-up': 'flipUp 0.15s ease-out forwards',
      },
      keyframes: {
        flipDown: {
          '0%': { transform: 'rotateX(0deg)' },
          '100%': { transform: 'rotateX(-90deg)' },
        },
        flipUp: {
          '0%': { transform: 'rotateX(90deg)' },
          '100%': { transform: 'rotateX(0deg)' },
        },
      },
    },
  },
  plugins: [],
}
