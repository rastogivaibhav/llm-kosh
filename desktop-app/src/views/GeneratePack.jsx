import React, { useState } from 'react';
import { api } from '../lib/api';
import { Package, Download, Folder, RefreshCcw, AlertTriangle, CheckCircle, Zap } from 'lucide-react';

export default function GeneratePack({ config, setStatusMessage }) {
  const [formData, setFormData] = useState({
    query: '',
    target: 'chatgpt',
    budget: 'medium',
    safePack: true,
    includePrivate: false,
    outputFolder: config?.defaultExportFolder || ''
  });

  const [loading, setLoading] = useState(false);
  const [output, setOutput] = useState('');
  const [successPath, setSuccessPath] = useState(null);
  const [error, setError] = useState(null);

  const targets = ['chatgpt', 'claude', 'gemini', 'deepseek', 'codex', 'human'];
  const budgets = ['small', 'medium', 'large'];

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    if (name === 'includePrivate' && checked) {
      if (!window.confirm("WARNING: This will include private context files in the pack. This may expose sensitive information to the LLM. Are you sure you want to enable this?")) {
        return;
      }
    }
    setFormData(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const handleSelectOutput = async () => {
    const folder = await api.selectOutputFolder();
    if (folder) {
      setFormData(prev => ({ ...prev, outputFolder: folder }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!config?.cartridgeRoot) {
      setError('Please select a cartridge root in the Settings tab first.');
      return;
    }
    
    setLoading(true);
    setError(null);
    setSuccessPath(null);
    setOutput('Compiling pack...\n');
    setStatusMessage('Generating pack...');

    const result = await api.generatePack(config.cartridgeRoot, formData);
    
    setLoading(false);
    if (result.ok) {
      setOutput(prev => prev + (result.stdout || 'Pack generated successfully.'));
      setSuccessPath(result.outPath);
      setStatusMessage('Pack generated successfully.');
    } else {
      setError(`Failed to generate pack:\n${result.stderr}`);
      setStatusMessage('Pack generation failed.');
    }
  };

  const handleReveal = () => {
    if (successPath) {
      api.revealInFolder(successPath);
    }
  };

  const handleReset = () => {
    setSuccessPath(null);
    setOutput('');
    setFormData(prev => ({ ...prev, query: '' }));
  };

  if (successPath) {
    return (
      <div className="bg-brand-panel p-8 rounded-2xl border border-brand-success/50 shadow-sm flex flex-col items-center justify-center min-h-[300px]">
        <CheckCircle className="text-brand-success mb-4" size={48} />
        <h2 className="text-2xl font-bold mb-2 text-brand-text">Context Pack Ready</h2>
        <p className="text-brand-muted mb-8 font-mono text-xs break-all bg-brand-success/10 px-4 py-2 rounded-lg border border-brand-success/20">{successPath}</p>
        
        <div className="flex gap-4">
          <button 
            onClick={handleReveal}
            className="flex items-center gap-2 bg-brand-accent hover:bg-brand-accentHover text-white px-6 py-3 rounded-xl transition-colors font-bold shadow-sm"
          >
            <Folder size={18} /> Reveal in Explorer
          </button>
          <button 
            onClick={handleReset}
            className="flex items-center gap-2 bg-brand-surface border border-brand-border hover:bg-brand-border text-brand-text px-6 py-3 rounded-xl transition-colors font-bold shadow-sm"
          >
            <RefreshCcw size={18} /> New Pack
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col">
      <div className="flex items-center gap-3 mb-6">
        <Package className="text-brand-accent" size={20} />
        <h2 className="text-lg font-bold text-brand-text">Generate Context Pack</h2>
      </div>

      <div className="flex gap-8 flex-1 min-h-0">
        <form onSubmit={handleSubmit} className="w-1/2 flex flex-col gap-6">
          
          <div className="flex flex-col gap-2">
            <label className="text-xs font-bold text-brand-muted uppercase tracking-wider">Goal / Objective</label>
            <textarea 
              name="query"
              value={formData.query}
              onChange={handleChange}
              required
              rows={3}
              className="w-full bg-brand-surface border border-brand-border rounded-xl p-4 text-brand-text text-sm focus:outline-none focus:border-brand-accent transition-colors resize-none placeholder-brand-muted/50"
              placeholder="What are you trying to accomplish? E.g., 'Rewrite the user auth flow'"
            />
          </div>

          <div className="flex gap-4">
            <div className="flex-1 flex flex-col gap-2">
              <label className="text-xs font-bold text-brand-muted uppercase tracking-wider">Target LLM</label>
              <select 
                name="target"
                value={formData.target}
                onChange={handleChange}
                className="w-full bg-brand-surface border border-brand-border rounded-xl p-3 text-brand-text text-sm focus:outline-none focus:border-brand-accent transition-colors"
              >
                {targets.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="flex-1 flex flex-col gap-2">
              <label className="text-xs font-bold text-brand-muted uppercase tracking-wider">Context Budget</label>
              <select 
                name="budget"
                value={formData.budget}
                onChange={handleChange}
                className="w-full bg-brand-surface border border-brand-border rounded-xl p-3 text-brand-text text-sm focus:outline-none focus:border-brand-accent transition-colors"
              >
                {budgets.map(b => <option key={b} value={b}>{b.charAt(0).toUpperCase() + b.slice(1)}</option>)}
              </select>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-bold text-brand-muted uppercase tracking-wider">Output Directory</label>
            <div className="flex gap-2">
              <input 
                type="text" 
                name="outputFolder"
                value={formData.outputFolder}
                onChange={handleChange}
                required
                className="flex-1 bg-brand-surface border border-brand-border rounded-xl p-3 text-brand-text font-mono text-xs focus:outline-none focus:border-brand-accent transition-colors"
                placeholder="/path/to/exports"
              />
              <button 
                type="button"
                onClick={handleSelectOutput}
                className="bg-brand-surface border border-brand-border hover:bg-brand-border text-brand-text px-4 py-2 rounded-xl text-sm transition-colors shadow-sm font-bold"
              >
                Browse
              </button>
            </div>
          </div>

          <div className="flex flex-col gap-4 pt-4 border-t border-brand-border">
            <label className="flex items-center gap-3 cursor-pointer group">
              <input 
                type="checkbox" 
                name="safePack"
                checked={formData.safePack}
                onChange={handleChange}
                className="w-4 h-4 text-brand-accent bg-brand-surface border-brand-border rounded focus:ring-brand-accent"
              />
              <span className="text-sm font-semibold text-brand-text group-hover:text-brand-accent transition-colors">Use safe-pack filter (Default: ON)</span>
            </label>

            <div className="bg-brand-danger/10 border border-brand-danger/30 p-4 rounded-xl">
              <label className="flex items-center gap-3 cursor-pointer group">
                <input 
                  type="checkbox" 
                  name="includePrivate"
                  checked={formData.includePrivate}
                  onChange={handleChange}
                  className="w-4 h-4 text-brand-danger bg-brand-surface border-brand-danger rounded focus:ring-brand-danger"
                />
                <span className="text-sm font-bold text-brand-danger group-hover:opacity-80 transition-opacity">Include Private Context</span>
              </label>
              <p className="text-xs font-medium text-brand-danger/80 mt-2 ml-7">
                Warning: This strips privacy filters and may expose sensitive local credentials to the LLM.
              </p>
            </div>
          </div>

          <button 
            type="submit"
            disabled={loading}
            className="w-full flex justify-center items-center gap-2 bg-brand-accent hover:bg-brand-accentHover disabled:opacity-50 text-white px-6 py-4 rounded-xl shadow-sm transition-colors font-bold mt-2"
          >
            {loading ? <RefreshCcw size={18} className="animate-spin" /> : <Zap size={18} />}
            {loading ? 'Compiling...' : 'Generate Context Pack'}
          </button>
        </form>

        <div className="w-1/2 flex flex-col">
          <h2 className="text-xs font-bold tracking-widest text-brand-muted uppercase mb-4 flex items-center gap-2">
            <TerminalSquare size={14} /> Pack Logs
          </h2>
          <div className="flex-1 bg-[#1C1917] p-4 rounded-xl border border-[#2D1B14] font-mono text-xs overflow-auto whitespace-pre-wrap shadow-inner leading-relaxed">
            {error && <div className="text-brand-danger mb-4 font-bold">{error}</div>}
            <div className="text-brand-success">{output || <span className="text-brand-muted italic opacity-70">Waiting for generation...</span>}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Temporary icon fallback since TerminalSquare isn't imported at the top
import { TerminalSquare } from 'lucide-react';
