/**
 * Página de inicio.
 * Muestra el estado del worker y explica el flujo vía OCI.
 */

import { WorkerStatus } from "@/modules/worker/WorkerStatus";

interface HomeProps {
  workerOnline: boolean;
}

export function Home({ workerOnline }: HomeProps) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-slate-900">Generar imagen</h1>
        <p className="text-slate-600 mt-2">
          Workflow activo: <span className="font-mono text-sm">FIBO 2.0 Edit</span>
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900 mb-3">Estado del worker</h2>
        <WorkerStatus />
      </div>

      <div className="rounded-xl border border-slate-200 bg-slate-50 p-6">
        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-3">
          Cómo funciona
        </h3>
        <ul className="space-y-2 text-sm text-slate-600 list-disc pl-6">
          <li>
            Sube una imagen (viaja en base64 en memoria, nunca en disco del worker).
          </li>
          <li>Ajusta el prompt y los parámetros de FIBO 2.0 Edit.</li>
          <li>
            Lanza la ejecución: la tarea se envía a OCI y el daemon de ComfyUI en
            Kaggle/Colab la ejecuta.
          </li>
          <li>
            El resultado se sube a OCI y se muestra directamente en pantalla.
          </li>
        </ul>
      </div>

      {!workerOnline && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-6">
          <h3 className="text-sm font-semibold text-amber-800 mb-2">
            Worker no disponible
          </h3>
          <p className="text-amber-700 text-sm">
            El daemon de ComfyUI no está enviando heartbeat a OCI. Asegúrate de que
            esté corriendo en Kaggle/Colab y escribiendo en el bucket{" "}
            <code className="font-mono">comfyuiOut</code>.
          </p>
        </div>
      )}
    </div>
  );
}