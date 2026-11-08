/**
 * Indicador visual del estado del worker.
 * Muestra verde si ComfyUI está encendido, rojo si no.
 */

import { useEffect, useState } from "react";
import { useWorker } from "./useWorker";
import { AlertCircle, CheckCircle2 } from "lucide-react";

export function WorkerStatus() {
  const { health, isLoading } = useWorker();
  const [animating, setAnimating] = useState(false);

  useEffect(() => {
    if (health?.online && !animating) {
      setAnimating(true);
      const t = setTimeout(() => setAnimating(false), 600);
      return () => clearTimeout(t);
    }
  }, [health?.online, animating]);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-50 text-amber-700 text-xs font-medium border border-amber-100">
        <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
        <span>Verificando worker...</span>
      </div>
    );
  }

  if (!health) {
    return null;
  }

  if (health.online) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-50 text-green-700 text-xs font-medium border border-green-100">
        <div className="relative">
          <CheckCircle2 className="w-3 h-3 text-green-500" />
          {animating && (
            <div className="absolute -inset-0.5 rounded-full border border-green-400/50 animate-ping" />
          )}
        </div>
        <span className="font-semibold">Worker encendido</span>
        <span className="ml-1 text-[10px] uppercase tracking-wider opacity-70">
          {health.pending_tasks ?? 0} pendiente(s)
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-50 text-red-700 text-xs font-medium border border-red-100">
      <AlertCircle className="w-3 h-3 text-red-500 animate-pulse" />
      <span>Worker apagado</span>
      <span className="ml-1 text-[10px] uppercase tracking-wider opacity-70">
        ComfyUI no responde
      </span>
    </div>
  );
}