import React, { useState } from 'react';
import { api } from '../lib/api';

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
      setError('Please select a cartridge root in the Home tab first.');
      return;
    }
    
    setLoading(true);
    setError(null);
    setSuccessPath(null);
    setOutput('Generating pack...');
    setStatusMessage('Generating pack...');

    const result = await api.generatePack(config.cartridgeRoot, formData);
    
    setLoading(false);
    if (result.ok) {
      setOutput(result.stdout || 'Pack generated successfully.');
      setSuccessPath(result.outPath);
      setStatusMessage('Pack generated successfully.');
    } else {
      setError(`Failed to generate pack: ${result.stderr}`);
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
      <div className="p-6 h-full flex flex-col items-center justify-center">
        <div className="bg-vscode-inputBg p-8 rounded border border-green-600 max-w-lg w-full text-center shadow-lg">
          <div className="text-green-400 text-5xl mb-4">✓</div>
          <h2 className="text-2xl font-bold mb-2 text-white">Pack Generated!</h2>
          <p className="text-gray-400 mb-6 font-mono text-sm break-all">{successPath}</p>
          
          <div className="flex justify-center space-x-4">
            <button 
              onClick={handleReveal}
              className="bg-vscode-buttonPrimary hover:bg-vscode-buttonHover text-white px-6 py-2 rounded shadow transition-colors font-semibold"
            >
              Reveal in Folder
            </button>
            <button 
              onClick={handleReset}
              className="bg-vscode-bg border border-vscode-border hover:bg-vscode-hover text-white px-6 py-2 rounded shadow transition-colors font-semibold"
            >
              Generate Another
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 h-full flex flex-col overflow-y-auto">
      <h1 className="text-2xl font-semibold mb-6">Generate Pack</h1>

      <div className="flex gap-6 flex-1 min-h-0">
        <form onSubmit={handleSubmit} className="w-1/2 space-y-6 overflow-y-auto pr-4">
          
          <div className="flex flex-col space-y-2">
            <label className="text-sm font-semibold text-gray-400">Query / Task Description</label>
            <textarea 
              name="query"
              value={formData.query}
              onChange={handleChange}
              required
              rows={4}
              className="w-full bg-vscode-inputBg border border-vscode-border rounded p-2 text-white font-mono text-sm focus:outline-none focus:border-vscode-statusBar"
              placeholder="E.g., I need to update the authentication flow..."
            />
          </div>

          <div className="flex space-x-4">
            <div className="flex-1 flex flex-col space-y-2">
              <label className="text-sm font-semibold text-gray-400">Target Model</label>
              <select 
                name="target"
                value={formData.target}
                onChange={handleChange}
                className="w-full bg-vscode-inputBg border border-vscode-border rounded p-2 text-white text-sm focus:outline-none focus:border-vscode-statusBar"
              >
                {targets.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="flex-1 flex flex-col space-y-2">
              <label className="text-sm font-semibold text-gray-400">Context Budget</label>
              <select 
                name="budget"
                value={formData.budget}
                onChange={handleChange}
                className="w-full bg-vscode-inputBg border border-vscode-border rounded p-2 text-white text-sm focus:outline-none focus:border-vscode-statusBar"
              >
                {budgets.map(b => <option key={b} value={b}>{b}</option>)}
              </select>
            </div>
          </div>

          <div className="flex flex-col space-y-2">
            <label className="text-sm font-semibold text-gray-400">Output Folder</label>
            <div className="flex space-x-2">
              <input 
                type="text" 
                name="outputFolder"
                value={formData.outputFolder}
                onChange={handleChange}
                required
                className="flex-1 bg-vscode-inputBg border border-vscode-border rounded p-2 text-white font-mono text-sm focus:outline-none focus:border-vscode-statusBar"
                placeholder="/path/to/exports"
              />
              <button 
                type="button"
                onClick={handleSelectOutput}
                className="bg-vscode-buttonPrimary hover:bg-vscode-buttonHover px-4 py-2 rounded text-sm transition-colors shadow"
              >
                Browse
              </button>
            </div>
          </div>

          <div className="flex flex-col space-y-4 pt-4 border-t border-vscode-border">
            <label className="flex items-center space-x-3 cursor-pointer">
              <input 
                type="checkbox" 
                name="safePack"
                checked={formData.safePack}
                onChange={handleChange}
                className="form-checkbox h-4 w-4 text-vscode-statusBar"
              />
              <span className="text-sm font-semibold text-gray-300">Use safe-pack (Default: ON)</span>
            </label>

            <div className="bg-red-900/20 border border-red-900/50 p-3 rounded">
              <label className="flex items-center space-x-3 cursor-pointer">
                <input 
                  type="checkbox" 
                  name="includePrivate"
                  checked={formData.includePrivate}
                  onChange={handleChange}
                  className="form-checkbox h-4 w-4 text-red-500"
                />
                <span className="text-sm font-semibold text-red-400">Include Private Context</span>
              </label>
              <p className="text-xs text-red-300/70 mt-1 ml-7">
                Warning: This may expose sensitive information to the LLM context.
              </p>
            </div>
          </div>

          <button 
            type="submit"
            disabled={loading}
            className="w-full bg-vscode-buttonPrimary hover:bg-vscode-buttonHover disabled:opacity-50 text-white px-6 py-3 rounded shadow transition-colors font-bold mt-4"
          >
            {loading ? 'Generating...' : 'Generate Pack'}
          </button>
        </form>

        <div className="w-1/2 flex flex-col">
          <h2 className="text-sm font-semibold text-gray-400 uppercase mb-2">Logs</h2>
          <div className="flex-1 bg-[#0d0d0d] p-4 rounded border border-vscode-border font-mono text-sm overflow-auto whitespace-pre-wrap">
            {error && <div className="text-red-400 mb-4">{error}</div>}
            <div className="text-green-400">{output || 'Waiting for execution...'}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
