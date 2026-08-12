import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User, Bot, Copy, Check, AlertTriangle } from 'lucide-react';
import { Message } from '../types';

interface ChatMessageProps {
  message: Message;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
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

      <div className="message-content-box">
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
        <span className="message-timestamp">{message.timestamp}</span>
      </div>
    </div>
  );
};
