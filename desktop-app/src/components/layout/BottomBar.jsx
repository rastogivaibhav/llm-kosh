import React from 'react';

export default function BottomBar({ rootPath, statusMessage }) {
  return (
    <div className="h-6 bg-vscode-statusBar text-white text-xs flex items-center px-3 justify-between">
      <div className="flex items-center space-x-4">
        <span>llm-kosh Desktop</span>
        {rootPath && (
          <span className="truncate max-w-[400px]" title={rootPath}>
            {rootPath}
          </span>
        )}
      </div>
      <div>
        <span>{statusMessage || 'Ready'}</span>
      </div>
    </div>
  );
}
