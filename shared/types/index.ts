export type AuthProvider = "github" | "email";

export type LLMProviderName = "openai" | "claude" | "gemini";

export interface User {
  id: string;
  email: string;
  name: string;
  avatar_url?: string;
  provider: AuthProvider;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface LLMRequest {
  provider: LLMProviderName;
  model: string;
  prompt: string;
  max_tokens?: number;
  temperature?: number;
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface LLMResponse {
  provider: LLMProviderName;
  model: string;
  content: string;
  usage: TokenUsage;
}

export interface ApiError {
  detail: string;
  status_code: number;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse {
  user: User;
  tokens: TokenResponse;
}
