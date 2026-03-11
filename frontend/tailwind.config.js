/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        saffron: {
          50:  '#fff8ed',
          100: '#ffefd0',
          200: '#ffdb9d',
          300: '#ffc165',
          400: '#ff9d2e',
          500: '#f97d0a',  // core saffron
          600: '#ea6005',
          700: '#c24608',
          800: '#9a380e',
          900: '#7c2f0f',
        },
        ember: {
          400: '#fb923c',
          500: '#f97316',
          600: '#ea580c',
        },
        surface: {
          50:  '#fafaf8',
          100: '#f5f4f0',
          200: '#eceae4',
          800: '#1a1917',
          850: '#141412',
          900: '#0f0e0d',
          950: '#080807',
        }
      },
      fontFamily: {
        display: ['Syne', 'sans-serif'],
        body: ['DM Sans', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'glow-pulse': 'glowPulse 2s ease-in-out infinite',
        'slide-up': 'slideUp 0.4s cubic-bezier(0.16,1,0.3,1)',
        'fade-in': 'fadeIn 0.3s ease-out',
        'shimmer': 'shimmer 1.5s infinite',
      },
      keyframes: {
        glowPulse: {
          '0%,100%': { boxShadow: '0 0 12px rgba(249,125,10,0.3)' },
          '50%': { boxShadow: '0 0 28px rgba(249,125,10,0.6)' },
        },
        slideUp: {
          from: { opacity: 0, transform: 'translateY(16px)' },
          to: { opacity: 1, transform: 'translateY(0)' }
        },
        fadeIn: {
          from: { opacity: 0 },
          to: { opacity: 1 }
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        }
      }
    }
  },
  plugins: []
}
