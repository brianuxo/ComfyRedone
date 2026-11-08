
/**
 * Historial de tareas recientes con vista de galería de imágenes desde OCI.
 */

import { useEffect, useState, useCallback } from "react";
import { Clock, Image as ImageIcon, Eye, Download, RotateCcw, Copy, ArrowUpRight, Settings, Hash, Type } from "lucide-react";
import { api } from "@/services/api";

interface HistoryTask {
  task_id: string;
  status: string;
  created_at: number;
  updated_at: number;
  has_image: boolean;
  error?: string;
  source?: string;
  image_b64?: string;
}

interface HistoryProps {
  onLoadImage?: (imageB64: string, taskId: string) => void;
  onReuseTask?: (taskData: any) => void;
}

export function History({ onLoadImage, onReuseTask }: HistoryProps) {
  const [tasks, setTasks] = useState<HistoryTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [previewTask, setPreviewTask] = useState<{
    task_id: string;
    image_b64: string;
  } | null>(null);
  const [imageCache, setImageCache] = useState<Record<string, string>>({});
  const [reuseTaskData, setReuseTaskData] = useState<any | null>(null);
  const [reuseMode, setReuseMode] = useState<"txt2img" | "img2img">("img2img");

  const fetchTasks = useCallback(async () => {
    try {
      const data = await api.listTasks();
      const completedTasks = data.filter((t) => t.status === "completed" && t.has_image);
      const sortedTasks = [...completedTasks].sort((a, b) => {
        const aTs = Number(a.created_at) || 0;
        const bTs = Number(b.created_at) || 0;
        return bTs - aTs;
      });
      setTasks(sortedTasks);
      await Promise.all(
        completedTasks.map(async (task) => {
          if (!imageCache[task.task_id]) {
            try {
              const taskData = await api.getTask(task.task_id);
              if (taskData.image_b64) {
                setImageCache((prev) => ({ ...prev, [task.task_id]: taskData.image_b64! }));
              }
            } catch (err) {
              console.error(`Error loading image for ${task.task_id}:`, err);
            }
          }
        })
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  const handlePreview = async (taskId: string) => {
    try {
      const task = await api.getTask(taskId);
      if (task.image_b64) {
        setPreviewTask({ task_id: taskId, image_b64: task.image_b64 });
        setImageCache((prev) => ({ ...prev, [taskId]: task.image_b64! }));
      }
    } catch (err) {
      console.error("Error fetching image:", err);
    }
  };

  const handleDownload = (taskId: string, imageB64: string) => {
    const link = document.createElement("a");
    link.href = `data:image/png;base64,${imageB64}`;
    link.download = `fibo2-edit-${taskId.slice(0, 8)}.png`;
    link.click();
  };

  const handleLoadToForm = (taskId: string, imageB64: string) => {
    if (onLoadImage) {
      onLoadImage(imageB64, taskId);
    }
  };

  const handleReuse = async (taskId: string) => {
    try {
      const taskData = await api.getTask(taskId);
      setReuseTaskData(taskData);
    } catch (err) {
      console.error("Error fetching task for reuse:", err);
    }
  };

  const handleReuseClose = () => {
    setReuseTaskData(null);
  };

  const handleReuseApply = () => {
    if (reuseTaskData && onReuseTask) {
      onReuseTask(reuseTaskData);
    }
    setReuseTaskData(null);
  };

  const formatDate = (ts: number) => {
    return new Date(ts).toLocaleString("es-ES", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (loading) {
    return (
      <div className="text-center py-8 text-slate-500">
        <Clock className="w-8 h-8 mx-auto mb-2 animate-spin" />
        <p>Cargando historial...</p>
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div className="text-center py-8 text-slate-500">
        <ImageIcon className="w-10 h-10 mx-auto mb-2 opacity-50" />
        <p className="text-sm">No hay tareas completadas con imágenes.</p>
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Clock className="w-5 h-5 text-slate-500" />
          <h3 className="text-lg font-semibold text-slate-900">Biblioteca de imágenes</h3>
        </div>
        <button
          onClick={fetchTasks}
          disabled={loading}
          className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 disabled:opacity-50 flex items-center gap-1"
        >
          <RotateCcw className="w-4 h-4" />
          Actualizar
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="grid grid-cols-3 gap-3">
          {tasks.map((task, index) => {
            const imageB64 = imageCache[task.task_id];
            const hasImage = !!imageB64;
            return (
              <div
                key={task.task_id}
                className="group relative rounded-lg border border-slate-200 bg-slate-50 overflow-hidden hover:border-indigo-300 hover:bg-white transition cursor-pointer"
                onClick={() => hasImage && handleLoadToForm(task.task_id, imageB64!)}
              >
                <div className="absolute top-2 left-2 z-10 bg-indigo-600 text-white text-xs font-bold px-2 py-1 rounded-full shadow-sm">
                  {index + 1}
                </div>

                <div className="aspect-square relative overflow-hidden bg-slate-100">
                  {hasImage ? (
                    <img
                      src={`data:image/png;base64,${imageB64}`}
                      alt={`Resultado ${task.task_id.slice(0, 8)}`}
                      className="w-full h-full object-cover transition-transform duration-200 group-hover:scale-105"
                      loading="lazy"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-slate-400">
                      <ImageIcon className="w-8 h-8" />
                    </div>
                  )}
                  <div className="absolute inset-0 bg-black/50 flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                    {hasImage && (
                      <>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handlePreview(task.task_id);
                          }}
                          className="p-2 rounded-full bg-white/90 text-slate-700 hover:bg-white shadow-lg"
                          title="Ver en grande"
                        >
                          <Eye className="w-5 h-5" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDownload(task.task_id, imageB64!);
                          }}
                          className="p-2 rounded-full bg-white/90 text-slate-700 hover:bg-white shadow-lg"
                          title="Descargar"
                        >
                          <Download className="w-5 h-5" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleReuse(task.task_id);
                          }}
                          className="p-2 rounded-full bg-white/90 text-slate-700 hover:bg-white shadow-lg"
                          title="Reutilizar parámetros"
                        >
                          <ArrowUpRight className="w-5 h-5" />
                        </button>
                      </>
                    )}
                  </div>
                </div>

                <div className="p-3 bg-white/50 border-t border-slate-100">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono text-slate-600">{task.task_id.slice(0, 8)}...</span>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                        task.status === "completed"
                          ? "bg-green-100 text-green-700"
                          : task.status === "failed"
                          ? "bg-red-100 text-red-700"
                          : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {task.status}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    {formatDate(task.created_at)}
                  </div>
                  <div className="mt-1 text-[9px] text-slate-400 font-mono">
                    ts: {task.created_at}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      {previewTask && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          onClick={() => setPreviewTask(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh] bg-white rounded-xl shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="font-semibold text-slate-900">Resultado: {previewTask.task_id.slice(0, 8)}...</h3>
              <button
                onClick={() => setPreviewTask(null)}
                className="p-2 rounded hover:bg-slate-100 text-slate-500 hover:text-slate-700"
              >
                X
              </button>
            </div>
            <div className="p-4">
              <img
                src={`data:image/png;base64,${previewTask.image_b64}`}
                alt={`Resultado ${previewTask.task_id}`}
                className="max-w-full max-h-[70vh] rounded-lg object-contain border border-slate-200 shadow-sm mx-auto"
              />
              <div className="mt-4 flex justify-end gap-2">
                <button
                  onClick={() => handleDownload(previewTask.task_id, previewTask.image_b64)}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm font-medium"
                >
                  <Download className="w-4 h-4 inline mr-1" />
                  Descargar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      {reuseTaskData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={handleReuseClose}>
          <div className="w-full max-w-2xl max-h-[90vh] bg-white rounded-xl shadow-xl flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b sticky top-0 bg-white z-10">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-slate-100 rounded-lg flex items-center justify-center overflow-hidden">
                  {reuseTaskData.image_b64 ? (
                    <img src={`data:image/png;base64,${reuseTaskData.image_b64}`} alt="Thumbnail" className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-6 h-6 text-slate-400 text-center">IMG</div>
                  )}
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900">Reutilizar parámetros</h3>
                  <p className="text-sm text-slate-500">{reuseTaskData.task_id.slice(0, 12)}...</p>
                </div>
              </div>
              <button onClick={handleReuseClose} className="p-2 rounded hover:bg-slate-100 text-slate-500 hover:text-slate-700">X</button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                  <Type className="w-4 h-4" />
                  Prompt positivo
                </label>
                <div className="flex gap-2">
                  <textarea readOnly className="flex-1 bg-slate-50 rounded-lg border border-slate-300 p-3 text-sm font-mono text-slate-700" rows={3} value={reuseTaskData.prompt || "—"} />
                  <button onClick={() => navigator.clipboard.writeText(reuseTaskData.prompt || "")} className="px-3 py-2 bg-slate-100 rounded-lg hover:bg-slate-200 text-slate-600 hover:text-indigo-600" title="Copiar">
                    <Copy className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                  <Hash className="w-4 h-4" />
                  Prompt negativo
                </label>
                <div className="flex gap-2">
                  <textarea readOnly className="flex-1 bg-slate-50 rounded-lg border border-slate-300 p-3 text-sm font-mono text-slate-700" rows={2} value={reuseTaskData.negative_prompt || "—"} />
                  <button onClick={() => navigator.clipboard.writeText(reuseTaskData.negative_prompt || "")} className="px-3 py-2 bg-slate-100 rounded-lg hover:bg-slate-200 text-slate-600 hover:text-indigo-600" title="Copiar">
                    <Copy className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div><label className="text-sm font-medium text-slate-700">Pasos</label><div className="mt-1 text-lg font-mono text-slate-900">{reuseTaskData.steps}</div></div>
                <div><label className="text-sm font-medium text-slate-700">Scheduler</label><div className="mt-1 text-lg font-mono text-slate-900">{reuseTaskData.scheduler}</div></div>
                <div><label className="text-sm font-medium text-slate-700">Guidance</label><div className="mt-1 text-lg font-mono text-slate-900">{reuseTaskData.guidance}</div></div>
                <div><label className="text-sm font-medium text-slate-700">Dimensiones</label><div className="mt-1 text-lg font-mono text-slate-900">{reuseTaskData.width} x {reuseTaskData.height}</div></div>
                <div><label className="text-sm font-medium text-slate-700">Seed</label><div className="mt-1 text-lg font-mono text-slate-900">{reuseTaskData.seed ?? "aleatorio"}</div></div>
                <div><label className="text-sm font-medium text-slate-700">LoRAs</label><div className="mt-1 text-lg font-mono text-slate-900">{reuseTaskData.loras?.length ? reuseTaskData.loras.join(", ") : "ninguna"}</div></div>
              </div>
              <div className="pt-4 border-t border-slate-200">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input type="checkbox" checked={reuseMode === "txt2img"} onChange={(e) => setReuseMode(e.target.checked ? "txt2img" : "img2img")} className="w-5 h-5 text-indigo-600 border-slate-300 rounded focus:ring-indigo-500" />
                  <div>
                    <p className="font-medium text-slate-900">{reuseMode === "txt2img" ? "Nueva imagen (txt2img)" : "Usar imagen de referencia (img2img)"}</p>
                    <p className="text-sm text-slate-500">{reuseMode === "txt2img" ? "Genera imagen nueva desde cero usando solo los prompts y parámetros" : "Usa la imagen del historial como referencia (img2img)"}</p>
                  </div>
                </label>
              </div>
              <div className="flex gap-3 pt-4 border-t border-slate-200">
                <button onClick={handleReuseApply} className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm font-medium transition">
                  <Settings className="w-4 h-4" />
                  Aplicar parámetros al formulario
                </button>
                <button onClick={handleReuseClose} className="px-4 py-2.5 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 text-sm font-medium transition">Cancelar</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
