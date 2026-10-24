export interface ABTestData {
  ab_test_id: string;
  session_id: string;
  input_text: string;
  choice_a: string;
  choice_b: string;
  reveal_info: {
    A: string;
    B: string;
  };
  mapping: {
    A: string;
    B: string;
  };
}

export interface RoutedInfo {
  model_id: string;
  category: string;
  reason: string;
}

export interface Message {
  id: string;
  sender: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  isError?: boolean;
  model?: string;
  abTest?: ABTestData;
  feedbackSelected?: 'A' | 'B' | 'tie';
  routedInfo?: RoutedInfo;
}

export interface ChatResponse {
  reply: string;
  session_id: string;
  model: string;
  ab_test?: ABTestData;
  routed_info?: RoutedInfo;
}

export interface CompareModelOption {
  id: string;
  name: string;
}

export interface AppConfig {
  model: string;
  has_api_key: boolean;
  default_compare_model?: string;
  compare_models?: CompareModelOption[];
}
