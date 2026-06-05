import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { Settings as SettingsIcon, Save, TerminalSquare, FolderOpen, ShieldCheck, HardDrive, TestTube, AlertCircle, CheckCircle, RefreshCcw } from 'lucide-react';

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

  const handleSelectExport = async () => {
    const path = await api.selectOutputFolder();
    if (path) {
      setFormData(prev => ({ ...prev, defaultExportFolder: path }));
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setStatusMessage('Saving config...');
    const newConfig = await api.writeConfig(formData);
    if (newConfig) {
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
    <div className="p-8 h-full flex flex-col bg-brand-bg overflow-y-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-brand-text flex items-center gap-3">
            <SettingsIcon className="text-brand-accent" size={28} />
            App Configuration
          </h1>
          <p className="text-brand-muted mt-1">Manage CLI integrations, workspace roots, and daemon behaviors.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 max-w-6xl">
        {/* Left Column: Form Settings */}
        <div className="flex flex-col gap-6">
          <form onSubmit={handleSave} className="flex flex-col gap-6">
            
            {/* Engine & CLI */}
            <div className="bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col gap-5">
              <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted flex items-center gap-2">
                <TerminalSquare size={16} /> Engine Bindings
              </h2>
              
              <div className="flex flex-col gap-2">
                <label className="text-xs font-bold text-brand-muted uppercase">CLI Resolution Mode</label>
                <select
                  name="cliMode"
                  value={formData.cliMode}
                  onChange={handleChange}
                  className="w-full bg-brand-surface border border-brand-border rounded-xl p-3 text-brand-text text-sm focus:outline-none focus:border-brand-accent transition-colors"
                >
                  <option value="Auto">Auto (Priority: Custom &gt; Bundled &gt; System)</option>
                  <option value="Bundled">Bundled Sidecar</option>
                  <option value="System PATH">System PATH</option>
                  <option value="Custom">Custom Path</option>
                </select>
              </div>

              {formData.cliMode === 'Custom' && (
                <div className="flex flex-col gap-2">
                  <label className="text-xs font-bold text-brand-muted uppercase">Custom Executable Path</label>
                  <div className="flex gap-2">
                    <input 
                      type="text" 
                      name="executablePath"
                      value={formData.executablePath}
                      onChange={handleChange}
                      className="flex-1 bg-brand-surface border border-brand-border rounded-xl p-3 text-brand-text font-mono text-xs focus:outline-none focus:border-brand-accent transition-colors"
                      placeholder="/path/to/venv/bin/llm-kosh"
                    />
                    <button 
                      type="button"
                      onClick={handleSelectExe}
                      className="bg-brand-surface border border-brand-border hover:bg-brand-border text-brand-text px-4 py-2 rounded-xl text-sm transition-colors shadow-sm font-bold"
                    >
                      Browse
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Storage Paths */}
            <div className="bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col gap-5">
              <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted flex items-center gap-2">
                <HardDrive size={16} /> Storage Paths
              </h2>
              
              <div className="flex flex-col gap-2">
                <label className="text-xs font-bold text-brand-muted uppercase">Default Cartridge Root</label>
                <div className="flex gap-2">
                  <input 
                    type="text" 
                    name="cartridgeRoot"
                    value={formData.cartridgeRoot}
                    onChange={handleChange}
                    className="flex-1 bg-brand-surface border border-brand-border rounded-xl p-3 text-brand-text font-mono text-xs focus:outline-none focus:border-brand-accent transition-colors"
                    placeholder="/path/to/cartridge"
                  />
                  <button 
                    type="button"
                    onClick={handleSelectRoot}
                    className="bg-brand-surface border border-brand-border hover:bg-brand-border text-brand-text px-4 py-2 rounded-xl text-sm transition-colors shadow-sm font-bold"
                  >
                    Browse
                  </button>
                </div>
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-xs font-bold text-brand-muted uppercase">Default Export Folder</label>
                <div className="flex gap-2">
                  <input 
                    type="text" 
                    name="defaultExportFolder"
                    value={formData.defaultExportFolder}
                    onChange={handleChange}
                    className="flex-1 bg-brand-surface border border-brand-border rounded-xl p-3 text-brand-text font-mono text-xs focus:outline-none focus:border-brand-accent transition-colors"
                    placeholder="/path/to/exports"
                  />
                  <button 
                    type="button"
                    onClick={handleSelectExport}
                    className="bg-brand-surface border border-brand-border hover:bg-brand-border text-brand-text px-4 py-2 rounded-xl text-sm transition-colors shadow-sm font-bold"
                  >
                    Browse
                  </button>
                </div>
              </div>
            </div>

            {/* Behaviors */}
            <div className="bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col gap-5">
              <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted flex items-center gap-2">
                <ShieldCheck size={16} /> Automation & OS
              </h2>
              
              <div className="flex flex-col gap-4">
                <label className="flex items-center gap-3 cursor-pointer group">
                  <input 
                    type="checkbox" 
                    name="startOnLogin"
                    checked={formData.startOnLogin}
                    onChange={handleChange}
                    className="w-4 h-4 text-brand-accent bg-brand-surface border-brand-border rounded focus:ring-brand-accent"
                  />
                  <span className="text-sm font-semibold text-brand-text group-hover:text-brand-accent transition-colors">Start llm-kosh Desktop on system login</span>
                </label>

                <label className="flex items-center gap-3 cursor-pointer group">
                  <input 
                    type="checkbox" 
                    name="autoStartDaemon"
                    checked={formData.autoStartDaemon}
                    onChange={handleChange}
                    className="w-4 h-4 text-brand-accent bg-brand-surface border-brand-border rounded focus:ring-brand-accent"
                  />
                  <span className="text-sm font-semibold text-brand-text group-hover:text-brand-accent transition-colors">Automatically start Daemon when app opens</span>
                </label>

                <label className="flex items-center gap-3 cursor-pointer group">
                  <input 
                    type="checkbox" 
                    name="daemonNotifications"
                    checked={formData.daemonNotifications}
                    onChange={handleChange}
                    className="w-4 h-4 text-brand-accent bg-brand-surface border-brand-border rounded focus:ring-brand-accent"
                  />
                  <span className="text-sm font-semibold text-brand-text group-hover:text-brand-accent transition-colors">Enable desktop notifications for Daemon events</span>
                </label>
              </div>

              <div className="flex flex-col gap-2 mt-2 border-t border-brand-border pt-4">
                <label className="text-xs font-bold text-brand-muted uppercase">Daemon Startup Mode</label>
                <select
                  name="daemonMode"
                  value={formData.daemonMode}
                  onChange={handleChange}
                  className="w-full bg-brand-surface border border-brand-border rounded-xl p-3 text-brand-text text-sm focus:outline-none focus:border-brand-accent transition-colors"
                >
                  <option value="auto">Auto (Default)</option>
                  <option value="polling">Polling (Fallback)</option>
                  <option value="watchdog">Watchdog (High Performance)</option>
                </select>
              </div>
            </div>

            <button 
              type="submit"
              className="flex items-center justify-center gap-2 w-full bg-brand-accent hover:bg-brand-accentHover text-white px-6 py-4 rounded-xl shadow-sm transition-colors font-bold"
            >
              <Save size={18} /> Apply Config
            </button>
          </form>
        </div>

        {/* Right Column: Diagnostics */}
        <div className="flex flex-col gap-6">
          <div className="bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col gap-4">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted flex items-center gap-2">
                <TestTube size={16} /> Engine Diagnostics
              </h2>
              <button onClick={checkCliHealth} className="text-brand-muted hover:text-brand-accent transition-colors">
                <RefreshCcw size={16} />
              </button>
            </div>
            
            {cliHealth ? (
              <div className={`p-4 rounded-xl border font-mono text-sm leading-relaxed ${cliHealth.ok ? 'bg-brand-success/10 border-brand-success/20 text-brand-success' : 'bg-brand-danger/10 border-brand-danger/20 text-brand-danger'}`}>
                <div className="font-bold flex items-center gap-2 mb-2">
                  {cliHealth.ok ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
                  CLI Health: {cliHealth.ok ? 'ONLINE' : 'ERROR'}
                </div>
                <div><span className="opacity-75">Mode:</span> {cliHealth.mode}</div>
                <div className="truncate"><span className="opacity-75">Path:</span> {cliHealth.executablePath || 'None'}</div>
                {cliHealth.version && <div><span className="opacity-75">Version:</span> {cliHealth.version}</div>}
                {!cliHealth.ok && cliHealth.stderr && (
                  <div className="mt-4 p-3 bg-black/20 rounded-lg text-xs opacity-90 whitespace-pre-wrap">{cliHealth.stderr}</div>
                )}
              </div>
            ) : (
              <p className="text-brand-muted italic text-sm">Checking CLI Status...</p>
            )}

            <button 
              type="button"
              onClick={handleRunSmokeTest}
              disabled={runningSmokeTest}
              className="mt-4 flex items-center justify-center gap-2 w-full bg-brand-surface border border-brand-border hover:bg-brand-border text-brand-text px-4 py-3 rounded-xl transition-colors font-bold disabled:opacity-50"
            >
              <TestTube size={16} />
              {runningSmokeTest ? 'Running Suite...' : 'Run Local Smoke Test'}
            </button>
          </div>

          {smokeTestResults && (
            <div className="bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col min-h-[300px]">
              <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted flex items-center gap-2 mb-4">
                <TerminalSquare size={16} /> Test Results
              </h2>
              <div className="flex-1 bg-[#1C1917] rounded-xl border border-[#2D1B14] p-4 font-mono text-xs space-y-4 overflow-auto shadow-inner">
                {smokeTestResults.map((res, i) => (
                  <div key={i} className="border-b border-[#2D1B14] pb-4 last:border-0 last:pb-0">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider ${res.ok ? 'bg-brand-success/20 text-brand-success' : 'bg-brand-danger/20 text-brand-danger'}`}>
                        {res.ok ? 'PASS' : 'FAIL'}
                      </span>
                      <span className="font-bold text-brand-text">{res.step}</span>
                      {res.durationMs && <span className="text-brand-muted opacity-50 ml-auto">{res.durationMs}ms</span>}
                    </div>
                    {res.error && <div className="text-brand-danger ml-12 whitespace-pre-wrap">{res.error}</div>}
                    {res.stderr && <div className="text-brand-danger ml-12 whitespace-pre-wrap opacity-80">{res.stderr}</div>}
                    {res.stdout && <div className="text-brand-muted ml-12 whitespace-pre-wrap leading-relaxed">{res.stdout.substring(0, 500)}{res.stdout.length > 500 ? '...' : ''}</div>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
