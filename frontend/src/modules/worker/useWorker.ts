/**
 * Hook para consultar el estado del worker (ComfyUI).
 * Hace polling al endpoint /health y expone el estado para el resto de la app.
 */

import { useEffect, useState, useCallback } from "react";
import type { WorkerHealth } from "@/types";

const HEALTH_URL = "/api/health";
const POLL_INTERVAL_MS = 5000;

export function useWorker() {
  const [health, setHealth] = useState<WorkerHealth | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch(HEALTH_URL);
      if (!res.ok) {
        throw new Error(`Health endpoint responded ${res.status}`);
      }
      const data: WorkerHealth = await res.json();
      setHealth(data);
    } catch (err) {
      setHealth({
        online: false,
        comfy_alive: false,
        comfy_url: HEALTH_URL,
        gpu_name: null,
        vram_total: null,
        vram_free: null,
        pending_tasks: null,
        timestamp: null,
        oci_online: false,
        error: err instanceof Error ? err.message : "Error desconocido",
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    const timer = setInterval(fetchHealth, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [fetchHealth]);

  return { health, isLoading, refetch: fetchHealth };
}