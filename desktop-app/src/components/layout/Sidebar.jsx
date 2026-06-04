import React from 'react';
import { Home, Settings, Package, Inbox, BookOpen, TerminalSquare, Activity } from 'lucide-react';

export default function Sidebar({ currentView, setCurrentView }) {
  const tabs = [
    { id: 'home', icon: Home, label: 'Home' },
    { id: 'daemon', icon: Activity, label: 'Daemon' },
    { id: 'prompts', icon: BookOpen, label: 'Prompt Library' },
    { id: 'generate', icon: Package, label: 'Generate Pack' },
    { id: 'receipts', icon: Inbox, label: 'Receipt Inbox' },
    { id: 'logs', icon: TerminalSquare, label: 'Logs' },
    { id: 'settings', icon: Settings, label: 'Settings' }
  ];

  return (
    <div className="w-14 flex-shrink-0 h-full bg-vscode-activityBar flex flex-col items-center py-4 border-r border-vscode-border">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = currentView === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => setCurrentView(tab.id)}
            className={`p-3 w-full flex justify-center mb-2 ${
              isActive ? 'text-white border-l-2 border-vscode-statusBar' : 'text-gray-500 hover:text-white'
            }`}
            title={tab.label}
          >
            <Icon size={24} />
          </button>
        );
      })}
    </div>
  );
}
