"""
Punto de entrada único de los experimentos (paper: sistema de tiempo fijo
vs. sistema descentralizado, en los escenarios de demanda normal y pico).

  # línea base de tiempo fijo (ciclo de 90 s) para un escenario y una semilla
  python src/experimento.py baseline --escenario pico --seed 101

  # entrenar el sistema descentralizado (120 episodios de 1 hora simulada)
  python src/experimento.py train --escenario pico --episodios 120 --seed 1

  # evaluar un modelo entrenado (política greedy, sin exploración)
  python src/experimento.py eval --escenario pico --modelo resultados/modelos/pico_s1.pkl --seed 101
"""
import argparse
import os
import random
import sys
import time
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import (traci, RAIZ, HORIZONTE, iniciar_sumo, AcumuladorCO2,  # noqa: E402
                   metricas, guardar_fila_csv, guardar_json)
from agente import crear_agentes, guardar_qtables, cargar_qtables  # noqa: E402

def resolver_cfg(args):
    if args.cfg:
        return os.path.abspath(args.cfg), os.path.splitext(os.path.basename(args.cfg))[0]
    return os.path.join(RAIZ, "escenarios", f"{args.escenario}.sumocfg"), args.escenario


def simular(cfg, seed, agentes_fn=None, epsilon=0.0, entrenar=False,
            net_override=None, modelo=None, max_t=HORIZONTE + 600):
    """Corre un episodio completo. Si agentes_fn es None, los semáforos usan
    el programa del .net.xml (baseline). Devuelve (métricas, agentes)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".xml", delete=False)
    tmp.close()
    iniciar_sumo(cfg, seed, tmp.name, net_override=net_override)
    try:
        agentes = agentes_fn() if agentes_fn else None
        if agentes and modelo:
            cargar_qtables(agentes, modelo)
        co2 = AcumuladorCO2()
        insertados = 0
        recompensa_total = 0.0
        t = 0
        while t < max_t:
            traci.simulationStep()
            t += 1
            insertados += traci.simulation.getDepartedNumber()
            co2.paso()
            if agentes:
                for ag in agentes.values():
                    r = ag.paso(epsilon, entrenar)
                    if r is not None:
                        recompensa_total += r
            if t >= HORIZONTE and traci.simulation.getMinExpectedNumber() == 0:
                break
    finally:
        traci.close()
    m = metricas(tmp.name, co2.total_mg, insertados)
    m["t_fin_sim"] = t
    if agentes:
        m["recompensa"] = round(recompensa_total, 1)
    os.unlink(tmp.name)
    return m, agentes


# ---------------------------------------------------------------- comandos
def cmd_baseline(args):
    cfg, nombre = resolver_cfg(args)
    t0 = time.time()
    m, _ = simular(cfg, args.seed)
    fila = {"escenario": nombre, "controlador": "tiempo_fijo",
            "seed": args.seed, **m, "seg": round(time.time() - t0, 1)}
    print(fila)
    guardar_eval(args.out, fila, f"{nombre}_tiempo_fijo_seed{args.seed}")


def guardar_eval(out, fila, clave):
    """Un CSV por corrida: evita que procesos paralelos (o jobs de Slurm)
    escriban al mismo archivo a la vez. analizar.py los junta."""
    path = os.path.join(out, "eval", f"{clave}.csv")
    if os.path.exists(path):
        os.remove(path)
    guardar_fila_csv(path, fila)


def cmd_train(args):
    cfg, nombre = resolver_cfg(args)
    random.seed(args.seed)
    np.random.seed(args.seed)
    os.makedirs(os.path.join(args.out, "modelos"), exist_ok=True)
    modelo = os.path.join(args.out, "modelos", f"{nombre}_s{args.seed}.pkl")
    curva = os.path.join(args.out, "curvas", f"{nombre}_s{args.seed}.csv")
    if os.path.exists(curva):
        os.remove(curva)

    estado = {"agentes": None}

    def fabrica():
        # Se crean una sola vez y se reutilizan entre episodios (mismas Q-tables)
        if estado["agentes"] is None:
            estado["agentes"] = crear_agentes(alpha=args.alpha, gamma=args.gamma)
        else:
            for ag in estado["agentes"].values():
                ag.reset_episodio()
        return estado["agentes"]

    for ep in range(args.episodios):
        # epsilon decae linealmente de 1.0 a 0.05 en el 80% de los episodios
        eps = max(0.05, 1.0 - ep / max(1, 0.8 * args.episodios))
        # cada episodio usa una realización distinta de la demanda
        seed_ep = args.seed * 1000 + ep
        t0 = time.time()
        m, _ = simular(cfg, seed_ep, agentes_fn=fabrica, epsilon=eps, entrenar=True)
        fila = {"episodio": ep, "epsilon": round(eps, 3), **m,
                "seg": round(time.time() - t0, 1)}
        print(fila, flush=True)
        guardar_fila_csv(curva, fila)
        if (ep + 1) % 10 == 0 or ep == args.episodios - 1:
            guardar_qtables(estado["agentes"], modelo)
    n_estados = {k: len(a.Q) for k, a in estado["agentes"].items()}
    guardar_json(os.path.join(args.out, "modelos", f"{nombre}_s{args.seed}.json"),
                 {"episodios": args.episodios, "alpha": args.alpha,
                  "gamma": args.gamma, "estados_visitados": n_estados})
    print(f"Modelo guardado en {modelo}")


def cmd_eval(args):
    cfg, nombre = resolver_cfg(args)
    random.seed(args.seed)
    t0 = time.time()
    m, _ = simular(cfg, args.seed, agentes_fn=lambda: crear_agentes(),
                   epsilon=0.0, entrenar=False, modelo=args.modelo)
    fila = {"escenario": nombre, "controlador": "descentralizado_rl",
            "seed": args.seed, **m, "seg": round(time.time() - t0, 1),
            "modelo": os.path.basename(args.modelo)}
    print(fila)
    mod = os.path.splitext(os.path.basename(args.modelo))[0]
    guardar_eval(args.out, fila, f"{nombre}_rl_{mod}_seed{args.seed}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for nombre in ("baseline", "train", "eval"):
        sp = sub.add_parser(nombre)
        g = sp.add_mutually_exclusive_group(required=True)
        g.add_argument("--escenario", choices=["normal", "pico"])
        g.add_argument("--cfg", help="ruta a un .sumocfg propio (otra red)")
        sp.add_argument("--seed", type=int, default=1)
        sp.add_argument("--out", default=os.path.join(RAIZ, "resultados"))
    sub.choices["train"].add_argument("--episodios", type=int, default=120)
    sub.choices["train"].add_argument("--alpha", type=float, default=0.1)
    sub.choices["train"].add_argument("--gamma", type=float, default=0.9)
    sub.choices["eval"].add_argument("--modelo", required=True)
    args = p.parse_args()
    {"baseline": cmd_baseline, "train": cmd_train, "eval": cmd_eval}[args.cmd](args)


if __name__ == "__main__":
    main()
