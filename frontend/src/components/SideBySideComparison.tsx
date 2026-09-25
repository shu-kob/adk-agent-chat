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
    <div className="side-by-side-container">
      {/* Header Banner */}
      <div className="side-by-side-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(99, 102, 241, 0.2)', color: '#818cf8' }}>
            <Scale size={16} />
          </div>
          <div>
            <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 600, color: '#ffffff', display: 'flex', alignItems: 'center', gap: '6px' }}>
              どちらの回答が優れていますか？
              <span className="card-label-badge" style={{ background: 'rgba(99, 102, 241, 0.2)', color: '#a5b4fc', borderColor: 'rgba(99, 102, 241, 0.4)' }}>
                Blind A/B Test
              </span>
            </h4>
            <p style={{ margin: '2px 0 0', fontSize: '12px', color: '#94a3b8' }}>
              位置バイアスを防ぐため、モデル配置はランダムです。回答をお選びください。
            </p>
          </div>
        </div>

        {selected && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', fontWeight: 500, color: '#34d399', background: 'rgba(16, 185, 129, 0.1)', padding: '4px 10px', borderRadius: '9999px', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
            <CheckCircle2 size={14} />
            <span>投票完了</span>
          </div>
        )}
      </div>

      {/* Reveal Banner (Shown after voting) */}
      {selected && (
        <div className="reveal-banner">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Eye size={16} color="#818cf8" />
            <span>
              <strong>モデル正解開示:</strong> 回答A = <code style={{ background: 'rgba(0,0,0,0.3)', padding: '2px 6px', borderRadius: '4px', color: '#fcd34d' }}>{abTest.reveal_info.A}</code> / 回答B = <code style={{ background: 'rgba(0,0,0,0.3)', padding: '2px 6px', borderRadius: '4px', color: '#67e8f9' }}>{abTest.reveal_info.B}</code>
            </span>
          </div>
          <span style={{ fontSize: '11px', color: '#94a3b8' }}>
            あなたの選択: <strong>{selected === 'tie' ? '同等' : `回答 ${selected}`}</strong>
          </span>
        </div>
      )}

      {/* Side-by-Side Cards (Guaranteed 2 Columns Horizontal Layout) */}
      <div className="side-by-side-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', width: '100%' }}>
        {/* Choice A */}
        <div className={`side-by-side-card ${selected === 'A' ? 'selected' : ''}`}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span className="card-label-badge">回答 A</span>
              {selected && (
                <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                  {abTest.reveal_info.A}
                </span>
              )}
            </div>
            <div className="card-content-text">
              {abTest.choice_a}
            </div>
          </div>

          <div className="card-actions">
            <button
              onClick={() => handleSelect('A')}
              disabled={!!selected || isSubmitting}
              className={`btn-vote-choice ${selected === 'A' ? 'active' : ''}`}
            >
              <ThumbsUp size={14} />
              <span>回答 A が良い</span>
            </button>
          </div>
        </div>

        {/* Choice B */}
        <div className={`side-by-side-card ${selected === 'B' ? 'selected' : ''}`}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span className="card-label-badge">回答 B</span>
              {selected && (
                <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                  {abTest.reveal_info.B}
                </span>
              )}
            </div>
            <div className="card-content-text">
              {abTest.choice_b}
            </div>
          </div>

          <div className="card-actions">
            <button
              onClick={() => handleSelect('B')}
              disabled={!!selected || isSubmitting}
              className={`btn-vote-choice ${selected === 'B' ? 'active' : ''}`}
            >
              <ThumbsUp size={14} />
              <span>回答 B が良い</span>
            </button>
          </div>
        </div>
      </div>

      {/* Tie Button */}
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '4px' }}>
        <button
          onClick={() => handleSelect('tie')}
          disabled={!!selected || isSubmitting}
          className={`btn-vote-choice ${selected === 'tie' ? 'active' : ''}`}
          style={{ borderRadius: '9999px', padding: '6px 16px' }}
        >
          <Scale size={14} />
          <span>どちらも同等 / 差はない</span>
        </button>
      </div>
    </div>
  );
};
