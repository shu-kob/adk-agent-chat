import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User, Bot, Copy, Check, AlertTriangle, Cpu } from 'lucide-react';
import { Message } from '../types';
import { SideBySideComparison } from './SideBySideComparison';

interface ChatMessageProps {
  message: Message;
  onVoteAbTest?: (messageId: string, choice: 'A' | 'B' | 'tie') => void;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, onVoteAbTest }) => {
  const [copied, setCopied] = useState(false);
  const isUser = message.sender === 'user';
  const isAssistant = message.sender === 'assistant';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`message-wrapper ${message.sender} ${message.isError ? 'error' : ''}`}>
      <div className={`avatar ${message.sender}`}>
        {isUser ? <User size={18} /> : isAssistant ? <Bot size={18} /> : <AlertTriangle size={18} />}
      </div>

      <div className="message-content-box" style={{ maxWidth: message.abTest ? '95%' : undefined, width: message.abTest ? '100%' : undefined }}>
        {message.abTest ? (
          <SideBySideComparison
            abTest={message.abTest}
            initialSelected={message.feedbackSelected}
            onVote={(choice) => onVoteAbTest?.(message.id, choice)}
          />
        ) : (
          <div className="message-bubble">
            {isAssistant ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            ) : (
              <p>{message.content}</p>
            )}

            {isAssistant && message.content && (
              <button
                onClick={handleCopy}
                style={{
                  position: 'absolute',
                  top: '8px',
                  right: '8px',
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '4px',
                  color: '#94a3b8',
                  cursor: 'pointer',
                }}
                title="コピー"
              >
                {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
              </button>
            )}
          </div>
        )}

        <div className="message-footer" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
          <span className="message-timestamp">{message.timestamp}</span>
          {isAssistant && message.model && !message.abTest && (
            <span
              className="message-model-badge"
              title={`応答生成モデル: ${message.model}`}
              style={{
                fontSize: '11px',
                padding: '1px 8px',
                borderRadius: '12px',
                background: 'rgba(99, 102, 241, 0.12)',
                color: '#a5b4fc',
                border: '1px solid rgba(99, 102, 241, 0.28)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                fontFamily: 'monospace',
                letterSpacing: '0.02em',
              }}
            >
              <Cpu size={12} color="#818cf8" />
              <span>{message.model}</span>
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
