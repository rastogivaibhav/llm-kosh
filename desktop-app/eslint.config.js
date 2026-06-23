const js = require('@eslint/js');
const globals = require('globals');
const reactHooks = require('eslint-plugin-react-hooks');
const reactRefresh = require('eslint-plugin-react-refresh');

module.exports = [
  { ignores: ['dist/**', 'dist-electron/**', 'node_modules/**', 'test-results/**'] },
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx}'],
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    languageOptions: {
      globals: { ...globals.browser, ...globals.node, ...globals.jest },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      ...reactRefresh.configs.vite.rules,
      'no-empty': ['error', { allowEmptyCatch: true }],
    },
  },
  {
    // ESLint 8's core rule does not mark identifiers used only as JSX tags.
    // Hook correctness remains enforced above.
    files: ['src/**/*.{js,jsx}'],
    rules: { 'no-unused-vars': 'off' },
  },
];
