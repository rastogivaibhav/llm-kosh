const fs = require('fs');
const path = require('path');

describe('Preload APIs', () => {
  test('exposes all required IPC endpoints securely', () => {
    const preloadContent = fs.readFileSync(path.join(__dirname, '../electron/preload.js'), 'utf8');
    
    const requiredEndpoints = [
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
      'removeWatchedFolder',
      'testCli',
      'getLogs',
      'runSmokeTest'
    ];

    requiredEndpoints.forEach(endpoint => {
      expect(preloadContent).toMatch(new RegExp(`${endpoint}:`));
    });
  });
});
