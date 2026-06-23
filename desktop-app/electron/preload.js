const { contextBridge, ipcRenderer } = require('electron');

const e2eMode = process.env.LLM_KOSH_E2E_MODE || '';

const e2eBridge = e2eMode
  ? {
      selectCartridgeRoot: async () => 'C:\\e2e\\root',
      createCartridgeRoot: async () => ({ ok: true, folder: 'C:\\e2e\\root' }),
      getStatus: async () => ({ ok: true, stdout: 'E2E status ok' }),
      selectExecutable: async () => 'llm-kosh',
      readConfig: async () => (
        e2eMode === 'onboarding'
          ? {}
          : {
              cartridgeRoot: 'C:\\e2e\\root',
              executablePath: 'llm-kosh',
              cliMode: 'Auto',
              daemonMode: 'auto',
            }
      ),
      writeConfig: async (config) => config,
      readCartridgeConfig: async () => ({ schema: 'llm-kosh.v0', version: '1.0.0', retrieval_weights: {} }),
      writeCartridgeConfig: async (rootPath, config) => config,
      revealInFolder: () => {},
      selectOutputFolder: async () => 'C:\\e2e\\exports',
      generatePack: async () => ({ ok: true, outPath: 'C:\\e2e\\exports\\pack.zip', stdout: 'Pack created' }),
      validatePack: async () => ({ ok: true, stdout: 'Pack valid' }),
      selectReceiptFile: async () => 'C:\\e2e\\receipt.md',
      readReceiptFile: async () => ({ success: true, content: '# MEMORY_RECEIPT\n' }),
      validateReceipt: async () => ({ ok: true, stdout: 'Receipt valid' }),
      absorbReceipt: async () => ({ ok: true, stdout: 'Receipt absorbed' }),
      setLoginItem: async () => ({ ok: true }),
      getServiceStatus: async () => ({ ok: true, isLocalRunning: false, stdout: 'Service stopped' }),
      getDaemonStatus: async () => ({ ok: true, isLocalRunning: false, stdout: 'Daemon stopped' }),
      getLocalServiceDetails: async () => ({ running: false }),
      getLocalDaemonDetails: async () => ({ running: false }),
      serviceOnce: async () => ({ ok: true, stdout: 'Service ran once' }),
      daemonOnce: async () => ({ ok: true, stdout: 'Daemon ran once' }),
      startMcp: async () => ({ ok: true }),
      stopMcp: async () => ({ ok: true }),
      getMcpStatus: async () => ({
        running: false,
        pid: null,
        startTime: null,
        lastEvent: 'Idle',
        logs: [],
      }),
      onMcpStatusChanged: () => () => {},
      onMcpLog: () => () => {},
      startService: async () => ({ ok: true }),
      startDaemon: async () => ({ ok: true }),
      stopService: async () => ({ ok: true }),
      stopDaemon: async () => ({ ok: true }),
      onServiceLog: () => () => {},
      onDaemonLog: () => () => {},
      listWatchedFolders: async () => ({ success: true, folders: [] }),
      addWatchedFolder: async () => ({ success: true, folders: ['C:\\e2e\\watched'] }),
      removeWatchedFolder: async () => ({ success: true, folders: [] }),
      readDirectory: async () => ({ success: true, items: [] }),
      testCli: async () => (
        e2eMode === 'onboarding'
          ? { ok: false, executablePath: null, mode: 'Auto', stderr: 'llm-kosh CLI not detected for E2E', exitCode: -1 }
          : { ok: true, executablePath: 'llm-kosh', mode: 'Bundled', version: '2.1.1', stdout: 'llm-kosh 2.1.1', stderr: '', exitCode: 0 }
      ),
      getLogs: async () => ({ ok: true, logs: [], config: {}, daemonRunning: false }),
      runSmokeTest: async () => ([
        { ok: true, step: 'create-temp-root', stdout: 'C:\\e2e\\root' },
        { ok: true, step: 'init' },
        { ok: true, step: 'status' },
        { ok: true, step: 'safe-pack' },
        { ok: true, step: 'validate-pack' },
        { ok: true, step: 'validate-receipt' },
        { ok: true, step: 'absorb' },
        { ok: true, step: 'service' },
        { ok: true, step: 'daemon' },
      ]),
      runKoshCommand: async () => ({ ok: true, stdout: 'Mock query output' }),
      installKosh: async () => ({ ok: true, stderr: '' }),
      uninstallKosh: async () => ({ ok: true, stderr: '' }),
      closeQuickCapture: () => {},
    }
  : null;

