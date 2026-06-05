const { app, BrowserWindow, ipcMain, dialog, shell, Tray, Menu, globalShortcut } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

const isDev = process.env.NODE_ENV === 'development';
const configPath = path.join(app.getPath('userData'), 'llm-kosh-config.json');

const { readConfig: rc, writeConfig: wc } = require('./config-store');
const { resolveLlmKoshExecutable } = require('./cli-resolver');
const readConfig = () => rc(configPath);
const writeConfig = (cfg) => wc(configPath, cfg);

const { daemonManager } = require('./daemon-manager');
const commandLogs = []; // Ring buffer for logs

function addLog(entry) {
  commandLogs.unshift(entry);
  if (commandLogs.length > 50) {
    commandLogs.pop();
  }
}

// Command execution wrapper
function runLlmKosh(command, args, cwd) {
  return new Promise((resolve) => {
    const startTime = Date.now();
    const config = readConfig();
    const resolveResult = resolveLlmKoshExecutable(configPath, process.resourcesPath);
    const exe = resolveResult.path;

    if (!exe) {
      const result = {
        ok: false,
        command: null,
        args: [command, ...(args || [])],
        stdout: '',
        stderr: resolveResult.error || 'Executable not found.',
        exitCode: -1,
        durationMs: Date.now() - startTime
      };
      addLog(result);
      return resolve(result);
    }

    const { buildCommandArgs } = require('./command-builder');
    
    let fullArgs;
    try {
      fullArgs = buildCommandArgs(command, args);
    } catch (err) {
      const result = {
        ok: false,
        command: exe,
        args: [command, ...(args || [])],
        stdout: '',
        stderr: err.message,
        exitCode: -1,
        durationMs: Date.now() - startTime
      };
      addLog(result);
      return resolve(result);
    }
    
    // SECURITY: Use spawn with array arguments, NEVER shell strings
    const proc = spawn(exe, fullArgs, {
      cwd: cwd || app.getPath('home'),
      shell: false 
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      const result = {
        ok: code === 0,
        command: exe,
        args: fullArgs,
        stdout,
        stderr,
        exitCode: code,
        durationMs: Date.now() - startTime
      };
      addLog(result);
      resolve(result);
    });

    proc.on('error', (err) => {
      const result = {
        ok: false,
        command: exe,
        args: fullArgs,
        stdout,
        stderr: `Failed to spawn process: ${err.message}`,
        exitCode: -1,
        durationMs: Date.now() - startTime
      };
      addLog(result);
      resolve(result);
    });
  });
}

let mainWindow = null;
let tray = null;
let quickCaptureWindow = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1024,
    height: 768,
    title: 'llm-kosh',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false, // SECURITY: disabled
    },
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    // mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  mainWindow.on('close', (event) => {
    // If tray exists and we are not quitting, hide window instead
    if (tray && !app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });
}

function createQuickCaptureWindow() {
  // If already open, bring to front and refocus
  if (quickCaptureWindow && !quickCaptureWindow.isDestroyed()) {
    quickCaptureWindow.focus();
    return;
  }

  const { screen } = require('electron');
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  const winWidth = 620;
  const winHeight = 160;

  quickCaptureWindow = new BrowserWindow({
    width: winWidth,
    height: winHeight,
    x: Math.round((width - winWidth) / 2),
    y: Math.round(height * 0.28), // 28% from top — spotlight-style
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    title: 'Quick Capture',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    quickCaptureWindow.loadURL('http://localhost:5173/?quick=1');
  } else {
    quickCaptureWindow.loadFile(path.join(__dirname, '../dist/index.html'), {
      query: { quick: '1' }
    });
  }

  // Close on blur — dismiss when user clicks away
  quickCaptureWindow.on('blur', () => {
    if (quickCaptureWindow && !quickCaptureWindow.isDestroyed()) {
      quickCaptureWindow.close();
    }
  });

  quickCaptureWindow.on('closed', () => {
    quickCaptureWindow = null;
  });
}

// IPC: renderer can close the quick capture window after submit
ipcMain.on('close-quick-capture', () => {
  if (quickCaptureWindow && !quickCaptureWindow.isDestroyed()) {
    quickCaptureWindow.close();
  }
});

function updateTrayMenu() {
  if (!tray) return;
  const status = daemonManager.getStatus();
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Open llm-kosh', click: () => { mainWindow?.show(); } },
    { type: 'separator' },
    { label: `Daemon: ${status.running ? 'Running' : 'Stopped'}`, enabled: false },
    { 
      label: status.running ? 'Stop Daemon' : 'Start Daemon', 
      click: () => {
        if (status.running) {
          daemonManager.stop();
        } else {
          const cfg = readConfig();
          if (cfg.cartridgeRoot) {
            daemonManager.start(configPath, process.resourcesPath, cfg.cartridgeRoot, cfg.daemonMode || 'auto');
          }
        }
        updateTrayMenu();
      } 
    },
    { type: 'separator' },
    { 
      label: 'Quit', 
      click: () => {
        app.isQuitting = true;
        app.quit();
      } 
    }
  ]);
  tray.setToolTip('llm-kosh memory cartridge');
  tray.setContextMenu(contextMenu);
}

