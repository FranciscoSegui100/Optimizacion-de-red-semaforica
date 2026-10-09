"""
Demanda sintética del paper (sección "Diseño experimental"): modelo gravitacional
simple que pondera cada acceso según jerarquía vial.

    T_ij = K * (w_i * w_j) / d_ij

  - w_i: peso del acceso. San Martín (avenida principal) pesa más que las calles locales.
  - d_ij: distancia Manhattan entre los accesos i y j.
  - K se ajusta para que el total sea el volumen del escenario.

Escenarios (1 hora simulada cada uno):
  normal : ~450 veh/h
  pico   : ~1100 veh/h

Vehículo tipo: auto de pasajeros a nafta, clase de emisión HBEFA4 PC_petrol_Euro-6ab
(emisiones de CO2 estimadas con el modelo HBEFA integrado en SUMO).

Los vehículos se insertan con probabilidad por segundo, así que cada semilla
de SUMO (--seed) produce una realización distinta de la misma demanda.

Uso:    python demanda/generate_demand.py
Genera: demanda/normal.rou.xml, demanda/pico.rou.xml y escenarios/*.sumocfg
"""
import os
import itertools

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

ESCENARIOS = {"normal": 450, "pico": 1100}
DURACION = 3600  # s
CLASE_EMISION = "HBEFA4/PC_petrol_Euro-6ab"

# acceso: (intersección vecina, peso, x, y)
BORDES = {
    "N_SM": ("J_SM_RSP", 3.0, 0, 270),
    "S_SM": ("J_SM_ESP", 3.0, 0, -150),
    "N_TB": ("J_TB_RSP", 1.0, 120, 270),
    "S_TB": ("J_TB_ESP", 1.0, 120, -150),
    "W_RSP": ("J_SM_RSP", 1.0, -150, 120),
    "E_RSP": ("J_TB_RSP", 1.2, 270, 120),
    "W_ESP": ("J_SM_ESP", 1.0, -150, 0),
    "E_ESP": ("J_TB_ESP", 1.2, 270, 0),
}


def matriz_od(total_vph):
    pares = {}
    for i, j in itertools.permutations(BORDES, 2):
        _, wi, xi, yi = BORDES[i]
        _, wj, xj, yj = BORDES[j]
        pares[(i, j)] = wi * wj / (abs(xi - xj) + abs(yi - yj))
    k = total_vph / sum(pares.values())
    return {p: v * k for p, v in pares.items()}


def escribir_rutas(nombre, total_vph):
    od = matriz_od(total_vph)
    path = os.path.join(AQUI, f"{nombre}.rou.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<routes>\n')
        f.write(f'    <vType id="auto" vClass="passenger" accel="2.6" decel="4.5" sigma="0.5" '
                f'length="4.5" minGap="2.5" maxSpeed="16.67" emissionClass="{CLASE_EMISION}"/>\n')
        for (i, j), vph in sorted(od.items()):
            jin = BORDES[i][0]
            jout = BORDES[j][0]
            f.write(f'    <flow id="f_{i}_{j}" type="auto" begin="0" end="{DURACION}" '
                    f'probability="{vph / 3600.0:.5f}" from="{i}__{jin}" to="{jout}__{j}" '
                    f'departLane="best" departSpeed="max"/>\n')
        f.write("</routes>\n")
    print(f"{nombre}: {total_vph} veh/h -> {path}")


def escribir_cfg(nombre):
    os.makedirs(os.path.join(RAIZ, "escenarios"), exist_ok=True)
    path = os.path.join(RAIZ, "escenarios", f"{nombre}.sumocfg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="../red/subred4.net.xml"/>
        <route-files value="../demanda/{nombre}.rou.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="{DURACION + 600}"/>
    </time>
    <processing>
        <time-to-teleport value="300"/>
    </processing>
    <report>
        <no-step-log value="true"/>
        <no-warnings value="true"/>
    </report>
</configuration>
""")


if __name__ == "__main__":
    for nombre, vph in ESCENARIOS.items():
        escribir_rutas(nombre, vph)
        escribir_cfg(nombre)
