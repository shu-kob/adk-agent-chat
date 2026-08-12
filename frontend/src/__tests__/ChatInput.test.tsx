import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ChatInput } from '../components/ChatInput';

describe('ChatInput Component', () => {
  it('allows typing and triggers onSendMessage on submit', () => {
    const handleSend = vi.fn();
    render(<ChatInput onSendMessage={handleSend} isLoading={false} />);

    const textarea = screen.getByPlaceholderText('メッセージを入力... (Shift+Enterで改行)');
    fireEvent.change(textarea, { target: { value: 'テストメッセージ' } });
    expect(textarea).toHaveValue('テストメッセージ');

    const sendButton = screen.getByTitle('送信');
    fireEvent.click(sendButton);
    expect(handleSend).toHaveBeenCalledWith('テストメッセージ');
    expect(textarea).toHaveValue('');
  });

  it('disables input when isLoading is true', () => {
    render(<ChatInput onSendMessage={vi.fn()} isLoading={true} />);
    const textarea = screen.getByPlaceholderText('メッセージを入力... (Shift+Enterで改行)');
    expect(textarea).toBeDisabled();
  });
});
