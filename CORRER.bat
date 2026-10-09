@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Experimento - Semaforos 4 intersecciones

if not exist venv\Scripts\activate.bat (
  echo Primero ejecuta INSTALAR.bat
  pause
  exit /b 1
)
call venv\Scripts\activate.bat

echo Elegi que correr:
echo   1 = Prueba rapida (~1-2 minutos)
echo   2 = Experimento completo (150 episodios x 3 semillas x 2 escenarios; ~20-40 min)
echo.
set /p OPC="Opcion (1 o 2): "

if "%OPC%"=="1" (
  python src\run_all.py --rapido --out resultados_prueba
  set "CARPETA=resultados_prueba"
) else (
  echo ATENCION: esto reemplaza la carpeta "resultados".
  pause
  python src\run_all.py
  set "CARPETA=resultados"
)

echo.
echo Listo. Abriendo la carpeta de resultados...
start "" "%CARPETA%"
pause
