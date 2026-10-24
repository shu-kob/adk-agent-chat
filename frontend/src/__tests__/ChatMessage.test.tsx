import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ChatMessage } from '../components/ChatMessage';
import { Message } from '../types';

describe('ChatMessage Component', () => {
  it('renders user message correctly', () => {
    const msg: Message = {
      id: '1',
      sender: 'user',
      content: 'こんにちは！',
      timestamp: '12:00',
    };
    render(<ChatMessage message={msg} />);
    expect(screen.getByText('こんにちは！')).toBeInTheDocument();
    expect(screen.getByText('12:00')).toBeInTheDocument();
  });

  it('renders assistant message with markdown content', () => {
    const msg: Message = {
      id: '2',
      sender: 'assistant',
      content: '**Hello!** I am ADK Agent.',
      timestamp: '12:01',
    };
    render(<ChatMessage message={msg} />);
    expect(screen.getByText('Hello!')).toBeInTheDocument();
    expect(screen.getByText('12:01')).toBeInTheDocument();
  });

  it('renders dynamic routing badge with category when routedInfo is present', () => {
    const msg: Message = {
      id: '3',
      sender: 'assistant',
      content: '分析結果をお伝えします。',
      timestamp: '12:02',
      model: 'gemini-3.8-flash',
      routedInfo: {
        model_id: 'gemini-3.8-flash',
        category: 'complex_reasoning',
        reason: '高度な論理推論・専門タスクと判定',
      },
    };
    render(<ChatMessage message={msg} />);
    expect(screen.getByText(/gemini-3.8-flash/)).toBeInTheDocument();
    expect(screen.getByText(/🧭 動的ルーティング/)).toBeInTheDocument();
  });
});
