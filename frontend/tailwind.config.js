/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: {
          primary: '#0a0a0f',
          surface: '#111118',
          muted: '#1a1a24',
        },
        border: {
          DEFAULT: '#2a2a3a',
          subtle: '#1e1e2a',
        },
        accent: {
          primary: '#6ee7b7',
          'primary-muted': '#134e4a',
          secondary: '#818cf8',
        },
        text: {
          primary: '#f1f5f9',
          secondary: '#94a3b8',
          muted: '#475569',
        },
        status: {
          success: '#22c55e',
          warning: '#f59e0b',
          error: '#ef4444',
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'ui-monospace', '"Cascadia Code"', '"Fira Code"', 'monospace'],
        mono: ['"JetBrains Mono"', 'ui-monospace', '"Cascadia Code"', '"Fira Code"', 'monospace'],
      },
      spacing: {
        '4.5': '1.125rem',
        '13': '3.25rem',
        '18': '4.5rem',
      },
      borderRadius: {
        card: '8px',
        input: '6px',
        modal: '12px',
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'fade-in': 'fade-in 0.3s ease-out',
        'slide-up': 'slide-up 0.3s ease-out',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { opacity: '1', boxShadow: '0 0 8px 2px rgba(110, 231, 183, 0.4)' },
          '50%': { opacity: '0.6', boxShadow: '0 0 16px 4px rgba(110, 231, 183, 0.6)' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      transitionDuration: {
        DEFAULT: '150ms',
      },
    },
  },
  plugins: [],
};
