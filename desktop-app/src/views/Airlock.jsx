import React, { useState } from 'react';
import { api } from '../lib/api';
import { ShieldAlert, Activity, ShieldCheck, HeartPulse, RefreshCcw, Lock } from 'lucide-react';

export default function Airlock({ config, setStatusMessage }) {
  const [root] = useState(config?.cartridgeRoot || '');
  
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditOutput, setAuditOutput] = useState('');

  const [healLoading, setHealLoading] = useState(false);
  const [healOutput, setHealOutput] = useState('');

  const [quarantineLoading, setQuarantineLoading] = useState(false);
  const [quarantineOutput, setQuarantineOutput] = useState('');

  const handleRunAudit = async () => {
    if (!root) return;
    setAuditLoading(true);
    setStatusMessage('Running system audit...');
    setAuditOutput('Scanning cartridge integrity...\n');
    
    const res = await api.runKoshCommand(root, 'audit', []);
    setAuditOutput(prev => prev + (res.ok ? res.stdout : res.stderr));
    
    setStatusMessage('Audit complete');
    setAuditLoading(false);
  };

  const handleRunHeal = async () => {
    if (!root) return;
    setHealLoading(true);
    setStatusMessage('Running auto-heal...');
    setHealOutput('Applying safe healing routines...\n');
    
    const res = await api.runKoshCommand(root, 'heal', ['--safe']);
    setHealOutput(prev => prev + (res.ok ? res.stdout : res.stderr));
    
    setStatusMessage('Heal complete');
    setHealLoading(false);
  };

  const handleListQuarantine = async () => {
    if (!root) return;
    setQuarantineLoading(true);
    setStatusMessage('Fetching quarantine zone...');
    setQuarantineOutput('Checking isolated memories...\n');
    
    const res = await api.runKoshCommand(root, 'quarantine', ['--list']);
    setQuarantineOutput(prev => prev + (res.ok ? res.stdout : res.stderr));
    
    setStatusMessage('Quarantine checked');
    setQuarantineLoading(false);
  };

  return (
    <div className="p-8 h-full flex flex-col bg-brand-bg overflow-y-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-brand-text flex items-center gap-3">
            <ShieldAlert className="text-brand-danger" size={28} />
            Airlock & Security
          </h1>
          <p className="text-brand-muted mt-1">Audit integrity, self-heal links, and manage quarantined context.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-[400px]">
        
        {/* Left Column: Audit & Heal */}
        <div className="flex flex-col gap-6">
          
          {/* Audit Card */}
          <div className="bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col h-[300px]">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted flex items-center gap-2">
                <Activity size={16} /> System Audit
              </h2>
              <button 
                onClick={handleRunAudit}
                disabled={auditLoading || !root}
                className="flex items-center gap-2 text-xs font-bold bg-brand-surface hover:bg-brand-border text-brand-text px-4 py-2 rounded-lg border border-brand-border transition-colors disabled:opacity-50"
              >
                <RefreshCcw size={14} className={auditLoading ? "animate-spin text-brand-accent" : ""} /> 
                {auditLoading ? 'Scanning...' : 'Run Audit'}
              </button>
            </div>
            <p className="text-xs text-brand-muted mb-4">Checks for dangling links, orphan receipts, and missing back-references in the index.</p>
            <div className="flex-1 bg-[#1C1917] p-4 rounded-xl border border-[#2D1B14] font-mono text-xs overflow-auto text-brand-text whitespace-pre-wrap shadow-inner leading-relaxed">
               {auditOutput || <span className="text-brand-muted italic opacity-70">No audit run yet.</span>}
            </div>
          </div>

          {/* Heal Card */}
          <div className="bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col h-[300px]">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted flex items-center gap-2">
                <HeartPulse size={16} className="text-brand-success" /> Auto-Heal (Safe Mode)
              </h2>
              <button 
                onClick={handleRunHeal}
                disabled={healLoading || !root}
                className="flex items-center gap-2 text-xs font-bold bg-brand-success hover:bg-[#2F855A] text-white px-4 py-2 rounded-lg transition-colors shadow-sm disabled:opacity-50"
              >
                <RefreshCcw size={14} className={healLoading ? "animate-spin" : ""} /> 
                {healLoading ? 'Healing...' : 'Heal Cartridge'}
              </button>
            </div>
            <p className="text-xs text-brand-muted mb-4">Automatically repairs missing cross-links and rebuilds indices safely without data loss.</p>
            <div className="flex-1 bg-[#1C1917] p-4 rounded-xl border border-[#2D1B14] font-mono text-xs overflow-auto text-brand-success whitespace-pre-wrap shadow-inner leading-relaxed">
               {healOutput || <span className="text-brand-muted italic opacity-70">Click to repair broken links.</span>}
            </div>
          </div>
          
        </div>

        {/* Right Column: Quarantine */}
        <div className="bg-brand-panel p-6 rounded-2xl border border-brand-danger/30 shadow-sm flex flex-col h-[624px]">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold tracking-widest uppercase text-brand-danger flex items-center gap-2">
              <Lock size={16} /> Quarantine Zone
            </h2>
            <button 
              onClick={handleListQuarantine}
              disabled={quarantineLoading || !root}
              className="flex items-center gap-2 text-xs font-bold bg-brand-surface border border-brand-danger/30 hover:bg-brand-danger/10 text-brand-danger px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
            >
              <RefreshCcw size={14} className={quarantineLoading ? "animate-spin" : ""} /> 
              {quarantineLoading ? 'Checking...' : 'List Items'}
            </button>
          </div>
          
          <div className="bg-brand-danger/10 border border-brand-danger/30 p-4 rounded-xl mb-4 flex items-start gap-3">
            <ShieldCheck className="text-brand-danger mt-0.5" size={18} />
            <div>
              <h3 className="text-sm font-bold text-brand-danger">Isolated Content</h3>
              <p className="text-xs font-medium text-brand-danger/80 mt-1">
                Memories in the Quarantine Zone are stripped from the main index and are never exported in `pack` operations. They are effectively sandboxed.
              </p>
            </div>
          </div>

          <div className="flex-1 bg-[#1C1917] p-4 rounded-xl border border-brand-danger/20 font-mono text-xs overflow-auto text-brand-danger whitespace-pre-wrap shadow-inner leading-relaxed">
             {quarantineOutput || <span className="text-brand-danger/50 italic opacity-70">Run check to list quarantined memories.</span>}
          </div>
        </div>

      </div>
    </div>
  );
}
