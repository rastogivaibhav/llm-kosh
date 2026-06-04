import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { RefreshCw, ClipboardList, Check } from 'lucide-react';

export default function Logs() {
  const [logsData, setLogsData] = useState({ logs: [], config: {}, daemonRunning: false });
  const [copied, setCopied] = useState(false);

  const loadLogs = async () => {
    const data = await api.getLogs();
    if (data.ok) {
      setLogsData(data);
    }
  };

  useEffect(() => {
    loadLogs();
  }, []);

  const handleCopyDiagnostics = async () => {
    const diag = {
      timestamp: new Date().toISOString(),
      config: logsData.config,
      daemonRunning: logsData.daemonRunning,
      recentLogs: logsData.logs
    };
    try {
      await navigator.clipboard.writeText(JSON.stringify(diag, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="p-6 h-full flex flex-col">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-semibold">Logs & Diagnostics</h1>
        <div className="flex gap-2">
          <button 
            onClick={loadLogs}
            className="flex items-center gap-2 text-xs bg-vscode-inputBg hover:bg-vscode-hover text-white px-3 py-1.5 rounded shadow border border-vscode-border transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            Refresh
          </button>
          <button 
            onClick={handleCopyDiagnostics}
            className="flex items-center gap-2 text-xs bg-vscode-buttonPrimary hover:bg-blue-600 text-white px-3 py-1.5 rounded shadow transition-colors"
          >
            {copied ? <Check className="w-3 h-3" /> : <ClipboardList className="w-3 h-3" />}
            {copied ? 'Copied' : 'Copy Diagnostics'}
          </button>
        </div>
      </div>

      <div className="flex-1 flex gap-6 min-h-0">
        <div className="flex-1 flex flex-col min-h-0">
          <h2 className="text-sm font-semibold text-gray-400 uppercase mb-2">Recent CLI Calls</h2>
          <div className="flex-1 bg-[#0d0d0d] p-4 rounded border border-vscode-border overflow-auto font-mono text-xs">
            {logsData.logs.length === 0 ? (
              <span className="text-gray-500">No recent CLI calls logged.</span>
            ) : (
              <ul className="space-y-4">
                {logsData.logs.map((log, i) => (
                  <li key={i} className="border-b border-gray-800 pb-3">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold ${log.ok ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
                        {log.ok ? 'OK' : 'ERR'}
                      </span>
                      <span className="text-blue-300">llm-kosh {log.args?.join(' ')}</span>
                      <span className="text-gray-500 ml-auto">{log.durationMs}ms</span>
                    </div>
                    {log.stdout && <pre className="text-gray-400 mt-2 whitespace-pre-wrap">{log.stdout}</pre>}
                    {log.stderr && <pre className="text-red-400 mt-2 whitespace-pre-wrap">{log.stderr}</pre>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="w-1/3 flex flex-col min-h-0">
          <h2 className="text-sm font-semibold text-gray-400 uppercase mb-2">App Config</h2>
          <div className="bg-[#0d0d0d] p-4 rounded border border-vscode-border font-mono text-xs text-gray-300 whitespace-pre-wrap overflow-auto">
            {JSON.stringify(logsData.config, null, 2)}
          </div>
          
          <h2 className="text-sm font-semibold text-gray-400 uppercase mt-6 mb-2">Daemon Status</h2>
          <div className={`p-4 rounded border font-mono text-xs ${logsData.daemonRunning ? 'bg-green-900/20 border-green-900 text-green-400' : 'bg-vscode-inputBg border-vscode-border text-gray-400'}`}>
            {logsData.daemonRunning ? '● Active process owned by desktop app' : '○ Not running in desktop app'}
          </div>
        </div>
      </div>
    </div>
  );
}
