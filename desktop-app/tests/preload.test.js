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

  test('production bridge forwards calls through context-isolated IPC', async () => {
    const invoke = jest.fn(async () => ({ ok: true }));
    const send = jest.fn();
    const on = jest.fn();
    const removeListener = jest.fn();
    const exposeInMainWorld = jest.fn();
    const previousE2E = process.env.LLM_KOSH_E2E_MODE;
    delete process.env.LLM_KOSH_E2E_MODE;

    jest.resetModules();
    jest.doMock('electron', () => ({
      contextBridge: { exposeInMainWorld },
      ipcRenderer: { invoke, send, on, removeListener },
    }));

    require('../electron/preload');
    const bridge = exposeInMainWorld.mock.calls[0][1];

    await bridge.getStatus('C:\\cartridge');
    expect(invoke).toHaveBeenCalledWith('get-status', 'C:\\cartridge');

    bridge.closeQuickCapture();
    expect(send).toHaveBeenCalledWith('close-quick-capture');

    const callback = jest.fn();
    const unsubscribe = bridge.onServiceLog(callback);
    expect(on).toHaveBeenCalledWith('service-log', expect.any(Function));
    unsubscribe();
    expect(removeListener).toHaveBeenCalledWith('service-log', expect.any(Function));

    if (previousE2E === undefined) delete process.env.LLM_KOSH_E2E_MODE;
    else process.env.LLM_KOSH_E2E_MODE = previousE2E;
  });
});
