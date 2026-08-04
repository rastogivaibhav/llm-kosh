import React, { useState } from 'react';
import { FolderOpen, CheckCircle2, AlertCircle } from 'lucide-react';
import { api } from '../lib/api';

export default function Onboarding({ config, setConfig, onComplete }) {
  const [sourceFolder, setSourceFolder] = useState(config?.sourceFolder || '');
  const [destinationFolder, setDestinationFolder] = useState(config?.destinationFolder || config?.cartridgeRoot || '');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const chooseSource = async () => {
    const selected = await api.selectSourceFolder();
    if (selected) setSourceFolder(selected);
  };

  const chooseDestination = async () => {
    const selected = await api.selectCartridgeRoot();
    if (selected) setDestinationFolder(selected);
  };

  const configure = async () => {
    setError('');
    if (!sourceFolder || !destinationFolder) {
      setError('Choose both folders to continue.');
      return;
    }
    setSaving(true);
    const result = await api.configureInstall(sourceFolder, destinationFolder);
    setSaving(false);
    if (!result?.ok) {
      setError(result?.error || result?.stderr || 'LLM-Kosh could not configure these folders.');
      return;
    }
    const nextConfig = await api.writeConfig({
      ...config,
      ...(result.config || {}),
      sourceFolder,
      destinationFolder,
      sourceFolders: [sourceFolder],
      cartridgeRoot: destinationFolder,
      setupComplete: true,
    });
    setConfig(nextConfig);
    onComplete();
  };

  return (
    <div className="flex flex-col items-center justify-center h-full p-8 text-center max-w-2xl mx-auto">
      <h1 className="text-4xl font-bold mb-3 text-brand-text">Welcome to llm-kosh</h1>
      <p className="text-brand-muted mb-10 text-lg">Choose your work folder and where LLM-Kosh keeps its local index.</p>

      <div className="w-full bg-brand-panel border border-brand-border rounded-2xl p-8 text-left shadow-sm">
        <div className="mb-7">
          <p className="text-sm font-bold text-brand-text mb-2">1. Work folder</p>
          <p className="text-sm text-brand-muted mb-3">Your files stay here. LLM-Kosh stores references and citations, not duplicate source files.</p>
          <div className="flex gap-3">
            <div className="flex-1 bg-brand-surface border border-brand-border rounded-xl px-4 py-3 font-mono text-xs break-all text-brand-text min-h-[42px]">
              {sourceFolder || <span className="text-brand-muted">No work folder selected</span>}
            </div>
            <button onClick={chooseSource} className="flex items-center gap-2 text-sm font-bold bg-brand-surface hover:bg-brand-border border border-brand-border text-brand-text px-4 py-3 rounded-xl">
              <FolderOpen size={17} /> Browse
            </button>
          </div>
        </div>

        <div className="mb-7">
          <p className="text-sm font-bold text-brand-text mb-2">2. LLM-Kosh data folder</p>
          <p className="text-sm text-brand-muted mb-3">The local index, metadata, citations, and configuration are stored here.</p>
          <div className="flex gap-3">
            <div className="flex-1 bg-brand-surface border border-brand-border rounded-xl px-4 py-3 font-mono text-xs break-all text-brand-text min-h-[42px]">
              {destinationFolder || <span className="text-brand-muted">No data folder selected</span>}
            </div>
            <button onClick={chooseDestination} className="flex items-center gap-2 text-sm font-bold bg-brand-surface hover:bg-brand-border border border-brand-border text-brand-text px-4 py-3 rounded-xl">
              <FolderOpen size={17} /> Browse
            </button>
          </div>
        </div>

        {error && (
          <div className="flex items-start gap-2 text-sm text-brand-danger bg-brand-danger/10 border border-brand-danger/20 rounded-xl p-4 mb-5">
            <AlertCircle size={18} className="mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <button onClick={configure} disabled={saving} className="w-full flex items-center justify-center gap-2 text-sm font-bold bg-brand-accent hover:bg-brand-accentHover text-white px-6 py-3.5 rounded-xl disabled:opacity-50">
          <CheckCircle2 size={18} />
          {saving ? 'Configuring and starting the index…' : 'Configure LLM-Kosh'}
        </button>
      </div>
    </div>
  );
}
