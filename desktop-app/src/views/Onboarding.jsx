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
      <h1 className="text-3xl font-bold mb-2 text-white">Welcome to llm-kosh</h1>
      <p className="text-gray-400 mb-8">Setup your local environment to get started.</p>

      <div className="w-full bg-vscode-inputBg border border-vscode-border rounded-lg p-6 mb-6 text-left">
        <div className="flex items-center gap-3 mb-4">
          <TerminalSquare className="w-6 h-6 text-blue-400" />
          <h2 className="text-lg font-semibold text-gray-200">1. CLI Engine</h2>
        </div>
        
        {testing ? (
          <p className="text-sm text-gray-400">Testing CLI...</p>
        ) : cliStatus?.ok ? (
          <div className="text-sm text-green-400 bg-green-900/30 p-3 rounded border border-green-800">
            CLI detected successfully at: <code className="text-green-300">{cliStatus.executablePath}</code>
          </div>
        ) : (
          <div className="text-sm text-red-400 bg-red-900/30 p-4 rounded border border-red-800 mb-4">
            <div className="flex items-center gap-2 mb-2">
              <AlertCircle className="w-4 h-4" />
              <span className="font-bold">CLI Not Found</span>
            </div>
            <p className="mb-2 text-red-300">
              The llm-kosh Python CLI was not found on your system PATH or bundled sidecar.
            </p>
            <p className="mb-2 font-mono text-xs text-red-200">
              {cliStatus?.stderr || 'Unknown error'}
            </p>
            <p className="text-gray-300 mt-4">
              Please install it using: <br/>
              <code className="bg-black/50 px-2 py-1 rounded text-white mt-1 inline-block">pip install llm-kosh</code>
            </p>
          </div>
        )}

        <div className="mt-4 flex gap-4">
          <button 
            onClick={handleTestCli}
            disabled={testing}
            className="text-sm bg-vscode-buttonPrimary hover:bg-blue-600 text-white px-4 py-2 rounded"
          >
            Retry Detection
          </button>
          <button 
            onClick={handleSelectExe}
            className="text-sm bg-vscode-inputBg hover:bg-vscode-hover border border-vscode-border text-white px-4 py-2 rounded"
          >
            Locate Custom Executable
          </button>
        </div>
      </div>

      <div className={`w-full bg-vscode-inputBg border border-vscode-border rounded-lg p-6 text-left transition-opacity ${!cliStatus?.ok ? 'opacity-50 pointer-events-none' : ''}`}>
        <div className="flex items-center gap-3 mb-4">
          <Settings className="w-6 h-6 text-purple-400" />
          <h2 className="text-lg font-semibold text-gray-200">2. Cartridge Root</h2>
        </div>
        
        <p className="text-sm text-gray-400 mb-6">
          A Cartridge Root is the local folder where your memory receipts and context configurations are stored.
        </p>

        <div className="flex gap-4">
          <button 
            onClick={handleCreateRoot}
            className="flex-1 flex items-center justify-center gap-2 text-sm bg-vscode-buttonPrimary hover:bg-blue-600 text-white px-4 py-3 rounded"
          >
            <FolderPlus className="w-4 h-4" />
            Create New Cartridge
          </button>
          <button 
            onClick={handleSelectRoot}
            className="flex-1 flex items-center justify-center gap-2 text-sm bg-vscode-inputBg hover:bg-vscode-hover border border-vscode-border text-white px-4 py-3 rounded"
          >
            <FolderOpen className="w-4 h-4" />
            Open Existing
          </button>
        </div>
      </div>
      
      {config?.cartridgeRoot && cliStatus?.ok && (
        <button 
          onClick={onComplete}
          className="mt-8 text-sm text-blue-400 hover:text-blue-300 underline"
        >
          Skip to app
        </button>
      )}
    </div>
  );
}
