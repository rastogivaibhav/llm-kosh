import React from 'react';
import { Activity, Inbox, Search, RefreshCcw, ShieldAlert, Settings, BookOpen, FolderOpen, BarChart2, Zap } from 'lucide-react';

export default function Sidebar({ currentView, setCurrentView }) {
  const tabs = [
    { id: 'dashboard', icon: Activity, label: 'Dashboard' },
    { id: 'explorer', icon: FolderOpen, label: 'Workspace Explorer' },
    { id: 'intake', icon: Inbox, label: 'Intake Hub' },
    { id: 'search', icon: Search, label: 'Memory Explorer' },
    { id: 'prompts', icon: BookOpen, label: 'Skills & Prompts' },
    { id: 'ailoop', icon: RefreshCcw, label: 'AI Loop (Pack & Absorb)' },
    { id: 'airlock', icon: ShieldAlert, label: 'Airlock (Security)' },
    { id: 'benchmarks', icon: BarChart2, label: 'Benchmark Suite' },
    { id: 'agentsim', icon: Zap, label: 'Agent Loop Simulator' },
    { id: 'settings', icon: Settings, label: 'Settings' }
  ];

  return (
    <div className="w-16 flex-shrink-0 h-full bg-brand-panel flex flex-col items-center py-6 border-r border-brand-border shadow-sm z-10">
      <div className="mb-8 w-11 h-11 rounded-xl overflow-hidden flex items-center justify-center bg-brand-surface border border-brand-border relative">
        <img 
          src="/logo.png" 
          alt="KOSH" 
          className="w-full h-full object-cover z-10" 
          onError={(e) => {
            e.target.style.display = 'none';
          }} 
        />
        <span className="font-bold text-brand-accent tracking-tighter text-[10px] absolute z-0">KOSH</span>
      </div>
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = currentView === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => setCurrentView(tab.id)}
            className={`p-3 w-12 h-12 flex items-center justify-center mb-4 rounded-xl transition-all duration-200 ${
              isActive 
                ? 'bg-brand-accent/10 text-brand-accent shadow-[inset_3px_0_0_0_rgba(242,110,34,1)]' 
                : 'text-brand-muted hover:text-brand-accent hover:bg-brand-surface'
            }`}
            title={tab.label}
          >
            <Icon size={22} strokeWidth={isActive ? 2.5 : 2} />
          </button>
        );
      })}
    </div>
  );
}
