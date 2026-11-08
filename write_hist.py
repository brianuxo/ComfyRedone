content = r'''
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
'''

with open(r'C:/Users/brian/Desktop/ALL/Proyectos/RustComfyCrear/frontend/src/modules/history/History.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Part 1 written')