/**
 * Calcula dimensiones compatibles con FIBO 2.0 Edit:
 * - Múltiplos de 16
 * - Área aproximada de 1MP (1024x1024)
 * - Mantiene aspect ratio de la imagen original
 * - Máximo 2048x2048, mínimo 256x256
 */
export function calculateFiboDimensions(
  originalWidth: number,
  originalHeight: number,
  maxArea: number = 1024 * 1024,
  maxDim: number = 2048,
  minDim: number = 256
): { width: number; height: number } {
  const aspectRatio = originalWidth / originalHeight;
  
  // Calcular dimensiones teóricas manteniendo aspect ratio
  let targetWidth = Math.sqrt(maxArea * aspectRatio);
  let targetHeight = targetWidth / aspectRatio;
  
  // Si excede maxDim, escalar hacia abajo
  if (targetWidth > maxDim || targetHeight > maxDim) {
    if (targetWidth > targetHeight) {
      targetWidth = maxDim;
      targetHeight = maxDim / aspectRatio;
    } else {
      targetHeight = maxDim;
      targetWidth = maxDim * aspectRatio;
    }
  }
  
  // Redondear a múltiplos de 16
  const roundTo16 = (n: number) => Math.max(minDim, Math.min(maxDim, Math.round(n / 16) * 16));
  
  let width = roundTo16(targetWidth);
  let height = roundTo16(targetHeight);
  
  // Re-ajustar height manteniendo aspect ratio después del redondeo de width
  height = roundTo16(width / aspectRatio);
  
  // Verificar que no exceda límites después del segundo redondeo
  if (width > maxDim) width = maxDim;
  if (height > maxDim) height = maxDim;
  if (width < minDim) width = minDim;
  if (height < minDim) height = minDim;
  
  return { width, height };
}

/**
 * Obtiene dimensiones de una imagen a partir de su base64 o File
 */
export function getImageDimensions(file: File): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      console.log("getImageDimensions: loaded", { width: img.naturalWidth, height: img.naturalHeight });
      resolve({ width: img.naturalWidth, height: img.naturalHeight });
      URL.revokeObjectURL(img.src);
    };
    img.onerror = (err) => {
      console.error("getImageDimensions: error loading image", err);
      URL.revokeObjectURL(img.src);
      reject(new Error('No se pudo cargar la imagen'));
    };
    const url = URL.createObjectURL(file);
    console.log("getImageDimensions: created blob URL", url);
    img.src = url;
  });
}

/**
 * Obtiene dimensiones de una imagen base64
 */
export function getImageDimensionsFromBase64(base64: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      resolve({ width: img.naturalWidth, height: img.naturalHeight });
    };
    img.onerror = () => reject(new Error('No se pudo cargar la imagen base64'));
    img.src = `data:image/png;base64,${base64}`;
  });
}