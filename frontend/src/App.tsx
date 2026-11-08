import { useState, useEffect, useCallback } from "react";
import { Home } from "./pages/Home";
import { WorkerStatus } from "@/modules/worker/WorkerStatus";
import { useWorker } from "@/modules/worker/useWorker";
import { ImageUpload } from "@/modules/image-upload/ImageUpload";
import { Fibo2EditForm, Fibo2EditParams } from "@/modules/fibo2-edit/Fibo2EditForm";
import { SavedPromptsPanel } from "@/modules/fibo2-edit/SavedPromptsPanel";
import { Execution } from "@/modules/execution/Execution";
import { History } from "@/modules/history/History";
import { Play, Layout } from "lucide-react";

import { calculateFiboDimensions } from "@/lib/imageUtils";

type Page = "home" | "execution" | "history";

const STORAGE_KEY = "comfy-spa-draft";

function loadDraft(): {
  imageB64: string | null;
  params: Partial<Fibo2EditParams>;
} | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function saveDraft(imageB64: string | null, params: Fibo2EditParams) {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ imageB64, params })
    );
  } catch {
    // localStorage puede no estar disponible en modo privado
  }
}

export default function App() {
  const { health, isLoading: workerLoading } = useWorker();
  const workerOnline = health?.online ?? false;
  const [page, setPage] = useState<Page>("home");
  const [imageB64, setImageB64] = useState<string | null>(null);
  const [params, setParams] = useState<Fibo2EditParams>({
    prompt: "",
    negative_prompt: "",
    image_b64: undefined,
    loras: [],
    seed: undefined,
    steps: 4,
    scheduler: "euler",
    guidance: 1.0,
    width: 1024,
    height: 1024,
  });

  // Cargar borrador guardado al iniciar
  useEffect(() => {
    const draft = loadDraft();
    if (draft) {
      setImageB64(draft.imageB64);
      setParams((prev) => ({ ...prev, ...draft.params }));
    }
  }, []);

  // Persistir borrador cada vez que cambie la imagen o los parámetros
  useEffect(() => {
    saveDraft(imageB64, params);
  }, [imageB64, params]);

  // Manejar imagen subida con auto-ajuste de dimensiones
  const handleImageReady = useCallback((b64: string, dimensions?: { width: number; height: number }) => {
    console.log("App.handleImageReady called:", { b64: b64?.length, dimensions });
    setImageB64(b64 || null);
    if (dimensions && b64) {
      const { width, height } = calculateFiboDimensions(dimensions.width, dimensions.height);
      console.log("App: Calculated FIBO dimensions:", { width, height });
      setParams((prev) => ({ ...prev, width, height }));
    } else if (!b64) {
      // Si se quita la imagen, resetear a defaults
      setParams((prev) => ({ ...prev, width: 1024, height: 1024 }));
    }
  }, []);

  // Manejar carga de imagen desde historial
  const handleLoadHistoryImage = useCallback((imageB64: string, taskId: string) => {
    console.log("Loading history image:", taskId);
    setImageB64(imageB64);
    // Las dimensiones se ajustarán automáticamente en handleImageReady
    // Pero necesitamos obtener las dimensiones de la imagen
    const img = new Image();
    img.onload = () => {
      const { width, height } = calculateFiboDimensions(img.width, img.height);
      setParams((prev) => ({ ...prev, width, height }));
    };
    img.src = `data:image/png;base64,${imageB64}`;
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold">
                C
              </div>
              <span className="font-bold text-xl tracking-tight">ComfyUI SPA</span>
            </div>
            <nav className="flex items-center gap-4">
              <button
                onClick={() => setPage("home")}
                className={`px-3 py-2 text-sm font-medium rounded-md transition ${
                  page === "home"
                    ? "bg-indigo-50 text-indigo-700"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <Layout className="w-4 h-4 mr-2" /> Inicio
              </button>
              <button
                onClick={() => setPage("execution")}
                className={`px-3 py-2 text-sm font-medium rounded-md transition ${
                  page === "execution"
                    ? "bg-indigo-50 text-indigo-700"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <Play className="w-4 h-4 mr-2" /> Ejecutar
              </button>
              <button
                onClick={() => setPage("history")}
                className={`px-3 py-2 text-sm font-medium rounded-md transition ${
                  page === "history"
                    ? "bg-indigo-50 text-indigo-700"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                Historial
              </button>
            </nav>
            <WorkerStatus />
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {workerLoading ? (
          <div className="text-center py-20 text-slate-500">
            Verificando worker...
          </div>
        ) : page === "home" ? (
          <Home workerOnline={workerOnline} />
        ) : page === "execution" ? (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
            <div className="lg:col-span-1">
              <SavedPromptsPanel
                currentParams={params}
                onLoadPrompt={(prompt, negative_prompt) =>
                  setParams((prev) => ({ ...prev, prompt, negative_prompt }))
                }
              />
            </div>
            <div className="lg:col-span-2 space-y-8">
              <ImageUpload onImageReady={handleImageReady} />
              <Fibo2EditForm
                imageB64={imageB64 ?? undefined}
                params={params}
                onParamsChange={setParams}
              />
              <Execution
                params={params}
                workerOnline={workerOnline}
              />
            </div>
            <div className="space-y-6">
              <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-slate-900 mb-3">Estado del worker</h3>
                <div className="flex items-center gap-2 text-sm">
                  {workerOnline ? (
                    <>
                      <span className="w-2 h-2 rounded-full bg-green-500" />
                      <span className="text-slate-600">ComfyUI en línea</span>
                    </>
                  ) : (
                    <>
                      <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                      <span className="text-slate-600">ComfyUI sin responder</span>
                    </>
                  )}
                </div>
                {health?.pending_tasks != null && (
                  <p className="mt-1 text-xs text-slate-500">
                    Tareas pendientes: {health.pending_tasks}
                  </p>
                )}
              </div>
              <History onLoadImage={handleLoadHistoryImage} />
            </div>
          </div>
        ) : page === "history" ? (
          <div className="space-y-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-bold text-slate-900">Historial de tareas</h2>
              <span className="text-sm text-slate-500">
                {health?.pending_tasks != null && `Tareas pendientes: ${health.pending_tasks}`}
              </span>
            </div>
            <History />
          </div>
        ) : null}
      </main>
    </div>
  );
}