import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../lib/api';
import { Search as SearchIcon, Database, Zap, RefreshCcw, Box, Sliders as SlidersIcon } from 'lucide-react';

export default function Search({ config, setStatusMessage }) {
  const [root] = useState(config?.cartridgeRoot || '');
  
  const [query, setQuery] = useState('');
  const [useSemantic, setUseSemantic] = useState(false);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState('');

  const [embedLoading, setEmbedLoading] = useState(false);
  const [embedOutput, setEmbedOutput] = useState('');

  // Cognitive Tuning states
  const [showCognitiveTuning, setShowCognitiveTuning] = useState(false);
  const [weights, setWeights] = useState({
    beta_sem: 0.7,
    beta_proc: 0.3,
    alpha: 0.02,
    gamma: 0.5,
    tau: 0.5
  });
  const [cartridgeConfig, setCartridgeConfig] = useState(null);
  const debounceTimeoutRef = useRef(null);

  const loadCartridgeConfig = useCallback(async () => {
    try {
      const cfg = await api.readCartridgeConfig(root);
      if (cfg) {
        setCartridgeConfig(cfg);
        if (cfg.retrieval_weights) {
          setWeights({
            beta_sem: cfg.retrieval_weights.beta_sem !== undefined ? cfg.retrieval_weights.beta_sem : 0.7,
            beta_proc: cfg.retrieval_weights.beta_proc !== undefined ? cfg.retrieval_weights.beta_proc : 0.3,
            alpha: cfg.retrieval_weights.alpha !== undefined ? cfg.retrieval_weights.alpha : 0.02,
            gamma: cfg.retrieval_weights.gamma !== undefined ? cfg.retrieval_weights.gamma : 0.5,
            tau: cfg.retrieval_weights.tau !== undefined ? cfg.retrieval_weights.tau : 0.5
          });
        }
      }
    } catch (err) {
      console.error('Failed to load cartridge config', err);
    }
  }, [root]);

  useEffect(() => {
    if (root) {
      loadCartridgeConfig();
    }
    return () => {
      if (debounceTimeoutRef.current) {
        clearTimeout(debounceTimeoutRef.current);
      }
    };
  }, [loadCartridgeConfig, root]);

  const updateWeightsInConfig = async (newWeights) => {
    if (!root) return;
    try {
      const updatedConfig = {
        ...(cartridgeConfig || { schema: 'llm-kosh.v0', version: '1.0.0' }),
        retrieval_weights: newWeights
      };
      await api.writeCartridgeConfig(root, updatedConfig);
      setCartridgeConfig(updatedConfig);
    } catch (err) {
      console.error('Failed to save cartridge config', err);
    }
  };

  const handleWeightChange = (key, val) => {
    let newWeights = { ...weights };
    const numericVal = parseFloat(val);
    if (key === 'beta_sem') {
      newWeights.beta_sem = numericVal;
      newWeights.beta_proc = parseFloat((1.0 - numericVal).toFixed(2));
    } else if (key === 'beta_proc') {
      newWeights.beta_proc = numericVal;
      newWeights.beta_sem = parseFloat((1.0 - numericVal).toFixed(2));
    } else {
      newWeights[key] = numericVal;
    }
    setWeights(newWeights);

    if (debounceTimeoutRef.current) {
      clearTimeout(debounceTimeoutRef.current);
    }

    debounceTimeoutRef.current = setTimeout(async () => {
      await updateWeightsInConfig(newWeights);
      if (query.trim()) {
        executeSearch(query.trim());
      }
    }, 150);
  };

  const executeSearch = async (searchQuery) => {
    if (!root || !searchQuery.trim()) return;
    
    setLoading(true);
    setStatusMessage(`Searching for "${searchQuery}"...`);
    setResults('Querying index...\n');
    
    const args = [searchQuery.trim()];
    if (useSemantic) args.push('--semantic');

    const res = await api.runKoshCommand(root, 'query', args);
    if (res.ok) {
      setResults(res.stdout || 'No results found.');
    } else {
      setResults(`Search failed:\n${res.stderr}`);
    }
    
    setStatusMessage('Search complete');
    setLoading(false);
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    await executeSearch(query);
  };

  const handleRebuildEmbeddings = async () => {
    if (!root) return;
    setEmbedLoading(true);
    setStatusMessage('Rebuilding vector embeddings...');
    setEmbedOutput('Running embedder pipeline...\n');
    
    const res = await api.runKoshCommand(root, 'embed', []);
    if (res.ok) {
      setEmbedOutput(prev => prev + (res.stdout || 'Embeddings generated successfully.'));
    } else {
      setEmbedOutput(prev => prev + `Embedder failed:\n${res.stderr}`);
    }
    
    setStatusMessage('Embeddings rebuilt');
    setEmbedLoading(false);
  };

  return (
    <div className="p-8 h-full flex flex-col bg-brand-bg overflow-y-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-brand-text flex items-center gap-3">
            <SearchIcon className="text-brand-accent" size={28} />
            Memory Explorer
          </h1>
          <p className="text-brand-muted mt-1">Full-Text and Semantic Vector Search</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-[400px]">
        
        {/* Search Interface (Spans 2 columns) */}
        <div className="lg:col-span-2 bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col">
          <form onSubmit={handleSearch} className="mb-6">
            <div className="relative flex items-center mb-4">
              <div className="absolute left-4 text-brand-muted">
                <SearchIcon size={20} />
              </div>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search across all decisions, prompts, and projects..."
                className="w-full bg-brand-surface border border-brand-border rounded-xl py-4 pl-12 pr-4 text-brand-text focus:outline-none focus:border-brand-accent transition-colors shadow-inner font-medium placeholder-brand-muted/50"
              />
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="absolute right-2 bg-brand-accent hover:bg-brand-accentHover text-white px-6 py-2.5 rounded-lg font-bold transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2"
              >
                {loading ? <RefreshCcw size={16} className="animate-spin" /> : 'Search'}
              </button>
            </div>
            
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-6 text-sm font-medium">
                <label className="flex items-center gap-2 cursor-pointer group">
                  <input
                    type="radio"
                    checked={!useSemantic}
                    onChange={() => setUseSemantic(false)}
                    className="w-4 h-4 text-brand-accent bg-brand-surface border-brand-border focus:ring-brand-accent focus:ring-2"
                  />
                  <span className={`flex items-center gap-1 ${!useSemantic ? 'text-brand-text font-bold' : 'text-brand-muted group-hover:text-brand-text'}`}>
                    <Database size={16} className={!useSemantic ? 'text-brand-accent' : ''} /> Full-Text (FTS5)
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer group">
                  <input
                    type="radio"
                    checked={useSemantic}
                    onChange={() => setUseSemantic(true)}
                    className="w-4 h-4 text-brand-accent bg-brand-surface border-brand-border focus:ring-brand-accent focus:ring-2"
                  />
                  <span className={`flex items-center gap-1 ${useSemantic ? 'text-brand-text font-bold' : 'text-brand-muted group-hover:text-brand-text'}`}>
                    <Zap size={16} className={useSemantic ? 'text-brand-warning' : ''} /> Semantic (TF-IDF/Vector)
                  </span>
                </label>
              </div>

              <button
                type="button"
                onClick={() => setShowCognitiveTuning(!showCognitiveTuning)}
                className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-brand-muted hover:text-brand-accent transition-colors bg-brand-surface/40 hover:bg-brand-surface border border-brand-border/40 py-1.5 px-3 rounded-lg shadow-sm"
              >
                <SlidersIcon size={14} className={showCognitiveTuning ? 'text-brand-accent' : ''} />
                {showCognitiveTuning ? 'Hide Tuning' : 'Tune Weights'}
              </button>
            </div>
          </form>

          {showCognitiveTuning && (
            <div className="mb-6 bg-brand-surface/30 border border-brand-border/60 rounded-xl p-5 flex flex-col gap-4 shadow-sm select-none">
              <div className="flex items-center gap-2 border-b border-brand-border/40 pb-2 mb-1">
                <SlidersIcon size={14} className="text-brand-accent" />
                <span className="text-xs font-bold text-brand-text uppercase tracking-widest">Cognitive Control Center</span>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-xs font-semibold">
                    <span className="text-brand-muted">Cognitive Bias Ratio</span>
                    <span className="text-brand-text font-mono">{(weights.beta_sem * 100).toFixed(0)}% Sem / {(weights.beta_proc * 100).toFixed(0)}% Proc</span>
                  </div>
                  <input
                    type="range"
                    min="0.0"
                    max="1.0"
                    step="0.05"
                    value={weights.beta_sem}
                    onChange={(e) => handleWeightChange('beta_sem', e.target.value)}
                    className="w-full h-1 bg-brand-border rounded-lg appearance-none cursor-pointer accent-brand-accent"
                  />
                  <div className="flex justify-between text-[9px] text-brand-muted font-medium mt-0.5">
                    <span>Pure Proc</span>
                    <span>Balanced</span>
                    <span>Pure Sem</span>
                  </div>
                </div>

                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-xs font-semibold">
                    <span className="text-brand-muted">Spatiotemporal Gravity (α)</span>
                    <span className="text-brand-text font-mono">{weights.alpha.toFixed(3)}</span>
                  </div>
                  <input
                    type="range"
                    min="0.0"
                    max="0.1"
                    step="0.005"
                    value={weights.alpha}
                    onChange={(e) => handleWeightChange('alpha', e.target.value)}
                    className="w-full h-1 bg-brand-border rounded-lg appearance-none cursor-pointer accent-brand-accent"
                  />
                  <div className="flex justify-between text-[9px] text-brand-muted font-medium mt-0.5">
                    <span>No Decay</span>
                    <span>Std (0.02)</span>
                    <span>High Decay</span>
                  </div>
                </div>

                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-xs font-semibold">
                    <span className="text-brand-muted">Associative Novelty Boost (γ)</span>
                    <span className="text-brand-text font-mono">{weights.gamma.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0.0"
                    max="2.0"
                    step="0.05"
                    value={weights.gamma}
                    onChange={(e) => handleWeightChange('gamma', e.target.value)}
                    className="w-full h-1 bg-brand-border rounded-lg appearance-none cursor-pointer accent-brand-accent"
                  />
                  <div className="flex justify-between text-[9px] text-brand-muted font-medium mt-0.5">
                    <span>No Boost</span>
                    <span>Std (0.50)</span>
                    <span>High Boost</span>
                  </div>
                </div>

                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between text-xs font-semibold">
                    <span className="text-brand-muted">Base Gating Threshold (τ)</span>
                    <span className="text-brand-text font-mono">{weights.tau.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0.0"
                    max="1.0"
                    step="0.05"
                    value={weights.tau}
                    onChange={(e) => handleWeightChange('tau', e.target.value)}
                    className="w-full h-1 bg-brand-border rounded-lg appearance-none cursor-pointer accent-brand-accent"
                  />
                  <div className="flex justify-between text-[9px] text-brand-muted font-medium mt-0.5">
                    <span>Accept All</span>
                    <span>Std (0.50)</span>
                    <span>Strict (1.0)</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="flex-1 bg-[#1C1917] p-6 rounded-xl border border-[#2D1B14] font-mono text-sm overflow-auto text-brand-text whitespace-pre-wrap shadow-inner leading-relaxed">
             {results || <span className="text-brand-muted italic opacity-70">Execute a query to see results...</span>}
          </div>
        </div>

        {/* Index Management */}
        <div className="bg-brand-panel p-6 rounded-2xl border border-brand-border shadow-sm flex flex-col h-full">
          <div className="flex items-center gap-2 mb-6">
            <Box className="text-brand-muted" size={18} />
            <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted">Index Control</h2>
          </div>
          
          <p className="text-sm text-brand-muted mb-6 leading-relaxed">
            The semantic search requires an offline vector index. If you have recently absorbed many new receipts or completed a large intake scan, you should rebuild the semantic graph.
          </p>

          <button
            onClick={handleRebuildEmbeddings}
            disabled={embedLoading || !root}
            className="flex items-center justify-center gap-2 w-full bg-brand-surface hover:bg-brand-border text-brand-text border border-brand-border py-3 rounded-xl font-bold transition-all shadow-sm disabled:opacity-50"
          >
            <RefreshCcw size={16} className={embedLoading ? "animate-spin text-brand-accent" : "text-brand-accent"} />
            {embedLoading ? 'Building Vectors...' : 'Rebuild Embeddings'}
          </button>
          
          {embedOutput && (
            <div className="mt-6 flex-1 bg-[#1C1917] p-4 rounded-xl border border-[#2D1B14] font-mono text-xs overflow-auto text-brand-success whitespace-pre-wrap shadow-inner">
               {embedOutput}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
