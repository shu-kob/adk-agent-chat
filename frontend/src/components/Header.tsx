import React from 'react';
import { Bot, RotateCcw, Sparkles, Scale, GitCompare } from 'lucide-react';
import { CompareModelOption } from '../types';

const DEFAULT_COMPARE_OPTIONS: CompareModelOption[] = [
  { id: 'random', name: '🎲 ランダム比較モード' },
  { id: 'gemini-3.5-flash-lite', name: '3.5-flash-lite' },
  { id: 'gemini-3.5-flash', name: '3.5-flash' },
  { id: 'gemini-4-argon', name: '4-argon' },
];

interface HeaderProps {
  modelName: string;
  abTestMode: 'auto' | 'always' | 'off';
  onChangeAbTestMode: (mode: 'auto' | 'always' | 'off') => void;
  compareModel: string;
  onChangeCompareModel: (model: string) => void;
  compareOptions?: CompareModelOption[];
  onResetSession: () => void;
  isLoading: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  modelName,
  abTestMode,
  onChangeAbTestMode,
  compareModel,
  onChangeCompareModel,
  compareOptions = DEFAULT_COMPARE_OPTIONS,
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

        {/* Compare Target Model Selector */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs transition-opacity ${
            abTestMode === 'off'
              ? 'opacity-40 pointer-events-none bg-slate-800/40 border-slate-700/40 text-slate-400'
              : 'bg-emerald-950/40 border-emerald-500/30 text-emerald-300'
          }`}
          title="Side-by-Side 比較対象モデル"
        >
          <GitCompare size={13} className={abTestMode === 'off' ? 'text-slate-400' : 'text-emerald-400'} />
          <span className="font-medium text-emerald-200">比較対象:</span>
          <select
            value={compareModel}
            onChange={(e) => onChangeCompareModel(e.target.value)}
            disabled={abTestMode === 'off'}
            className="bg-transparent text-white font-semibold cursor-pointer outline-none text-xs"
          >
            {compareOptions.map((opt) => (
              <option key={opt.id} value={opt.id} className="bg-slate-900 text-white">
                {opt.name}
              </option>
            ))}
          </select>
        </div>

        <div className="badge-model" title="標準ベースラインモデル">
          <Sparkles size={14} className="sparkle-icon" />
          <span>標準: {modelName}</span>
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
