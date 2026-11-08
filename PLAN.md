# Plan de Implementación — ComfyUI SPA (FIBO 2.0 Edit)

**Objetivo:** Aplicación tipo ComfyUI pero **sin nodos visuales ni interfaz interactiva de nodos**. SPA con parámetros ajustables y prompts, subida de imagen en memoria (base64, cero disco del worker), y ejecución del único workflow disponible por ahora: **FIBO 2.0 Edit**. Arquitectura extremadamente modular y ordenada, separando carpetas por cada trabajo de la app para evitar código spaghetti.

---

## 1. Alcance del MVP

| Característica | Estado |
|---|---|
| Workflows soportados | Solo **FIBO 2.0 Edit** (nodos 1, 30–31 LoRAs, 2/2b/2c/2d LoadImageRAM, 3 Conditioning, 4 EmptyLatent, 5 Scheduler, 6 Guider, 7 RandomNoise, 8 KSamplerSelect, 9 SamplerCustomAdvanced, 10 VAEDecode, 11 SaveImageWebsocket, 15 TextEncoder, 16 VAE) |
| Interfaz | SPA web (React + TypeScript + Vite + Tailwind) |
| Subida de imagen | Base64 en memoria (frontend y backend), **nunca escribe en disco del worker** |
| Salida de imagen | Capturada por WebSocket de ComfyUI (`SaveImageWebsocket`), devuelta al frontend como base64 en memoria |
| Almacenamiento | Memoria RAM del backend (TTL opcional). OCI/S3 solo como respaldo opcional en nube, sin tocar disco local |
| Verificación de worker | Módulo dedicado que detecta si ComfyUI está encendido (`GET /health` → `system_stats`) |
| Requisito del usuario | El script Kaggle → OCI se pasará al final y se integrará como referencia de configuración |

---

## 2. Arquitectura modular

**Regla de oro:** cada carpeta de `workflows/` es un trabajo independiente. Tocar `fibo2-edit` no afecta a ningún otro flujo futuro.

```
comfy-spa/
├── backend/
│   ├── app/
│   │   ├── core/                 # config, env, logging, constantes
│   │   ├── db/                   # almacén en memoria (task_id → estado, resultado base64, errores)
│   │   ├── workers/              # salud del worker, gestor de proceso ComfyUI, heartbeat
│   │   ├── workflows/            # UN workflow por carpeta
│   │   │   └── fibo2_edit/
│   │   │       ├── schema.py     # Pydantic: parámetros de entrada del SPA
│   │   │       ├── builder.py    # construye JSON "prompt" de ComfyUI (nodos fijos)
│   │   │       ├── executor.py   # WS a ComfyUI, captura PNG en memoria, devuelve base64
│   │   │       └── validator.py  # rechaza SaveImage/PreviewImage (no-disk) y valida estructura
│   │   ├── storage/              # abstracción OCI/S3 (opcional, solo respaldo en nube)
│   │   ├── api/                  # rutas REST y WebSocket
│   │   │   ├── health.py         # verificar si el worker está encendido
│   │   │   ├── tasks.py          # crear, consultar, cancelar tareas
│   │   │   ├── images.py         # subir imagen base64 a memoria
│   │   │   └── workflows.py      # metadatos del workflow disponible
│   │   └── main.py               # punto de entrada FastAPI
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── modules/              # un módulo por "trabajo" de la app
│   │   │   ├── worker/           # verificar si el worker está encendido (polling + indicador)
│   │   │   ├── fibo2-edit/       # formulario de parámetros FIBO 2.0 Edit
│   │   │   ├── image-upload/     # subir imagen → base64 en memoria + preview
│   │   │   ├── execution/        # lanzar ejecución, stream por WS, recibir imagen base64
│   │   │   └── history/          # historial en memoria de tareas (resultados temporales)
│   │   ├── components/           # UI compartida (botones, inputs, modales, loader)
│   │   ├── pages/                # rutas de la SPA (Home, Ejecución, Historial, Ajustes)
│   │   ├── services/             # cliente API (axios/fetch) y servicio WS
│   │   ├── types/                # tipos TypeScript compartidos con backend
│   │   ├── utils/                # base64 helpers, validación de imagen, formateo
│   │   └── main.tsx
│   ├── index.html
│   └── vite.config.ts
│
└── docker-compose.yml (opcional)
```

