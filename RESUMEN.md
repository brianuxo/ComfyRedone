# Resumen del Proyecto — ComfyUI SPA (FIBO 2.0 Edit)

## Estado actual

Sprints completados: **1, 2 y 3**

- ✅ **Sprint 1 — Base y Worker Check**: Backend FastAPI con `GET /health` que consulta ComfyUI. Frontend React con `useWorker()` (polling cada 5s) y `WorkerStatus` (indicador verde/rojo).
- ✅ **Sprint 2 — Backend FIBO 2.0 Edit**: `schema.py`, `builder.py`, `validator.py`, `executor.py`, `db/store.py` y endpoints `/api/tasks`, `/api/images/upload`.
- ✅ **Sprint 3 — Frontend**: Módulos `worker`, `image-upload`, `fibo2-edit`, `execution`, `history`; páginas Inicio / Ejecutar / Historial.

## Arquitectura (cero disco del worker)

```
backend/
  app/core/config.py          # Variables de entorno (COMFY_HOST, COMFY_PORT, OCI_*, CORS, TTL)
  app/workers/health.py       # WorkerHealth: consulta /system_stats de ComfyUI
  app/api/health.py           # GET /health -> { online, comfy_alive, ... }
  app/api/tasks.py            # POST/GET/DELETE /api/tasks
  app/api/images.py           # POST /api/images/upload (base64 en memoria)
  app/db/store.py             # TaskStore en memoria con TTL (thread-safe)
  app/workflows/fibo2_edit/
    schema.py                 # Pydantic: prompt, image_b64, loras, seed, steps, scheduler, guidance, width, height
    builder.py                # Construye JSON prompt de ComfyUI (15 nodos fijos)
    validator.py              # Rechaza SaveImage/PreviewImage (anti-disco); valida nodos obligatorios
    executor.py               # WS a ComfyUI, captura PNG del nodo 11, devuelve base64 en memoria
frontend/
  src/modules/worker/         # useWorker + WorkerStatus (verifica si worker está encendido)
  src/modules/image-upload/   # FileReader -> base64 + preview (memoria solo)
  src/modules/fibo2-edit/     # Formulario parámetros FIBO 2.0 Edit
  src/modules/execution/      # Lanzar tarea, polling, mostrar imagen resultado
  src/modules/history/        # Historial de tareas recientes
  src/services/api.ts         # Cliente REST
  src/services/ws.ts          # Utilidad WebSocket
```

## Funciona SIN ComfyUI encendido

La app es totalmente independiente de ComfyUI:

- **Frontend**: se carga y navega normalmente.
- **`GET /health`**: devuelve `online: false` si ComfyUI no responde en `127.0.0.1:8188`.
- **Botón "Generar imagen"**: se deshabilita automáticamente si el worker está offline.
- **Constructor de workflow** (`builder.py`): genera el JSON de ComfyUI sin necesidad de que el servidor esté activo.
- **Validación** (`validator.py`): rechaza nodos de disco sin necesidad de ComfyUI.

Cuando ComfyUI **sí** esté encendido, el indicador se pone verde y se puede ejecutar el flujo completo.

## Cómo ejecutar

### Backend (puerto 8000)
```powershell
cd C:\Users\brian\Desktop\ALL\Proyectos\RustComfyCrear\backend
cp .env.example .env
# Editar .env si es necesario (COMFY_HOST, COMFY_PORT, OCI_*)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Frontend (puerto 5173)
```powershell
cd C:\Users\brian\Desktop\ALL\Proyectos\RustComfyCrear\frontend
npm run dev
```

Luego abrir `http://localhost:5173`.

## Endpoints disponibles

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Info de la app |
| GET | `/health` | Estado del worker ComfyUI (online/offline) |
| GET | `/health/simple` | Health ligero del backend |
| POST | `/api/tasks` | Lanzar ejecución FIBO 2.0 Edit |
| GET | `/api/tasks/{id}` | Consultar estado/resultado de una tarea |
| DELETE | `/api/tasks/{id}` | Cancelar/eliminar tarea |
| GET | `/api/tasks` | Listar tareas recientes |
| POST | `/api/images/upload` | Subir imagen base64 a memoria |

## Documentación técnica de referencia

El directorio `C:\Users\brian\Desktop\ALL\Proyectos\reaComfy/` contiene el análisis REA de ComfyUI que confirma:
- `POST /prompt` recibe `{ "prompt": {...}, "client_id": "..." }` (formato API)
- Los links entre nodos se representan como `["node_id", slot]`
- WebSocket `/ws?clientId=<sid>` para progreso en tiempo real
- Nodos `SaveImage`/`PreviewImage` escriben a disco (rechazados por nuestro validator)

## Próximos pasos (Sprint 4)

1. Levantar ComfyUI en `127.0.0.1:8188` con custom nodes `ComfyUI-Fibo2`, `LoadImageRAM`, `SaveImageWebsocket`.
2. Probar flujo E2E: subir imagen → ajustar parámetros → ejecutar → ver imagen resultado en base64.
3. Verificar que no se escribe nada en disco del worker.
4. (Opcional) Integrar `storage/oci_client.py` para respaldar resultados en OCI desde memoria.