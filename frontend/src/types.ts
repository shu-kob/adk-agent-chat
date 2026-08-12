export interface Message {
  id: string;
  sender: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  isError?: boolean;
}

export interface ChatResponse {
  reply: string;
  session_id: string;
  model: string;
}

export interface AppConfig {
  model: string;
  has_api_key: boolean;
}
