import React, { useState, useEffect } from 'react';
import { Play, Square, RefreshCw, Activity } from 'lucide-react';
import { api } from '../lib/api';

export default function Daemon({ config }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchStatus = async () => {
    try {
      const st = await api.getLocalDaemonDetails();
      setStatus(st);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleStart = async () => {
    setLoading(true);
    await api.startDaemon(config.cartridgeRoot, config.daemonMode || 'auto');
    await fetchStatus();
    setLoading(false);
  };

  const handleStop = async () => {
    setLoading(true);
    await api.stopDaemon();
    await fetchStatus();
    setLoading(false);
  };

  const handleRunOnce = async () => {
    setLoading(true);
    await api.daemonOnce(config.cartridgeRoot, config.daemonMode || 'auto');
    setLoading(false);
  };

  if (!config?.cartridgeRoot) {
    return (
      <div className="p-6 h-full flex items-center justify-center text-gray-500">
        Please configure a cartridge root in settings first.
      </div>
    );
  }

  const isRunning = status?.running;
  const uptimeStr = status?.uptimeMs ? new Date(status.uptimeMs).toISOString().substr(11, 8) : '00:00:00';

  return (
    <div className="flex flex-col h-full bg-vscode-bg">
      <div className="flex items-center justify-between p-4 border-b border-vscode-border">
        <h1 className="text-xl font-semibold flex items-center gap-2">
          <Activity size={20} className={isRunning ? 'text-green-500' : 'text-gray-500'} />
          Daemon Manager
        </h1>
        <div className="flex gap-2">
          {isRunning ? (
            <button
              onClick={handleStop}
              disabled={loading}
              className="flex items-center gap-2 px-3 py-1.5 bg-red-900/50 hover:bg-red-900 text-red-200 rounded border border-red-800 transition-colors disabled:opacity-50"
            >
              <Square size={16} fill="currentColor" /> Stop Daemon
            </button>
          ) : (
            <button
              onClick={handleStart}
              disabled={loading}
              className="flex items-center gap-2 px-3 py-1.5 bg-green-900/50 hover:bg-green-900 text-green-200 rounded border border-green-800 transition-colors disabled:opacity-50"
            >
              <Play size={16} fill="currentColor" /> Start Daemon
            </button>
          )}
          <button
            onClick={handleRunOnce}
            disabled={loading || isRunning}
            className="flex items-center gap-2 px-3 py-1.5 bg-vscode-buttonPrimary hover:bg-vscode-buttonHover text-white rounded transition-colors disabled:opacity-50"
            title="Runs the daemon loop exactly once and exits"
          >
            <RefreshCw size={16} /> Run Once
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4 flex flex-col gap-4">
        {/* Status Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded border border-vscode-border bg-[#0a0a0a]">
            <div className="text-xs text-gray-500 uppercase font-semibold mb-1">Status</div>
            <div className={`font-mono text-lg ${isRunning ? 'text-green-400' : 'text-gray-400'}`}>
              {isRunning ? 'RUNNING' : 'STOPPED'}
            </div>
          </div>
          <div className="p-4 rounded border border-vscode-border bg-[#0a0a0a]">
            <div className="text-xs text-gray-500 uppercase font-semibold mb-1">PID</div>
            <div className="font-mono text-lg text-gray-300">{status?.pid || '---'}</div>
          </div>
          <div className="p-4 rounded border border-vscode-border bg-[#0a0a0a]">
            <div className="text-xs text-gray-500 uppercase font-semibold mb-1">Uptime</div>
            <div className="font-mono text-lg text-gray-300">{isRunning ? uptimeStr : '---'}</div>
          </div>
          <div className="p-4 rounded border border-vscode-border bg-[#0a0a0a]">
            <div className="text-xs text-gray-500 uppercase font-semibold mb-1">Mode</div>
            <div className="font-mono text-lg text-gray-300">{config.daemonMode || 'auto'}</div>
          </div>
        </div>

        {status?.lastError && (
          <div className="p-4 rounded border border-red-800 bg-red-900/20 text-red-200 text-sm">
            <strong>Last Error:</strong> {status.lastError}
          </div>
        )}
        
        {status?.lastEvent && (
          <div className="p-4 rounded border border-blue-800 bg-blue-900/20 text-blue-200 text-sm">
            <strong>Last Event:</strong> {status.lastEvent}
          </div>
        )}

        <div className="flex-1 flex flex-col min-h-0 border border-vscode-border rounded overflow-hidden">
          <div className="bg-vscode-inputBg px-3 py-2 text-xs font-semibold text-gray-400 border-b border-vscode-border flex justify-between">
            <span>Daemon Logs</span>
            <span>Last 50 entries</span>
          </div>
          <div className="flex-1 overflow-auto p-2 bg-[#050505] font-mono text-xs">
            {status?.logs?.length ? (
              [...status.logs].reverse().map((log, i) => (
                <div key={i} className="mb-1 flex gap-2">
                  <span className="text-gray-600 shrink-0">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                  <span className={
                    log.type === 'error' || log.type === 'stderr' ? 'text-red-400' :
                    log.type === 'system' ? 'text-blue-400' : 'text-gray-300'
                  }>
                    {log.message.trim()}
                  </span>
                </div>
              ))
            ) : (
              <div className="text-gray-600 p-2">No logs yet...</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
