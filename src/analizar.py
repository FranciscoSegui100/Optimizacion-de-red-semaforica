"""
Genera la Tabla 1 y la Figura 1 del paper a partir de las corridas de evaluación.

  resultados/tabla1.md / tabla1.tex   Tabla 1: tiempo fijo vs. sistema descentralizado
                                      (Normal / Pico), media sobre las semillas de evaluación
  resultados/figura1.png              Figura 1: espera promedio y CO2 total
  resultados/curvas_aprendizaje.png   Evolución del entrenamiento
  resultados/resumen.csv              Media y desvío de cada métrica
  resultados/evaluacion.csv           Todas las corridas

Uso: python src/analizar.py --out resultados
"""
import argparse
import glob
import os

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FILAS = [
    ("espera_prom_s", "Espera promedio (s)", 1),
    ("flujo_veh_h", "Flujo (veh/hora)", 0),
    ("viajes_completos", "Viajes completados", 0),
    ("co2_total_kg", "CO2 total (kg)", 1),
    ("co2_por_viaje_g", "CO2 por vehículo (g)", 1),
]
CTRL = [("tiempo_fijo", "Fijo"), ("descentralizado_rl", "RL")]
ESC = [("normal", "Normal"), ("pico", "Pico")]


def fmt(x, dec):
    return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def cargar(out):
    archivos = sorted(glob.glob(os.path.join(out, "eval", "*.csv")))
    if archivos:
        df = pd.concat([pd.read_csv(f) for f in archivos], ignore_index=True)
        df.to_csv(os.path.join(out, "evaluacion.csv"), index=False)
        return df
    path = os.path.join(out, "evaluacion.csv")
    if os.path.exists(path):
        return pd.read_csv(path)
    raise SystemExit(f"No hay resultados en {out}/")


def tablas(df, out):
    media = df.groupby(["escenario", "controlador"]).mean(numeric_only=True)
    desv = df.groupby(["escenario", "controlador"]).std(numeric_only=True)
    n = df.groupby(["escenario", "controlador"]).size()

    filas = []
    for m, _, _ in FILAS:
        for e, _ in ESC:
            for c, _ in CTRL:
                filas.append({"metrica": m, "escenario": e, "controlador": c,
                              "media": media.loc[(e, c), m], "desvio": desv.loc[(e, c), m],
                              "n": n.loc[(e, c)]})
    pd.DataFrame(filas).round(2).to_csv(os.path.join(out, "resumen.csv"), index=False)

    md = ["| Métrica | Normal Fijo | Normal RL | Pico Fijo | Pico RL |", "|---|---|---|---|---|"]
    tex = [r"\begin{table}[ht]", r"\centering",
           r"\caption{Comparación entre el sistema de tiempo fijo y el sistema descentralizado, "
           r"sobre la red de 4 intersecciones, en dos escenarios de demanda (1 hora simulada cada uno).}",
           r"\label{tab:resultados}", r"\begin{tabular}{lrrrr}", r"\hline",
           r" & \multicolumn{2}{c}{Normal} & \multicolumn{2}{c}{Pico} \\",
           r"Métrica & Fijo & RL & Fijo & RL \\", r"\hline"]
    for m, nombre, dec in FILAS:
        vals = [fmt(media.loc[(e, c), m], dec) for e, _ in ESC for c, _ in CTRL]
        md.append(f"| {nombre} | " + " | ".join(vals) + " |")
        tex.append(nombre.replace("CO2", r"CO$_2$") + " & " + " & ".join(vals) + r" \\")
    tex += [r"\hline", r"\end{tabular}", r"\end{table}"]

    var = ["", "**Variación del sistema descentralizado respecto de tiempo fijo:**", ""]
    for e, en in ESC:
        partes = []
        for m, nombre, _ in FILAS:
            f, r = media.loc[(e, "tiempo_fijo"), m], media.loc[(e, "descentralizado_rl"), m]
            partes.append(f"{nombre}: {100 * (r - f) / f:+.1f} %".replace(".", ","))
        var.append(f"- {en}: " + "; ".join(partes))
    nota = (f"\nValores: media sobre {int(n.min())} semillas de evaluación por escenario. "
            "Vehículo tipo: auto de pasajeros a nafta (HBEFA4 PC_petrol_Euro-6ab). "
            "Línea base de tiempo fijo: ciclo de 90 s (42 s de verde + 3 s de amarillo por fase).")
    with open(os.path.join(out, "tabla1.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md + var) + "\n" + nota + "\n")
    with open(os.path.join(out, "tabla1.tex"), "w", encoding="utf-8") as f:
        f.write("\n".join(tex) + "\n")
    print("\n".join(md + var) + nota)
    return media, desv


def figura1(media, desv, out):
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
    colores = {"tiempo_fijo": "#8a8f98", "descentralizado_rl": "#2f6fb2"}
    nombres = {"tiempo_fijo": "Tiempo fijo", "descentralizado_rl": "Descentralizado (RL)"}
    for ax, (m, titulo) in zip(axes, [("espera_prom_s", "Espera promedio (s)"),
                                      ("co2_total_kg", "CO$_2$ total (kg)")]):
        for i, (c, _) in enumerate(CTRL):
            xs = [k + (i - 0.5) * 0.38 for k in range(len(ESC))]
            ys = [media.loc[(e, c), m] for e, _ in ESC]
            es = [desv.loc[(e, c), m] for e, _ in ESC]
            ax.bar(xs, ys, 0.38, yerr=es, capsize=3, color=colores[c], label=nombres[c])
        ax.set_xticks(range(len(ESC)))
        ax.set_xticklabels([en for _, en in ESC])
        ax.set_title(titulo)
        ax.grid(axis="y", alpha=0.3)
        ax.set_axisbelow(True)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "figura1.png"), dpi=200)
    plt.close(fig)


def curvas(out):
    archivos = sorted(glob.glob(os.path.join(out, "curvas", "*.csv")))
    if not archivos:
        return
    fig, ax = plt.subplots(figsize=(6, 3.8))
    for a in archivos:
        d = pd.read_csv(a)
        ax.plot(d["episodio"], d["espera_prom_s"].rolling(5, min_periods=1).mean(),
                label=os.path.basename(a).replace(".csv", "").replace("_s", " (semilla ") + ")")
    ax.set_xlabel("Episodio")
    ax.set_ylabel("Espera promedio (s, media móvil 5)")
    ax.set_title("Entrenamiento del sistema descentralizado")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "curvas_aprendizaje.png"), dpi=150)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="resultados")
    a = p.parse_args()
    df = cargar(a.out)
    media, desv = tablas(df, a.out)
    figura1(media, desv, a.out)
    curvas(a.out)
    print(f"\nListo: {a.out}/tabla1.md, tabla1.tex, figura1.png, curvas_aprendizaje.png")


if __name__ == "__main__":
    main()
