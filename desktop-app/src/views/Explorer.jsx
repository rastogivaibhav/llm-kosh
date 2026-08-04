import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../lib/api';
import { 
  Folder, FolderOpen, FileText, ChevronRight, ChevronDown, 
  Plus, Trash2, Shield, Eye, Code, FileCode, Monitor, 
  CheckCircle, Database, AlertCircle, Compass 
} from 'lucide-react';

// --- Recursive Folder Node Component ---
function FileNode({ node, onFileSelect, expandedFolders, toggleFolder, folderContents }) {
  const isExpanded = expandedFolders[node.path];
  const children = folderContents[node.path] || [];

  if (node.isDirectory) {
    return (
      <div className="select-none text-sm font-medium">
        <button 
          onClick={() => toggleFolder(node.path)}
          className="flex items-center gap-1.5 w-full text-left py-1 px-2 hover:bg-brand-surface rounded text-brand-text/90 hover:text-brand-text transition-colors group"
        >
          <span className="text-brand-muted group-hover:text-brand-text transition-colors">
            {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </span>
          <span className="text-brand-accent">
            {isExpanded ? <FolderOpen size={16} /> : <Folder size={16} />}
          </span>
          <span className="truncate flex-1">{node.name}</span>
        </button>
        
        {isExpanded && (
          <div className="pl-4 border-l border-brand-border/30 ml-3.5 my-0.5 flex flex-col gap-0.5">
            {children.length === 0 ? (
              <span className="text-xs text-brand-muted italic py-0.5 pl-6">Empty folder</span>
            ) : (
              children.map(child => (
                <FileNode 
                  key={child.path} 
                  node={child} 
                  onFileSelect={onFileSelect}
                  expandedFolders={expandedFolders}
                  toggleFolder={toggleFolder}
                  folderContents={folderContents}
                />
              ))
            )}
          </div>
        )}
      </div>
    );
  }

  // Render File Node
  const isMd = node.name.toLowerCase().endswith?.('.md') || node.name.toLowerCase().endsWith('.md');
  const isJson = node.name.toLowerCase().endswith?.('.json') || node.name.toLowerCase().endsWith('.json');

  return (
    <button 
      onClick={() => onFileSelect(node)}
      className="flex items-center gap-2 w-full text-left py-1 px-6 hover:bg-brand-surface rounded text-sm text-brand-muted hover:text-brand-text transition-colors group"
    >
      <span className={isMd ? "text-brand-accent" : isJson ? "text-brand-warning" : "text-brand-muted"}>
        {isMd ? <FileText size={15} /> : <FileCode size={15} />}
      </span>
      <span className="truncate">{node.name}</span>
    </button>
  );
}

// Simple Custom Markdown Renderer
function MarkdownRenderer({ content }) {
  const lines = content.split('\n');
  let inCodeBlock = false;
  let codeBuffer = [];

  const renderedLines = [];

  lines.forEach((line, index) => {
    const trimmed = line.trim();

    // Code Blocks
    if (trimmed.startsWith('```')) {
      if (inCodeBlock) {
        inCodeBlock = false;
        renderedLines.push(
          <pre key={`code-${index}`} className="bg-brand-bg/70 border border-brand-border/40 p-4 rounded-xl font-mono text-xs overflow-x-auto my-3 text-brand-text shadow-inner">
            <code>{codeBuffer.join('\n')}</code>
          </pre>
        );
        codeBuffer = [];
      } else {
        inCodeBlock = true;
      }
      return;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      return;
    }

    // Headers
    if (trimmed.startsWith('# ')) {
      renderedLines.push(<h1 key={index} className="text-2xl font-bold text-brand-text border-b border-brand-border/40 pb-2 mt-6 mb-3">{trimmed.substring(2)}</h1>);
    } else if (trimmed.startsWith('## ')) {
      renderedLines.push(<h2 key={index} className="text-xl font-bold text-brand-accent mt-5 mb-2">{trimmed.substring(3)}</h2>);
    } else if (trimmed.startsWith('### ')) {
      renderedLines.push(<h3 key={index} className="text-base font-bold text-brand-text/90 mt-4 mb-2">{trimmed.substring(4)}</h3>);
    } 
    // Bullet Points
    else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      renderedLines.push(<li key={index} className="ml-4 text-brand-muted text-sm my-1 list-disc">{trimmed.substring(2)}</li>);
    } 
    // Horizontal Rule
    else if (trimmed === '---' || trimmed === '***') {
      renderedLines.push(<hr key={index} className="border-brand-border/30 my-4" />);
    } 
    // Plain Paragraph
    else if (trimmed) {
      renderedLines.push(<p key={index} className="text-sm text-brand-muted/95 leading-relaxed my-2">{line}</p>);
    } else {
      renderedLines.push(<div key={index} className="h-2" />);
    }
  });

  return (
    <div className="markdown-body select-text select-all">
      {renderedLines}
    </div>
  );
}

