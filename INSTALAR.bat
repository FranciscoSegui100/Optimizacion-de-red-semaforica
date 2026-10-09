@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Instalador - Semaforos 4 intersecciones

echo ============================================================
echo   Instalador - Semaforos IA (subred de 4 intersecciones)
echo ============================================================
echo.

REM ---------- 1) Buscar Python 3.10+ ----------
set "PY="
for %%V in (3.13 3.12 3.11 3.10) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys; assert sys.version_info>=(3,10)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)

if not defined PY (
  echo [1/5] No encontre Python. Lo instalo con winget...
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  ) else (
    echo.
    echo  No pude instalar Python automaticamente.
    echo  Instalalo a mano desde https://www.python.org/downloads/
    echo  ^(tilda "Add Python to PATH"^) y volve a ejecutar este archivo.
    pause
    exit /b 1
  )
) else (
  echo [1/5] Python encontrado: %PY%
)

REM ---------- 2) Entorno virtual ----------
echo.
echo [2/5] Creando entorno virtual en .\venv ...
if not exist venv\Scripts\python.exe (
  %PY% -m venv venv || goto :error
)
call venv\Scripts\activate.bat || goto :error
python -m pip install --upgrade pip --quiet

REM ---------- 3) Dependencias ----------
echo.
echo [3/5] Instalando SUMO y librerias (puede tardar unos minutos, son ~300 MB)...
pip install "eclipse-sumo>=1.20" "traci>=1.20" "sumolib>=1.20" numpy pandas matplotlib || goto :error
echo     Intentando instalar libsumo (acelera ~10x; si falla se usa traci)...
pip install "libsumo>=1.20" --quiet || echo     libsumo no disponible, se usara traci.

for /f "delims=" %%H in ('python -c "import sumo; print(sumo.SUMO_HOME)"') do set "SUMO_HOME=%%H"
echo     SUMO_HOME=%SUMO_HOME%

REM ---------- 4) Generar red y demanda ----------
echo.
echo [4/5] Generando la red de 4 intersecciones y la demanda...
python red\build_network.py || goto :error
python demanda\generate_demand.py || goto :error

REM ---------- 5) Prueba ----------
echo.
echo [5/5] Simulacion de prueba (escenario pico, tiempo fijo)...
python src\experimento.py baseline --escenario pico --seed 1 --out "%TEMP%\prueba_semaforos" || goto :error

echo.
echo ============================================================
echo   LISTO. Todo instalado y funcionando.
echo.
echo   Para correr el experimento completo: doble clic en CORRER.bat
echo   Los resultados ya calculados estan en la carpeta "resultados"
echo ============================================================
pause
exit /b 0

:error
echo.
echo ************************************************************
echo   Algo fallo. Saca una captura de esta ventana y pasamela.
echo ************************************************************
pause
exit /b 1
