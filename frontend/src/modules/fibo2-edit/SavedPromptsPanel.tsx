/**
 * Panel de prompts guardados.
 * Permite listar, cargar, guardar y eliminar prompts.
 */

import { useState, useEffect, useCallback } from "react";
import { Plus, Trash2, Loader2, AlertCircle } from "lucide-react";
import { api } from "@/services/api";
import { SavedPrompt, Fibo2EditParams } from "@/types";

interface SavedPromptsPanelProps {
  onLoadPrompt: (prompt: string, negative_prompt: string) => void;
  currentParams: Fibo2EditParams;
}

export function SavedPromptsPanel({ onLoadPrompt, currentParams }: SavedPromptsPanelProps) {
  const [prompts, setPrompts] = useState<SavedPrompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saveTitle, setSaveTitle] = useState("");
  const [error, setError] = useState<string | null>(null);

  const loadPrompts = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.prompts.list();
      setPrompts(data);
    } catch (err) {
      console.error("Error loading prompts:", err);
      setError("No se pudieron cargar los prompts guardados");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPrompts();
  }, [loadPrompts]);

  const handleLoad = (prompt: SavedPrompt) => {
    onLoadPrompt(prompt.prompt, prompt.negative_prompt);
  };

  const handleSave = async () => {
    if (!saveTitle.trim()) {
      setError("El título es obligatorio");
      return;
    }
    if (!currentParams.prompt.trim()) {
      setError("El prompt positivo no puede estar vacío");
      return;
    }

    try {
      setSaving(true);
      setError(null);
      await api.prompts.create({
        title: saveTitle.trim(),
        prompt: currentParams.prompt,
        negative_prompt: currentParams.negative_prompt,
      });
      setShowSaveModal(false);
      setSaveTitle("");
      await loadPrompts();
    } catch (err) {
      console.error("Error saving prompt:", err);
      setError("No se pudo guardar el prompt");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (promptId: string) => {
    if (!confirm("Eliminar este prompt guardado?")) return;
    try {
      setDeletingId(promptId);
      await api.prompts.delete(promptId);
      setPrompts((prev) => prev.filter((p) => p.id !== promptId));
    } catch (err) {
      console.error("Error deleting prompt:", err);
      setError("No se pudo eliminar el prompt");
    } finally {
      setDeletingId(null);
    }
  };

  const formatDate = (ts: number) => {
    return new Date(ts).toLocaleDateString("es-ES", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm h-full">
      <div className="flex items-center justify-between mb-4">
        <h3 className="flex items-center gap-2 text-lg font-semibold text-slate-900">
          <span className="w-5 h-5" />
          Prompts guardados
        </h3>
        <button
          onClick={() => setShowSaveModal(true)}
          disabled={saving || !currentParams.prompt.trim()}
          className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center gap-1"
        >
          <Plus className="w-4 h-4" />
          Guardar
        </button>
      </div>

      {error && (
        <div className="mb-3 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-8 text-slate-500">
          <Loader2 className="w-5 h-5 animate-spin text-indigo-600" />
        </div>
      ) : prompts.length === 0 ? (
        <div className="text-center py-8 text-slate-500">
          <p className="text-sm">No hay prompts guardados</p>
          <p className="text-xs text-slate-400 mt-1">
            Configura un prompt y haz clic en "Guardar"
          </p>
        </div>
      ) : (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {prompts.map((prompt) => (
            <div
              key={prompt.id}
              className="group relative rounded-lg border border-slate-200 bg-slate-50 p-3 hover:border-indigo-300 hover:bg-white transition"
            >
              <button
                onClick={() => handleLoad(prompt)}
                className="w-full text-left flex items-start justify-between gap-2 pr-8"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-slate-900 truncate">{prompt.title}</p>
                  <p className="text-xs text-slate-500 mt-0.5 truncate">{prompt.prompt}</p>
                  {prompt.negative_prompt && (
                    <p className="text-xs text-slate-400 mt-0.5 truncate">
                      Neg: {prompt.negative_prompt}
                    </p>
                  )}
                  <p className="text-xs text-slate-400 mt-1">{formatDate(prompt.updated_at)}</p>
                </div>
              </button>
              <div className="absolute right-2 top-2 flex gap-1 opacity-0 group-hover:opacity-100 transition">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(prompt.id);
                  }}
                  disabled={deletingId === prompt.id}
                  className="p-1.5 rounded text-slate-400 hover:text-red-600 hover:bg-red-50 disabled:opacity-50"
                  title="Eliminar"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
              {deletingId === prompt.id && (
                <div className="absolute inset-0 flex items-center justify-center bg-white/80">
                  <Loader2 className="w-5 h-5 animate-spin text-indigo-600" />
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {showSaveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h4 className="text-lg font-semibold text-slate-900 mb-4">Guardar prompt actual</h4>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Título</label>
                <input
                  type="text"
                  value={saveTitle}
                  onChange={(e) => setSaveTitle(e.target.value)}
                  placeholder="Ej: Estilo cyberpunk"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                  autoFocus
                />
              </div>
              <div className="text-xs text-slate-500">
                Prompt positivo: {currentParams.prompt.slice(0, 80)}{currentParams.prompt.length > 80 ? "..." : ""}
              </div>
              {currentParams.negative_prompt && (
                <div className="text-xs text-slate-500">
                  Prompt negativo: {currentParams.negative_prompt.slice(0, 80)}{currentParams.negative_prompt.length > 80 ? "..." : ""}
                </div>
              )}
              {error && (
                <div className="text-sm text-red-600">{error}</div>
              )}
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => {
                  setShowSaveModal(false);
                  setSaveTitle("");
                  setError(null);
                }}
                className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200"
              >
                Cancelar
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                {saving ? "Guardando..." : "Guardar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}