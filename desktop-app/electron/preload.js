const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('llmKosh', {
  selectCartridgeRoot: () => ipcRenderer.invoke('select-cartridge-root'),
  createCartridgeRoot: (ownerName) => ipcRenderer.invoke('create-cartridge-root', ownerName),
  getStatus: (rootPath) => ipcRenderer.invoke('get-status', rootPath),
  selectExecutable: () => ipcRenderer.invoke('select-executable'),
  readConfig: () => ipcRenderer.invoke('read-config'),
  writeConfig: (config) => ipcRenderer.invoke('write-config', config),
  revealInFolder: (path) => ipcRenderer.invoke('reveal-in-folder', path),
  selectOutputFolder: () => ipcRenderer.invoke('select-output-folder'),
  generatePack: (rootPath, options) => ipcRenderer.invoke('generate-pack', rootPath, options),
  validatePack: (rootPath, packPath) => ipcRenderer.invoke('validate-pack', rootPath, packPath),
  selectReceiptFile: () => ipcRenderer.invoke('select-receipt-file'),
  readReceiptFile: (filePath) => ipcRenderer.invoke('read-receipt-file', filePath),
  validateReceipt: (rootPath, receiptPath) => ipcRenderer.invoke('validate-receipt', rootPath, receiptPath),
  absorbReceipt: (rootPath, receiptPath) => ipcRenderer.invoke('absorb-receipt', rootPath, receiptPath),
  setLoginItem: (enable) => ipcRenderer.invoke('set-login-item', enable),
  getDaemonStatus: (rootPath) => ipcRenderer.invoke('get-daemon-status', rootPath),
  getLocalDaemonDetails: () => ipcRenderer.invoke('get-local-daemon-details'),
  daemonOnce: (rootPath, mode) => ipcRenderer.invoke('daemon-once', rootPath, mode),
  startDaemon: (rootPath, mode) => ipcRenderer.invoke('start-daemon', rootPath, mode),
  stopDaemon: () => ipcRenderer.invoke('stop-daemon'),
  onDaemonLog: (callback) => {
    const subscription = (event, msg) => callback(msg);
    ipcRenderer.on('daemon-log', subscription);
    return () => {
      ipcRenderer.removeListener('daemon-log', subscription);
    };
  },
  listWatchedFolders: () => ipcRenderer.invoke('list-watched-folders'),
  addWatchedFolder: () => ipcRenderer.invoke('add-watched-folder'),
  removeWatchedFolder: (path) => ipcRenderer.invoke('remove-watched-folder', path),
  testCli: () => ipcRenderer.invoke('test-cli'),
  getLogs: () => ipcRenderer.invoke('get-logs'),
  runSmokeTest: () => ipcRenderer.invoke('run-smoke-test')
});
