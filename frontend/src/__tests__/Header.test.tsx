import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Header } from '../components/Header';

describe('Header Component', () => {
  it('renders standard Gemini version in model badge regardless of routingMode (auto or manual)', () => {
    const { rerender } = render(
      <Header
        modelName="gemini-3.8-flash"
        abTestMode="auto"
        onChangeAbTestMode={vi.fn()}
        compareModel="random"
        onChangeCompareModel={vi.fn()}
        routingMode="auto"
        onChangeRoutingMode={vi.fn()}
        onResetSession={vi.fn()}
        isLoading={false}
      />
    );
    
    expect(screen.getByText('ADK Agent Chat')).toBeInTheDocument();
    expect(screen.getByText('標準: gemini-3.8-flash')).toBeInTheDocument();
    expect(screen.getByText('比較対象:')).toBeInTheDocument();
    expect(screen.getByText('🎲 ランダム比較モード')).toBeInTheDocument();
    expect(screen.getByText('ルーティング:')).toBeInTheDocument();
    expect(screen.getByText('会話をリセット')).toBeInTheDocument();
    expect(screen.getByText('A/Bテスト:')).toBeInTheDocument();

    rerender(
      <Header
        modelName="gemini-3.8-flash"
        abTestMode="auto"
        onChangeAbTestMode={vi.fn()}
        compareModel="random"
        onChangeCompareModel={vi.fn()}
        routingMode="manual"
        onChangeRoutingMode={vi.fn()}
        onResetSession={vi.fn()}
        isLoading={false}
      />
    );

    expect(screen.getByText('標準: gemini-3.8-flash')).toBeInTheDocument();
  });

  it('triggers onChangeRoutingMode when routing mode is changed', () => {
    const handleRoutingChange = vi.fn();
    render(
      <Header
        modelName="gemini-3.8-flash"
        abTestMode="auto"
        onChangeAbTestMode={vi.fn()}
        compareModel="random"
        onChangeCompareModel={vi.fn()}
        routingMode="auto"
        onChangeRoutingMode={handleRoutingChange}
        onResetSession={vi.fn()}
        isLoading={false}
      />
    );

    const selects = screen.getAllByRole('combobox');
    // 3番目の select がルーティングモード
    const routingSelect = selects[2];
    fireEvent.change(routingSelect, { target: { value: 'manual' } });
    expect(handleRoutingChange).toHaveBeenCalledWith('manual');
  });

  it('triggers onChangeCompareModel when compare target is changed', () => {
    const handleCompareChange = vi.fn();
    render(
      <Header
        modelName="gemini-3.8-flash"
        abTestMode="always"
        onChangeAbTestMode={vi.fn()}
        compareModel="random"
        onChangeCompareModel={handleCompareChange}
        routingMode="manual"
        onChangeRoutingMode={vi.fn()}
        onResetSession={vi.fn()}
        isLoading={false}
      />
    );

    const selects = screen.getAllByRole('combobox');
    // 2番目の select が比較対象モデル
    const compareSelect = selects[1];
    fireEvent.change(compareSelect, { target: { value: 'gemini-3.5-flash' } });
    expect(handleCompareChange).toHaveBeenCalledWith('gemini-3.5-flash');
  });

  it('triggers onResetSession when reset button is clicked', () => {
    const handleReset = vi.fn();
    render(
      <Header
        modelName="gemini-3.8-flash"
        abTestMode="auto"
        onChangeAbTestMode={vi.fn()}
        compareModel="random"
        onChangeCompareModel={vi.fn()}
        routingMode="auto"
        onChangeRoutingMode={vi.fn()}
        onResetSession={handleReset}
        isLoading={false}
      />
    );
    
    const resetButton = screen.getByText('会話をリセット');
    fireEvent.click(resetButton);
    expect(handleReset).toHaveBeenCalledTimes(1);
  });
});
