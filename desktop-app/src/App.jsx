import React, { useState, useEffect } from 'react';
import Sidebar from './components/layout/Sidebar';
import BottomBar from './components/layout/BottomBar';
import Home from './views/Home';
import Settings from './views/Settings';
import GeneratePack from './views/GeneratePack';
import Receipts from './views/Receipts';
import Prompts from './views/Prompts';
import Logs from './views/Logs';
import Daemon from './views/Daemon';
import Onboarding from './views/Onboarding';
import { api } from './lib/api';

function App() {
  const [currentView, setCurrentView] = useState('home');
  const [config, setConfig] = useState(null);
  const [statusMessage, setStatusMessage] = useState('Initializing...');
  const [needsOnboarding, setNeedsOnboarding] = useState(false);

  useEffect(() => {
    async function init() {
      const cfg = await api.readConfig();
      setConfig(cfg);
      
      const cli = await api.testCli();
      if (!cfg.cartridgeRoot || !cli.ok) {
        setNeedsOnboarding(true);
      }
      
      setStatusMessage('Ready');
    }
    init();
  }, []);

  if (needsOnboarding) {
    return (
      <div className="flex flex-col h-screen overflow-hidden bg-vscode-bg">
        <Onboarding 
          config={config} 
          setConfig={setConfig} 
          onComplete={() => setNeedsOnboarding(false)} 
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <div className="flex flex-1 overflow-hidden">
        <Sidebar currentView={currentView} setCurrentView={setCurrentView} />
        
        <main className="flex-1 bg-vscode-bg overflow-hidden relative">
          {currentView === 'home' && (
            <Home 
              config={config} 
              setConfig={setConfig} 
              setStatusMessage={setStatusMessage} 
            />
          )}
          {currentView === 'prompts' && (
            <Prompts />
          )}
          {currentView === 'logs' && (
            <Logs />
          )}
          {currentView === 'generate' && (
            <GeneratePack 
              config={config} 
              setStatusMessage={setStatusMessage} 
            />
          )}
          {currentView === 'receipts' && (
            <Receipts 
              config={config} 
              setStatusMessage={setStatusMessage} 
            />
          )}
          {currentView === 'daemon' && (
            <Daemon 
              config={config} 
            />
          )}
          {currentView === 'settings' && (
            <Settings 
              config={config} 
              setConfig={setConfig} 
              setStatusMessage={setStatusMessage} 
            />
          )}
        </main>
      </div>
      
      <BottomBar 
        rootPath={config?.cartridgeRoot} 
        statusMessage={statusMessage} 
      />
    </div>
  );
}

export default App;
