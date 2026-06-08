import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { Settings, FolderPlus, FolderOpen, TerminalSquare, AlertCircle } from 'lucide-react';

export default function Onboarding({ config, setConfig, onComplete }) {
  const [cliStatus, setCliStatus] = useState(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    handleTestCli();
  }, []);

  const handleTestCli = async () => {
    setTesting(true);
    const res = await api.testCli();
    setCliStatus(res);
    setTesting(false);
  };

  const handleSelectRoot = async () => {
    const root = await api.selectCartridgeRoot();
    if (root) {
      const newCfg = await api.writeConfig({ ...config, cartridgeRoot: root });
      setConfig(newCfg);
      if (cliStatus?.ok) onComplete();
    }
  };

  const handleCreateRoot = async () => {
    const res = await api.createCartridgeRoot('user');
    if (res && res.ok && res.folder) {
      const newCfg = await api.writeConfig({ ...config, cartridgeRoot: res.folder });
      setConfig(newCfg);
      if (cliStatus?.ok) onComplete();
    }
  };

  const handleSelectExe = async () => {
    const exe = await api.selectExecutable();
    if (exe) {
      const newCfg = await api.writeConfig({ ...config, executablePath: exe });
      setConfig(newCfg);
      handleTestCli();
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-full p-8 text-center max-w-2xl mx-auto">
      <h1 className="text-4xl font-bold mb-3 text-brand-text">Welcome to llm-kosh</h1>
      <p className="text-brand-muted mb-10 text-lg">Setup your local environment to get started.</p>

      <div className="w-full bg-brand-panel border border-brand-border rounded-2xl p-8 mb-6 text-left shadow-sm">
        <div className="flex items-center gap-3 mb-6">
          <TerminalSquare className="w-6 h-6 text-brand-accent" />
          <h2 className="text-xl font-bold text-brand-text">1. CLI Engine</h2>
        </div>
        
        {testing ? (
          <p className="text-sm font-medium text-brand-muted">Testing CLI...</p>
        ) : cliStatus?.ok ? (
          <div className="text-sm text-brand-success bg-brand-success/10 p-4 rounded-xl border border-brand-success/20 font-medium">
            CLI detected successfully at: <code className="text-brand-success font-bold font-mono ml-2">{cliStatus.executablePath}</code>
          </div>
        ) : (
          <div className="text-sm text-brand-danger bg-brand-danger/10 p-5 rounded-xl border border-brand-danger/20 mb-6">
            <div className="flex items-center gap-2 mb-3">
              <AlertCircle className="w-5 h-5" />
              <span className="font-bold text-base">CLI Not Found</span>
            </div>
            <p className="mb-3 font-medium">
              The llm-kosh Python CLI was not found on your system PATH or bundled sidecar.
            </p>
            <p className="mb-4 font-mono text-xs opacity-80 p-2 bg-brand-danger/10 rounded">
              {cliStatus?.stderr || 'Unknown error'}
            </p>
            <p className="font-medium mt-2">
              Please install it using: <br/>
              <code className="bg-brand-surface border border-brand-border px-3 py-1.5 rounded-lg text-brand-text mt-2 inline-block font-mono">pip install llm-kosh</code>
            </p>
          </div>
        )}

        <div className="mt-6 flex gap-4">
          <button 
            onClick={handleTestCli}
            disabled={testing}
            className="text-sm font-bold bg-brand-accent hover:bg-brand-accentHover text-white px-6 py-3 rounded-xl transition-colors shadow-sm disabled:opacity-50"
          >
            Retry Detection
          </button>
          <button 
            onClick={handleSelectExe}
            className="text-sm font-bold bg-brand-surface hover:bg-brand-border border border-brand-border text-brand-text px-6 py-3 rounded-xl transition-colors"
          >
            Locate Custom Executable
          </button>
        </div>
      </div>

      <div className={`w-full bg-brand-panel border border-brand-border rounded-2xl p-8 text-left shadow-sm transition-opacity ${!cliStatus?.ok ? 'opacity-40 pointer-events-none grayscale' : ''}`}>
        <div className="flex items-center gap-3 mb-4">
          <Settings className="w-6 h-6 text-brand-muted" />
          <h2 className="text-xl font-bold text-brand-text">2. Cartridge Root</h2>
        </div>
        
        <p className="text-sm font-medium text-brand-muted mb-8">
          A Cartridge Root is the local folder where your memory receipts and context configurations are stored.
        </p>

        <div className="flex gap-4">
          <button 
            onClick={handleCreateRoot}
            className="flex-1 flex items-center justify-center gap-2 text-sm font-bold bg-brand-accent hover:bg-brand-accentHover text-white px-4 py-3.5 rounded-xl transition-colors shadow-sm"
          >
            <FolderPlus className="w-5 h-5" />
            Create New Cartridge
          </button>
          <button 
            onClick={handleSelectRoot}
            className="flex-1 flex items-center justify-center gap-2 text-sm font-bold bg-brand-surface hover:bg-brand-border border border-brand-border text-brand-text px-4 py-3.5 rounded-xl transition-colors"
          >
            <FolderOpen className="w-5 h-5" />
            Open Existing
          </button>
        </div>
      </div>
      
      {config?.cartridgeRoot && cliStatus?.ok && (
        <button 
          onClick={onComplete}
          className="mt-8 text-sm font-bold text-brand-accent hover:text-brand-accentHover underline transition-colors"
        >
          Skip to app
        </button>
      )}
    </div>
  );
}