app.whenReady().then(() => {
  createWindow();

  // Setup Tray
  const iconPath = isDev 
    ? path.join(__dirname, '../build/icon.png')
    : path.join(process.resourcesPath, 'icon.png');
    
  if (fs.existsSync(iconPath)) {
    tray = new Tray(iconPath);
    tray.on('click', () => {
      mainWindow?.show();
    });
    updateTrayMenu();
  }

  // Subscribe to daemon events to update tray
  daemonManager.subscribe((eventName) => {
    if (eventName === 'daemon-status-changed') {
      updateTrayMenu();
    }
  });

  // Handle Auto-start features
  const config = readConfig();
  if (config.startOnLogin !== undefined) {
    app.setLoginItemSettings({ openAtLogin: config.startOnLogin });
  }

  if (config.autoStartDaemon && config.cartridgeRoot) {
    daemonManager.start(configPath, process.resourcesPath, config.cartridgeRoot, config.daemonMode || 'auto');
  }

  // Register global Quick Capture hotkey
  const registered = globalShortcut.register('CommandOrControl+Shift+Space', () => {
    createQuickCaptureWindow();
  });
  if (!registered) {
    console.warn('Quick Capture hotkey (Ctrl+Shift+Space) could not be registered — may be taken by another app.');
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    } else {
      mainWindow?.show();
    }
  });
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
});

app.on('window-all-closed', () => {
  daemonManager.stop();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC Handlers
ipcMain.handle('select-cartridge-root', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory']
  });
  return result.filePaths[0] || null;
});

ipcMain.handle('create-cartridge-root', async (event, ownerName) => {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory'],
    title: 'Select Folder for New Cartridge'
  });
  const folder = result.filePaths[0];
  if (folder) {
    const res = await runLlmKosh('init', ['--root', folder, '--owner', ownerName || 'user']);
    return { ok: res.ok, folder, ...res };
  }
  return { ok: false, folder: null, stderr: 'Cancelled' };
});

ipcMain.handle('get-status', async (event, rootPath) => {
  return await runLlmKosh('status', ['--root', rootPath]);
});

ipcMain.handle('select-executable', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openFile']
  });
  return result.filePaths[0] || null;
});

ipcMain.handle('set-login-item', (event, enable) => {
  app.setLoginItemSettings({ openAtLogin: enable });
  return { ok: true };
});

ipcMain.handle('read-config', () => {
  return readConfig();
});

ipcMain.handle('write-config', (event, config) => {
  return writeConfig(config);
});

ipcMain.handle('reveal-in-folder', (event, pathToReveal) => {
  shell.showItemInFolder(pathToReveal);
});

ipcMain.handle('select-output-folder', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory'],
    title: 'Select Output Folder for Pack'
  });
  return result.filePaths[0] || null;
});

ipcMain.handle('generate-pack', async (event, rootPath, options) => {
  const command = options.safePack ? 'safe-pack' : 'pack';
  const args = ['--root', rootPath];

  if (options.query) {
    args.push(options.query);
  } else {
    return { ok: false, stderr: "Query is required" };
  }

  const allowedTargets = ['chatgpt', 'claude', 'gemini', 'deepseek', 'codex', 'human'];
  if (!allowedTargets.includes(options.target)) {
    return { ok: false, stderr: `Invalid target: ${options.target}` };
  }
  args.push('--for', options.target);

  if (options.budget) {
    args.push('--budget', options.budget);
  }

  if (options.includePrivate) {
    args.push('--include-private');
  }

  let outPath = null;
  if (options.outputFolder) {
    outPath = path.join(options.outputFolder, `context_${Date.now()}.zip`);
    args.push('--out', outPath);
  }

  const res = await runLlmKosh(command, args);
  return { ...res, outPath };
});

ipcMain.handle('validate-pack', async (event, rootPath, packPath) => {
  return await runLlmKosh('validate-pack', ['--root', rootPath, packPath]);
});

ipcMain.handle('select-receipt-file', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openFile'],
    filters: [{ name: 'Markdown Files', extensions: ['md'] }],
    title: 'Select MEMORY_RECEIPT.md'
  });
  return result.filePaths[0] || null;
});

