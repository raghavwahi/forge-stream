// Shared TypeScript types for ForgeStream
// Used by /web and any other TS consumers

export interface User {
  id: string;
  email: string;
  name: string;
  avatar_url?: string;
  provider: "github" | "email";
  created_at: string;
  updated_at: string;
}

export interface LLMProvider {
  id: string;
  name: "openai" | "anthropic" | "gemini" | "ollama";
  model: string;
}

export interface LLMRequest {
  prompt: string;
  model?: string;
  max_tokens?: number;
  temperature?: number;
}

export interface LLMResponse {
  text: string;
  model: string;
  provider: LLMProvider["name"];
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  latency_ms: number;
}

export interface ApiError {
  detail: string;
  status_code: number;
}
