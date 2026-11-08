/**
 * Módulo de ejecución.
 * Lanza la tarea vía API REST, escucha el resultado y muestra la imagen generada.
 */

import { useState, useCallback } from "react";
import { Play, RefreshCw } from "lucide-react";
import { api } from "@/services/api";

interface ExecutionProps {
  params: {
    prompt: string;
    image_b64?: string;
    loras: string[];
    seed?: number;
    steps: number;
    scheduler: string;
    guidance: number;
    width: number;
    height: number;
  };
  workerOnline: boolean;
}

export function Execution({ params, workerOnline }: ExecutionProps) {
  const [isRunning, setIsRunning] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [resultImage, setResultImage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const run = useCallback(async () => {
    if (!workerOnline) {
      setError("El worker (ComfyUI) está apagado. Enciéndelo primero.");
      return;
    }
    setIsRunning(true);
    setError(null);
    setResultImage(null);
    setStatus("ejecutando");

    try {
      const res = await api.createTask({
        prompt: params.prompt,
        image_b64: params.image_b64,
        loras: params.loras.filter(Boolean),
        seed: params.seed,
        steps: params.steps,
        scheduler: params.scheduler,
        guidance: params.guidance,
        width: params.width,
        height: params.height,
      });
      setTaskId(res.task_id);

      // Polling del resultado (en futuro reemplazar por WS dedicado)
      const poll = async () => {
        for (let i = 0; i < 120; i++) {
          const task = await api.getTask(res.task_id);
          setStatus(task.status);
          if (task.status === "completed") {
            setResultImage(task.image_b64 ?? null);
            setIsRunning(false);
            return;
          }
          if (task.status === "failed") {
            setError(task.error ?? "Error desconocido");
            setIsRunning(false);
            return;
          }
          await new Promise((r) => setTimeout(r, 2000));
        }
        setError("Tiempo de espera agotado");
        setIsRunning(false);
      };
      poll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al ejecutar");
      setIsRunning(false);
    }
  }, [params, workerOnline]);

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <Play className="w-5 h-5 text-indigo-600" />
            Ejecutar FIBO 2.0 Edit
          </h3>
          {workerOnline ? (
            <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">
              Worker online
            </span>
          ) : (
            <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">
              Worker offline
            </span>
          )}
        </div>

        <button
          onClick={run}
          disabled={isRunning || !workerOnline}
          className={`w-full px-6 py-3 text-lg font-semibold rounded-lg transition ${
            isRunning || !workerOnline
              ? "bg-slate-300 text-slate-500 cursor-not-allowed"
              : "bg-indigo-600 text-white hover:bg-indigo-700"
          }`}
        >
          {isRunning ? "Ejecutando..." : "Generar imagen"}
        </button>

        {error && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700 text-sm">
            {error}
          </div>
        )}
      </div>

      {status && (
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-100 text-slate-600 text-xs font-medium">
          <RefreshCw className="w-3 h-3 animate-spin" />
          <span>Estado: {status}</span>
        </div>
      )}

      {resultImage && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Resultado</h3>
          <img
            src={`data:image/png;base64,${resultImage}`}
            alt="Resultado FIBO 2.0 Edit"
            className="max-w-full max-h-[600px] rounded-lg object-contain border border-slate-200 shadow-sm mx-auto"
          />
          <div className="mt-4 flex justify-end">
            <button
              onClick={() => {
                const link = document.createElement("a");
                link.href = `data:image/png;base64,${resultImage}`;
                link.download = `fibo2-edit-${taskId?.slice(0, 8)}.png`;
                link.click();
              }}
              className="text-sm text-indigo-600 hover:underline"
            >
              Descargar imagen
            </button>
          </div>
        </div>
      )}
    </div>
  );
}