function subscribe(channel, callback) {
  const listener = (_event, payload) => callback(payload);
  ipcRenderer.on(channel, listener);
  return () => ipcRenderer.removeListener(channel, listener);
}

const liveBridge = {
  selectCartridgeRoot: () => ipcRenderer.invoke('select-cartridge-root'),
  createCartridgeRoot: (ownerName) => ipcRenderer.invoke('create-cartridge-root', ownerName),
  getStatus: (rootPath) => ipcRenderer.invoke('get-status', rootPath),
  selectExecutable: () => ipcRenderer.invoke('select-executable'),
  setLoginItem: (enable) => ipcRenderer.invoke('set-login-item', enable),
  readConfig: () => ipcRenderer.invoke('read-config'),
  writeConfig: (config) => ipcRenderer.invoke('write-config', config),
  readCartridgeConfig: (rootPath) => ipcRenderer.invoke('read-cartridge-config', rootPath),
  writeCartridgeConfig: (rootPath, config) => ipcRenderer.invoke('write-cartridge-config', rootPath, config),
  revealInFolder: (pathToReveal) => ipcRenderer.invoke('reveal-in-folder', pathToReveal),
  selectOutputFolder: () => ipcRenderer.invoke('select-output-folder'),
  generatePack: (rootPath, options) => ipcRenderer.invoke('generate-pack', rootPath, options),
  validatePack: (rootPath, packPath) => ipcRenderer.invoke('validate-pack', rootPath, packPath),
  selectReceiptFile: () => ipcRenderer.invoke('select-receipt-file'),
  readReceiptFile: (filePath) => ipcRenderer.invoke('read-receipt-file', filePath),
  validateReceipt: (rootPath, receiptPath) => ipcRenderer.invoke('validate-receipt', rootPath, receiptPath),
  absorbReceipt: (rootPath, receiptPath) => ipcRenderer.invoke('absorb-receipt', rootPath, receiptPath),
  getServiceStatus: (rootPath) => ipcRenderer.invoke('get-service-status', rootPath),
  getDaemonStatus: (rootPath) => ipcRenderer.invoke('get-daemon-status', rootPath),
  getLocalServiceDetails: () => ipcRenderer.invoke('get-local-service-details'),
  getLocalDaemonDetails: () => ipcRenderer.invoke('get-local-daemon-details'),
  serviceOnce: (rootPath, mode) => ipcRenderer.invoke('service-once', rootPath, mode),
  daemonOnce: (rootPath, mode) => ipcRenderer.invoke('daemon-once', rootPath, mode),
  startService: (rootPath, mode) => ipcRenderer.invoke('start-service', rootPath, mode),
  startDaemon: (rootPath, mode) => ipcRenderer.invoke('start-daemon', rootPath, mode),
  stopService: () => ipcRenderer.invoke('stop-service'),
  stopDaemon: () => ipcRenderer.invoke('stop-daemon'),
  onServiceLog: (callback) => subscribe('service-log', callback),
  onDaemonLog: (callback) => subscribe('daemon-log', callback),
  getLogs: () => ipcRenderer.invoke('get-logs'),
  testCli: () => ipcRenderer.invoke('test-cli'),
  listWatchedFolders: () => ipcRenderer.invoke('list-watched-folders'),
  readDirectory: (dirPath) => ipcRenderer.invoke('read-directory', dirPath),
  addWatchedFolder: () => ipcRenderer.invoke('add-watched-folder'),
  removeWatchedFolder: (folderPath) => ipcRenderer.invoke('remove-watched-folder', folderPath),
  runSmokeTest: () => ipcRenderer.invoke('run-smoke-test'),
  getMcpStatus: () => ipcRenderer.invoke('get-mcp-status'),
  startMcp: (rootPath, options) => ipcRenderer.invoke('start-mcp', rootPath, options),
  stopMcp: () => ipcRenderer.invoke('stop-mcp'),
  onMcpStatusChanged: (callback) => subscribe('mcp-status-changed', callback),
  onMcpLog: (callback) => subscribe('mcp-log', callback),
  runKoshCommand: (rootPath, command, args) => ipcRenderer.invoke('run-kosh-command', rootPath, command, args),
  installKosh: () => ipcRenderer.invoke('install-kosh'),
  uninstallKosh: () => ipcRenderer.invoke('uninstall-kosh'),
  closeQuickCapture: () => ipcRenderer.send('close-quick-capture'),
};

const bridge = e2eBridge || liveBridge;

contextBridge.exposeInMainWorld('llmKosh', bridge);
