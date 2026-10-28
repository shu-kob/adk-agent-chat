/**
 * フロントエンド上部メニューバー（ヘッダー）コンポーネント (frontend/src/components/Header.tsx)
 *
 * 【役割】
 * - アプリケーションタイトルとブランドアイコンの表示
 * - A/Bテストモード（自動 / 常時オン / オフ）の切り替え
 * - Side-by-Side 比較対象モデルの選択
 * - 動的モデルルーティングモード（自動 / 固定）の切り替え
 * - 現在の標準 Gemini バージョン（ベースラインモデル名）の常時バッジ表示
 * - バッチ FinOps モーダル起動および会話セッションリセット操作の提供
 */
import React from 'react';
import { Bot, RotateCcw, Sparkles, Scale, GitCompare, Compass } from 'lucide-react';
import { CompareModelOption } from '../types';

/** Side-by-Side 比較対象モデルのデフォルト選択肢リスト */
const DEFAULT_COMPARE_OPTIONS: CompareModelOption[] = [
  { id: 'random', name: '🎲 ランダム比較モード' },
  { id: 'gemini-3.5-flash-lite', name: '3.5-flash-lite' },
  { id: 'gemini-3.5-flash', name: '3.5-flash' },
  { id: 'gemini-4-argon', name: '4-argon' },
];

/**
 * Header コンポーネントのプロパティ定義
 * @property modelName - バックエンドに設定されている現在の標準 Gemini モデル名（例: 'gemini-3.8-flash'）
 * @property abTestMode - Side-by-Side A/Bテストの発生モード ('auto' | 'always' | 'off')
 * @property onChangeAbTestMode - A/Bテストモード変更時のコールバック関数
 * @property compareModel - 選択中の比較対象モデルID
 * @property onChangeCompareModel - 比較対象モデル変更時のコールバック関数
 * @property compareOptions - 選択可能な比較対象モデルのリスト（省略時は DEFAULT_COMPARE_OPTIONS）
 * @property routingMode - ルーティングモード ('auto': 動的ルーティング, 'manual': 標準モデル固定)
 * @property onChangeRoutingMode - ルーティングモード変更時のコールバック関数
 * @property onOpenFinOps - バッチ FinOps モーダルを開くコールバック関数（任意）
 * @property onResetSession - 会話セッションをリセットするコールバック関数
 * @property isLoading - 応答生成中かどうかのフラグ（ローディング中はリセットボタン等を無効化）
 */
interface HeaderProps {
  modelName: string;
  abTestMode: 'auto' | 'always' | 'off';
  onChangeAbTestMode: (mode: 'auto' | 'always' | 'off') => void;
  compareModel: string;
  onChangeCompareModel: (model: string) => void;
  compareOptions?: CompareModelOption[];
  routingMode: 'auto' | 'manual';
  onChangeRoutingMode: (mode: 'auto' | 'manual') => void;
  onOpenFinOps?: () => void;
  onResetSession: () => void;
  isLoading: boolean;
}

/**
 * アプリケーション上部のメニューバー（ヘッダー）を描画するコンポーネント
 * @param props - HeaderProps
 * @returns JSX.Element
 */
export const Header: React.FC<HeaderProps> = ({
  modelName,
  abTestMode,
  onChangeAbTestMode,
  compareModel,
  onChangeCompareModel,
  compareOptions = DEFAULT_COMPARE_OPTIONS,
  routingMode,
  onChangeRoutingMode,
  onOpenFinOps,
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

        {/* Dynamic Routing Mode Selector */}
        <div
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-cyan-950/40 border border-cyan-500/30 text-xs"
          title="クエリの性質に応じて最適モデルを自動選定（高度推論: 3.8-flash / 日常共感: 3.5-lite）"
        >
          <Compass size={13} className="text-cyan-400" />
          <span className="font-medium text-cyan-200">ルーティング:</span>
          <select
            value={routingMode}
            onChange={(e) => onChangeRoutingMode(e.target.value as any)}
            className="bg-transparent text-white font-semibold cursor-pointer outline-none text-xs"
          >
            <option value="auto" className="bg-slate-900 text-white">🧭 動的 (Contextual)</option>
            <option value="manual" className="bg-slate-900 text-white">🔒 固定 ({modelName})</option>
          </select>
        </div>

        {/* Standard Gemini Version Badge: ルーティングモードに関わらず現在の標準モデルバージョンを常時表示 */}
        <div className="badge-model" title="標準ベースラインモデル">
          <Sparkles size={14} className="sparkle-icon" />
          <span>標準: {modelName}</span>
          <span className="status-dot"></span>
        </div>

        {onOpenFinOps && (
          <button
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-blue-600/40 to-emerald-600/30 border border-blue-500/40 text-blue-200 hover:text-white hover:border-blue-400 text-xs font-semibold shadow-sm transition-all"
            onClick={onOpenFinOps}
            title="Gemini Batch API 50% OFF コスト最適化試算を開く"
          >
            <span className="text-amber-400 font-bold">💰</span>
            <span>バッチFinOps</span>
          </button>
        )}

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
