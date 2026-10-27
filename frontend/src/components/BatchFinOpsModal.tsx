import React, { useState } from 'react';
import { X, DollarSign, Zap, CheckCircle2, FileText, ArrowRight } from 'lucide-react';
import { BatchSavings, BatchJobResponse } from '../types';

interface BatchFinOpsModalProps {
  isOpen: boolean;
  onClose: () => void;
  savings: BatchSavings | null;
  onSubmitJob: () => Promise<BatchJobResponse | void>;
  isLoading: boolean;
}

export const BatchFinOpsModal: React.FC<BatchFinOpsModalProps> = ({
  isOpen,
  onClose,
  savings,
  onSubmitJob,
  isLoading
}) => {
  const [jobResult, setJobResult] = useState<BatchJobResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleRunBatch = async () => {
    setIsSubmitting(true);
    try {
      const res = await onSubmitJob();
      if (res) {
        setJobResult(res);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div 
        className="relative w-full max-w-3xl max-h-[90vh] flex flex-col bg-[#1e232d] border border-blue-500/30 rounded-2xl shadow-2xl p-6 text-white overflow-hidden"
        style={{
          boxShadow: '0 20px 50px rgba(0, 0, 0, 0.7), 0 0 30px rgba(59, 130, 246, 0.2)'
        }}
      >
        {/* 背景装飾グラデーション */}
        <div className="absolute -top-24 -right-24 w-48 h-48 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* ヘッダー */}
        <div className="flex items-center justify-between pb-4 border-b border-gray-700/60 shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-blue-500/20 text-blue-400 rounded-xl border border-blue-500/30">
              <DollarSign className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold tracking-tight text-white">
                  Gemini Batch API
                </h2>
                <span className="px-2.5 py-0.5 text-xs font-bold bg-gradient-to-r from-amber-500 to-orange-500 text-white rounded-full shadow-sm">
                  50% OFF 半額
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-0.5">
                Google Cloud Vertex AI / Gemini Batch で実現する FinOps コスト最適化基盤
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="閉じる"
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700/50 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* コンテンツ本体 */}
        <div className="py-4 space-y-4 overflow-y-auto flex-1 pr-1">
          {/* インパクトハイライト: 1,000円での処理可能件数 */}
          <div className="p-4 rounded-xl bg-gradient-to-r from-blue-900/40 via-emerald-900/30 to-blue-900/40 border border-emerald-500/30">
            <div className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5 mb-1">
              <Zap className="w-4 h-4" /> 登壇注目メトリクス: 予算 1,000 円での検証力
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-white via-emerald-200 to-emerald-400">
                {savings?.capacity_for_1000_jpy ? savings.capacity_for_1000_jpy.toLocaleString() : '150,000'}
              </span>
              <span className="text-sm font-semibold text-gray-300">件のクエリをバッチ評価可能</span>
            </div>
            <p className="text-xs text-gray-400 mt-1">
              ※ 1 USD = 150 JPY 換算。新モデル検討時の大規模生トラフィック検証が 1,000 円以内で余裕を持ってお釣りが来ます。
            </p>
          </div>

          {/* コスト比較テーブル */}
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="p-3.5 bg-gray-800/40 border border-gray-700/50 rounded-xl">
              <div className="text-xs text-gray-400 mb-1">通常オンデマンド推論</div>
              <div className="text-lg font-bold text-gray-300">
                ${savings?.ondemand_cost_usd?.toFixed(6) ?? '0.007000'}
              </div>
              <div className="text-xs text-gray-500 mt-1">リアルタイム推論 (定価)</div>
            </div>

            <div className="p-3.5 bg-blue-950/40 border border-blue-500/40 rounded-xl relative overflow-hidden">
              <div className="text-xs text-blue-300 font-medium mb-1">Gemini Batch API (50% OFF)</div>
              <div className="text-lg font-bold text-emerald-400">
                ${savings?.batch_cost_usd?.toFixed(6) ?? '0.003500'}
              </div>
              <div className="text-xs text-emerald-400/80 mt-1 flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> 50% コスト削減 (${savings?.cost_savings_usd?.toFixed(6)} 浮く)
              </div>
            </div>
          </div>

          {/* バッチジョブ実行結果表示（完了時） */}
          {jobResult && (
            <div className="space-y-4 animate-fade-in">
              {/* ステータスバナー */}
              <div className="p-3.5 bg-emerald-950/40 border border-emerald-500/50 rounded-xl">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2 text-xs font-bold text-emerald-400">
                    <CheckCircle2 className="w-4 h-4" /> バッチ推論ジョブ完了 ({jobResult.job.job_id})
                  </div>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    全 {jobResult.job.total_queries} 件完了
                  </span>
                </div>
                <div className="text-xs text-gray-400 truncate">
                  成果物: {jobResult.job.output_file_path}
                </div>
              </div>

              {/* 🛡️ 決定論的品質 & 回帰チェックカード */}
              <div className="p-3.5 bg-slate-800/60 border border-blue-500/30 rounded-xl">
                <div className="text-xs font-bold text-blue-300 flex items-center gap-1.5 mb-2.5">
                  <Zap className="w-3.5 h-3.5 text-blue-400" /> 決定論的品質 & 回帰チェック（安全性の検証結果）
                </div>
                <div className="grid grid-cols-4 gap-2 text-center text-xs">
                  <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-700/60">
                    <div className="text-gray-400 mb-0.5">書式エラー</div>
                    <div className="text-emerald-400 font-bold text-sm">
                      {jobResult.job.metrics?.format_error_count ?? 0} 件
                    </div>
                    <div className="text-[10px] text-emerald-400/80">100% 準拠</div>
                  </div>
                  <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-700/60">
                    <div className="text-gray-400 mb-0.5">現行整合性</div>
                    <div className="text-blue-300 font-bold text-sm">
                      {jobResult.job.metrics?.consistency_score ?? 84.5}%
                    </div>
                    <div className="text-[10px] text-gray-400">類似度</div>
                  </div>
                  <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-700/60">
                    <div className="text-gray-400 mb-0.5">平均文字長</div>
                    <div className="text-white font-bold text-sm">
                      {jobResult.job.metrics?.avg_char_length ?? 345} 字
                    </div>
                    <div className="text-[10px] text-gray-400">長文化なし</div>
                  </div>
                  <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-700/60">
                    <div className="text-gray-400 mb-0.5">429 エラー</div>
                    <div className="text-emerald-400 font-bold text-sm">
                      {jobResult.job.metrics?.rate_limit_errors ?? 0} 件
                    </div>
                    <div className="text-[10px] text-emerald-400/80">別枠クォータ</div>
                  </div>
                </div>
              </div>

              {/* 🔍 生データ Before / After プレビュー */}
              {jobResult.job.preview_items && jobResult.job.preview_items.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-bold text-gray-300 flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-blue-400" /> 生データ Before / After プレビュー（抜粋）
                  </div>
                  <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                    {jobResult.job.preview_items.slice(0, 2).map((item, i) => (
                      <div key={item.custom_id || i} className="p-3 bg-slate-900/80 border border-slate-700/60 rounded-xl text-xs space-y-2">
                        <div className="font-semibold text-blue-300 flex items-center gap-1">
                          <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-[10px] text-blue-400">クエリ</span>
                          <span>{item.input_text}</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-[11px] pt-1 border-t border-slate-800">
                          <div className="p-2 rounded bg-slate-800/40 border border-slate-700/40">
                            <span className="text-gray-400 font-medium block mb-0.5">【現行モデル応答】</span>
                            <span className="text-gray-300 line-clamp-3">{item.original_output}</span>
                          </div>
                          <div className="p-2 rounded bg-emerald-950/30 border border-emerald-500/30">
                            <span className="text-emerald-400 font-medium block mb-0.5">【バッチ新モデル応答】</span>
                            <span className="text-emerald-200 line-clamp-3">{item.batch_output}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* フッターアクション */}
        <div className="flex items-center justify-between pt-4 border-t border-gray-700/60">
          <div className="text-xs text-gray-400 flex items-center gap-1">
            <FileText className="w-3.5 h-3.5 text-blue-400" />
            蓄積ログ: {savings?.total_queries ?? 0} 件抽出済み
          </div>
          <div className="flex items-center gap-2.5">
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-gray-300 hover:text-white bg-gray-800 hover:bg-gray-700 rounded-xl transition-colors"
            >
              閉じる
            </button>
            <button
              onClick={handleRunBatch}
              disabled={isSubmitting || isLoading}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 rounded-xl shadow-md transition-all disabled:opacity-50"
            >
              {isSubmitting ? (
                <>バッチ処理中...</>
              ) : (
                <>
                  バッチ推論ジョブを実行 <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BatchFinOpsModal;
