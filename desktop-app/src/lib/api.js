export const api = {
  ...window.llmKosh,
  daemonOnce: async (rootPath, mode) => window.llmKosh.daemonOnce(rootPath, mode),
  
  startMcp: async (rootPath, options) => window.llmKosh.startMcp(rootPath, options),
  stopMcp: async () => window.llmKosh.stopMcp(),
  getMcpStatus: async () => window.llmKosh.getMcpStatus(),
  onMcpStatusChanged: (cb) => window.llmKosh.onMcpStatusChanged((e, status) => cb(status)),
  onMcpLog: (cb) => window.llmKosh.onMcpLog((e, log) => cb(log)),

  testCli: async () => window.llmKosh.testCli(),
  closeQuickCapture: () => window.llmKosh.closeQuickCapture?.(),
  readDirectory: async (dirPath) => window.llmKosh.readDirectory(dirPath),
};
