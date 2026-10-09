"""
Corre el experimento completo del paper sobre la red de 4 intersecciones:

  1. Entrena el sistema descentralizado en cada escenario de demanda
     (normal y pico): 120 episodios de 1 hora simulada.
  2. Evalúa la línea base de tiempo fijo y el sistema descentralizado sobre las
     mismas semillas de evaluación (distintas de las de entrenamiento).
  3. Genera la Tabla 1 y la Figura 1 (src/analizar.py).

Uso:
  python src/run_all.py              # experimento completo
  python src/run_all.py --rapido     # prueba rápida (~1 min)
"""
import argparse
import os
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
PY = sys.executable
EXP = os.path.join(AQUI, "experimento.py")


def correr(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return f"ERROR {' '.join(cmd)}\n{r.stderr[-2000:]}"
    return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "ok"


def en_paralelo(cmds, procesos, titulo):
    print(f"\n== {titulo}: {len(cmds)} corridas en {procesos} procesos ==", flush=True)
    errores = 0
    with ProcessPoolExecutor(max_workers=procesos) as ex:
        futs = {ex.submit(correr, c): c for c in cmds}
        for i, f in enumerate(as_completed(futs), 1):
            res = f.result()
            if res.startswith("ERROR"):
                errores += 1
                print(res, flush=True)
            else:
                print(f"[{i}/{len(cmds)}] {res[:160]}", flush=True)
    if errores:
        sys.exit(f"{errores} corridas fallaron")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--procesos", type=int, default=os.cpu_count())
    p.add_argument("--episodios", type=int, default=120)
    p.add_argument("--seeds-train", type=int, nargs="+", default=[1])
    p.add_argument("--seeds-eval", type=int, nargs="+", default=list(range(101, 111)))
    p.add_argument("--escenarios", nargs="+", default=["normal", "pico"])
    p.add_argument("--out", default=os.path.join(RAIZ, "resultados"))
    p.add_argument("--rapido", action="store_true")
    a = p.parse_args()
    if a.rapido:
        a.episodios, a.seeds_eval = 5, [101, 102]

    if os.path.exists(a.out):
        shutil.rmtree(a.out)

    cmds = [[PY, EXP, "train", "--escenario", e, "--seed", str(s),
             "--episodios", str(a.episodios), "--out", a.out]
            for e in a.escenarios for s in a.seeds_train]
    en_paralelo(cmds, a.procesos, "Entrenamiento")

    cmds = []
    for e in a.escenarios:
        for s in a.seeds_eval:
            cmds.append([PY, EXP, "baseline", "--escenario", e, "--seed", str(s), "--out", a.out])
            for st in a.seeds_train:
                cmds.append([PY, EXP, "eval", "--escenario", e, "--seed", str(s), "--out", a.out,
                             "--modelo", os.path.join(a.out, "modelos", f"{e}_s{st}.pkl")])
    en_paralelo(cmds, a.procesos, "Evaluación")

    subprocess.run([PY, os.path.join(AQUI, "analizar.py"), "--out", a.out], check=True)


if __name__ == "__main__":
    main()
