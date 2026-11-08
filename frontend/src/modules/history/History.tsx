/**
 * Historial de tareas recientes con vista previa de imágenes desde OCI.
 */

import { useEffect, useState } from "react";
import { Clock, Image as ImageIcon, Eye, Download } from "lucide-react";
import { api } from "@/services/api";

export function History() {
  const [tasks, setTasks] = useState<
    Array<{
      task_id: string;
      status: string;
      created_at: number;
      updated_at: number;
      has_image: boolean;
      error?: string;
      source?: string;
    }>
  >([]);
  const [loading, setLoading] = useState(true);
  const [previewTask, setPreviewTask] = useState<{
    task_id: string;
    image_b64: string;
  } | null>(null);

  useEffect(() => {
    api.listTasks().then(setTasks).finally(() => setLoading(false));
  }, []);

  const handlePreview = async (taskId: string) => {
    try {
      const task = await api.getTask(taskId);
      if (task.image_b64) {
        setPreviewTask({ task_id: taskId, image_b64: task.image_b64 });
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
        <p className="text-sm">No hay tareas recientes.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <Clock className="w-5 h-5 text-slate-500" />
        <h3 className="text-lg font-semibold text-slate-900">Historial de tareas</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500 uppercase">
              <th className="pb-3 pr-4">ID</th>
              <th className="pb-3">Estado</th>
              <th className="pb-3">Creada</th>
              <th className="pb-3">Origen</th>
              <th className="pb-3">Imagen</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {tasks.map((t) => (
              <tr key={t.task_id} className="hover:bg-slate-50 cursor-pointer">
                <td className="py-3 pr-4 font-mono text-xs text-slate-600">
                  {t.task_id.slice(0, 8)}…
                </td>
                <td className="py-3">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      t.status === "completed"
                        ? "bg-green-100 text-green-700"
                        : t.status === "failed"
                        ? "bg-red-100 text-red-700"
                        : t.status === "running"
                        ? "bg-blue-100 text-blue-700"
                        : "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {t.status}
                  </span>
                </td>
                <td className="py-3 text-xs text-slate-600">
                  {new Date(t.created_at * 1000).toLocaleString()}
                </td>
                <td className="py-3 text-xs text-slate-500">
                  {t.source === "oci_results" ? (
                    <span className="text-green-600">☁️ OCI</span>
                  ) : t.source === "oci_processing" ? (
                    <span className="text-blue-600">⚙️ Procesando</span>
                  ) : (
                    <span className="text-slate-600">💾 Caché</span>
                  )}
                </td>
                <td className="py-3 text-xs text-slate-600">
                  {t.has_image ? (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePreview(t.task_id);
                        }}
                        className="p-1.5 rounded hover:bg-slate-100 text-slate-600 hover:text-indigo-600 transition"
                        title="Ver imagen"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          // Para descargar necesitaríamos fetch la imagen
                          handlePreview(t.task_id);
                        }}
                        className="p-1.5 rounded hover:bg-slate-100 text-slate-600 hover:text-indigo-600 transition"
                        title="Descargar"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                    </div>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal de vista previa */}
      {previewTask && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          onClick={() => setPreviewTask(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh] bg-white rounded-xl shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="font-semibold text-slate-900">Resultado: {previewTask.task_id.slice(0, 8)}…</h3>
              <button
                onClick={() => setPreviewTask(null)}
                className="p-2 rounded hover:bg-slate-100 text-slate-500 hover:text-slate-700"
              >
                ✕
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