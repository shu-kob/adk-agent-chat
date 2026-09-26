import React, { useState, useRef, useEffect } from 'react';
import { Send, Square } from 'lucide-react';

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  onStop?: () => void;
  isLoading: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSendMessage, onStop, isLoading }) => {
  const [text, setText] = useState('');
  const [isComposing, setIsComposing] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!text.trim() || isLoading) return;
    onSendMessage(text.trim());
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // 日本語入力の変換確定Enter (isComposing や keyCode 229) では送信しない
    if (e.key === 'Enter' && !e.shiftKey) {
      if (e.nativeEvent.isComposing || isComposing || e.keyCode === 229) {
        return;
      }
      e.preventDefault();
      handleSubmit();
    }
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [text]);

  return (
    <div className="input-container">
      <form onSubmit={handleSubmit} className="input-box">
        <textarea
          ref={textareaRef}
          className="chat-textarea"
          placeholder="メッセージを入力... (Shift+Enterで改行)"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          onCompositionStart={() => setIsComposing(true)}
          onCompositionEnd={() => setIsComposing(false)}
          disabled={isLoading}
          rows={1}
        />
        {isLoading ? (
          <button
            type="button"
            className="btn-send"
            onClick={onStop}
            title="生成を停止"
            style={{ backgroundColor: '#ef4444', color: '#ffffff' }}
          >
            <Square size={16} fill="currentColor" />
          </button>
        ) : (
          <button
            type="submit"
            className="btn-send"
            disabled={!text.trim()}
            title="送信"
          >
            <Send size={18} />
          </button>
        )}
      </form>
    </div>
  );
};
