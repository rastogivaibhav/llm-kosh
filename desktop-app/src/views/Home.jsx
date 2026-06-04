import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';

export default function Home({ config, setConfig, setStatusMessage }) {
  const [root, setRoot] = useState(config?.cartridgeRoot || '');
  const [statusOutput, setStatusOutput] = useState(null);
  const [loading, setLoading] = useState(false);

  // Daemon state
  const [daemonMode, setDaemonMode] = useState('auto');
  const [daemonStatus, setDaemonStatus] = useState(null);
  const [daemonLogs, setDaemonLogs] = useState('');
  const [isDaemonRunning, setIsDaemonRunning] = useState(false);
  const [daemonLoading, setDaemonLoading] = useState(false);

  // Watched Folders state
  const [watchedFolders, setWatchedFolders] = useState([]);

  const loadWatchedFolders = async () => {
    const res = await api.listWatchedFolders();
    if (res.success) setWatchedFolders(res.folders); // listWatchedFolders still returns { success, folders } natively in main.js without runLlmKosh
  };

  useEffect(() => {
    if (config?.cartridgeRoot) {
      setRoot(config.cartridgeRoot);
      handleRefresh(config.cartridgeRoot);
      handleRefreshDaemon(config.cartridgeRoot);
    }
    loadWatchedFolders();
  }, [config?.cartridgeRoot]);

  useEffect(() => {
    // Subscribe to daemon logs via IPC
    const unsubscribe = api.onDaemonLog((msg) => {
      setDaemonLogs((prev) => {
        const newLog = prev + msg.data;
        // Keep logs from getting too huge
        return newLog.length > 10000 ? newLog.substring(newLog.length - 10000) : newLog;
      });
      if (msg.type === 'exit' || msg.type === 'error') {
        setIsDaemonRunning(false);
      }
    });
    return () => unsubscribe();
  }, []);

  const saveRoot = async (newRoot) => {
    setRoot(newRoot);
    const newConfig = await api.writeConfig({ cartridgeRoot: newRoot });
    setConfig(newConfig);
    handleRefresh(newRoot);
    handleRefreshDaemon(newRoot);
  };

  const handleOpen = async () => {
    const folder = await api.selectCartridgeRoot();
    if (folder) await saveRoot(folder);
  };

  const handleCreate = async () => {
    const ownerName = prompt("Enter owner name (default: 'user'):") || 'user';
    try {
      setStatusMessage('Creating cartridge...');
      setLoading(true);
      const folder = await api.createCartridgeRoot(ownerName);
      if (folder) {
        await saveRoot(folder);
        setStatusMessage('Cartridge created successfully.');
      }
    } catch (e) {
      setStatusMessage('Failed to create cartridge.');
      setStatusOutput(`Error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async (path = root) => {
    if (!path) return;
    setStatusMessage('Checking status...');
    setLoading(true);
    const result = await api.getStatus(path);
    if (result.ok) {
      setStatusOutput(result.stdout);
      setStatusMessage('Status updated.');
    } else {
      setStatusOutput(`Error running status: ${result.stderr}`);
      setStatusMessage('Status failed.');
    }
    setLoading(false);
  };

  const handleRefreshDaemon = async (path = root) => {
    if (!path) return;
    setDaemonLoading(true);
    const result = await api.getDaemonStatus(path);
    setDaemonLoading(false);
    if (result.ok) {
      setDaemonStatus(result.stdout);
      setIsDaemonRunning(result.isLocalRunning);
    } else {
      setDaemonStatus(`Error getting status: ${result.stderr}`);
      setIsDaemonRunning(result.isLocalRunning);
    }
  };

  const handleDaemonOnce = async () => {
    if (!root) return;
    setDaemonLoading(true);
    const result = await api.daemonOnce(root, daemonMode);
    setDaemonLoading(false);
    if (result.ok) {
      setDaemonLogs((prev) => prev + `\n--- RUN ONCE COMPLETE ---\n${result.stdout}\n`);
    } else {
      setDaemonLogs((prev) => prev + `\n--- RUN ONCE ERROR ---\n${result.stderr}\n`);
    }
    handleRefreshDaemon(root);
  };

  const handleToggleDaemon = async () => {
    if (!root) return;
    
    if (isDaemonRunning) {
      const res = await api.stopDaemon();
      if (res.ok) {
        setIsDaemonRunning(false);
        setDaemonLogs((prev) => prev + `\n--- DAEMON STOPPED ---\n`);
      }
    } else {
      const res = await api.startDaemon(root, daemonMode);
      if (res.ok) {
        setIsDaemonRunning(true);
        setDaemonLogs((prev) => prev + `\n--- DAEMON STARTED (${daemonMode}) ---\n`);
      } else {
        setDaemonLogs((prev) => prev + `\n--- DAEMON START ERROR ---\n${res.stderr}\n`);
      }
    }
    handleRefreshDaemon(root);
  };

  const promptDaemonRestart = async () => {
    if (isDaemonRunning) {
      const confirmRestart = window.confirm("Watched folders have changed. Restart the daemon to pick up these changes?");
      if (confirmRestart) {
        await api.stopDaemon();
        setIsDaemonRunning(false);
        setDaemonLogs((prev) => prev + `\n--- RESTARTING DAEMON... ---\n`);
        const res = await api.startDaemon(root, daemonMode);
        if (res.ok) {
          setIsDaemonRunning(true);
          setDaemonLogs((prev) => prev + `\n--- DAEMON STARTED (${daemonMode}) ---\n`);
        } else {
          setDaemonLogs((prev) => prev + `\n--- DAEMON START ERROR ---\n${res.stderr}\n`);
        }
        handleRefreshDaemon(root);
      }
    }
  };

  const handleAddWatchedFolder = async () => {
    const res = await api.addWatchedFolder();
    if (res.success) {
      const foldersChanged = res.folders.length !== watchedFolders.length;
      setWatchedFolders(res.folders);
      if (foldersChanged) await promptDaemonRestart();
    }
  };

  const handleRemoveWatchedFolder = async (path) => {
    const res = await api.removeWatchedFolder(path);
    if (res.success) {
      setWatchedFolders(res.folders);
      await promptDaemonRestart();
    }
  };

  return (
    <div className="p-6 h-full flex flex-col">
      <h1 className="text-2xl font-semibold mb-6">Cartridge & Daemon Control</h1>
      
      <div className="flex space-x-4 mb-8">
        <button 
          onClick={handleOpen}
          className="bg-vscode-buttonPrimary hover:bg-vscode-buttonHover text-white px-4 py-2 rounded shadow transition-colors"
        >
          Open Existing Cartridge
        </button>
        <button 
          onClick={handleCreate}
          className="bg-vscode-inputBg hover:bg-vscode-hover text-white px-4 py-2 rounded shadow border border-vscode-border transition-colors"
        >
          Create New Cartridge
        </button>
      </div>

      <div className="mb-4">
        <h2 className="text-sm font-semibold text-gray-400 uppercase mb-2">Current Context</h2>
        <div className="bg-vscode-inputBg p-3 rounded border border-vscode-border font-mono text-sm break-all">
          {root ? (
            <div className="flex justify-between items-center">
              <span>{root}</span>
              <button 
                onClick={() => api.revealInFolder(root)}
                className="text-vscode-statusBar hover:underline ml-4"
              >
                Reveal
              </button>
            </div>
          ) : (
            <span className="text-gray-500">No cartridge selected</span>
          )}
        </div>
      </div>

      <div className="flex-1 flex gap-6 min-h-0">
        {/* Left Column */}
        <div className="flex-1 flex flex-col min-h-0">
          
          {/* Watched Folders Section */}
          <div className="mb-4">
            <div className="flex justify-between items-center mb-2">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-gray-400 uppercase">Watched Folders</h2>
                {isDaemonRunning && (
                  <span title="Daemon is monitoring these folders" className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_#22c55e]"></span>
                )}
              </div>
              <button 
                onClick={handleAddWatchedFolder}
                className="text-xs bg-vscode-inputBg hover:bg-vscode-hover text-white px-2 py-1 rounded shadow border border-vscode-border transition-colors"
              >
                + Add Folder
              </button>
            </div>
            <div className="bg-vscode-inputBg p-2 rounded border border-vscode-border font-mono text-sm">
              {watchedFolders.length === 0 ? (
                <span className="text-gray-500 p-2 block text-xs">No folders added.</span>
              ) : (
                <ul className="space-y-1">
                  {watchedFolders.map(f => (
                    <li key={f} className="flex justify-between items-center group text-xs bg-[#0d0d0d] p-2 rounded border border-transparent hover:border-vscode-border">
                      <span className="truncate mr-4 text-gray-300" title={f}>📁 {f}</span>
                      <button 
                        onClick={() => handleRemoveWatchedFolder(f)}
                        className="text-red-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Remove folder"
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Cartridge Status Section */}
          <div className="flex-1 flex flex-col min-h-0">
            <div className="flex justify-between items-center mb-2">
              <h2 className="text-sm font-semibold text-gray-400 uppercase">CLI Output</h2>
              <button 
                onClick={() => handleRefresh(root)}
                disabled={!root || loading}
                className="text-xs bg-vscode-inputBg hover:bg-vscode-hover text-white px-2 py-1 rounded shadow border border-vscode-border transition-colors disabled:opacity-50"
              >
                Refresh Status
              </button>
            </div>
            <div className="flex-1 bg-[#0d0d0d] p-4 rounded border border-vscode-border font-mono text-sm overflow-auto text-green-400 whitespace-pre-wrap">
              {loading && !statusOutput ? 'Executing...' : (statusOutput || 'Ready for command execution...')}
            </div>
          </div>
        </div>

        {/* Daemon Control Section */}
        <div className="flex-1 flex flex-col min-h-0 border-l border-vscode-border pl-6">
          <div className="flex justify-between items-center mb-2">
            <h2 className="text-sm font-semibold text-gray-400 uppercase">Daemon Control</h2>
            <span className={`text-xs px-2 py-1 rounded border ${isDaemonRunning ? 'border-green-500 text-green-500' : 'border-gray-500 text-gray-500'}`}>
              {isDaemonRunning ? '● RUNNING' : '○ STOPPED'}
            </span>
          </div>

          <div className="bg-vscode-inputBg p-4 rounded border border-vscode-border mb-4 flex flex-col space-y-4">
            <div className="flex items-center space-x-4">
              <label className="text-sm font-semibold text-gray-400">Mode:</label>
              <select 
                value={daemonMode}
                onChange={(e) => setDaemonMode(e.target.value)}
                disabled={isDaemonRunning || !root}
                className="flex-1 bg-[#0d0d0d] border border-vscode-border rounded p-1 text-sm text-white"
              >
                <option value="auto">auto</option>
                <option value="polling">polling</option>
                <option value="watchdog">watchdog</option>
              </select>
            </div>
            
            <div className="flex space-x-4">
              <button 
                onClick={handleToggleDaemon}
                disabled={!root || daemonLoading}
                className={`flex-1 px-4 py-2 rounded shadow font-semibold transition-colors disabled:opacity-50 ${isDaemonRunning ? 'bg-red-800 hover:bg-red-700 text-white' : 'bg-vscode-buttonPrimary hover:bg-vscode-buttonHover text-white'}`}
              >
                {isDaemonRunning ? 'Stop Daemon' : 'Start Daemon'}
              </button>
              
              <button 
                onClick={handleDaemonOnce}
                disabled={!root || isDaemonRunning || daemonLoading}
                className="flex-1 bg-vscode-inputBg hover:bg-vscode-hover border border-vscode-border text-white px-4 py-2 rounded shadow transition-colors disabled:opacity-50"
              >
                Run Once
              </button>
            </div>
          </div>

          <div className="flex justify-between items-center mb-2 mt-2">
            <h3 className="text-xs font-semibold text-gray-400 uppercase">Daemon Logs</h3>
            <button 
              onClick={() => handleRefreshDaemon(root)}
              disabled={!root || daemonLoading}
              className="text-xs text-vscode-statusBar hover:underline"
            >
              Check Daemon CLI Status
            </button>
          </div>
          
          {daemonStatus && (
            <div className="mb-2 p-2 bg-blue-900/20 border border-blue-900/50 rounded font-mono text-xs text-blue-300">
              {daemonStatus}
            </div>
          )}

          <div className="flex-1 bg-[#0d0d0d] p-4 rounded border border-vscode-border font-mono text-xs overflow-auto text-gray-300 whitespace-pre-wrap flex flex-col-reverse">
            {/* flex-col-reverse keeps it anchored to bottom (latest logs) if logs is just simple text. Actually we can just show logs text directly. */}
            <div>{daemonLogs || 'No logs yet...'}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
