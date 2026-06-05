/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          bg: '#FFFBF7', // Cream background from logo
          panel: '#FFFFFF', // Pure white panels
          surface: '#F5EFE6', // Slightly darker warm surface
          border: '#E8DFD5', // Warm border
          text: '#2D1B14', // Deep warm espresso text
          muted: '#8A7366', // Muted warm gray/brown
          accent: '#F26E22', // The exact vibrant orange from the logo
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
          buttonHover: '#D95A15'
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['Fira Code', 'monospace'],
      }
    },
  },
  plugins: [],
}
