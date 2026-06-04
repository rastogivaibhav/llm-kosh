import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';

export default function Settings({ config, setConfig, setStatusMessage }) {
  const [formData, setFormData] = useState({
    executablePath: 'llm-kosh',
    cartridgeRoot: '',
    defaultExportFolder: ''
  });
  
  const [cliHealth, setCliHealth] = useState(null);
  const [runningSmokeTest, setRunningSmokeTest] = useState(false);
  const [smokeTestResults, setSmokeTestResults] = useState(null);

  useEffect(() => {
    if (config) {
      setFormData({
        cliMode: config.cliMode || 'Auto',
        executablePath: config.executablePath || 'llm-kosh',
        cartridgeRoot: config.cartridgeRoot || '',
        defaultExportFolder: config.defaultExportFolder || '',
        autoStartDaemon: config.autoStartDaemon || false,
        startOnLogin: config.startOnLogin || false,
        daemonMode: config.daemonMode || 'auto',
        daemonNotifications: config.daemonNotifications !== false
      });
    }
    // Check health on load
    checkCliHealth();
  }, [config]);

  const checkCliHealth = async () => {
    const res = await api.testCli();
    setCliHealth(res);
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({ 
      ...prev, 
      [name]: type === 'checkbox' ? checked : value 
    }));
  };

  const handleSelectExe = async () => {
    const path = await api.selectExecutable();
    if (path) {
      setFormData(prev => ({ ...prev, executablePath: path, cliMode: 'Custom' }));
    }
  };

  const handleSelectRoot = async () => {
    const path = await api.selectCartridgeRoot();
    if (path) {
      setFormData(prev => ({ ...prev, cartridgeRoot: path }));
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setStatusMessage('Saving config...');
    const newConfig = await api.writeConfig(formData);
    if (newConfig) {
      // update login item if supported
      await api.setLoginItem(formData.startOnLogin);
      setConfig(newConfig);
      setStatusMessage('Settings saved successfully.');
      checkCliHealth();
    } else {
      setStatusMessage('Failed to save settings.');
    }
  };

  const handleRunSmokeTest = async () => {
    setRunningSmokeTest(true);
    setSmokeTestResults(null);
    setStatusMessage('Running End-to-End Smoke Test...');
    const results = await api.runSmokeTest();
    setSmokeTestResults(results);
    setRunningSmokeTest(false);
    setStatusMessage('Smoke test completed.');
  };

  return (
    <div className="p-6 h-full overflow-y-auto">
      <h1 className="text-2xl font-semibold mb-6">Settings</h1>

      <form onSubmit={handleSave} className="space-y-6 max-w-2xl">
        <div className="flex flex-col space-y-2">
          <label className="text-sm font-semibold text-gray-400">CLI Resolution Mode</label>
          <select
            name="cliMode"
            value={formData.cliMode}
            onChange={handleChange}
            className="w-full bg-vscode-inputBg border border-vscode-border rounded p-2 text-white font-mono text-sm focus:outline-none focus:border-vscode-statusBar"
          >
            <option value="Auto">Auto (Priority: Custom &gt; Bundled &gt; System)</option>
            <option value="Bundled">Bundled Sidecar</option>
            <option value="System PATH">System PATH</option>
            <option value="Custom">Custom Path</option>
          </select>
        </div>

        {formData.cliMode === 'Custom' && (
          <div className="flex flex-col space-y-2">
            <label className="text-sm font-semibold text-gray-400">Custom Executable Path</label>
            <div className="flex space-x-2">
              <input 
                type="text" 
                name="executablePath"
                value={formData.executablePath}
                onChange={handleChange}
                className="flex-1 bg-vscode-inputBg border border-vscode-border rounded p-2 text-white font-mono text-sm focus:outline-none focus:border-vscode-statusBar"
                placeholder="e.g. /path/to/venv/bin/llm-kosh"
              />
              <button 
                type="button"
                onClick={handleSelectExe}
                className="bg-vscode-buttonPrimary hover:bg-vscode-buttonHover px-4 py-2 rounded text-sm transition-colors shadow"
              >
                Browse
              </button>
            </div>
            <p className="text-xs text-gray-500">Path to the llm-kosh executable or python script.</p>
          </div>
        )}

        {cliHealth && (
          <div className={`p-3 rounded border text-sm flex flex-col gap-1 ${cliHealth.ok ? 'bg-green-900/20 border-green-800 text-green-400' : 'bg-red-900/20 border-red-800 text-red-400'}`}>
            <div className="font-semibold flex items-center justify-between">
              <span>CLI Health: {cliHealth.ok ? 'OK' : 'Error'}</span>
              <button type="button" onClick={checkCliHealth} className="text-xs underline opacity-75 hover:opacity-100">Refresh</button>
            </div>
            <div><span className="opacity-75">Mode:</span> {cliHealth.mode}</div>
            <div><span className="opacity-75">Resolved Path:</span> {cliHealth.executablePath || 'None'}</div>
            {cliHealth.version && <div><span className="opacity-75">Version:</span> {cliHealth.version}</div>}
            {!cliHealth.ok && cliHealth.stderr && (
              <div className="mt-2 text-xs opacity-75 whitespace-pre-wrap">{cliHealth.stderr}</div>
            )}
          </div>
        )}

        <div className="flex flex-col space-y-2">
          <label className="text-sm font-semibold text-gray-400">Default Cartridge Root</label>
          <div className="flex space-x-2">
            <input 
              type="text" 
              name="cartridgeRoot"
              value={formData.cartridgeRoot}
              onChange={handleChange}
              className="flex-1 bg-vscode-inputBg border border-vscode-border rounded p-2 text-white font-mono text-sm focus:outline-none focus:border-vscode-statusBar"
              placeholder="/path/to/cartridge"
            />
            <button 
              type="button"
              onClick={handleSelectRoot}
              className="bg-vscode-buttonPrimary hover:bg-vscode-buttonHover px-4 py-2 rounded text-sm transition-colors shadow"
            >
              Browse
            </button>
          </div>
        </div>

        <div className="flex flex-col space-y-2">
          <label className="text-sm font-semibold text-gray-400">Default Export Folder</label>
          <input 
            type="text" 
            name="defaultExportFolder"
            value={formData.defaultExportFolder}
            onChange={handleChange}
            className="w-full bg-vscode-inputBg border border-vscode-border rounded p-2 text-white font-mono text-sm focus:outline-none focus:border-vscode-statusBar"
            placeholder="/path/to/exports"
          />
        </div>

        <div className="flex flex-col space-y-2 pt-6 border-t border-vscode-border">
          <h2 className="text-lg font-semibold text-white mb-2">App & Daemon Behavior</h2>
          
          <label className="flex items-center space-x-2 text-sm text-gray-300">
            <input 
              type="checkbox" 
              name="startOnLogin"
              checked={formData.startOnLogin}
              onChange={handleChange}
              className="rounded bg-vscode-inputBg border-vscode-border"
            />
            <span>Start llm-kosh Desktop on system login</span>
          </label>

          <label className="flex items-center space-x-2 text-sm text-gray-300">
            <input 
              type="checkbox" 
              name="autoStartDaemon"
              checked={formData.autoStartDaemon}
              onChange={handleChange}
              className="rounded bg-vscode-inputBg border-vscode-border"
            />
            <span>Automatically start Daemon when app opens</span>
          </label>

          <label className="flex items-center space-x-2 text-sm text-gray-300">
            <input 
              type="checkbox" 
              name="daemonNotifications"
              checked={formData.daemonNotifications}
              onChange={handleChange}
              className="rounded bg-vscode-inputBg border-vscode-border"
            />
            <span>Enable desktop notifications for Daemon receipt events</span>
          </label>
        </div>

        <div className="flex flex-col space-y-2">
          <label className="text-sm font-semibold text-gray-400">Daemon Startup Mode</label>
          <select
            name="daemonMode"
            value={formData.daemonMode}
            onChange={handleChange}
            className="w-full bg-vscode-inputBg border border-vscode-border rounded p-2 text-white font-mono text-sm focus:outline-none focus:border-vscode-statusBar"
          >
            <option value="auto">Auto (Default)</option>
            <option value="polling">Polling</option>
            <option value="watchdog">Watchdog</option>
          </select>
          <p className="text-xs text-gray-500">Determines how the daemon monitors files. Changes apply next time daemon starts.</p>
        </div>

        <div className="pt-4 border-t border-vscode-border">
          <button 
            type="submit"
            className="bg-vscode-buttonPrimary hover:bg-vscode-buttonHover text-white px-6 py-2 rounded shadow transition-colors font-semibold mr-4"
          >
            Save Settings
          </button>
          <button 
            type="button"
            onClick={handleRunSmokeTest}
            disabled={runningSmokeTest}
            className="bg-vscode-inputBg hover:bg-vscode-hover border border-vscode-border text-white px-6 py-2 rounded shadow transition-colors font-semibold disabled:opacity-50"
          >
            {runningSmokeTest ? 'Running Smoke Test...' : 'Run Local Smoke Test'}
          </button>
        </div>
      </form>

      {smokeTestResults && (
        <div className="mt-8 max-w-2xl">
          <h2 className="text-xl font-semibold mb-4">Smoke Test Results</h2>
          <div className="bg-[#0d0d0d] rounded border border-vscode-border p-4 font-mono text-sm space-y-4">
            {smokeTestResults.map((res, i) => (
              <div key={i} className="border-b border-vscode-border pb-4 last:border-0 last:pb-0">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-bold ${res.ok ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
                    {res.ok ? 'PASS' : 'FAIL'}
                  </span>
                  <span className="font-bold text-gray-300">Step: {res.step}</span>
                  {res.durationMs && <span className="text-gray-500 text-xs ml-auto">{res.durationMs}ms</span>}
                </div>
                {res.error && <div className="text-red-400 ml-12 text-xs">{res.error}</div>}
                {res.stderr && <div className="text-red-400 ml-12 text-xs whitespace-pre-wrap">{res.stderr}</div>}
                {res.stdout && <div className="text-gray-400 ml-12 text-xs whitespace-pre-wrap">{res.stdout.substring(0, 500)}{res.stdout.length > 500 ? '...' : ''}</div>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
