import { useState, useCallback, useRef, useEffect } from "react";
import { Upload } from "lucide-react";
import { getImageDimensions } from "@/lib/imageUtils";

interface ImageUploadProps {
  onImageReady: (imageB64: string, dimensions?: { width: number; height: number }) => void;
  imageB64?: string | null;  // Imagen existente para mostrar (persistencia)
}

export function ImageUpload({ onImageReady, imageB64: externalImageB64 }: ImageUploadProps) {
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const previewRef = useRef<HTMLImageElement>(null);

  // Sincronizar con imagen externa (desde draft/historial)
  useEffect(() => {
    if (externalImageB64) {
      const b64 = externalImageB64.startsWith("data:") 
        ? externalImageB64.split(",")[1] 
        : externalImageB64;
      setPreview(b64 ? `data:image/png;base64,${b64}` : null);
    } else {
      setPreview(null);
    }
  }, [externalImageB64]);

  const handleFile = useCallback(
    async (file: File) => {
      setLoading(true);
      try {
        // Obtener dimensiones de la imagen
        console.log("ImageUpload: Getting dimensions for file:", file.name, file.size, file.type);
        const dimensions = await getImageDimensions(file);
        console.log("ImageUpload: Got dimensions:", dimensions);
        
        const reader = new FileReader();
        reader.onload = (e) => {
          const b64 = (e.target?.result as string).split(",")[1]; // quitar data URL header
          setPreview(b64 ? `data:image/png;base64,${b64}` : null);
          console.log("ImageUpload: Calling onImageReady with b64 length:", b64?.length, "dimensions:", dimensions);
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
          console.log("ImageUpload: Fallback - calling onImageReady without dimensions");
          onImageReady(b64);
        };
        reader.readAsDataURL(file);
      } finally {
        setLoading(false);
      }
    },
    [onImageReady]
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
              ref={previewRef}
              src={preview}
              alt="Preview"
              className="max-w-64 max-h-64 rounded-lg object-contain border border-slate-200 shadow-sm bg-slate-50"
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