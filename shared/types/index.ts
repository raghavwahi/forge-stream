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
  name: "openai" | "claude" | "gemini";
  model: string;
}

export interface LLMRequest {
  provider: LLMProvider["name"];
  model: string;
  prompt: string;
  max_tokens?: number;
  temperature?: number;
}

export interface LLMResponse {
  provider: LLMProvider["name"];
  model: string;
  content: string;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

export interface ApiError {
  detail: string;
  status_code: number;
}