ipcMain.handle('read-receipt-file', (event, filePath) => {
  try {
    if (fs.existsSync(filePath)) {
      return { success: true, content: fs.readFileSync(filePath, 'utf8') };
    }
    return { success: false, error: 'File not found' };
  } catch (err) {
    return { success: false, error: err.message };
  }
});

ipcMain.handle('validate-receipt', async (event, rootPath, receiptPath) => {
  return await runLlmKosh('validate-receipt', ['--root', rootPath, receiptPath]);
});

ipcMain.handle('absorb-receipt', async (event, rootPath, receiptPath) => {
  return await runLlmKosh('absorb', ['--root', rootPath, receiptPath]);
});

ipcMain.handle('get-daemon-status', async (event, rootPath) => {
  const isLocalRunning = daemonManager.getStatus().running;
  const res = await runLlmKosh('daemon', ['status', '--root', rootPath]);
  return { ...res, isLocalRunning };
});

ipcMain.handle('get-local-daemon-details', () => {
  return daemonManager.getStatus();
});

ipcMain.handle('daemon-once', async (event, rootPath, mode) => {
  const args = ['once', '--root', rootPath];
  if (mode) args.push('--mode', mode);
  return await runLlmKosh('daemon', args);
});

ipcMain.handle('start-daemon', async (event, rootPath, mode) => {
  const config = readConfig();
  const daemonMode = mode || config.daemonMode || 'auto';
  
  if (daemonManager.getStatus().running) {
    return { ok: false, stderr: 'Daemon is already running in this app instance.' };
  }
  
  // Forward logs from daemonManager to the renderer
  daemonManager.subscribe((eventName, payload) => {
    if (eventName === 'daemon-log') {
      try { event.sender.send('daemon-log', { type: payload.type, data: payload.message }); } catch (e) {}
    }
  });

  return daemonManager.start(configPath, process.resourcesPath, rootPath, daemonMode);
});

ipcMain.handle('stop-daemon', () => {
  return daemonManager.stop();
});

ipcMain.handle('get-logs', () => {
  const config = readConfig();
  // Sanitize config - remove any hypothetical secrets if added later
  const safeConfig = { ...config };
  return {
    ok: true,
    logs: commandLogs,
    config: safeConfig,
    daemonRunning: daemonManager.getStatus().running
  };
});

ipcMain.handle('test-cli', () => {
  return new Promise((resolve) => {
    const resolveResult = resolveLlmKoshExecutable(configPath, process.resourcesPath);
    const exe = resolveResult.path;

    if (!exe) {
      return resolve({
        ok: false,
        executablePath: null,
        mode: resolveResult.mode,
        stdout: '',
        stderr: resolveResult.error || 'Executable not found.',
        exitCode: -1
      });
    }

    // Create a mini-script to run help and version
    const procVersion = spawn(exe, ['--version'], { shell: false });
    let versionStdout = '';
    procVersion.stdout.on('data', d => versionStdout += d.toString());
    
    procVersion.on('close', () => {
      const proc = spawn(exe, ['--help'], { shell: false });
      
      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (data) => stdout += data.toString());
      proc.stderr.on('data', (data) => stderr += data.toString());

      proc.on('close', (code) => {
        resolve({
          ok: code === 0,
          executablePath: exe,
          mode: resolveResult.mode,
          version: versionStdout.trim(),
          stdout,
          stderr,
          exitCode: code
        });
      });

      proc.on('error', (err) => {
        resolve({
          ok: false,
          executablePath: exe,
          mode: resolveResult.mode,
          version: versionStdout.trim(),
          stdout: '',
          stderr: err.message,
          exitCode: -1
        });
      });
    });

    procVersion.on('error', (err) => {
      resolve({
        ok: false,
        executablePath: exe,
        mode: resolveResult.mode,
        version: '',
        stdout: '',
        stderr: err.message,
        exitCode: -1
      });
    });
  });
});

ipcMain.handle('list-watched-folders', () => {
  const config = readConfig();
  if (!config.cartridgeRoot) return { success: false, folders: [] };
  const policyPath = path.join(config.cartridgeRoot, 'LLM_KOSH_POLICY.json');
  try {
    if (fs.existsSync(policyPath)) {
      const pol = JSON.parse(fs.readFileSync(policyPath, 'utf8'));
      return { success: true, folders: pol?.daemon?.watched_directories || [] };
    }
  } catch (e) {}
  return { success: true, folders: [] };
});

