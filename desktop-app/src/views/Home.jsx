import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { Activity, Folder, Terminal, Play, Square, Settings, RefreshCcw } from 'lucide-react';

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

  // MCP State
  const [mcpStatus, setMcpStatus] = useState(null);
  const [mcpLogs, setMcpLogs] = useState('');
  const [mcpOptions, setMcpOptions] = useState({ allowWrite: false, allowMutate: false, allowPrivate: false });
  const [isMcpRunning, setIsMcpRunning] = useState(false);
  const [mcpLoading, setMcpLoading] = useState(false);

  const loadWatchedFolders = async () => {
    const res = await api.listWatchedFolders();
    if (res.success) setWatchedFolders(res.folders);
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
    const unsubscribe = api.onDaemonLog((msg) => {
      setDaemonLogs((prev) => {
        const newLog = prev + msg.data;
        return newLog.length > 10000 ? newLog.substring(newLog.length - 10000) : newLog;
      });
      if (msg.type === 'exit' || msg.type === 'error') {
        setIsDaemonRunning(false);
      }
    });

    const mcpSub = api.onMcpLog((msg) => {
      setMcpLogs((prev) => {
        const line = `[${new Date(msg.timestamp).toLocaleTimeString()}] [${msg.type}] ${msg.message}\n`;
        const newLog = prev + line;
        return newLog.length > 10000 ? newLog.substring(newLog.length - 10000) : newLog;
      });
    });

    const mcpStatusSub = api.onMcpStatusChanged((status) => {
      setMcpStatus(status);
      setIsMcpRunning(status.running);
    });

    return () => { unsubscribe(); mcpSub(); mcpStatusSub(); };
  }, []);

  const handleRefreshMcp = async () => {
    setMcpLoading(true);
    const result = await api.getMcpStatus();
    setMcpLoading(false);
    setMcpStatus(result);
    setIsMcpRunning(result.running);
    if (result.logs) {
      setMcpLogs(result.logs.map(msg => `[${new Date(msg.timestamp).toLocaleTimeString()}] [${msg.type}] ${msg.message}`).join('\n') + '\n');
    }
  };

  useEffect(() => {
    handleRefreshMcp();
  }, []);

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

  const handleToggleDaemon = async () => {
    if (!root) return;
    if (isDaemonRunning) {
      const res = await api.stopDaemon();
      if (res.ok) {
        setIsDaemonRunning(false);
        setDaemonLogs((prev) => prev + `\n[System] Daemon stopped.\n`);
      }
    } else {
      const res = await api.startDaemon(root, daemonMode);
      if (res.ok) {
        setIsDaemonRunning(true);
        setDaemonLogs((prev) => prev + `\n[System] Daemon started (${daemonMode}).\n`);
      } else {
        setDaemonLogs((prev) => prev + `\n[Error] Daemon start failed: ${res.stderr}\n`);
      }
    }
    handleRefreshDaemon(root);
  };

  const handleAddWatchedFolder = async () => {
    const res = await api.addWatchedFolder();
    if (res.success) {
      setWatchedFolders(res.folders);
    }
  };

  const handleRemoveWatchedFolder = async (path) => {
    const res = await api.removeWatchedFolder(path);
    if (res.success) {
      setWatchedFolders(res.folders);
    }
  };

  const handleToggleMcp = async () => {
    if (!root) return;
    setMcpLoading(true);
    if (isMcpRunning) {
      await api.stopMcp();
    } else {
      const res = await api.startMcp(root, mcpOptions);
      if (!res.ok) {
        setMcpLogs(prev => prev + `[System] Failed to start MCP: ${res.error}\n`);
      }
    }
    await handleRefreshMcp();
    setMcpLoading(false);
  };

  return (
    <div className="p-8 h-full flex flex-col bg-brand-bg overflow-y-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-brand-text flex items-center gap-3">
            <Activity className="text-brand-accent" size={28} />
            System Dashboard
          </h1>
          <p className="text-brand-muted mt-1">Real-time telemetry and daemon control</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* Cartridge Context Card */}
        <div className="bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted flex items-center gap-2">
              <Folder size={16} /> Active Cartridge
            </h2>
            <button 
              onClick={() => api.revealInFolder(root)}
              className="text-brand-accent hover:text-brand-accentHover text-sm font-medium transition-colors"
            >
              Reveal in OS
            </button>
          </div>
          <div className="bg-brand-surface p-4 rounded-xl border border-brand-border font-mono text-sm break-all text-brand-text mb-4 flex-1">
            {root || <span className="text-brand-muted italic">No cartridge selected</span>}
          </div>
          <div className="flex justify-between items-center mt-auto">
             <span className="text-xs font-semibold text-brand-muted uppercase">Health Status</span>
             <button 
                onClick={() => handleRefresh(root)}
                disabled={loading}
                className="flex items-center gap-2 text-xs font-semibold bg-brand-surface hover:bg-brand-border text-brand-text px-3 py-1.5 rounded-lg border border-brand-border transition-colors disabled:opacity-50"
             >
                <RefreshCcw size={14} className={loading ? "animate-spin" : ""} /> Refresh
             </button>
          </div>
        </div>

        {/* Daemon Pulse Card */}
        <div className="bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted flex items-center gap-2">
              <Activity size={16} /> Daemon Pulse
            </h2>
            <div className={`flex items-center gap-2 px-3 py-1 rounded-full border text-xs font-bold ${isDaemonRunning ? 'border-brand-success/30 text-brand-success bg-brand-success/10' : 'border-brand-muted/30 text-brand-muted bg-brand-muted/10'}`}>
              <div className={`w-2 h-2 rounded-full ${isDaemonRunning ? 'bg-brand-success animate-pulse' : 'bg-brand-muted'}`}></div>
              {isDaemonRunning ? 'ACTIVE' : 'IDLE'}
            </div>
          </div>
          
          <div className="flex items-center gap-4 mb-6">
             <div className="flex-1">
               <label className="text-xs font-semibold text-brand-muted uppercase mb-1 block">Operation Mode</label>
               <select 
                  value={daemonMode}
                  onChange={(e) => setDaemonMode(e.target.value)}
                  disabled={isDaemonRunning || !root}
                  className="w-full bg-brand-surface border border-brand-border rounded-xl p-2.5 text-sm font-medium text-brand-text focus:outline-none focus:border-brand-accent transition-colors"
                >
                  <option value="auto">Auto (Events + Polling)</option>
                  <option value="watchdog">Watchdog (Events Only)</option>
                  <option value="polling">Polling (Timed Only)</option>
                </select>
             </div>
             <div className="pt-5">
               <button 
                  onClick={handleToggleDaemon}
                  disabled={!root || daemonLoading}
                  className={`flex items-center gap-2 px-6 py-2.5 rounded-xl font-bold transition-all shadow-sm ${
                    isDaemonRunning 
                    ? 'bg-brand-surface text-brand-danger border border-brand-danger/30 hover:bg-brand-danger/10' 
                    : 'bg-brand-accent text-white hover:bg-brand-accentHover hover:shadow-md'
                  }`}
                >
                  {isDaemonRunning ? <><Square size={16} fill="currentColor" /> Stop</> : <><Play size={16} fill="currentColor" /> Start</>}
                </button>
             </div>
          </div>

          <div className="mt-auto">
             <h3 className="text-xs font-semibold text-brand-muted uppercase mb-2">Background Watched Folders</h3>
             <div className="flex flex-wrap gap-2">
               {watchedFolders.length === 0 ? (
                 <span className="text-xs text-brand-muted italic">No external folders watched.</span>
               ) : (
                 watchedFolders.map(f => (
                   <div key={f} className="group flex items-center gap-2 bg-brand-surface border border-brand-border px-3 py-1.5 rounded-lg text-xs font-mono text-brand-text">
                     <span className="truncate max-w-[150px]" title={f}>{f.split('\\').pop() || f.split('/').pop()}</span>
                     <button onClick={() => handleRemoveWatchedFolder(f)} className="text-brand-muted hover:text-brand-danger opacity-0 group-hover:opacity-100 transition-opacity">×</button>
                   </div>
                 ))
               )}
               <button onClick={handleAddWatchedFolder} className="text-xs font-bold text-brand-accent hover:text-brand-accentHover px-3 py-1.5 rounded-lg border border-dashed border-brand-accent/50 hover:bg-brand-accent/5 transition-colors">
                 + Add
               </button>
             </div>
          </div>
        </div>

        {/* MCP Protocol Card */}
        <div className="bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted flex items-center gap-2">
              <Terminal size={16} /> MCP Server
            </h2>
            <div className={`flex items-center gap-2 px-3 py-1 rounded-full border text-xs font-bold ${isMcpRunning ? 'border-brand-success/30 text-brand-success bg-brand-success/10' : 'border-brand-muted/30 text-brand-muted bg-brand-muted/10'}`}>
              <div className={`w-2 h-2 rounded-full ${isMcpRunning ? 'bg-brand-success animate-pulse' : 'bg-brand-muted'}`}></div>
              {isMcpRunning ? 'ONLINE' : 'OFFLINE'}
            </div>
          </div>
          
          <div className="flex flex-col gap-3 mb-6 flex-1">
             <label className="flex items-center gap-2 text-sm text-brand-text font-medium cursor-pointer">
               <input type="checkbox" checked={mcpOptions.allowWrite} onChange={(e) => setMcpOptions({...mcpOptions, allowWrite: e.target.checked})} disabled={isMcpRunning} className="rounded border-brand-border text-brand-accent bg-brand-surface focus:ring-brand-accent" />
               Allow Write (Receipts)
             </label>
             <label className="flex items-center gap-2 text-sm text-brand-text font-medium cursor-pointer">
               <input type="checkbox" checked={mcpOptions.allowMutate} onChange={(e) => setMcpOptions({...mcpOptions, allowMutate: e.target.checked})} disabled={isMcpRunning} className="rounded border-brand-border text-brand-accent bg-brand-surface focus:ring-brand-accent" />
               Allow Mutation (Healing)
             </label>
             <label className="flex items-center gap-2 text-sm text-brand-text font-medium cursor-pointer">
               <input type="checkbox" checked={mcpOptions.allowPrivate} onChange={(e) => setMcpOptions({...mcpOptions, allowPrivate: e.target.checked})} disabled={isMcpRunning} className="rounded border-brand-border text-brand-accent bg-brand-surface focus:ring-brand-accent" />
               Expose Private Memories
             </label>
          </div>
          <div className="pt-2 mt-auto">
            <button 
              onClick={handleToggleMcp}
              disabled={!root || mcpLoading}
              className={`w-full flex justify-center items-center gap-2 px-6 py-2.5 rounded-xl font-bold transition-all shadow-sm ${
                isMcpRunning 
                ? 'bg-brand-surface text-brand-danger border border-brand-danger/30 hover:bg-brand-danger/10' 
                : 'bg-brand-accent text-white hover:bg-brand-accentHover hover:shadow-md'
              }`}
            >
              {isMcpRunning ? <><Square size={16} fill="currentColor" /> Stop Server</> : <><Play size={16} fill="currentColor" /> Start Server</>}
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-[300px]">
        {/* System Status Output */}
        <div className="bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col">
          <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted flex items-center gap-2 mb-4">
             <Terminal size={16} /> Ledger Status
          </h2>
          <div className="flex-1 bg-[#1C1917] p-4 rounded-xl border border-[#2D1B14] font-mono text-xs overflow-auto text-brand-success whitespace-pre-wrap shadow-inner">
             {loading && !statusOutput ? 'Scanning ledger...' : (statusOutput || 'Ledger status ready...')}
          </div>
        </div>

        {/* Daemon Logs */}
        <div className="bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col">
          <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted flex items-center gap-2 mb-4">
             <Terminal size={16} /> Daemon Output
          </h2>
          <div className="flex-1 bg-[#1C1917] p-4 rounded-xl border border-[#2D1B14] font-mono text-xs overflow-auto text-[#E2E8F0] whitespace-pre-wrap shadow-inner flex flex-col-reverse">
             <div>{daemonLogs || 'Listening for events...'}</div>
          </div>
        </div>

        {/* MCP Logs */}
        <div className="bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col">
          <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted flex items-center gap-2 mb-4">
             <Terminal size={16} /> MCP Output
          </h2>
          <div className="flex-1 bg-[#1C1917] p-4 rounded-xl border border-[#2D1B14] font-mono text-xs overflow-auto text-[#E2E8F0] whitespace-pre-wrap shadow-inner flex flex-col-reverse">
             <div>{mcpLogs || 'MCP offline...'}</div>
          </div>
        </div>
      </div>

    </div>
  );
}
