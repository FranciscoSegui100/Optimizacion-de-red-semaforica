"""
Construye la red SUMO de 4 intersecciones del centro de Luján de Cuyo (Mendoza),
tal como se describe en el paper (sección "Entorno de simulación"):

  Grilla que reproduce la disposición de cuadras y calles de la zona, con la
  geometría reconstruida manualmente (sin importación automática desde OSM).

Intersecciones semaforizadas (grilla 2x2, cuadras de 120 m):
    J_SM_RSP : San Martín & Roque Sáenz Peña
    J_SM_ESP : San Martín & España
    J_TB_RSP : Taboada    & Roque Sáenz Peña
    J_TB_ESP : Taboada    & España

Cada intersección tiene 4 aproximaciones: eje vertical (San Martín / Taboada,
Norte-Sur) y eje horizontal (Roque Sáenz Peña / España, Este-Oeste).
San Martín es la avenida principal (2 carriles por sentido, 50 km/h); las demás
son calles locales (1 carril por sentido, 40 km/h).

Línea base de tiempo fijo (paper, Tabla 1): ciclo por defecto de la herramienta
de compilación de la red, 90 s = 2 fases x (42 s de verde + 3 s de amarillo).

Uso:    python red/build_network.py
Genera: red/subred4.net.xml
"""
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
CUADRA = 120.0      # largo de cuadra (m)
ACCESO = 150.0      # largo de los tramos de entrada/salida de la red (m)

VERDE = 42          # s de verde por fase   } ciclo de 90 s con 2 fases
AMARILLO = 3        # s de amarillo por fase}

# Coordenadas: x crece hacia el Este, y hacia el Norte.
X_SM, X_TB = 0.0, CUADRA
Y_ESP, Y_RSP = 0.0, CUADRA

NODOS = {
    "J_SM_RSP": (X_SM, Y_RSP, "traffic_light"),
    "J_SM_ESP": (X_SM, Y_ESP, "traffic_light"),
    "J_TB_RSP": (X_TB, Y_RSP, "traffic_light"),
    "J_TB_ESP": (X_TB, Y_ESP, "traffic_light"),
    "N_SM": (X_SM, Y_RSP + ACCESO, "priority"),
    "S_SM": (X_SM, Y_ESP - ACCESO, "priority"),
    "N_TB": (X_TB, Y_RSP + ACCESO, "priority"),
    "S_TB": (X_TB, Y_ESP - ACCESO, "priority"),
    "W_RSP": (X_SM - ACCESO, Y_RSP, "priority"),
    "E_RSP": (X_TB + ACCESO, Y_RSP, "priority"),
    "W_ESP": (X_SM - ACCESO, Y_ESP, "priority"),
    "E_ESP": (X_TB + ACCESO, Y_ESP, "priority"),
}

# tipos de calle: (carriles por sentido, velocidad m/s, prioridad)
PRINCIPAL = (2, 13.89, 3)   # 50 km/h
LOCAL = (1, 11.11, 2)       # 40 km/h

TRAMOS = [
    ("San Martín", "N_SM", "J_SM_RSP", PRINCIPAL),
    ("San Martín", "J_SM_RSP", "J_SM_ESP", PRINCIPAL),
    ("San Martín", "J_SM_ESP", "S_SM", PRINCIPAL),
    ("Taboada", "N_TB", "J_TB_RSP", LOCAL),
    ("Taboada", "J_TB_RSP", "J_TB_ESP", LOCAL),
    ("Taboada", "J_TB_ESP", "S_TB", LOCAL),
    ("Roque Sáenz Peña", "W_RSP", "J_SM_RSP", LOCAL),
    ("Roque Sáenz Peña", "J_SM_RSP", "J_TB_RSP", LOCAL),
    ("Roque Sáenz Peña", "J_TB_RSP", "E_RSP", LOCAL),
    ("España", "W_ESP", "J_SM_ESP", LOCAL),
    ("España", "J_SM_ESP", "J_TB_ESP", LOCAL),
    ("España", "J_TB_ESP", "E_ESP", LOCAL),
]


def escribir_nodos(path):
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<nodes>\n')
        for nid, (x, y, tipo) in NODOS.items():
            f.write(f'    <node id="{nid}" x="{x:.2f}" y="{y:.2f}" type="{tipo}"/>\n')
        f.write("</nodes>\n")


def escribir_aristas(path):
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<edges>\n')
        for nombre, a, b, (lanes, speed, prio) in TRAMOS:
            for (u, v) in ((a, b), (b, a)):
                f.write(f'    <edge id="{u}__{v}" from="{u}" to="{v}" numLanes="{lanes}" '
                        f'speed="{speed}" priority="{prio}" name="{nombre}"/>\n')
        f.write("</edges>\n")


def verificar(net_path):
    import sumolib
    net = sumolib.net.readNet(net_path, withPrograms=True)
    for t in net.getTrafficLights():
        fases = t.getPrograms()["0"].getPhases()
        ciclo = sum(p.duration for p in fases)
        print(f"  {t.getID()}: {len(fases)} fases, ciclo {ciclo:.0f} s "
              f"({' / '.join(f'{p.duration:.0f}' for p in fases)})")
        if ciclo != 2 * (VERDE + AMARILLO):
            sys.exit(f"Ciclo inesperado en {t.getID()}: {ciclo} s")


def main():
    nod = os.path.join(AQUI, "subred4.nod.xml")
    edg = os.path.join(AQUI, "subred4.edg.xml")
    net = os.path.join(AQUI, "subred4.net.xml")
    escribir_nodos(nod)
    escribir_aristas(edg)
    cmd = [
        "netconvert", "--node-files", nod, "--edge-files", edg, "--output-file", net,
        "--no-turnarounds", "true",
        "--tls.default-type", "static",
        "--tls.green.time", str(VERDE),
        "--tls.yellow.time", str(AMARILLO),
        "--junctions.join", "false",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        sys.exit(r.returncode)
    print(f"OK -> {net}")
    verificar(net)


if __name__ == "__main__":
    main()
