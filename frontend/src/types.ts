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

export interface BatchSavings {
  model_id: string;
  total_queries: number;
  estimated_prompt_tokens: number;
  estimated_output_tokens: number;
  ondemand_cost_usd: number;
  batch_cost_usd: number;
  discount_percentage: string;
  cost_savings_usd: number;
  capacity_for_1000_jpy: number;
  cost_per_1000_queries_jpy: number;
}

export interface BatchFinOpsResponse {
  savings: BatchSavings;
  report_markdown: string;
}

export interface BatchJobResponse {
  status: string;
  job: {
    job_id: string;
    status: string;
    model_id: string;
    total_queries: number;
    input_file_path: string;
    output_file_path: string;
    submitted_at: string;
    savings: BatchSavings;
  };
}
