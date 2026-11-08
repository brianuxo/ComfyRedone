@echo off
cd /d "%~dp0"

echo ========================================
echo   ComfyUI SPA - FIBO 2.0 Edit
echo   Levantando Backend y Frontend
echo ========================================
echo.

REM Verificar que exista el backend
if not exist "backend\app\main.py" (
    echo [ERROR] No se encontro backend/app/main.py
    pause
    exit /b 1
)

REM Verificar que exista el frontend
if not exist "frontend\package.json" (
    echo [ERROR] No se encontro frontend/package.json
    pause
    exit /b 1
)

REM Verificar que exista .env en backend
if not exist "backend\.env" (
    echo [WARN] No se encontro backend/.env
    echo [INFO] Copia backend/.env.example a backend/.env y rellena tus credenciales
    echo.
)

echo [1/3] Iniciando Backend (FastAPI en puerto 8000)...
start "Backend-ComfySPA" /D "backend" python run_windows.py

echo [2/3] Iniciando Frontend (Vite en puerto 5173)...
start "Frontend-ComfySPA" /D "frontend" cmd /c "npm run dev"

echo [3/3] Esperando a que los servicios esten listos...
timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo   SERVICIOS EN LINEA
echo   - Backend:  http://127.0.0.1:8000
echo   - Frontend: http://localhost:5173
echo   - Health:   http://127.0.0.1:8000/api/health
echo ========================================
echo.
echo Presione CUALQUIER TECLA para detener los servicios y cerrar esta ventana.
echo ========================================
pause >nul

echo.
echo Deteniendo Backend...
taskkill /FI "WINDOWTITLE eq Backend-ComfySPA" /F >nul 2>&1

echo Deteniendo Frontend...
taskkill /FI "WINDOWTITLE eq Frontend-ComfySPA" /F >nul 2>&1

echo.
echo Servicios detenidos. Cerrando ventana...
exit /b 0