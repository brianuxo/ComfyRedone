/**
 * Cliente REST para la API del backend.
 * Todas las llamadas van a /api (proxy de Vite en desarrollo).
 * El backend se comunica con OCI (Oracle Cloud) como intermediario;
 * nunca se conecta directamente a ComfyUI.
 */

const API_BASE = "/api";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Error ${res.status} en ${path}`);
  }
  return (await res.json()) as T;
}

export const api = {
  /** Subir imagen base64 a memoria (opcional, para preview separado) */
  uploadImage: (imageB64: string) =>
    request<{ image_id: string; image_b64: string; size_bytes: number }>(
      "/images/upload",
      { method: "POST", body: JSON.stringify({ image_b64: imageB64 }) }
    ),

  /** Lanzar una tarea FIBO 2.0 Txt2Img (generación desde cero) → sube a OCI queue/pending */
  createTxt2ImgTask: (body: {
    prompt: string;
    negative_prompt?: string;
    loras?: string[];
    seed?: number;
    steps?: number;
    scheduler?: string;
    guidance?: number;
    width?: number;
    height?: number;
  }) => request<{ task_id: string; status: string; created_at: string }>(
    "/tasks/txt2img",
    { method: "POST", body: JSON.stringify(body) }
  ),

  /** Lanzar una tarea FIBO 2.0 Edit → sube a OCI queue/pending */
  createTask: (body: {
    prompt: string;
    image_b64?: string;
    loras?: string[];
    seed?: number;
    steps?: number;
    scheduler?: string;
    guidance?: number;
    width?: number;
    height?: number;
  }) => request<{ task_id: string; status: string; created_at: string }>(
    "/tasks",
    { method: "POST", body: JSON.stringify(body) }
  ),

  /** Lanzar una tarea Moss Image (text-to-image) → sube a OCI queue/pending */
  createMossTask: (body: {
    prompt: string;
    negative_prompt?: string;
    loras?: string[];
    seed?: number;
    steps?: number;
    scheduler?: string;
    guidance?: number;
    width?: number;
    height?: number;
  }) => request<{ task_id: string; status: string; created_at: string }>(
    "/tasks/moss",
    { method: "POST", body: JSON.stringify(body) }
  ),

  /** Consultar estado/resultado de una tarea → lee de OCI results/ */
  getTask: (taskId: string) =>
    request<{
      task_id: string;
      status: string;
      image_b64?: string;
      error?: string;
      created_at: string;
      updated_at: string;
    }>(`/tasks/${taskId}`),

  /** Eliminar/cancelar una tarea → marca en OCI queue/cancelled */
  deleteTask: (taskId: string) =>
    request<{ task_id: string; status: string }>(`/tasks/${taskId}`, {
      method: "DELETE",
    }),

  /** Listar tareas recientes */
  listTasks: () =>
    request<{
      task_id: string;
      status: string;
      created_at: number;
      updated_at: number;
      has_image: boolean;
      error?: string;
    }[]>(`/tasks`),

  /** Health check del worker → lee status/worker.json de OCI */
  health: () => request<{
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
  }>("/health"),

  /** Prompts guardados */
  prompts: {
    list: () =>
      request<{
        id: string;
        title: string;
        prompt: string;
        negative_prompt: string;
        created_at: number;
        updated_at: number;
      }[]>("/prompts"),

    create: (data: { title: string; prompt: string; negative_prompt: string }) =>
      request<{
        id: string;
        title: string;
        prompt: string;
        negative_prompt: string;
        created_at: number;
        updated_at: number;
      }>("/prompts", { method: "POST", body: JSON.stringify(data) }),

    get: (promptId: string) =>
      request<{
        id: string;
        title: string;
        prompt: string;
        negative_prompt: string;
        created_at: number;
        updated_at: number;
      }>(`/prompts/${promptId}`),

    update: (promptId: string, data: { title: string; prompt: string; negative_prompt: string }) =>
      request<{
        id: string;
        title: string;
        prompt: string;
        negative_prompt: string;
        created_at: number;
        updated_at: number;
      }>(`/prompts/${promptId}`, { method: "PUT", body: JSON.stringify(data) }),

    delete: (promptId: string) =>
      request<{ ok: boolean; message: string }>(`/prompts/${promptId}`, { method: "DELETE" }),
  },
};