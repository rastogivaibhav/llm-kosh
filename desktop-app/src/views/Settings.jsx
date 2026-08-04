import React, { useState, useEffect, useRef } from 'react';
import { api } from '../lib/api';
import { Settings as SettingsIcon, Save, TerminalSquare, FolderOpen, ShieldCheck, HardDrive, TestTube, AlertCircle, CheckCircle, RefreshCcw, Plug, Copy, Play, Square, ClipboardCheck } from 'lucide-react';

export default function Settings({ config, setConfig, setStatusMessage }) {
  const [formData, setFormData] = useState({
    executablePath: 'llm-kosh',
    cartridgeRoot: '',
    defaultExportFolder: ''
  });
  
  const [cliHealth, setCliHealth] = useState(null);
  const [runningSmokeTest, setRunningSmokeTest] = useState(false);
  const [smokeTestResults, setSmokeTestResults] = useState(null);
  const [serviceLoading, setServiceLoading] = useState(false);

  // MCP Panel State
  const [mcpStatus, setMcpStatus] = useState({ running: false, pid: null });
  const [mcpLogs, setMcpLogs] = useState([]);
  const [mcpLoading, setMcpLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const mcpLogEndRef = useRef(null);
  const [mcpOptions, setMcpOptions] = useState({ allowWrite: false, allowMutate: false, allowPrivate: false });

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
    loadMcpStatus();
  }, [config]);

  const loadMcpStatus = async () => {
    const st = await api.getMcpStatus();
    if (st) {
      setMcpStatus(st);
      if (st.logs) setMcpLogs(st.logs);
    }
  };

  useEffect(() => {
    const unsub = api.onMcpLog((entry) => {
      setMcpLogs(prev => [...prev.slice(-99), entry]);
    });
    const unsubStatus = api.onMcpStatusChanged((st) => {
      setMcpStatus(st);
    });
    return () => { unsub?.(); unsubStatus?.(); };
  }, []);

  useEffect(() => {
    mcpLogEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [mcpLogs]);

  const handleStartMcp = async () => {
    setMcpLoading(true);
    setMcpLogs([]);
    const root = formData.cartridgeRoot || config?.cartridgeRoot;
    await api.startMcp(root, mcpOptions);
    await loadMcpStatus();
    setMcpLoading(false);
  };

  const handleStopMcp = async () => {
    setMcpLoading(true);
    await api.stopMcp();
    await loadMcpStatus();
    setMcpLoading(false);
  };

  const getMcpConfigJson = () => {
    const root = formData.cartridgeRoot || config?.cartridgeRoot || 'C:\\path\\to\\your\\cartridge';
    const exe = formData.executablePath || 'llm-kosh';
    const args = ['--root', root, 'mcp-server'];
    if (mcpOptions.allowWrite) args.push('--allow-write');
    if (mcpOptions.allowMutate) args.push('--allow-mutate');
    if (mcpOptions.allowPrivate) args.push('--allow-private');
    return JSON.stringify({
      mcpServers: {
        'llm-kosh': { command: exe, args }
      }
    }, null, 2);
  };

  const handleCopyConfig = async () => {
    try {
      await navigator.clipboard.writeText(getMcpConfigJson());
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch(e) {}
  };

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

  const handleInstallKosh = async () => {
    setServiceLoading(true);
    setStatusMessage('Installing llm-kosh...');
    const res = await api.installKosh();
    setServiceLoading(false);
    setStatusMessage(res?.ok ? 'llm-kosh installed.' : `Install failed: ${res?.stderr || 'unknown error'}`);
    checkCliHealth();
  };

  const handleUninstallKosh = async () => {
    setServiceLoading(true);
    setStatusMessage('Uninstalling llm-kosh...');
    const res = await api.uninstallKosh();
    setServiceLoading(false);
    setStatusMessage(res?.ok ? 'llm-kosh uninstalled.' : `Uninstall failed: ${res?.stderr || 'unknown error'}`);
    checkCliHealth();
  };

  return (
    <div className="p-8 h-full flex flex-col bg-brand-bg overflow-y-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-brand-text flex items-center gap-3">
            <SettingsIcon className="text-brand-accent" size={28} />
            App Configuration
          </h1>
          <p className="text-brand-muted mt-1">Manage CLI integrations, workspace roots, and service behaviors.</p>
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
                  <span className="text-sm font-semibold text-brand-text group-hover:text-brand-accent transition-colors">Automatically start the background service when app opens</span>
                </label>

                <label className="flex items-center gap-3 cursor-pointer group">
                  <input 
                    type="checkbox" 
                    name="daemonNotifications"
                    checked={formData.daemonNotifications}
                    onChange={handleChange}
                    className="w-4 h-4 text-brand-accent bg-brand-surface border-brand-border rounded focus:ring-brand-accent"
                  />
                  <span className="text-sm font-semibold text-brand-text group-hover:text-brand-accent transition-colors">Enable desktop notifications for service events</span>
                </label>
              </div>

              <div className="flex flex-col gap-2 mt-2 border-t border-brand-border pt-4">
                <label className="text-xs font-bold text-brand-muted uppercase">Service Startup Mode</label>
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

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
              <button
                type="button"
                onClick={handleInstallKosh}
                disabled={serviceLoading}
                className="flex items-center justify-center gap-2 w-full bg-brand-success/10 border border-brand-success/30 hover:bg-brand-success/20 text-brand-success px-4 py-3 rounded-xl transition-colors font-bold disabled:opacity-50"
              >
                <Play size={16} fill="currentColor" />
                {serviceLoading ? 'Working...' : 'Install / Repair'}
              </button>
              <button
                type="button"
                onClick={handleUninstallKosh}
                disabled={serviceLoading}
                className="flex items-center justify-center gap-2 w-full bg-brand-danger/10 border border-brand-danger/30 hover:bg-brand-danger/20 text-brand-danger px-4 py-3 rounded-xl transition-colors font-bold disabled:opacity-50"
              >
                <Square size={16} fill="currentColor" />
                {serviceLoading ? 'Working...' : 'Uninstall'}
              </button>
            </div>
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

      {/* MCP Setup Panel — full width below the grid */}
      <div className="mt-8 max-w-6xl">
        <div className="bg-brand-panel rounded-2xl border border-brand-border shadow-sm overflow-hidden">
          
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-5 border-b border-brand-border">
            <div>
              <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted flex items-center gap-2">
                <Plug size={16} className="text-brand-accent" /> Connect to Claude Desktop (MCP)
              </h2>
              <p className="text-xs text-brand-muted mt-1 max-w-lg">
                The MCP server exposes your local cartridge directly to Claude Desktop, Cursor, and any MCP-compatible AI. 
                Paste the generated config into <code className="bg-brand-surface px-1 py-0.5 rounded text-brand-accent">%APPDATA%\Claude\claude_desktop_config.json</code> and restart Claude.
              </p>
              <p className="text-xs text-brand-accent mt-2 max-w-lg">
                Company Brain context is served through <code>company_context_compile</code>, with cited evidence available through <code>company_memory_search</code> and <code>company_artifact_inspect</code>.
              </p>
            </div>
            <div className="flex items-center gap-2">
              {mcpStatus.running ? (
                <button
                  onClick={handleStopMcp}
                  disabled={mcpLoading}
                  className="flex items-center gap-2 text-xs font-bold bg-brand-danger/10 border border-brand-danger/30 hover:bg-brand-danger/20 text-brand-danger px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
                >
                  <Square size={14} fill="currentColor" />
                  {mcpLoading ? 'Stopping...' : 'Stop MCP Server'}
                </button>
              ) : (
                <button
                  onClick={handleStartMcp}
                  disabled={mcpLoading || !config?.cartridgeRoot}
                  className="flex items-center gap-2 text-xs font-bold bg-brand-success/10 border border-brand-success/30 hover:bg-brand-success/20 text-brand-success px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
                >
                  <Play size={14} fill="currentColor" />
                  {mcpLoading ? 'Starting...' : 'Start MCP Server'}
                </button>
              )}
              <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold border ${
                mcpStatus.running 
                  ? 'bg-brand-success/10 border-brand-success/30 text-brand-success'
                  : 'bg-brand-surface border-brand-border text-brand-muted'
              }`}>
                <span className={`w-1.5 h-1.5 rounded-full ${ mcpStatus.running ? 'bg-brand-success animate-pulse' : 'bg-brand-muted'}`} />
                {mcpStatus.running ? `Live · PID ${mcpStatus.pid || '?'}` : 'Offline'}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-0 divide-y xl:divide-y-0 xl:divide-x divide-brand-border">

            {/* Left: Config generator */}
            <div className="p-6 flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-brand-muted uppercase">Permissions for this session</span>
              </div>
              <div className="flex flex-wrap gap-4">
                {[
                  { key: 'allowWrite', label: 'Allow Write', desc: 'Let Claude submit memory receipts' },
                  { key: 'allowMutate', label: 'Allow Mutate', desc: 'Let Claude apply intake proposals directly' },
                  { key: 'allowPrivate', label: 'Allow Private', desc: 'Include private memories in context packs' },
                ].map(opt => (
                  <label key={opt.key} className="flex items-start gap-2 cursor-pointer group">
                    <input
                      type="checkbox"
                      checked={mcpOptions[opt.key]}
                      onChange={e => setMcpOptions(prev => ({ ...prev, [opt.key]: e.target.checked }))}
                      className="mt-0.5 w-4 h-4 text-brand-accent bg-brand-surface border-brand-border rounded focus:ring-brand-accent"
                    />
                    <div>
                      <div className="text-sm font-semibold text-brand-text group-hover:text-brand-accent transition-colors">{opt.label}</div>
                      <div className="text-xs text-brand-muted">{opt.desc}</div>
                    </div>
                  </label>
                ))}
              </div>

              <div className="relative">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-brand-muted uppercase">MCP client config JSON</span>
                  <button
                    onClick={handleCopyConfig}
                    className={`flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-lg border transition-all ${
                      copied
                        ? 'bg-brand-success/10 border-brand-success/30 text-brand-success'
                        : 'bg-brand-surface border-brand-border text-brand-muted hover:text-brand-accent hover:border-brand-accent'
                    }`}
                  >
                    {copied ? <ClipboardCheck size={13} /> : <Copy size={13} />}
                    {copied ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <pre className="bg-[#0D0D0D] border border-brand-border rounded-xl p-4 text-xs font-mono text-brand-accent overflow-x-auto whitespace-pre leading-relaxed">
                  {getMcpConfigJson()}
                </pre>
              </div>

              <div className="bg-brand-surface border border-brand-border rounded-xl p-4 text-xs text-brand-muted leading-relaxed">
                <strong className="text-brand-text block mb-1">📋 Steps to install:</strong>
                1. Copy the config above.<br />
                2. Open <code className="text-brand-accent">%APPDATA%\Claude\claude_desktop_config.json</code> in any text editor.<br />
                3. Merge the <code className="text-brand-accent">mcpServers</code> block into the file (or create the file if it doesn't exist).<br />
                4. Restart Claude Desktop. The <strong className="text-brand-text">llm-kosh</strong> tool will appear in Claude's tool list.
              </div>
            </div>

            {/* Right: Live log stream */}
            <div className="p-6 flex flex-col">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-bold text-brand-muted uppercase flex items-center gap-2">
                  <TerminalSquare size={14} /> Live MCP Log
                </span>
                <button onClick={() => setMcpLogs([])} className="text-xs text-brand-muted hover:text-brand-accent transition-colors">Clear</button>
              </div>
              <div className="flex-1 min-h-[280px] bg-[#0D0D0D] border border-brand-border rounded-xl p-4 font-mono text-xs overflow-y-auto">
                {mcpLogs.length === 0 ? (
                  <span className="text-brand-muted italic opacity-60">
                    {mcpStatus.running ? 'Waiting for MCP activity...' : 'Start the MCP server to see live logs here.'}
                  </span>
                ) : (
                  mcpLogs.map((entry, i) => (
                    <div key={i} className={`mb-1 leading-relaxed ${
                      entry.type === 'stderr' ? 'text-brand-danger' :
                      entry.type === 'system' ? 'text-blue-400' :
                      'text-brand-accent'
                    }`}>
                      <span className="text-brand-muted mr-2 opacity-50">[{new Date(entry.timestamp).toLocaleTimeString()}]</span>
                      {entry.message.trim()}
                    </div>
                  ))
                )}
                <div ref={mcpLogEndRef} />
              </div>
            </div>

          </div>
        </div>
      </div>

    </div>
  );
}
