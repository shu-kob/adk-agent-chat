import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import BatchFinOpsModal from '../components/BatchFinOpsModal';
import { BatchSavings } from '../types';

const mockSavings: BatchSavings = {
  model_id: 'gemini-3.5-flash-lite',
  total_queries: 100,
  estimated_prompt_tokens: 15000,
  estimated_output_tokens: 40000,
  ondemand_cost_usd: 0.007,
  batch_cost_usd: 0.0035,
  discount_percentage: '50.0%',
  cost_savings_usd: 0.0035,
  capacity_for_1000_jpy: 190000,
  cost_per_1000_queries_jpy: 5.25
};

describe('BatchFinOpsModal', () => {
  it('renders finops metrics with 50% discount and 1000 jpy capacity', () => {
    const handleClose = vi.fn();
    const handleSubmitJob = vi.fn();

    render(
      <BatchFinOpsModal
        isOpen={true}
        onClose={handleClose}
        savings={mockSavings}
        onSubmitJob={handleSubmitJob}
        isLoading={false}
      />
    );

    // タイトルと50%OFFバッジの確認
    expect(screen.getByText(/Gemini Batch API.*50% OFF/i)).toBeInTheDocument();
    
    // 1,000円での処理可能件数の確認
    expect(screen.getByText(/190,000/)).toBeInTheDocument();

    // 閉じるボタンの動作確認
    const closeBtns = screen.getAllByRole('button', { name: /閉じる/i });
    fireEvent.click(closeBtns[0]);
    expect(handleClose).toHaveBeenCalledTimes(1);

    // バッチジョブ実行ボタンの動作確認
    const runBtn = screen.getByRole('button', { name: /バッチ推論ジョブを実行/i });
    fireEvent.click(runBtn);
    expect(handleSubmitJob).toHaveBeenCalledTimes(1);
  });

  it('renders quality metrics and preview items when job completes', async () => {
    const handleClose = vi.fn();
    const mockJobResponse = {
      status: 'ok',
      job: {
        job_id: 'batch-test-123',
        status: 'completed',
        model_id: 'gemini-3.5-flash-lite',
        total_queries: 77,
        input_file_path: '/path/to/input.jsonl',
        output_file_path: '/path/to/output.jsonl',
        submitted_at: '2026-10-25T12:00:00Z',
        savings: mockSavings,
        metrics: {
          format_error_count: 0,
          consistency_score: 84.5,
          avg_char_length: 345,
          rate_limit_errors: 0,
          pass_rate: 100.0
        },
        preview_items: [
          {
            custom_id: 'req-1',
            input_text: '今晩の献立、キャベツと豚肉',
            original_output: '回鍋肉がおすすめです',
            batch_output: '豚キャベツ重ね蒸しがおすすめです'
          }
        ]
      }
    };
    const handleSubmitJob = vi.fn().mockResolvedValue(mockJobResponse);

    render(
      <BatchFinOpsModal
        isOpen={true}
        onClose={handleClose}
        savings={mockSavings}
        onSubmitJob={handleSubmitJob}
        isLoading={false}
      />
    );

    const runBtn = screen.getByRole('button', { name: /バッチ推論ジョブを実行/i });
    fireEvent.click(runBtn);

    // ジョブ完了後の品質メトリクスカードとプレビューが表示されることを検証
    expect(await screen.findByText(/バッチ推論ジョブ完了/i)).toBeInTheDocument();
    expect(screen.getByText(/決定論的品質 & 回帰チェック/i)).toBeInTheDocument();
    expect(screen.getByText(/84.5%/)).toBeInTheDocument();
    expect(screen.getByText(/今晩の献立、キャベツと豚肉/)).toBeInTheDocument();
  });
});
