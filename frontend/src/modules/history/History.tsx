/**
 * Historial de tareas recientes con vista de galería de imágenes desde OCI.
 * Muestra imágenes completadas en grid 3 columnas con numeración.
 * Click en imagen carga la imagen en el formulario principal.
 */

import { useEffect, useState, useCallback } from "react";
import { Clock, Image as ImageIcon, Eye, Download, RotateCcw } from "lucide-react";
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
}

export function History({ onLoadImage }: HistoryProps) {
  const [tasks, setTasks] = useState<HistoryTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [previewTask, setPreviewTask] = useState<{
    task_id: string;
    image_b64: string;
  } | null>(null);
  const [imageCache, setImageCache] = useState<Record<string, string>>({});

  const fetchTasks = useCallback(async () => {
    try {
      const data = await api.listTasks();
      console.log("[History] Raw API data:", data.map(d => ({ id: d.task_id.slice(0,8), created_at: d.created_at, status: d.status, has_image: d.has_image })));
      const completedTasks = data.filter((t) => t.status === "completed" && t.has_image);
      console.log("[History] Filtered completed:", completedTasks.map(d => ({ id: d.task_id.slice(0,8), created_at: d.created_at })));
      // Ordenar por fecha más reciente primero (created_at descendente)
      // IMPORTANTE: crear nuevo array para que React detecte el cambio
      const sortedTasks = [...completedTasks].sort((a, b) => {
        const aTs = Number(a.created_at) || 0;
        const bTs = Number(b.created_at) || 0;
        const diff = bTs - aTs; // descendente: más reciente primero
        console.log(`[History] Sort compare: a=${a.task_id.slice(0,8)}(${aTs}) b=${b.task_id.slice(0,8)}(${bTs}) diff=${diff}`);
        return diff;
      });
      console.log("[History] Sorted array (first 5):", sortedTasks.slice(0,5).map(d => ({ id: d.task_id.slice(0,8), created_at: d.created_at })));
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

  const formatDate = (ts: number) => {
    // ts viene en segundos (Unix timestamp), Date espera milisegundos
    return new Date(ts * 1000).toLocaleString("es-ES", {
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
          <h3 className="text-lg font-semibold text-slate-900">Historial de imágenes</h3>
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
                  {/* Debug: show raw timestamp */}
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
    </div>
  );
}
