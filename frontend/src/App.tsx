import React, { useState, useEffect, useRef } from 'react';
import { Sparkles, MessageSquare, Code, Zap } from 'lucide-react';
import { Header } from './components/Header';
import { ChatMessage } from './components/ChatMessage';
import { ChatInput } from './components/ChatInput';
import { Message, AppConfig } from './types';

export const App: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string>(() => {
    return sessionStorage.getItem('adk_chat_session_id') || `session_${Date.now()}`;
  });
  const [config, setConfig] = useState<AppConfig>({
    model: 'gemini-3.5-flash-lite',
    has_api_key: false,
  });
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Save session ID
  useEffect(() => {
    sessionStorage.setItem('adk_chat_session_id', sessionId);
  }, [sessionId]);

  // Fetch backend config on mount
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const res = await fetch('/api/config');
        if (res.ok) {
          const data: AppConfig = await res.json();
          setConfig(data);
        }
      } catch (e) {
        console.warn('Backend API config fetch failed, using defaults.', e);
      }
    };
    fetchConfig();
  }, []);

  // Auto scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSendMessage = async (text: string) => {
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMsg: Message = {
      id: `usr_${Date.now()}`,
      sender: 'user',
      content: text,
      timestamp: now,
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
          user_id: 'default_user',
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: 'API error' }));
        throw new Error(errData.detail || `Server error ${response.status}`);
      }

      const data = await response.json();
      if (data.session_id) {
        setSessionId(data.session_id);
      }

      const botMsg: Message = {
        id: `bot_${Date.now()}`,
        sender: 'assistant',
        content: data.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err: any) {
      console.error('Chat API Error:', err);
      const errorMsg: Message = {
        id: `err_${Date.now()}`,
        sender: 'assistant',
        content: `⚠️ エラーが発生しました: ${err.message || 'サーバーとの通信に失敗しました。'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isError: true,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetSession = async () => {
    try {
      await fetch('/api/sessions/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      });
    } catch (e) {
      console.warn('Failed to reset backend session:', e);
    }
    const newSessionId = `session_${Date.now()}`;
    setSessionId(newSessionId);
    setMessages([]);
  };

  const handleSuggestionClick = (prompt: string) => {
    handleSendMessage(prompt);
  };

  return (
    <div className="app-container">
      <Header
        modelName={config.model}
        onResetSession={handleResetSession}
        isLoading={isLoading}
      />

      <main className="chat-main">
        <div className="messages-container">
          {messages.length === 0 ? (
            <div className="welcome-card">
              <div className="welcome-icon">
                <Sparkles size={28} />
              </div>
              <h2>Google ADK Agent Chat</h2>
              <p>
                Google Agent Development Kit (ADK) と FastAPI、React、Gemini-3.5-Flash-Lite を利用したAIチャットボットです。メッセージを入力して会話を始めましょう。
              </p>

              <div className="suggestion-chips">
                <button
                  className="chip"
                  onClick={() => handleSuggestionClick('Google ADK (Agent Development Kit) の主な特徴について教えてください。')}
                >
                  <Zap size={14} style={{ display: 'inline', marginRight: 4 }} />
                  ADK の特徴
                </button>
                <button
                  className="chip"
                  onClick={() => handleSuggestionClick('FastAPI と React で作るAIチャットボットの設計ポイントは？')}
                >
                  <MessageSquare size={14} style={{ display: 'inline', marginRight: 4 }} />
                  チャットボット設計
                </button>
                <button
                  className="chip"
                  onClick={() => handleSuggestionClick('Python で簡単な非同期関数のサンプルコードを作成してください。')}
                >
                  <Code size={14} style={{ display: 'inline', marginRight: 4 }} />
                  Python コード例
                </button>
              </div>
            </div>
          ) : (
            messages.map((msg) => <ChatMessage key={msg.id} message={msg} />)
          )}

          {isLoading && (
            <div className="message-wrapper assistant">
              <div className="avatar assistant">
                <Sparkles size={16} />
              </div>
              <div className="message-content-box">
                <div className="message-bubble">
                  <div className="typing-indicator">
                    <span className="typing-dot"></span>
                    <span className="typing-dot"></span>
                    <span className="typing-dot"></span>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
      </main>
    </div>
  );
};

export default App;
