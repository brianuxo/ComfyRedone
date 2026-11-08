/** Tipos compartidos entre frontend y backend. */

export interface WorkerHealth {
  online: boolean;
  comfy_alive: boolean;
  comfy_url: string | null;
  gpu_name: string | null;
  vram_total: number | null;
  vram_free: number | null;
  pending_tasks: number | null;
  timestamp: string | null;
  oci_online: boolean;
  error: string | null;
}

export interface Fibo2EditParams {
  prompt: string;
  negative_prompt: string;
  image_b64?: string;
  loras: string[];
  seed?: number;
  steps: number;
  scheduler: string;
  guidance: number;
  width: number;
  height: number;
}

export interface TaskResponse {
  task_id: string;
  status: string;
  created_at: string;
}

export interface TaskResult {
  task_id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  image_b64?: string;
  error?: string;
  created_at: string;
  updated_at: string;
}

export interface SavedPrompt {
  id: string;
  title: string;
  prompt: string;
  negative_prompt: string;
  created_at: number;
  updated_at: number;
}