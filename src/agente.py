"""
Sistema de control semafórico descentralizado, según la formulación del paper
(secciones "Arquitectura propuesta" y "Formulación del agente descentralizado").

Arquitectura de 4 capas, replicada en cada intersección (independiente de las demás):
  1. Captura        : lee el estado de la red desde la simulación (TraCI).
  2. Procesamiento  : estima las variables de decisión: vehículos detenidos por
                      carril, ocupación de los carriles de salida y tiempo
                      transcurrido en la fase activa.
  3. Decisión       : agente Q-learning tabular que decide mantener o avanzar la fase.
  4. Ejecución      : aplica la decisión modificando la fase activa del semáforo.

Agente (uno por intersección, 4 en total):
  Estado     : 3 variables discretas
                 - cola en el eje vertical   (4 bins)
                 - cola en el eje horizontal (4 bins)
                 - fase actual
  Acción     : 2 alternativas -> 0 = mantener la fase, 1 = avanzar a la siguiente
  Decisión   : cada 5 s, con un verde mínimo de 10 s
  Recompensa : negativo de la cola total en sus 4 aproximaciones, computada sobre
               la totalidad de los accesos (no solo sobre la fase verde activa).
  Al avanzar de fase se intercala un amarillo de 3 s.
"""
import random
import pickle
from collections import defaultdict

import numpy as np

from comun import traci

VERDE_MINIMO = 10   # s
INTERVALO = 5       # s entre decisiones
AMARILLO = 3        # s
BINS_COLA = (0, 3, 7)   # 4 bins: 0 | 1-3 | 4-7 | 8+  (vehículos detenidos)
MANTENER, AVANZAR = 0, 1
N_ACCIONES = 2


def discretizar(n):
    for i, corte in enumerate(BINS_COLA):
        if n <= corte:
            return i
    return len(BINS_COLA)


class Interseccion:
    """Las 4 capas de una intersección + su agente Q-learning."""

    def __init__(self, tls_id, alpha=0.1, gamma=0.9):
        self.id = tls_id
        self.alpha, self.gamma = alpha, gamma
        logica = traci.trafficlight.getAllProgramLogics(tls_id)[0]
        self.fases = [p.state for p in logica.phases
                      if ("G" in p.state or "g" in p.state) and "y" not in p.state]

        # carriles de entrada clasificados por eje según la dirección de la calle
        entrada = list(dict.fromkeys(traci.trafficlight.getControlledLanes(tls_id)))
        self.carriles_v, self.carriles_h = [], []
        for c in entrada:
            (x0, y0), (x1, y1) = traci.lane.getShape(c)[0], traci.lane.getShape(c)[-1]
            (self.carriles_v if abs(y1 - y0) >= abs(x1 - x0) else self.carriles_h).append(c)
        self.carriles_entrada = entrada
        self.carriles_salida = list(dict.fromkeys(
            l[0][1] for l in traci.trafficlight.getControlledLinks(tls_id) if l))

        self.Q = defaultdict(lambda: np.zeros(N_ACCIONES))
        self.reset_episodio()

    # ---------------------------------------------------------- ciclo de vida
    def reset_episodio(self):
        self.fase = 0
        self.t_en_fase = 0
        self.en_amarillo = 0
        self.s_prev, self.a_prev = None, None
        traci.trafficlight.setRedYellowGreenState(self.id, self.fases[0])

    # ------------------------------------------------- capas 1 y 2: captura + procesamiento
    def procesar(self):
        detenidos = {c: traci.lane.getLastStepHaltingNumber(c) for c in self.carriles_entrada}
        ocupacion_salida = {c: traci.lane.getLastStepOccupancy(c) for c in self.carriles_salida}
        return {
            "detenidos": detenidos,
            "cola_v": sum(detenidos[c] for c in self.carriles_v),
            "cola_h": sum(detenidos[c] for c in self.carriles_h),
            "ocupacion_salida": ocupacion_salida,
            "t_en_fase": self.t_en_fase,
        }

    def estado(self, v):
        return (discretizar(v["cola_v"]), discretizar(v["cola_h"]), self.fase)

    @staticmethod
    def recompensa(v):
        return -float(sum(v["detenidos"].values()))

    # ------------------------------------------------------------ capa 3: decisión
    def decidir(self, s, epsilon):
        if random.random() < epsilon:
            return random.randrange(N_ACCIONES)
        q = self.Q[s]
        return int(random.choice(np.flatnonzero(q == q.max())))

    # ------------------------------------------------------------ capa 4: ejecución
    def ejecutar(self, accion):
        if accion == AVANZAR:
            actual = self.fases[self.fase]
            siguiente = (self.fase + 1) % len(self.fases)
            nueva = self.fases[siguiente]
            amarillo = "".join("y" if (a in "Gg" and b not in "Gg") else a
                               for a, b in zip(actual, nueva))
            traci.trafficlight.setRedYellowGreenState(self.id, amarillo)
            self.en_amarillo = AMARILLO
            self.fase_destino = siguiente

    # ------------------------------------------------------------ paso de 1 s
    def paso(self, epsilon, entrenar):
        if self.en_amarillo > 0:
            self.en_amarillo -= 1
            if self.en_amarillo == 0:
                self.fase = self.fase_destino
                self.t_en_fase = 0
                traci.trafficlight.setRedYellowGreenState(self.id, self.fases[self.fase])
            return None

        self.t_en_fase += 1
        if self.t_en_fase < VERDE_MINIMO or self.t_en_fase % INTERVALO != 0:
            return None

        v = self.procesar()
        s = self.estado(v)
        r = self.recompensa(v)
        if entrenar and self.s_prev is not None:
            q = self.Q[self.s_prev]
            q[self.a_prev] += self.alpha * (r + self.gamma * self.Q[s].max() - q[self.a_prev])
        a = self.decidir(s, epsilon)
        self.s_prev, self.a_prev = s, a
        self.ejecutar(a)
        return r

    # ------------------------------------------------------------ persistencia
    def exportar(self):
        return {"fases": self.fases, "Q": dict(self.Q)}

    def importar(self, data):
        self.Q = defaultdict(lambda: np.zeros(N_ACCIONES), data["Q"])


def crear_agentes(**kw):
    return {t: Interseccion(t, **kw) for t in traci.trafficlight.getIDList()}


def guardar_qtables(agentes, path):
    with open(path, "wb") as f:
        pickle.dump({k: a.exportar() for k, a in agentes.items()}, f)


def cargar_qtables(agentes, path):
    with open(path, "rb") as f:
        data = pickle.load(f)
    for k, a in agentes.items():
        if k in data:
            a.importar(data[k])
