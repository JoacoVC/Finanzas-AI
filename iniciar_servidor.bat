@echo off
chcp 65001 >nul
title Finanzas AI — Servidor Local
color 0B

echo ========================================================
echo    💸 FINANZAS AI — PANEL DE CONTROL LOCAL
echo ========================================================
echo.

cd /d "%~dp0"

REM 1. Verificar si existe el entorno virtual venv
if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXEC=venv\Scripts\python.exe"
    echo [OK] Entorno virtual detectado: venv
) else (
    set "PYTHON_EXEC=python"
    echo [INFO] Usando Python del sistema...
)

REM 2. Verificar que el archivo .env exista
if not exist ".env" (
    echo [ADVERTENCIA] No se encontro el archivo .env. Asegurate de configurar tus credenciales.
)

echo [INFO] Iniciando servidor FastAPI en http://127.0.0.1:8000 ...
echo [INFO] Presiona CTRL + C para detener el servidor en cualquier momento.
echo.

REM 3. Abrir automáticamente el navegador tras 2 segundos
start "" "http://127.0.0.1:8000"

REM 4. Lanzar uvicorn con recarga en caliente
"%PYTHON_EXEC%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================================
    echo  [ERROR] El servidor se detuvo con errores.
    echo ========================================================
    pause
)
