import React, { useState } from 'react';
import { PROMPTS } from '../data/prompts';
import { searchPrompts } from '../lib/prompt-search';
import { Search, Copy, Check } from 'lucide-react';

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
    <div className="p-6 h-full flex flex-col overflow-hidden">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-semibold">Prompt Library</h1>
        
        <div className="relative w-64">
          <input 
            type="text" 
            placeholder="Search prompts..." 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full bg-vscode-inputBg border border-vscode-border rounded py-2 pl-10 pr-4 text-sm text-white focus:outline-none focus:border-vscode-buttonPrimary"
          />
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
        </div>
      </div>

      <div className="flex-1 overflow-auto pr-2">
        {filteredPrompts.length === 0 ? (
          <div className="text-gray-500 text-center mt-10">No prompts found matching your search.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pb-6">
            {filteredPrompts.map((prompt) => (
              <div key={prompt.id} className="bg-vscode-inputBg rounded border border-vscode-border flex flex-col">
                <div className="p-4 border-b border-vscode-border flex justify-between items-start bg-[#1e1e1e] rounded-t">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-200">{prompt.title}</h2>
                    <p className="text-sm text-gray-400 mt-1">{prompt.description}</p>
                  </div>
                  <button 
                    onClick={() => handleCopy(prompt.id, prompt.content)}
                    className="ml-4 p-2 rounded hover:bg-vscode-hover transition-colors text-gray-300 hover:text-white"
                    title="Copy to clipboard"
                  >
                    {copiedId === prompt.id ? (
                      <Check className="w-5 h-5 text-green-500" />
                    ) : (
                      <Copy className="w-5 h-5" />
                    )}
                  </button>
                </div>
                <div className="p-4 flex-1 bg-[#0d0d0d] rounded-b overflow-auto relative">
                  <pre className="text-xs font-mono text-green-300 whitespace-pre-wrap font-medium">
                    {prompt.content}
                  </pre>
                  {copiedId === prompt.id && (
                    <div className="absolute top-2 right-4 bg-green-900/80 text-green-100 text-xs px-2 py-1 rounded shadow animate-fade-in-out">
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