---

## 3. Módulo "Verificar Worker" (requisito explícito)

### Backend
- `GET /health` consulta `http://127.0.0.1:8188/system_stats` de ComfyUI.
- Respuesta: `online`, `comfy_alive` (bool), `gpu_name`, `vram`, `pending_tasks`, `timestamp`.
- Si ComfyUI no responde, puede intentar reiniciarlo (reutilizando lógica de `subprocess.Popen` del script proporcionado).

### Frontend
- Componente `WorkerStatus` que hace polling cada 5–10 s a `/health`.
- Indicador visual (verde/rojo) en la cabecera de la SPA.
- Si el worker está apagado, deshabilita el botón de "Ejecutar" y muestra aviso.
- Hook `useWorker()` para que otros módulos consulten estado antes de enviar tareas.

---

## 4. Flujo de ejecución (cero disco del worker)

1. Usuario abre SPA → `WorkerStatus` verifica que ComfyUI esté encendido.
2. Usuario sube imagen (solo modo edit) → `FileReader` → base64 → preview en pantalla. Se guarda en `Map` en memoria del frontend (y opcionalmente en `db/` del backend, clave `task_id`, sin disco).
3. Usuario ajusta parámetros (prompt, LoRAs, seed, pasos, scheduler).
4. Usuario pulsa "Ejecutar":
   - Frontend llama `POST /api/tasks` con el DTO de FIBO 2.0 Edit.
   - Backend `builder.py` construye el JSON `prompt` de ComfyUI con nodos fijos (inyectando `image_b64` en nodos `LoadImageRAM`).
   - `validator.py` rechaza si hay `SaveImage`/`PreviewImage` o nodos de escritura a disco.
   - `executor.py` abre WS `ws://127.0.0.1:8188/ws?clientId=...`, envía `/prompt`, escucha mensajes, captura binario del nodo `11` (`SaveImageWebsocket`), convierte a base64 en memoria.
   - Resultado se almacena en `db/` (memoria) y se devuelve al frontend.
5. Frontend muestra la imagen desde base64 (`<img src="data:image/png;base64,...">`). **Nunca se escribió en disco.**

---

## 5. Reutilización del script Kaggle → OCI

| Parte del script | Destino en nueva arquitectura |
|---|---|
| Config OCI (bucket, claves, endpoint) | `backend/app/storage/oci_client.py` (respaldos opcionales en nube) |
| Descarga de modelos con `wget` | Se mantiene fuera (setup/provisioning del worker) |
| `LoadImageRAM` (custom node) | Sigue usándose en ComfyUI; backend le envía `image_b64` por workflow JSON |
| `SaveImageWebsocket` | Sigue usándose; backend captura binario por WS y lo devuelve al frontend |
| `fix_seed`, `validate_no_disk_writes` | Se llevan a `backend/app/workflows/fibo2_edit/validator.py` y `builder.py` |
| `run_polling_loop` / cola S3 | Se reemplaza por API REST + `db/` en memoria del backend |
| Heartbeat a `status/worker.json` | Se simplifica a `GET /health` que consulta `system_stats` |

---

## 6. Stack tecnológico

- **Backend:** Python + FastAPI (async, WebSocket nativo, Pydantic para validación).
- **Comunicación:** REST para tareas/imágenes; WebSocket para ejecución en tiempo real (progreso y captura de imagen).
- **Frontend:** React + Vite + TypeScript + Tailwind CSS. Tipos TypeScript compartidos con el backend para evitar desajustes.
- **Imágenes:** Base64 end-to-end; en backend `io.BytesIO` + PIL/torch solo en memoria.
- **Worker:** ComfyUI local (127.0.0.1:8188) con custom node `ComfyUI-Fibo2` y `LoadImageRAM`.

---

## 7. Sprint 1 — Base y Worker Check

**Objetivo:** Tener el esqueleto del proyecto, el backend corriendo, y el frontend capaz de detectar si el worker (ComfyUI) está encendido.

### Entregables
1. Repositorio inicial con estructura de carpetas (backend + frontend).
2. `backend/app/core/config.py` con variables de entorno (`COMFY_HOST`, `COMFY_PORT`, `OCI_*`, etc.).
3. `backend/app/workers/health.py` + `backend/app/api/health.py`: endpoint `GET /health` que consulta `system_stats` de ComfyUI.
4. `frontend/src/modules/worker/`: componente `WorkerStatus` + hook `useWorker()` + polling a `/health`.
5. Página de inicio (`frontend/src/pages/Home.tsx`) que muestra el estado del worker.

