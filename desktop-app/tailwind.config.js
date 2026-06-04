/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        vscode: {
          bg: '#1e1e1e',
          sidebar: '#252526',
          activityBar: '#333333',
          statusBar: '#007acc',
          text: '#cccccc',
          border: '#3c3c3c',
          activeTab: '#1e1e1e',
          inactiveTab: '#2d2d2d',
          hover: '#2a2d2e',
          inputBg: '#3c3c3c',
          buttonPrimary: '#0e639c',
          buttonHover: '#1177bb'
        }
      }
    },
  },
  plugins: [],
}
