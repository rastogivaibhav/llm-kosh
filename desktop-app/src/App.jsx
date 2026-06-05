import React, { useState, useEffect } from 'react';
import Sidebar from './components/layout/Sidebar';
import BottomBar from './components/layout/BottomBar';
import Home from './views/Home'; 
import Intake from './views/Intake';
import Search from './views/Search';
import Prompts from './views/Prompts';
import Airlock from './views/Airlock';
import Receipts from './views/Receipts'; 
import GeneratePack from './views/GeneratePack'; 
import Settings from './views/Settings';
import Daemon from './views/Daemon';
import Onboarding from './views/Onboarding';
import { api } from './lib/api';

function App() {
  const [currentView, setCurrentView] = useState('dashboard');
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
      <div className="flex flex-col h-screen overflow-hidden bg-brand-bg text-brand-text font-sans">
        <Onboarding 
          config={config} 
          setConfig={setConfig} 
          onComplete={() => setNeedsOnboarding(false)} 
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-brand-bg text-brand-text font-sans">
      <div className="flex flex-1 overflow-hidden">
        <Sidebar currentView={currentView} setCurrentView={setCurrentView} />
        
        <main className="flex-1 overflow-hidden relative flex flex-col">
          {currentView === 'dashboard' && (
            <Home 
              config={config} 
              setConfig={setConfig} 
              setStatusMessage={setStatusMessage} 
            />
          )}
          {currentView === 'intake' && (
            <Intake 
              config={config} 
              setStatusMessage={setStatusMessage} 
            />
          )}
          {currentView === 'search' && (
            <Search 
              config={config} 
              setStatusMessage={setStatusMessage} 
            />
          )}
          {currentView === 'prompts' && (
            <Prompts />
          )}
          {currentView === 'ailoop' && (
            <div className="p-8 h-full flex flex-col bg-brand-bg overflow-y-auto">
              <div className="mb-6">
                <h1 className="text-3xl font-bold text-brand-text flex items-center gap-3">
                  <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-brand-accent"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
                  AI Execution Loop
                </h1>
                <p className="text-brand-muted mt-1">Pack your context, send it to the AI, and absorb the resulting receipt.</p>
              </div>
              <div className="flex flex-col gap-8 flex-1 min-h-[500px]">
                <GeneratePack 
                  config={config} 
                  setStatusMessage={setStatusMessage} 
                />
                <Receipts 
                  config={config} 
                  setStatusMessage={setStatusMessage} 
                />
              </div>
            </div>
          )}
          {currentView === 'airlock' && (
            <Airlock 
              config={config} 
              setStatusMessage={setStatusMessage} 
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
