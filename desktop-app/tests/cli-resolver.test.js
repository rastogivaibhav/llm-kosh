const { resolveLlmKoshExecutable } = require('../electron/cli-resolver');
const fs = require('fs');
const path = require('path');

jest.mock('fs');

describe('CLI Resolver', () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  test('Auto Mode: resolves from custom path if available', () => {
    fs.existsSync.mockImplementation((p) => p === '/mock/config.json');
    fs.readFileSync.mockReturnValue(JSON.stringify({ cliMode: 'Auto', executablePath: '/custom/venv/bin/llm-kosh' }));

    const exe = resolveLlmKoshExecutable('/mock/config.json', '/mock/resources');
    expect(exe.path).toBe('/custom/venv/bin/llm-kosh');
    expect(exe.mode).toBe('Auto (Custom)');
  });

  test('Auto Mode: resolves from sidecar if custom missing', () => {
    fs.existsSync.mockImplementation((p) => {
      if (p === '/mock/config.json') return false; // Default Auto mode
      if (p.includes('resources') && p.includes('llm-kosh')) return true;
      return false;
    });

    const exe = resolveLlmKoshExecutable('/mock/config.json', '/mock/resources');
    const isWin = process.platform === 'win32';
    expect(exe.path).toBe(path.join('/mock/resources', 'bin', isWin ? 'llm-kosh.exe' : 'llm-kosh'));
    expect(exe.mode).toBe('Auto (Bundled)');
  });

  test('Auto Mode: falls back to system PATH if neither exists', () => {
    fs.existsSync.mockReturnValue(false);

    const exe = resolveLlmKoshExecutable('/mock/config.json', '/mock/resources');
    expect(exe.path).toBe('llm-kosh');
    expect(exe.mode).toBe('Auto (System)');
  });

  test('Bundled Mode: returns sidecar if present', () => {
    fs.existsSync.mockImplementation((p) => {
      if (p === '/mock/config.json') return true;
      if (p.includes('resources') && p.includes('llm-kosh')) return true;
      return false;
    });
    fs.readFileSync.mockReturnValue(JSON.stringify({ cliMode: 'Bundled' }));

    const exe = resolveLlmKoshExecutable('/mock/config.json', '/mock/resources');
    expect(exe.mode).toBe('Bundled');
    expect(exe.path).not.toBeNull();
  });

  test('Bundled Mode: returns error if missing', () => {
    fs.existsSync.mockImplementation((p) => p === '/mock/config.json');
    fs.readFileSync.mockReturnValue(JSON.stringify({ cliMode: 'Bundled' }));

    const exe = resolveLlmKoshExecutable('/mock/config.json', '/mock/resources');
    expect(exe.mode).toBe('Bundled');
    expect(exe.path).toBeNull();
    expect(exe.error).toBeDefined();
  });

  test('Custom Mode: returns error if missing path', () => {
    fs.existsSync.mockImplementation((p) => p === '/mock/config.json');
    fs.readFileSync.mockReturnValue(JSON.stringify({ cliMode: 'Custom' }));

    const exe = resolveLlmKoshExecutable('/mock/config.json', '/mock/resources');
    expect(exe.mode).toBe('Custom');
    expect(exe.path).toBeNull();
    expect(exe.error).toBeDefined();
  });
});
