import React, { useState } from 'react';
import { api } from '../lib/api';
import { Inbox, FileText, CheckCircle, RefreshCcw, Send } from 'lucide-react';

export default function Intake({ config, setStatusMessage }) {
  const [root] = useState(config?.cartridgeRoot || '');
  
  // Inbox state
  const [inboxText, setInboxText] = useState('');
  const [inboxProject, setInboxProject] = useState('');
  const [inboxLoading, setInboxLoading] = useState(false);
  const [inboxResult, setInboxResult] = useState('');

  // Intake Scanner state
  const [scanOutput, setScanOutput] = useState('');
  const [scanLoading, setScanLoading] = useState(false);

  const handleCaptureInbox = async (e) => {
    e.preventDefault();
    if (!root || !inboxText.trim()) return;
    
    setInboxLoading(true);
    setStatusMessage('Adding to inbox...');
    
    const args = [inboxText];
    if (inboxProject.trim()) {
      args.push('--project', inboxProject.trim());
    }

    const res = await api.runKoshCommand(root, 'inbox', args);
    if (res.ok) {
      setInboxResult('Note captured successfully!');
      setInboxText('');
      setInboxProject('');
    } else {
      setInboxResult(`Failed: ${res.stderr}`);
    }
    
    setStatusMessage('Ready');
    setInboxLoading(false);
    
    setTimeout(() => setInboxResult(''), 3000);
  };

  const handleRunScanner = async () => {
    if (!root) return;
    setScanLoading(true);
    setStatusMessage('Scanning intake folders...');
    
    setScanOutput('Running intake scan...\n');
    const scanRes = await api.runKoshCommand(root, 'intake', ['scan']);
    setScanOutput(prev => prev + (scanRes.ok ? scanRes.stdout : scanRes.stderr) + '\n');
    
    if (scanRes.ok) {
      setScanOutput(prev => prev + 'Running processor rules...\n');
      const procRes = await api.runKoshCommand(root, 'processor', ['run']);
      setScanOutput(prev => prev + (procRes.ok ? procRes.stdout : procRes.stderr));
    }

    setStatusMessage('Scan complete');
    setScanLoading(false);
  };

  return (
    <div className="p-8 h-full flex flex-col bg-brand-bg overflow-y-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-brand-text flex items-center gap-3">
            <Inbox className="text-brand-accent" size={28} />
            Intake Hub
          </h1>
          <p className="text-brand-muted mt-1">Capture raw thoughts and process external files.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-[400px]">
        {/* Inbox Capture Form */}
        <div className="bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col">
          <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted flex items-center gap-2 mb-6">
            <FileText size={16} /> Quick Capture
          </h2>
          
          <form onSubmit={handleCaptureInbox} className="flex flex-col flex-1 gap-4">
            <div className="flex-1 flex flex-col">
              <label className="text-xs font-semibold text-brand-muted uppercase mb-2">Note Content</label>
              <textarea
                value={inboxText}
                onChange={(e) => setInboxText(e.target.value)}
                placeholder="What's on your mind? e.g. 'We should use Redis for the cache queue.'"
                className="flex-1 w-full bg-brand-surface border border-brand-border rounded-xl p-4 text-sm text-brand-text focus:outline-none focus:border-brand-accent transition-colors resize-none placeholder-brand-muted/50"
                required
              />
            </div>
            
            <div>
              <label className="text-xs font-semibold text-brand-muted uppercase mb-2 block">Project Link (Optional)</label>
              <input
                type="text"
                value={inboxProject}
                onChange={(e) => setInboxProject(e.target.value)}
                placeholder="e.g. SelectiveOS"
                className="w-full bg-brand-surface border border-brand-border rounded-xl p-3 text-sm text-brand-text focus:outline-none focus:border-brand-accent transition-colors placeholder-brand-muted/50"
              />
            </div>

            <button
              type="submit"
              disabled={inboxLoading || !inboxText.trim()}
              className="mt-4 flex items-center justify-center gap-2 w-full bg-brand-accent hover:bg-brand-accentHover text-white py-3 rounded-xl font-bold transition-all shadow-sm disabled:opacity-50 disabled:hover:bg-brand-accent"
            >
              {inboxLoading ? <RefreshCcw size={18} className="animate-spin" /> : <Send size={18} />}
              Send to Inbox
            </button>

            {inboxResult && (
              <div className={`mt-2 text-sm font-medium flex items-center gap-2 ${inboxResult.includes('Failed') ? 'text-brand-danger' : 'text-brand-success'}`}>
                {inboxResult.includes('Failed') ? null : <CheckCircle size={16} />}
                {inboxResult}
              </div>
            )}
          </form>
        </div>

        {/* File Scanner Terminal */}
        <div className="bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted flex items-center gap-2">
              <RefreshCcw size={16} /> Batch Processing
            </h2>
            <button 
              onClick={handleRunScanner}
              disabled={scanLoading || !root}
              className="flex items-center gap-2 text-xs font-bold bg-brand-surface hover:bg-brand-border text-brand-text px-4 py-2 rounded-lg border border-brand-border transition-colors disabled:opacity-50"
            >
              <RefreshCcw size={14} className={scanLoading ? "animate-spin text-brand-accent" : ""} /> 
              {scanLoading ? 'Scanning...' : 'Run Scanner'}
            </button>
          </div>
          
          <p className="text-xs text-brand-muted mb-4">
            This pulls raw files from `intake/` and watched folders, classifying them into the memory index via `processor` rules.
          </p>

          <div className="flex-1 bg-[#1C1917] p-4 rounded-xl border border-[#2D1B14] font-mono text-xs overflow-auto text-brand-accent whitespace-pre-wrap shadow-inner">
             {scanOutput || 'Click "Run Scanner" to fetch and process new files...'}
          </div>
        </div>
      </div>
    </div>
  );
}
