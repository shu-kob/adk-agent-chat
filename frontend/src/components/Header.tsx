import React from 'react';
import { Bot, RotateCcw, Sparkles, Scale } from 'lucide-react';

interface HeaderProps {
  modelName: string;
  abTestMode: 'auto' | 'always' | 'off';
  onChangeAbTestMode: (mode: 'auto' | 'always' | 'off') => void;
  onResetSession: () => void;
  isLoading: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  modelName,
  abTestMode,
  onChangeAbTestMode,
  onResetSession,
  isLoading,
}) => {
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
        {/* A/B Test Mode Selector */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-indigo-950/50 border border-indigo-500/30 text-xs">
          <Scale size={13} className="text-indigo-400" />
          <span className="text-indigo-300 font-medium">A/Bテスト:</span>
          <select
            value={abTestMode}
            onChange={(e) => onChangeAbTestMode(e.target.value as any)}
            className="bg-transparent text-white font-semibold cursor-pointer outline-none text-xs"
          >
            <option value="auto" className="bg-slate-900 text-white">自動 (時々)</option>
            <option value="always" className="bg-slate-900 text-white">常時オン ⚡️</option>
            <option value="off" className="bg-slate-900 text-white">オフ</option>
          </select>
        </div>

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
