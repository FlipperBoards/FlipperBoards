/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"JetBrains Mono"', '"Share Tech Mono"', '"Courier New"', 'monospace'],
        display: ['"Share Tech Mono"', '"JetBrains Mono"', '"Courier New"', 'monospace'],
      },
      colors: {
        surface: {
          DEFAULT: 'rgba(255,255,255,0.035)',
          hover:   'rgba(255,255,255,0.06)',
          active:  'rgba(59,130,246,0.12)',
        },
        ink: {
          1: '#e2e8f0',
          2: '#94a3b8',
          3: '#475569',
          4: '#2d3748',
        },
      },
      animation: {
        'flip-down': 'flipDown 0.15s ease-in forwards',
        'flip-up':   'flipUp 0.15s ease-out forwards',
      },
      keyframes: {
        flipDown: {
          '0%':   { transform: 'rotateX(0deg)' },
          '100%': { transform: 'rotateX(-90deg)' },
        },
        flipUp: {
          '0%':   { transform: 'rotateX(90deg)' },
          '100%': { transform: 'rotateX(0deg)' },
        },
      },
    },
  },
  plugins: [],
}
