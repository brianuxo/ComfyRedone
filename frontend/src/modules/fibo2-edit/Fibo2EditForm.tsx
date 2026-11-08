/**
 * Formulario de parámetros FIBO 2.0 Edit.
 * Exposición de un DTO listo para enviar al backend.
 */

import { useEffect, useCallback } from "react";
import { Bot, Type, Sparkles } from "lucide-react";

export interface Fibo2EditParams {
  prompt: string;
  image_b64?: string;
  loras: string[];
  seed?: number;
  steps: number;
  scheduler: string;
  guidance: number;
  width: number;
  height: number;
}

interface Fibo2EditFormProps {
  onParamsChange: (params: Fibo2EditParams | ((prev: Fibo2EditParams) => Fibo2EditParams)) => void;
  imageB64?: string;
  params: Fibo2EditParams;
}

export function Fibo2EditForm({ onParamsChange, imageB64, params }: Fibo2EditFormProps) {
  // Sincronizar imagen entrante cuando cambia (solo image_b64, no todo params)
  useEffect(() => {
    if (imageB64) {
      onParamsChange((prev) => ({ ...prev, image_b64: imageB64 }));
    }
  }, [imageB64, onParamsChange]);

  // Wrapper para notificar cambios al padre
  const notifyParamsChange = useCallback((updater: Fibo2EditParams | ((prev: Fibo2EditParams) => Fibo2EditParams)) => {
    onParamsChange(updater);
  }, [onParamsChange]);

  const handleLoraAdd = () => {
    notifyParamsChange((prev) => ({
      ...prev,
      loras: [...prev.loras, ""],
    }));
  };

  const handleLoraRemove = (index: number) => {
    notifyParamsChange((prev) => ({
      ...prev,
      loras: prev.loras.filter((_, i) => i !== index),
    }));
  };

  const handleLoraChange = (index: number, value: string) => {
    notifyParamsChange((prev) => {
      const loras = [...prev.loras];
      loras[index] = value;
      return { ...prev, loras };
    });
  };

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center gap-3 mb-4">
          <Bot className="w-5 h-5 text-indigo-600" />
          <h3 className="text-lg font-semibold text-slate-900">Parámetros FIBO 2.0 Edit</h3>
        </div>

        {/* Prompt */}
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
            <Type className="w-4 h-4" />
            Prompt / Instrucción
          </label>
          <textarea
            value={params.prompt}
            onChange={(e) =>
              notifyParamsChange((prev) => ({ ...prev, prompt: e.target.value }))
            }
            rows={3}
            className="w-full rounded-lg border border-slate-300 p-3 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
            placeholder="Ej: Cambia el estilo de la imagen a cyberpunk..."
          />
        </div>

        {/* LoRAs */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
              <Sparkles className="w-4 h-4" />
              LoRAs (encadenadas)
            </label>
            <button
              onClick={handleLoraAdd}
              className="text-xs px-2 py-1 rounded bg-slate-100 text-slate-600 hover:bg-slate-200"
            >
              + Añadir LoRA
            </button>
          </div>
          <div className="space-y-2">
            {params.loras.map((lora, i) => (
              <div key={i} className="flex gap-2">
                <input
                  value={lora}
                  onChange={(e) => handleLoraChange(i, e.target.value)}
                  placeholder="Nombre de la LoRA"
                  className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                />
                <button
                  onClick={() => handleLoraRemove(i)}
                  className="p-1.5 rounded-lg text-red-500 hover:bg-red-50"
                >
                  ×
                </button>
              </div>
            ))}
            {params.loras.length === 0 && (
              <p className="text-xs text-slate-400 italic">
                Opcional: LoRas encadenadas imitando AusBoss
              </p>
            )}
          </div>
        </div>

        {/* Seed, steps, scheduler, guidance en grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">Seed</label>
            <input
              type="number"
              value={params.seed ?? ""}
              onChange={(e) =>
                notifyParamsChange((prev) => ({
                  ...prev,
                  seed: e.target.value ? parseInt(e.target.value, 10) : undefined,
                }))
              }
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
              placeholder="Aleatorio"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">Pasos</label>
            <input
              type="number"
              value={params.steps}
              min="1"
              max="100"
              onChange={(e) =>
                notifyParamsChange((prev) => ({ ...prev, steps: parseInt(e.target.value, 10) || 20 }))
              }
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">Scheduler</label>
            <select
              value={params.scheduler}
              onChange={(e) =>
                notifyParamsChange((prev) => ({ ...prev, scheduler: e.target.value }))
              }
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
            >
              <option value="euler">Euler</option>
              <option value="euler_ancestral">Euler Ancestral</option>
              <option value="heun">Heun</option>
              <option value="dpm_2">DPM 2</option>
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">Guidance</label>
            <input
              type="number"
              value={params.guidance}
              min="0"
              max="20"
              step="0.1"
              onChange={(e) =>
                notifyParamsChange((prev) => ({ ...prev, guidance: parseFloat(e.target.value) || 3.5 }))
              }
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">Ancho</label>
            <input
              type="number"
              value={params.width}
              min="256"
              max="2048"
              onChange={(e) =>
                notifyParamsChange((prev) => ({ ...prev, width: parseInt(e.target.value, 10) || 1024 }))
              }
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">Alto</label>
            <input
              type="number"
              value={params.height}
              min="256"
              max="2048"
              onChange={(e) =>
                notifyParamsChange((prev) => ({ ...prev, height: parseInt(e.target.value, 10) || 1024 }))
              }
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
            />
          </div>
        </div>
      </div>

      {/* Resumen visual de lo que se enviará */}
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
        <h4 className="text-sm font-semibold text-slate-700 mb-2">Resumen de envío</h4>
        <ul className="text-xs text-slate-600 space-y-1">
          <li>Prompt: <span className="font-mono truncate block">{params.prompt || "—"}</span></li>
          <li>
            Imagen de entrada:{params.image_b64 ? " ✅ cargada" : " ❌ ninguna"}
          </li>
          <li>LoRAs: {params.loras.length > 0 ? params.loras.join(", ") : "ninguna"}</li>
          <li>Seed: {params.seed ?? "aleatorio"}</li>
          <li>Pasos: {params.steps}</li>
          <li>Scheduler: {params.scheduler}</li>
          <li>Guidance: {params.guidance}</li>
          <li>Tamaño: {params.width} × {params.height}</li>
        </ul>
      </div>
    </div>
  );
}