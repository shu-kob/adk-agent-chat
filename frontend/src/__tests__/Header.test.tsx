import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Header } from '../components/Header';

describe('Header Component', () => {
  it('renders model name badge and title correctly', () => {
    render(
      <Header
        modelName="gemini-3.5-flash-lite"
        abTestMode="auto"
        onChangeAbTestMode={vi.fn()}
        onResetSession={vi.fn()}
        isLoading={false}
      />
    );
    
    expect(screen.getByText('ADK Agent Chat')).toBeInTheDocument();
    expect(screen.getByText('gemini-3.5-flash-lite')).toBeInTheDocument();
    expect(screen.getByText('会話をリセット')).toBeInTheDocument();
    expect(screen.getByText('A/Bテスト:')).toBeInTheDocument();
  });

  it('triggers onResetSession when reset button is clicked', () => {
    const handleReset = vi.fn();
    render(
      <Header
        modelName="gemini-3.5-flash-lite"
        abTestMode="auto"
        onChangeAbTestMode={vi.fn()}
        onResetSession={handleReset}
        isLoading={false}
      />
    );
    
    const resetButton = screen.getByText('会話をリセット');
    fireEvent.click(resetButton);
    expect(handleReset).toHaveBeenCalledTimes(1);
  });
});
