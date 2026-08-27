/**
 * TypeScript contracts for AI model registry, endpoints, pools, and user preferences.
 */

export type ReasoningEffort = "disabled" | "low" | "medium" | "high" | "xhigh";

export interface AIEndpoint {
  id: string;
  name: string;
  endpoint_type: "generation" | "embedding" | "rerank";
  base_url: string;
  is_active: boolean;
  created_at: string;
}

export interface AIModel {
  id: string;
  endpoint_id: string;
  model_id: string;
  display_name: string;
  family: string;
  context_window: number;
  qualification_status: "passed" | "failed" | "pending";
  is_default: boolean;
  created_at: string;
}

export interface AIRuntimePool {
  id: string;
  name: string;
  max_in_flight: number;
  interactive_reserve: number;
  created_at: string;
}

export interface UserAIPreference {
  user_id: string;
  preferred_gen_model: string | null;
  preferred_reasoning_effort: ReasoningEffort;
}