ipcMain.handle('add-watched-folder', async () => {
  const result = await dialog.showOpenDialog({ properties: ['openDirectory'] });
  if (!result.canceled && result.filePaths.length > 0) {
    const selected = result.filePaths[0];
    const config = readConfig();
    if (!config.cartridgeRoot) return { success: false, folders: [] };
    const policyPath = path.join(config.cartridgeRoot, 'LLM_KOSH_POLICY.json');
    let pol = {};
    try {
      if (fs.existsSync(policyPath)) pol = JSON.parse(fs.readFileSync(policyPath, 'utf8'));
    } catch (e) {}
    
    if (!pol.daemon) pol.daemon = {};
    if (!pol.daemon.watched_directories) pol.daemon.watched_directories = [];
    
    if (!pol.daemon.watched_directories.includes(selected)) {
      pol.daemon.watched_directories.push(selected);
      fs.writeFileSync(policyPath, JSON.stringify(pol, null, 2));
    }
    return { success: true, folders: pol.daemon.watched_directories };
  }
  return { success: false, folders: [] };
});

ipcMain.handle('remove-watched-folder', (event, folderPath) => {
  const config = readConfig();
  if (!config.cartridgeRoot) return { success: false, folders: [] };
  const policyPath = path.join(config.cartridgeRoot, 'LLM_KOSH_POLICY.json');
  let pol = {};
  try {
    if (fs.existsSync(policyPath)) pol = JSON.parse(fs.readFileSync(policyPath, 'utf8'));
  } catch (e) {}
  
  if (!pol.daemon) pol.daemon = {};
  if (!pol.daemon.watched_directories) pol.daemon.watched_directories = [];
  
  pol.daemon.watched_directories = pol.daemon.watched_directories.filter(f => f !== folderPath);
  fs.writeFileSync(policyPath, JSON.stringify(pol, null, 2));
  return { success: true, folders: pol.daemon.watched_directories };
});

ipcMain.handle('run-smoke-test', async () => {
  const { runSmokeTestSequence } = require('./smoke-test');
  return await runSmokeTestSequence(resolveLlmKoshExecutable(configPath, process.resourcesPath).path);
});

// MCP Server Manager
let mcpProcess = null;
let mcpLogs = [];
let mcpStatus = { running: false, pid: null, startTime: null, lastEvent: null };

function broadcastMcpLog(type, message) {
  const entry = { type, message, timestamp: Date.now() };
  mcpLogs.push(entry);
  if (mcpLogs.length > 100) mcpLogs.shift();
  if (mainWindow) {
    try { mainWindow.webContents.send('mcp-log', entry); } catch (e) {}
  }
}

ipcMain.handle('get-mcp-status', () => {
  return { ...mcpStatus, logs: [...mcpLogs].reverse() };
});

ipcMain.handle('start-mcp', async (event, rootPath, options) => {
  if (mcpProcess) {
    return { ok: false, error: 'MCP server already running' };
  }
  
  const resolveResult = resolveLlmKoshExecutable(configPath, process.resourcesPath);
  if (!resolveResult.path) {
    return { ok: false, error: 'Executable not found' };
  }

  const args = ['mcp', '--root', rootPath];
  if (options?.allowWrite) args.push('--allow-write');
  if (options?.allowMutate) args.push('--allow-mutate');
  if (options?.allowPrivate) args.push('--allow-private');

  mcpLogs = [];
  mcpStatus = { running: true, pid: null, startTime: Date.now(), lastEvent: 'Started MCP Server' };
  
  broadcastMcpLog('system', `Spawning: llm-kosh ${args.join(' ')}`);

  mcpProcess = spawn(resolveResult.path, args, {
    cwd: app.getPath('home'),
    shell: false
  });

  mcpStatus.pid = mcpProcess.pid;

  mcpProcess.stdout.on('data', (data) => broadcastMcpLog('stdout', data.toString()));
  mcpProcess.stderr.on('data', (data) => broadcastMcpLog('stderr', data.toString()));

  mcpProcess.on('close', (code) => {
    mcpStatus = { running: false, pid: null, startTime: null, lastEvent: `Exited with code ${code}` };
    mcpProcess = null;
    broadcastMcpLog('system', `MCP Process exited with code ${code}`);
    if (mainWindow) {
      try { mainWindow.webContents.send('mcp-status-changed', mcpStatus); } catch (e) {}
    }
  });

  return { ok: true };
});

ipcMain.handle('stop-mcp', () => {
  if (mcpProcess) {
    broadcastMcpLog('system', 'Sending kill signal to MCP Process');
    mcpProcess.kill();
    mcpProcess = null;
    mcpStatus = { running: false, pid: null, startTime: null, lastEvent: 'Stopped manually' };
  }
  return { ok: true };
});

// Generic command runner for the UI to access full CLI capabilities
ipcMain.handle('run-kosh-command', async (event, rootPath, command, args) => {
  // Safe generic execution since runLlmKosh prevents shell injection
  const fullArgs = ['--root', rootPath, ...(args || [])];
  return await runLlmKosh(command, fullArgs);
});
