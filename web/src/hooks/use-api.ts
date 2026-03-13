import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

/* ---------- Types ---------- */

export interface ConfigPayload {
  llm_partner: string;
  github_token: string;
}

export interface PromptPayload {
  prompt: string;
  model?: string;
}

export interface EnhancePromptPayload {
  prompt: string;
  model?: string;
}

export interface EnhancePromptResponse {
  enhanced_prompt: string;
}

export interface ProposedItem {
  id: string;
  title: string;
  description: string;
  type: string;
}

export interface GenerateResponse {
  items: ProposedItem[];
}

export interface CreateRepoPayload {
  items: ProposedItem[];
}

export interface CreationProgress {
  step: string;
  progress: number;
  done: boolean;
  error?: string;
  repo_url?: string;
}

/* ---------- Configuration ---------- */

export function useConfig() {
  return useQuery({
    queryKey: ["config"],
    queryFn: () => apiFetch<ConfigPayload>("/api/config"),
  });
}

export function useSaveConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ConfigPayload) =>
      apiFetch<ConfigPayload>("/api/config", {
        method: "PUT",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["config"] }),
  });
}

/* ---------- Prompt / Generate ---------- */

export function useGenerate() {
  return useMutation({
    mutationFn: (payload: PromptPayload) =>
      apiFetch<GenerateResponse>("/api/v1/work-items/generate", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}

export function useEnhancePrompt() {
  return useMutation({
    mutationFn: (payload: EnhancePromptPayload) =>
      apiFetch<EnhancePromptResponse>("/api/v1/work-items/enhance-prompt", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}

/* ---------- Create Repo ---------- */

export function useCreateRepo() {
  return useMutation({
    mutationFn: (payload: CreateRepoPayload) =>
      apiFetch<CreationProgress>("/api/create", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}