### Tareas
- [ ] Crear estructura de directorios vacía.
- [ ] Inicializar proyecto FastAPI con `main.py`, `core/config.py`.
- [ ] Implementar `GET /health` (consulta a ComfyUI, manejo de errores si no responde).
- [ ] Inicializar proyecto React + Vite + TypeScript + Tailwind.
- [ ] Implementar `WorkerStatus` y `useWorker` con polling.
- [ ] Conectar frontend con backend (CORS, proxy de desarrollo).
- [ ] Prueba: abrir SPA, apagar/encender ComfyUI, verificar que el indicador cambia.

### Criterios de aceptación
- `GET /health` devuelve `online: true` cuando ComfyUI responde, `false` cuando no.
- La SPA muestra un indicador visual claro de estado del worker.
- El código cumple con la estructura de carpetas definida (sin spaghetti).

---

## 8. Sprint 2 — Backend: Workflow FIBO 2.0 Edit

**Objetivo:** Backend capaz de construir, validar y ejecutar el workflow FIBO 2.0 Edit, devolviendo la imagen resultante en base64 sin tocar disco.

### Entregables
1. `backend/app/workflows/fibo2_edit/schema.py`: Pydantic con parámetros de entrada (prompt, imágenes base64, LoRAs, seed, scheduler, pasos, etc.).
2. `backend/app/workflows/fibo2_edit/builder.py`: construye JSON `prompt` de ComfyUI con los nodos fijos.
3. `backend/app/workflows/fibo2_edit/validator.py`: rechaza `SaveImage`/`PreviewImage` y valida estructura.
4. `backend/app/workflows/fibo2_edit/executor.py`: WS a ComfyUI, captura PNG en memoria, devuelve base64.
5. `backend/app/db/`: almacén en memoria (`task_id` → estado, resultado, error).
6. `backend/app/api/tasks.py`: `POST /api/tasks`, `GET /api/tasks/{id}`, `DELETE /api/tasks/{id}`.
7. `backend/app/api/images.py`: `POST /api/images/upload` (guarda base64 en memoria).

### Tareas
- [ ] Definir schema Pydantic de FIBO 2.0 Edit.
- [ ] Implementar builder de workflow JSON (nodos 1, 30+, 2/2b/2c/2d, 3, 4, 5, 6, 7, 8, 9, 10, 11, 15, 16).
- [ ] Implementar validador anti-disco (rechaza SaveImage/PreviewImage).
- [ ] Implementar executor WebSocket (captura binario del nodo 11, conversión a base64).
- [ ] Implementar db en memoria con TTL.
- [ ] Implementar endpoints REST de tareas e imágenes.
- [ ] Pruebas unitarias de builder y validador.

### Criterios de aceptación
- Se puede enviar un POST con parámetros FIBO 2.0 Edit y recibir un `task_id`.
- El executor devuelve la imagen generada como base64 (sin escribir en disco).
- Si se intenta incluir un nodo `SaveImage`/`PreviewImage`, el backend rechaza con error claro.
- El almacén en memoria guarda estados y resultados por `task_id`.

---

## 9. Sprint 3 — Frontend: Módulos de la SPA

**Objetivo:** Frontend completo con formularios, subida de imagen, ejecución y visualización de resultados.

### Entregables
1. `frontend/src/modules/image-upload/`: subida de imagen → base64 en memoria + preview.
2. `frontend/src/modules/fibo2-edit/`: formulario de parámetros (prompt, LoRAs, seed, pasos, scheduler, imágenes).
3. `frontend/src/modules/execution/`: lanzar ejecución, stream por WS, recibir imagen base64, mostrar resultado.
4. `frontend/src/modules/history/`: historial en memoria de tareas recientes.
5. `frontend/src/services/api.ts`: cliente REST; `frontend/src/services/ws.ts`: servicio WebSocket.
6. Páginas: Home, Ejecución, Historial, Ajustes.

