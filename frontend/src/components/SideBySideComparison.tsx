import React, { useState } from 'react';
import { CheckCircle2, ThumbsUp, Scale, Eye } from 'lucide-react';
import { ABTestData } from '../types';

interface SideBySideProps {
  abTest: ABTestData;
  initialSelected?: 'A' | 'B' | 'tie';
  onVote: (selected: 'A' | 'B' | 'tie') => void;
}

export const SideBySideComparison: React.FC<SideBySideProps> = ({
  abTest,
  initialSelected,
  onVote,
}) => {
  const [selected, setSelected] = useState<'A' | 'B' | 'tie' | undefined>(initialSelected);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSelect = async (choice: 'A' | 'B' | 'tie') => {
    if (selected || isSubmitting) return;
    setSelected(choice);
    setIsSubmitting(true);

    try {
      await fetch('/api/eval/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ab_test_id: abTest.ab_test_id,
          session_id: abTest.session_id,
          selected_choice: choice,
          mapping: abTest.mapping,
        }),
      });
      onVote(choice);
    } catch (err) {
      console.error('Failed to submit feedback:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full my-4 p-4 rounded-2xl bg-gradient-to-br from-indigo-900/20 via-slate-900/40 to-purple-900/20 border border-indigo-500/30 shadow-xl backdrop-blur-md transition-all">
      {/* Header Banner */}
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-white/10">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-400">
            <Scale className="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-white flex items-center gap-1.5">
              どちらの回答が優れていますか？
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                Blind A/B Test
              </span>
            </h4>
            <p className="text-xs text-slate-400">
              位置バイアスを防ぐため、モデル配置はランダムです。回答をお選びください。
            </p>
          </div>
        </div>

        {selected && (
          <div className="flex items-center gap-1 text-xs font-medium text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20 animate-fade-in">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>投票完了</span>
          </div>
        )}
      </div>

      {/* Reveal Banner (Shown after voting) */}
      {selected && (
        <div className="mb-4 p-3 rounded-xl bg-indigo-950/60 border border-indigo-500/30 text-xs text-indigo-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Eye className="w-4 h-4 text-indigo-400" />
            <span>
              <strong>モデル正解開示:</strong> 回答A = <code className="bg-black/30 px-1.5 py-0.5 rounded text-amber-300">{abTest.reveal_info.A}</code> / 回答B = <code className="bg-black/30 px-1.5 py-0.5 rounded text-cyan-300">{abTest.reveal_info.B}</code>
            </span>
          </div>
          <span className="text-[11px] text-slate-400">
            あなたの選択: <strong>{selected === 'tie' ? '同等' : `回答 ${selected}`}</strong>
          </span>
        </div>
      )}

      {/* Side-by-Side Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
        {/* Choice A */}
        <div
          className={`flex flex-col justify-between p-4 rounded-xl border transition-all duration-200 ${
            selected === 'A'
              ? 'bg-indigo-900/30 border-indigo-400 ring-2 ring-indigo-500/30 shadow-lg'
              : 'bg-slate-900/60 border-white/10 hover:border-white/20'
          }`}
        >
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-slate-300 px-2.5 py-0.5 rounded-md bg-white/5 border border-white/10">
                回答 A
              </span>
              {selected && (
                <span className="text-[11px] text-slate-400">
                  {abTest.reveal_info.A}
                </span>
              )}
            </div>
            <div className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
              {abTest.choice_a}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-white/5 flex justify-end">
            <button
              onClick={() => handleSelect('A')}
              disabled={!!selected || isSubmitting}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                selected === 'A'
                  ? 'bg-indigo-600 text-white shadow-md'
                  : selected
                  ? 'opacity-40 cursor-not-allowed bg-white/5 text-slate-400'
                  : 'bg-white/10 hover:bg-indigo-600 text-slate-200 hover:text-white cursor-pointer active:scale-95'
              }`}
            >
              <ThumbsUp className="w-3.5 h-3.5" />
              <span>回答 A が良い</span>
            </button>
          </div>
        </div>

        {/* Choice B */}
        <div
          className={`flex flex-col justify-between p-4 rounded-xl border transition-all duration-200 ${
            selected === 'B'
              ? 'bg-indigo-900/30 border-indigo-400 ring-2 ring-indigo-500/30 shadow-lg'
              : 'bg-slate-900/60 border-white/10 hover:border-white/20'
          }`}
        >
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-slate-300 px-2.5 py-0.5 rounded-md bg-white/5 border border-white/10">
                回答 B
              </span>
              {selected && (
                <span className="text-[11px] text-slate-400">
                  {abTest.reveal_info.B}
                </span>
              )}
            </div>
            <div className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
              {abTest.choice_b}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-white/5 flex justify-end">
            <button
              onClick={() => handleSelect('B')}
              disabled={!!selected || isSubmitting}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                selected === 'B'
                  ? 'bg-indigo-600 text-white shadow-md'
                  : selected
                  ? 'opacity-40 cursor-not-allowed bg-white/5 text-slate-400'
                  : 'bg-white/10 hover:bg-indigo-600 text-slate-200 hover:text-white cursor-pointer active:scale-95'
              }`}
            >
              <ThumbsUp className="w-3.5 h-3.5" />
              <span>回答 B が良い</span>
            </button>
          </div>
        </div>
      </div>

      {/* Tie Button */}
      <div className="flex items-center justify-center pt-1">
        <button
          onClick={() => handleSelect('tie')}
          disabled={!!selected || isSubmitting}
          className={`flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-medium transition-all ${
            selected === 'tie'
              ? 'bg-purple-600 text-white ring-2 ring-purple-400/30 shadow-md'
              : selected
              ? 'opacity-40 cursor-not-allowed bg-white/5 text-slate-400'
              : 'bg-white/5 hover:bg-white/15 text-slate-400 hover:text-white cursor-pointer'
          }`}
        >
          <Scale className="w-3.5 h-3.5" />
          <span>どちらも同等 / 差はない</span>
        </button>
      </div>
    </div>
  );
};
