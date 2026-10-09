#!/bin/bash
# Instala y prueba el proyecto en Ubuntu (por ejemplo WSL en Windows).
# Uso, desde la carpeta del proyecto o desde cualquier lado:
#   bash instalar_wsl.sh
# Si el proyecto está en una carpeta de Windows (/mnt/c/...), se copia a ~/ para
# que corra rápido y los resultados de la prueba se copian de vuelta.
set -e
ORIGEN="$(cd "$(dirname "$0")" && pwd)"
if [[ "$ORIGEN" == /mnt/* ]]; then
  DEST="$HOME/$(basename "$ORIGEN")"
else
  DEST="$ORIGEN"
fi

echo "== 1/4 Paquetes del sistema (puede pedir tu contraseña de Ubuntu) =="
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip rsync

if [ "$DEST" != "$ORIGEN" ]; then
  echo "== 2/4 Copiando el proyecto a $DEST =="
  mkdir -p "$DEST"
  rsync -a --delete --exclude venv --exclude .git "$ORIGEN/" "$DEST/"
else
  echo "== 2/4 Usando el proyecto en $DEST =="
fi

echo "== 3/4 Entorno Python + SUMO =="
cd "$DEST"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt
python red/build_network.py
python demanda/generate_demand.py

echo "== 4/4 Prueba rápida =="
python src/run_all.py --rapido --out resultados_prueba
if [ "$DEST" != "$ORIGEN" ]; then
  cp -r resultados_prueba "$ORIGEN/" 2>/dev/null || true
fi

echo
echo "LISTO. Para trabajar después:"
echo "  cd $DEST && source venv/bin/activate"
echo "  python src/run_all.py      # experimento completo"