### Tareas
- [ ] Implementar tipos TypeScript compartidos con backend.
- [ ] Implementar servicio API (axios/fetch) y servicio WS.
- [ ] Módulo `image-upload`: input file, `FileReader` a base64, preview, envío a `/api/images/upload`.
- [ ] Módulo `fibo2-edit`: formulario dinámico de parámetros FIBO 2.0 Edit.
- [ ] Módulo `execution`: botón ejecutar, conexión WS, progreso por nodo, visualización de imagen resultante.
- [ ] Módulo `history`: lista de tareas con thumbnails en base64.
- [ ] Navegación entre páginas (React Router o similar ligero).

### Criterios de aceptación
- Se puede subir una imagen y ver su preview sin que toque disco del worker.
- Se pueden ajustar parámetros FIBO 2.0 Edit y lanzar ejecución.
- La imagen generada se muestra en pantalla desde base64.
- El historial muestra tareas completadas con sus resultados.

---

## 10. Sprint 4 — Integración y prueba end-to-end

**Objetivo:** Conectar backend y frontend, probar el flujo completo con el workflow real FIBO 2.0 Edit del usuario.

### Entregables
1. Integración backend-frontend (CORS, variables de entorno, proxy).
2. Prueba E2E: subir imagen → ajustar parámetros → ejecutar → ver imagen resultado.
3. Manejo de errores: worker apagado, error en ComfyUI, timeout, cancelación.
4. Documentación básica de variables de entorno y cómo correr el proyecto.

### Tareas
- [ ] Configurar CORS y variables de entorno para desarrollo y producción.
- [ ] Conectar formulario frontend con endpoint `POST /api/tasks`.
- [ ] Conectar WS de ejecución con `executor.py` del backend.
- [ ] Probar con el script/workflow real de FIBO 2.0 Edit proporcionado por el usuario.
- [ ] Probar escenarios de error (ComfyUI apagado, imagen inválida, parámetros incorrectos).
- [ ] Agregar indicadores de carga y mensajes de error en UI.

### Criterios de aceptación
- Flujo E2E funcional: imagen en memoria → ejecución → imagen resultado en pantalla.
- No hay escritura en disco del worker en ningún punto del flujo.
- Errores se muestran amablemente al usuario (no crashea la app).

---

## 11. Sprint 5 — Pulido, escalabilidad y despliegue

**Objetivo:** Código limpio, escalable, listo para producción y fácil de extender con nuevos workflows.

### Entregables
1. Refactor final para asegurar separación estricta de módulos (ninguna importación cruzada innecesaria).
2. Pruebas unitarias y de integración críticas.
3. Dockerfile y `docker-compose.yml` para despliegue.
4. README con arquitectura, cómo añadir un nuevo workflow, y cómo configurar OCI (opcional).
5. Integración opcional con OCI/S3 para respaldar resultados en la nube (sin tocar disco local).

### Tareas
- [ ] Revisar imports y acoplamiento entre módulos.
- [ ] Agregar pruebas de `builder.py`, `validator.py`, `executor.py`.
- [ ] Crear Dockerfile para backend y frontend.
- [ ] Crear `docker-compose.yml`.
- [ ] Documentar cómo agregar un segundo workflow (ej. FIBO 2.0 Text-to-Image) sin tocar `fibo2_edit`.
- [ ] (Opcional) Conectar `storage/oci_client.py` para subir resultados a OCI desde memoria.

### Criterios de aceptación
- Se puede agregar un nuevo workflow creando una carpeta nueva bajo `workflows/` sin modificar código existente.
- Proyecto desplegable con Docker Compose.
- Código documentado y con pruebas críticas pasando.

---

## 8. Notas sobre el script del usuario

El script Kaggle → OCI que pasarás al final se usará como referencia para:
- Credenciales y configuración de OCI (`OCI_NAMESPACE`, `OCI_BUCKET`, claves, endpoint).
- Custom nodes de ComfyUI (`LoadImageRAM`, `SaveImageWebsocket`).
- Funciones de utilidad (`fix_seed`, `validate_no_disk_writes`, `purge_disk_dirs`).

En la nueva arquitectura estas funciones viven en el backend (Python) y se ejecutan sin depender de la cola S3/polling original, ya que la SPA se comunica directamente mediante REST/WebSocket.

---

**Estado del plan:** Listo para revisión.  
**Siguiente paso:** Confirmar el plan o solicitar ajustes antes de pasar a la implementación de los sprints.