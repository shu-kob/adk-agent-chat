import React from 'react';
import { Bot, RotateCcw, Sparkles } from 'lucide-react';

interface HeaderProps {
  modelName: string;
  onResetSession: () => void;
  isLoading: boolean;
}

export const Header: React.FC<HeaderProps> = ({ modelName, onResetSession, isLoading }) => {
  return (
    <header className="app-header">
      <div className="brand-section">
        <div className="brand-icon">
          <Bot size={22} />
        </div>
        <div className="brand-title">
          <h1>ADK Agent Chat</h1>
          <span>Powered by Google Agent Development Kit</span>
        </div>
      </div>

      <div className="header-actions">
        <div className="badge-model" title="Configured Model">
          <Sparkles size={14} className="sparkle-icon" />
          <span>{modelName}</span>
          <span className="status-dot"></span>
        </div>

        <button
          className="btn-icon"
          onClick={onResetSession}
          disabled={isLoading}
          title="会話セッションをリセット"
        >
          <RotateCcw size={16} />
          <span>会話をリセット</span>
        </button>
      </div>
    </header>
  );
};
