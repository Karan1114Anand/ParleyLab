import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './hooks/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-inter)', 'system-ui', 'sans-serif'],
      },
      colors: {
        brand: {
          50:  '#f0f4ff',
          100: '#e0e9ff',
          200: '#c7d6fe',
          300: '#a5b8fd',
          400: '#8093fa',
          500: '#6470f3',
          600: '#5050e8',
          700: '#433fcf',
          800: '#3634a8',
          900: '#302f84',
          950: '#1e1c4f',
        },
        surface: {
          50:  'rgba(255,255,255,0.05)',
          100: 'rgba(255,255,255,0.08)',
          200: 'rgba(255,255,255,0.12)',
          300: 'rgba(255,255,255,0.18)',
        },
      },
      animation: {
        'pulse-slow': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-in-right': 'slideInRight 0.35s ease-out',
        'fade-up': 'fadeUp 0.4s ease-out',
        'recording-ring': 'recordingRing 1.5s ease-in-out infinite',
      },
      keyframes: {
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(24px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        recordingRing: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(239, 68, 68, 0.4)' },
          '50%': { boxShadow: '0 0 0 12px rgba(239, 68, 68, 0)' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
};

export default config;
