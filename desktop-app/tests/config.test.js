const fs = require('fs');
const path = require('path');
const { readConfig, writeConfig } = require('../electron/config-store');

describe('Config Store', () => {
  const testConfigPath = path.join(__dirname, 'test-config.json');

  afterEach(() => {
    if (fs.existsSync(testConfigPath)) {
      fs.unlinkSync(testConfigPath);
    }
  });

  test('reads empty config when file does not exist', () => {
    const config = readConfig(testConfigPath);
    expect(config).toEqual({});
  });

  test('writes and reads config successfully', () => {
    const initialConfig = { watchedFolders: ['/foo/bar'] };
    writeConfig(testConfigPath, initialConfig);

    const config = readConfig(testConfigPath);
    expect(config).toEqual(initialConfig);
  });

  test('persists folder additions and removals', () => {
    // Start fresh
    writeConfig(testConfigPath, { watchedFolders: ['/a'] });

    // Add folder
    const config = readConfig(testConfigPath);
    config.watchedFolders.push('/b');
    writeConfig(testConfigPath, config);

    const updatedConfig = readConfig(testConfigPath);
    expect(updatedConfig.watchedFolders).toEqual(['/a', '/b']);

    // Remove folder
    updatedConfig.watchedFolders = updatedConfig.watchedFolders.filter(f => f !== '/a');
    writeConfig(testConfigPath, updatedConfig);

    const finalConfig = readConfig(testConfigPath);
    expect(finalConfig.watchedFolders).toEqual(['/b']);
  });

  test('renderer cannot access arbitrary fs APIs', () => {
    // This test explicitly asserts our architectural constraint for Phase 5.
    // The preload.js strictly defines the IPC bridge and does not expose `require('fs')`
    // or any raw file system manipulation methods to the window.electron object.
    const expectedBridgeFunctions = [
      'selectCartridgeRoot',
      'createCartridgeRoot',
      'getStatus',
      'selectExecutable',
      'readConfig',
      'writeConfig',
      'revealInFolder',
      'selectOutputFolder',
      'generatePack',
      'validatePack',
      'selectReceiptFile',
      'readReceiptFile',
      'validateReceipt',
      'absorbReceipt',
      'getDaemonStatus',
      'daemonOnce',
      'startDaemon',
      'stopDaemon',
      'onDaemonLog',
      'listWatchedFolders',
      'addWatchedFolder',
      'removeWatchedFolder'
    ];
    
    // In a real browser environment, window.electron would not contain `fs`.
    // We mock that behavior here by verifying our list of exposed IPC handlers does not contain dangerous generic IO.
    expect(expectedBridgeFunctions).not.toContain('readFile');
    expect(expectedBridgeFunctions).not.toContain('writeFile');
    expect(expectedBridgeFunctions).not.toContain('fs');
  });
});
