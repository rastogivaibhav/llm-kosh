import React, { useState } from 'react';
import { PROMPTS } from '../data/prompts';
import { searchPrompts } from '../lib/prompt-search';
import { Search, Copy, Check, BookOpen } from 'lucide-react';

export default function Prompts() {
  const [query, setQuery] = useState('');
  const [copiedId, setCopiedId] = useState(null);

  const filteredPrompts = searchPrompts(query, PROMPTS);

  const handleCopy = async (id, content) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  return (
    <div className="p-8 h-full flex flex-col bg-brand-bg overflow-y-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-brand-text flex items-center gap-3">
            <BookOpen className="text-brand-accent" size={28} />
            Skills & Prompts
          </h1>
          <p className="text-brand-muted mt-1">Ready-to-use receipts, skills, and connector layers for your LLMs.</p>
        </div>
        
        <div className="relative w-72">
          <input 
            type="text" 
            placeholder="Search templates..." 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full bg-brand-surface border border-brand-border rounded-xl py-3 pl-10 pr-4 text-sm text-brand-text font-bold focus:outline-none focus:border-brand-accent transition-colors placeholder-brand-muted/50 shadow-sm"
          />
          <Search className="absolute left-4 top-3.5 w-4 h-4 text-brand-muted" />
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {filteredPrompts.length === 0 ? (
          <div className="text-brand-muted text-center mt-12 bg-brand-surface p-12 rounded-2xl border-2 border-dashed border-brand-border">
            <Search size={32} className="mx-auto mb-4 opacity-50" />
            <p className="font-semibold text-lg">No prompts found matching your search.</p>
            <p className="text-sm opacity-75 mt-2">Try adjusting your keywords.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 pb-6">
            {filteredPrompts.map((prompt) => (
              <div key={prompt.id} className="bg-brand-panel rounded-2xl border border-brand-border shadow-sm flex flex-col overflow-hidden">
                <div className="p-5 border-b border-brand-border flex justify-between items-start bg-brand-surface">
                  <div>
                    <h2 className="text-lg font-bold text-brand-text">{prompt.title}</h2>
                    <p className="text-sm font-medium text-brand-muted mt-1">{prompt.description}</p>
                  </div>
                  <button 
                    onClick={() => handleCopy(prompt.id, prompt.content)}
                    className="ml-4 p-2 rounded-xl bg-brand-panel border border-brand-border hover:border-brand-accent hover:text-brand-accent transition-colors text-brand-text shadow-sm"
                    title="Copy to clipboard"
                  >
                    {copiedId === prompt.id ? (
                      <Check className="w-5 h-5 text-brand-success" />
                    ) : (
                      <Copy className="w-5 h-5" />
                    )}
                  </button>
                </div>
                <div className="p-5 flex-1 bg-[#1C1917] relative">
                  <pre className="text-xs font-mono text-brand-muted whitespace-pre-wrap leading-relaxed">
                    {prompt.content}
                  </pre>
                  {copiedId === prompt.id && (
                    <div className="absolute top-4 right-4 bg-brand-success/20 border border-brand-success/50 text-brand-success font-bold text-xs px-3 py-1.5 rounded-lg shadow-sm">
                      Copied!
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
