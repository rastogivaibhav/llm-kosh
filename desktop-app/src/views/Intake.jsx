import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../lib/api';
import { Inbox, FileText, CheckCircle, RefreshCcw, Send, Zap, X } from 'lucide-react';

// ─── Quick Capture Overlay ──────────────────────────────────────────────────
// Rendered when Electron opens this window with ?quick=1 in the URL.
// A slim, always-on-top, frameless floating bar — Spotlight-style.
function QuickCaptureOverlay({ config }) {
  const [text, setText] = useState('');
  const [project, setProject] = useState('');
  const [state, setState] = useState('idle'); // idle | loading | done | error
  const inputRef = useRef(null);

  useEffect(() => {
    // Auto-focus the textarea as soon as the overlay appears
    setTimeout(() => inputRef.current?.focus(), 80);

    const onKey = (e) => {
      if (e.key === 'Escape') api.closeQuickCapture();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const handleSubmit = useCallback(async (e) => {
    e?.preventDefault();
    if (!text.trim() || state === 'loading') return;

    setState('loading');
    const root = config?.cartridgeRoot;
    if (!root) { setState('error'); return; }

    const args = [text.trim()];
    if (project.trim()) args.push('--project', project.trim());

    const res = await api.runKoshCommand(root, 'inbox', args);
    if (res.ok) {
      setState('done');
      setTimeout(() => api.closeQuickCapture(), 900);
    } else {
      setState('error');
      setTimeout(() => setState('idle'), 2000);
    }
  }, [text, project, state, config]);

  // Also submit on Ctrl+Enter
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') handleSubmit();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [handleSubmit]);

  const borderColor = state === 'done' ? '#22c55e' : state === 'error' ? '#ef4444' : 'rgba(242,110,34,0.5)';

  return (
    <div
      style={{
        width: '100vw', height: '100vh',
        background: 'transparent',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        WebkitAppRegion: 'drag', // make the whole outer area draggable
      }}
    >
      <form
        onSubmit={handleSubmit}
        className="w-full mx-3"
        style={{
          WebkitAppRegion: 'no-drag',
          background: 'rgba(18, 18, 22, 0.92)',
          backdropFilter: 'blur(24px)',
          border: `1.5px solid ${borderColor}`,
          borderRadius: '16px',
          boxShadow: '0 8px 40px rgba(0,0,0,0.7)',
          transition: 'border-color 0.2s',
          overflow: 'hidden',
        }}
      >
        {/* Top row: icon + textarea */}
        <div className="flex items-center px-4 py-3 gap-3">
          <Zap size={18} color="#f26e22" style={{ flexShrink: 0 }} />
          <textarea
            ref={inputRef}
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="Capture a thought, decision, or note… (Ctrl+Enter to save, Esc to cancel)"
            rows={2}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              resize: 'none',
              color: '#e5e0da',
              fontSize: '13px',
              lineHeight: '1.5',
              fontFamily: 'inherit',
            }}
          />
          <button
            type="submit"
            disabled={!text.trim() || state === 'loading' || state === 'done'}
            style={{
              flexShrink: 0,
              background: state === 'done' ? '#22c55e' : state === 'error' ? '#ef4444' : '#f26e22',
              border: 'none',
              borderRadius: '10px',
              padding: '8px 14px',
              color: '#fff',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '6px',
              transition: 'background 0.2s',
              opacity: !text.trim() ? 0.4 : 1,
            }}
          >
            {state === 'loading' ? <RefreshCcw size={13} style={{ animation: 'spin 0.8s linear infinite' }} /> :
             state === 'done'    ? <CheckCircle size={13} /> :
             state === 'error'   ? <X size={13} /> :
                                   <Send size={13} />}
            {state === 'done' ? 'Saved!' : state === 'error' ? 'Failed' : 'Save'}
          </button>
        </div>

        {/* Bottom row: project tag */}
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', padding: '6px 16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11px', color: '#6b6b6b', flexShrink: 0 }}>Project:</span>
          <input
            type="text"
            value={project}
            onChange={e => setProject(e.target.value)}
            placeholder="optional (e.g. MyApp)"
            style={{
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: '#9a9a9a',
              fontSize: '11px',
              fontFamily: 'inherit',
              flex: 1,
            }}
          />
          <button
            type="button"
            onClick={() => api.closeQuickCapture()}
            style={{ background: 'none', border: 'none', color: '#4a4a4a', cursor: 'pointer', padding: '2px' }}
            title="Close (Esc)"
          >
            <X size={12} />
          </button>
        </div>
      </form>
    </div>
  );
}

export default function Intake({ config, setStatusMessage }) {
  // Detect if we were launched in Quick Capture mode by the global hotkey
  const isQuickMode = new URLSearchParams(window.location.search).get('quick') === '1';
  if (isQuickMode) return <QuickCaptureOverlay config={config} />;

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
