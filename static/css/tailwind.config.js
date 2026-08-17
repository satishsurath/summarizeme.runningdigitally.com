/**
 * Tailwind CSS Configuration for SummarizeMe
 * 
 * Customizes Tailwind with project-specific design tokens:
 * - Primary color palette (blue-500 based)
 * - Semantic colors (success, warning, error)
 * - Custom spacing for touch targets
 * - Content paths for tree-shaking
 */
module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        success: '#22c55e',
        warning: '#f59e0b',
        error: '#ef4444',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      spacing: {
        '44': '11px', // minimum touch target height
        '56': '14px',
      },
    },
  },
  plugins: [],
};
