"""
Utilidades comunes: arranque de SUMO, métricas y escritura de resultados.

Variables dependientes del paper (Tabla 1):
  - espera_prom_s      : tiempo promedio de espera por vehículo (s)
  - flujo_veh_h        : flujo vehicular por hora = viajes completados en el
                         escenario de 1 hora simulada
  - viajes_completos   : viajes que llegaron a destino
  - co2_total_kg       : emisiones totales de CO2 (modelo HBEFA de SUMO)
  - co2_por_viaje_g    : CO2 normalizado por vehículo (total / viajes completados)
"""
import os
import sys
import json
import csv
import xml.etree.ElementTree as ET

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# libsumo es ~10x más rápido que traci (mismo API, sin socket). Se usa por
# defecto si está instalado (pip install libsumo). Para forzar traci clásico
# (por ejemplo para ver la simulación en sumo-gui):  USE_LIBSUMO=0
USANDO_LIBSUMO = False
if os.environ.get("USE_LIBSUMO", "1") != "0":
    try:
        import libsumo as traci  # noqa: F401
        USANDO_LIBSUMO = True
    except ImportError:
        import traci  # noqa: F401
else:
    import traci  # noqa: F401

HORIZONTE = 3600  # s de demanda (la sim corre hasta vaciar la red o +600 s)


def iniciar_sumo(cfg, seed, tripinfo_path, net_override=None, gui=False):
    binario = "sumo-gui" if (gui and not USANDO_LIBSUMO) else "sumo"
    cmd = [
        binario, "-c", cfg,
        "--seed", str(seed),
        "--tripinfo-output", tripinfo_path,
        "--device.emissions.probability", "1",
        "--no-step-log", "true",
        "--no-warnings", "true",
        "--time-to-teleport", "300",
    ]
    if net_override:
        cmd += ["--net-file", net_override]
    traci.start(cmd)


class AcumuladorCO2:
    """Suma el CO2 de toda la red paso a paso (incluye autos que no terminan)."""

    def __init__(self):
        self.edges = [e for e in traci.edge.getIDList() if not e.startswith(":")]
        self.total_mg = 0.0

    def paso(self, dt=1.0):
        # getCO2Emission devuelve mg/s del último paso en la arista
        self.total_mg += sum(traci.edge.getCO2Emission(e) for e in self.edges) * dt


def leer_tripinfo(path):
    esperas, llegadas = [], []
    for ev, el in ET.iterparse(path, events=("end",)):
        if el.tag == "tripinfo":
            esperas.append(float(el.get("waitingTime", 0)))
            llegadas.append(float(el.get("arrival", 0)))
            el.clear()
    return esperas, llegadas


def metricas(tripinfo_path, co2_mg, insertados, horizonte_s=HORIZONTE):
    esperas, _ = leer_tripinfo(tripinfo_path)
    n = len(esperas)
    return {
        "espera_prom_s": round(sum(esperas) / n, 2) if n else None,
        "flujo_veh_h": round(n / (horizonte_s / 3600.0), 1),
        "viajes_completos": n,
        "co2_total_kg": round(co2_mg / 1e6, 3),
        "co2_por_viaje_g": round(co2_mg / 1e3 / n, 1) if n else None,
        "insertados": insertados,
    }


def guardar_fila_csv(path, fila):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    nuevo = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fila.keys()))
        if nuevo:
            w.writeheader()
        w.writerow(fila)


def guardar_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
