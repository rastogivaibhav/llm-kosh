import React, { useState } from 'react';
import { api } from '../lib/api';
import { Search as SearchIcon, Database, Zap, RefreshCcw, Box } from 'lucide-react';

export default function Search({ config, setStatusMessage }) {
  const [root] = useState(config?.cartridgeRoot || '');
  
  const [query, setQuery] = useState('');
  const [useSemantic, setUseSemantic] = useState(false);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState('');

  const [embedLoading, setEmbedLoading] = useState(false);
  const [embedOutput, setEmbedOutput] = useState('');

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!root || !query.trim()) return;
    
    setLoading(true);
    setStatusMessage(`Searching for "${query}"...`);
    setResults('Querying index...\n');
    
    const args = [query.trim()];
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
          </form>

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
