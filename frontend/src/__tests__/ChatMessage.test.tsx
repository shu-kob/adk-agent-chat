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
});
