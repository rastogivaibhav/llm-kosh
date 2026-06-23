/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          bg: '#FFFBF7',
          panel: '#FFFFFF',
          surface: '#F5EFE6',
          border: '#E8DFD5',
          text: '#2D1B14',
          muted: '#8A7366',
          accent: '#F26E22',
          accentHover: '#D95A15',
          success: '#10B981',
          warning: '#F59E0B',
          danger: '#EF4444',
        },
        vscode: {
          bg: '#FFFBF7',
          sidebar: '#FFFFFF',
          activityBar: '#F5EFE6',
          statusBar: '#F26E22',
          text: '#2D1B14',
          border: '#E8DFD5',
          activeTab: '#FFFBF7',
          inactiveTab: '#F5EFE6',
          hover: '#E8DFD5',
          inputBg: '#FFFFFF',
          buttonPrimary: '#F26E22',
          buttonHover: '#D95A15',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
