const path = require('path');
const fs = require('fs');

function resolveLlmKoshExecutable(configPath, resourcesPath) {
  let config = {};
  try {
    if (fs.existsSync(configPath)) {
      config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
    }
  } catch (e) {
    // Ignore config read errors
  }

  const mode = config.cliMode || 'Auto';
  const customPath = (config.executablePath && config.executablePath.trim() !== '') ? config.executablePath : null;

  const isWin = process.platform === 'win32';
  const bundledPath = resourcesPath ? path.join(resourcesPath, 'bin', isWin ? 'llm-kosh.exe' : 'llm-kosh') : null;
  const systemPath = 'llm-kosh';

  if (mode === 'Custom' && customPath) {
    return { path: customPath, mode: 'Custom' };
  } else if (mode === 'Custom' && !customPath) {
    return { path: null, mode: 'Custom', error: 'Custom mode selected but no path provided.' };
  }

  if (mode === 'Bundled') {
    if (bundledPath && fs.existsSync(bundledPath)) {
      return { path: bundledPath, mode: 'Bundled' };
    }
    return { path: null, mode: 'Bundled', error: 'Bundled executable not found.' };
  }

  if (mode === 'System PATH') {
    return { path: systemPath, mode: 'System PATH' };
  }

  // Auto Mode
  if (customPath) {
    return { path: customPath, mode: 'Auto (Custom)' };
  }
  
  if (bundledPath && fs.existsSync(bundledPath)) {
    return { path: bundledPath, mode: 'Auto (Bundled)' };
  }

  return { path: systemPath, mode: 'Auto (System)' };
}

module.exports = { resolveLlmKoshExecutable };
