/**
 * Módulo de subida de imagen.
 * Lee un archivo con FileReader → base64 → preview en pantalla.
 * El base64 se envía al backend al lanzar la ejecución (vía POST /api/tasks).
 * Nunca se guarda en disco del worker; solo viaja en memoria.
 * También extrae las dimensiones de la imagen para auto-ajustar ancho/alto.
 */

import { useState, useCallback, useRef } from "react";
import { Upload } from "lucide-react";
import { getImageDimensions } from "@/lib/imageUtils";

interface ImageUploadProps {
  onImageReady: (imageB64: string, dimensions?: { width: number; height: number }) => void;
}

export function ImageUpload({ onImageReady }: ImageUploadProps) {
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setLoading(true);
      try {
        // Obtener dimensiones de la imagen
        const dimensions = await getImageDimensions(file);
        
        const reader = new FileReader();
        reader.onload = (e) => {
          const b64 = (e.target?.result as string).split(",")[1]; // quitar data URL header
          setPreview(b64 ? `data:image/png;base64,${b64}` : null);
          onImageReady(b64, dimensions);
        };
        reader.readAsDataURL(file);
      } catch (error) {
        console.error("Error leyendo imagen:", error);
        // Fallback sin dimensiones
        const reader = new FileReader();
        reader.onload = (e) => {
          const b64 = (e.target?.result as string).split(",")[1];
          setPreview(b64 ? `data:image/png;base64,${b64}` : null);
          onImageReady(b64);
        };
        reader.readAsDataURL(file);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const handleRemove = useCallback(() => {
    setPreview(null);
    onImageReady("");
  }, [onImageReady]);

  const handleClickUpload = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  return (
    <div className="rounded-xl border-2 border-dashed border-slate-300 bg-white p-8 text-center hover:border-indigo-400 transition">
      <div className="flex flex-col items-center gap-4 cursor-pointer" onClick={handleClickUpload}>
        {preview ? (
          <>
            <img
              src={preview}
              alt="Preview"
              className="w-48 h-48 rounded-lg object-cover border border-slate-200 shadow-sm"
            />
            <button
              onClick={handleRemove}
              className="text-xs text-red-500 hover:text-red-700 underline"
            >
              Quitar imagen
            </button>
          </>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Upload className="w-10 h-10 text-slate-400" />
            <p className="text-sm text-slate-500">Haz clic para subir una imagen</p>
            <p className="text-xs text-slate-400">
              Viaja en base64 en memoria, nunca en disco del worker.
            </p>
          </div>
        )}
      </div>

      {loading && (
        <div className="flex items-center justify-center gap-2 text-xs text-slate-500 mt-2">
          <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <span>Leyendo dimensiones...</span>
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />
    </div>
  );
}