export default function Explorer({ config, setStatusMessage }) {
  const rootPath = config?.cartridgeRoot || '';
  const [rootNode, setRootNode] = useState(null);
  const [watchedFolders, setWatchedFolders] = useState([]);
  
  // File Tree Cache States
  const [expandedFolders, setExpandedFolders] = useState({});
  const [folderContents, setFolderContents] = useState({});

  // Active Open File States
  const [activeFile, setActiveFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [viewMode, setViewMode] = useState('preview'); // preview | source
  const [fileLoading, setFileLoading] = useState(false);

  // Read Directory Contents
  const fetchFolderItems = useCallback(async (dirPath) => {
    const res = await api.readDirectory(dirPath);
    if (res.success) {
      // Sort: Directories first, then files alphabetically
      const sorted = (res.items || []).sort((a, b) => {
        if (a.isDirectory && !b.isDirectory) return -1;
        if (!a.isDirectory && b.isDirectory) return 1;
        return a.name.localeCompare(b.name);
      });
      setFolderContents(prev => ({ ...prev, [dirPath]: sorted }));
    }
  }, []);

  // Load Watched Folders
  const loadWatchedFolders = useCallback(async () => {
    const res = await api.listWatchedFolders();
    if (res.success) {
      setWatchedFolders(res.folders);
      // Refresh watched folder items
      for (const folder of res.folders) {
        fetchFolderItems(folder);
      }
    }
  }, [fetchFolderItems]);

  // Toggle expand / collapse folder
  const toggleFolder = async (dirPath) => {
    const isExpanded = expandedFolders[dirPath];
    setExpandedFolders(prev => ({ ...prev, [dirPath]: !isExpanded }));
    
    // Always refresh on open
    if (!isExpanded) {
      await fetchFolderItems(dirPath);
    }
  };

  // Select File to view
  const handleFileSelect = async (node) => {
    setFileLoading(true);
    setActiveFile(node);
    setStatusMessage(`Opening ${node.name}...`);
    
    const res = await api.readReceiptFile(node.path);
    if (res.success) {
      setFileContent(res.content);
      // Auto toggle to source for non-markdown
      const isMd = node.name.toLowerCase().endsWith('.md');
      setViewMode(isMd ? 'preview' : 'source');
      setStatusMessage('File loaded');
    } else {
      setFileContent(`Error loading file: ${res.error}`);
      setViewMode('source');
      setStatusMessage('Load failed');
    }
    setFileLoading(false);
  };

  // Add Watched Folder
  const handleAddWatchedFolder = async () => {
    const res = await api.addWatchedFolder();
    if (res.success) {
      loadWatchedFolders();
      setStatusMessage('Watched folder added');
    }
  };

  // Remove Watched Folder
  const handleRemoveWatchedFolder = async (e, path) => {
    e.stopPropagation();
    const res = await api.removeWatchedFolder(path);
    if (res.success) {
      loadWatchedFolders();
      setStatusMessage('Watched folder removed');
    }
  };

  // Refresh tree contents
  const handleRefreshWorkspace = useCallback(async () => {
    if (rootPath) {
      setRootNode({
        name: rootPath.split('\\').pop() || rootPath.split('/').pop() || 'Cartridge Root',
        path: rootPath,
        isDirectory: true
      });
      fetchFolderItems(rootPath);
    }
    loadWatchedFolders();
  }, [rootPath, loadWatchedFolders, fetchFolderItems]);

  useEffect(() => {
    handleRefreshWorkspace();
  }, [handleRefreshWorkspace]);

  // Line counter layout helper for source code raw view
  const renderSourceWithLines = () => {
    if (!fileContent) return <span className="text-brand-muted italic">No content</span>;
    const lines = fileContent.split('\n');
    return (
      <div className="flex font-mono text-sm leading-relaxed select-text select-all">
        {/* Line Numbers */}
        <div className="text-right text-brand-muted/40 pr-4 border-r border-brand-border/20 select-none min-w-[3rem] bg-brand-bg/20">
          {lines.map((_, i) => (
            <div key={i}>{i + 1}</div>
          ))}
        </div>
        {/* Source Text */}
        <div className="pl-4 flex-1 text-brand-text/90 whitespace-pre overflow-x-auto select-text">
          {lines.map((line, i) => (
            <div key={i} className="hover:bg-brand-surface/30 px-1">{line || ' '}</div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-1 overflow-hidden bg-brand-bg h-full">
      {/* ─── File Explorer Left Panel ─── */}
      <div className="w-80 flex-shrink-0 border-r border-brand-border bg-brand-panel flex flex-col overflow-hidden h-full">
        {/* Panel Header */}
        <div className="p-4 border-b border-brand-border/60 flex items-center justify-between">
          <h2 className="text-sm font-bold tracking-widest uppercase text-brand-muted flex items-center gap-2">
            <Compass size={16} /> Explorer
          </h2>
        </div>

        {/* Tree Container */}
        <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-6">
          
          {/* Section 1: Active Cartridge */}
          <div>
            <h3 className="text-xs font-semibold text-brand-muted uppercase mb-2 px-2 flex items-center justify-between">
              <span>Active Workspace</span>
              <span className="text-[10px] text-brand-accent px-1.5 py-0.5 rounded border border-brand-accent/20 bg-brand-accent/5 font-mono">LOCAL</span>
            </h3>
            
            {rootNode ? (
              <div className="flex flex-col gap-0.5">
                <FileNode 
                  node={rootNode} 
                  onFileSelect={handleFileSelect}
                  expandedFolders={expandedFolders}
                  toggleFolder={toggleFolder}
                  folderContents={folderContents}
                />
              </div>
            ) : (
              <span className="text-xs text-brand-muted italic px-2">No workspace cartridge initialized.</span>
            )}
          </div>

          {/* Section 2: Watched Folders */}
          <div>
            <h3 className="text-xs font-semibold text-brand-muted uppercase mb-2 px-2 flex items-center justify-between">
              <span>Watched Folders</span>
              <button 
                onClick={handleAddWatchedFolder}
                className="text-brand-accent hover:text-brand-accentHover p-1 hover:bg-brand-surface rounded transition-colors"
                title="Add folder to watch"
              >
                <Plus size={14} />
              </button>
            </h3>

            <div className="flex flex-col gap-2">
              {watchedFolders.length === 0 ? (
                <span className="text-xs text-brand-muted italic px-2">No source folders configured.</span>
              ) : (
                watchedFolders.map(folder => {
                  const folderNode = {
                    name: folder.split('\\').pop() || folder.split('/').pop() || folder,
                    path: folder,
                    isDirectory: true
                  };
                  return (
                    <div key={folder} className="group relative border border-brand-border/30 rounded-lg p-1.5 bg-brand-bg/40">
                      <div className="flex items-center justify-between pr-8">
                        <FileNode 
                          node={folderNode} 
                          onFileSelect={handleFileSelect}
                          expandedFolders={expandedFolders}
                          toggleFolder={toggleFolder}
                          folderContents={folderContents}
                        />
                      </div>
                      <button 
                        onClick={(e) => handleRemoveWatchedFolder(e, folder)}
                        className="absolute right-2 top-2 text-brand-muted hover:text-brand-danger opacity-0 group-hover:opacity-100 p-1 hover:bg-brand-surface rounded transition-all"
                        title="Stop watching folder"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ─── File Viewer Right Panel ─── */}
      <div className="flex-1 flex flex-col bg-brand-bg overflow-hidden h-full">
        {activeFile ? (
          <div className="flex-1 flex flex-col overflow-hidden">
            
            {/* Header Tab Bar */}
            <div className="h-11 border-b border-brand-border bg-brand-panel flex items-center justify-between px-6">
              {/* File Title */}
              <div className="flex items-center gap-2 truncate">
                <FileText size={16} className="text-brand-accent flex-shrink-0" />
                <span className="text-sm font-semibold text-brand-text truncate" title={activeFile.path}>
                  {activeFile.name}
                </span>
                <span className="text-xs text-brand-muted truncate max-w-[200px] hover:text-brand-text transition-colors cursor-help" title={activeFile.path}>
                  ({activeFile.path})
                </span>
              </div>

              {/* Toolbar Controls */}
              <div className="flex items-center gap-3">
                {activeFile.name.toLowerCase().endsWith('.md') && (
                  <div className="flex border border-brand-border rounded-lg overflow-hidden bg-brand-surface p-0.5">
                    <button 
                      onClick={() => setViewMode('preview')}
                      className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-bold transition-all ${
                        viewMode === 'preview' 
                          ? 'bg-brand-accent text-white shadow-sm' 
                          : 'text-brand-muted hover:text-brand-text'
                      }`}
                    >
                      <Eye size={13} /> Preview
                    </button>
                    <button 
                      onClick={() => setViewMode('source')}
                      className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-bold transition-all ${
                        viewMode === 'source' 
                          ? 'bg-brand-accent text-white shadow-sm' 
                          : 'text-brand-muted hover:text-brand-text'
                      }`}
                    >
                      <Code size={13} /> Source
                    </button>
                  </div>
                )}
                
                <button 
                  onClick={() => api.revealInFolder(activeFile.path)}
                  className="text-xs font-bold border border-brand-border hover:border-brand-accent/50 hover:bg-brand-surface text-brand-text px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-all"
                >
                  <Monitor size={13} /> Reveal
                </button>
              </div>
            </div>

            {/* Viewer Area */}
            <div className="flex-1 overflow-auto p-8 relative">
              {fileLoading ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-brand-bg/50 backdrop-blur-sm">
                  <div className="w-8 h-8 rounded-full border-2 border-brand-accent border-t-transparent animate-spin mb-2"></div>
                  <span className="text-sm text-brand-muted font-medium">Opening File...</span>
                </div>
              ) : (
                <div className="max-w-4xl mx-auto bg-brand-panel/30 border border-brand-border/40 p-6 md:p-8 rounded-2xl shadow-sm h-fit">
                  {viewMode === 'preview' ? (
                    <MarkdownRenderer content={fileContent} />
                  ) : (
                    renderSourceWithLines()
                  )}
                </div>
              )}
            </div>

            {/* Viewer Footer */}
            <div className="h-6 border-t border-brand-border bg-brand-panel px-6 flex items-center justify-between text-[11px] font-mono text-brand-muted select-none">
              <div>
                Character count: <span className="text-brand-text">{fileContent.length}</span>
              </div>
              <div>
                Type: <span className="text-brand-text">{activeFile.name.split('.').pop()?.toUpperCase() || 'UNKNOWN'}</span>
              </div>
            </div>

          </div>
        ) : (
          /* Empty Splash State */
          <div className="flex-1 flex flex-col items-center justify-center p-8 select-none">
            <div className="w-16 h-16 rounded-2xl bg-brand-panel border border-brand-border flex items-center justify-center mb-6 shadow-inner text-brand-accent/70">
              <Database size={32} />
            </div>
            <h2 className="text-xl font-bold text-brand-text mb-2">Workspace & Watched Folder Explorer</h2>
            <p className="text-sm text-brand-muted text-center max-w-md mb-8 leading-relaxed">
              Explore memory vault items, reference-only source folders, and inspected evidence.
            </p>
            <div className="grid grid-cols-2 gap-4 max-w-md w-full">
              <div className="bg-brand-panel p-4 rounded-xl border border-brand-border/60 flex flex-col items-center text-center">
                <CheckCircle size={18} className="text-brand-success mb-2" />
                <span className="text-xs font-bold text-brand-text mb-1">Click Folders</span>
                <span className="text-[11px] text-brand-muted">Expand directories to navigate project documents.</span>
              </div>
              <div className="bg-brand-panel p-4 rounded-xl border border-brand-border/60 flex flex-col items-center text-center">
                <Shield size={18} className="text-brand-accent mb-2" />
                <span className="text-xs font-bold text-brand-text mb-1">Watch Folders</span>
                <span className="text-[11px] text-brand-muted">Prune or configure directory listeners at will.</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
