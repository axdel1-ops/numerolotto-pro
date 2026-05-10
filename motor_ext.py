# -*- coding: utf-8 -*-
"""
Capa de evaluación sobre es_consistente: duras/suaves, penalización, selección de candidatos.

Importa es_consistente y Grid; la penalización sigue los códigos definidos en motor.py.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Tuple

from motor import Grid, es_consistente, esperado_y3_2, es_valido, partner_a, partner_b

# ---------------------------------------------------------------------------
# 2. Clasificación de reglas
# ---------------------------------------------------------------------------

DURAS = {
    "ANCLAJE_Y3_2",
    "ANCLAJE_Y4_3",
    "DOMINIO_DIGITO",
    "PARAMETRO_P_INDEFINIDO",
}

SUAVES = {
    "PAREJA_TABLA_A",
    "PAREJA_TABLA_B",
    "COHERENCIA_TRIADA",
    "EXTENSIBILIDAD",
    "COMPLETITUD",
    "SUMA_PIVOTE",
    "SUMA_PLAN",
    "COHERENCIA_Y3_Y4",
    "BLOQUEO_PROPAGACION_X",
    "EXPANSION_INVALIDA",
    "DENSIDAD_INSUFICIENTE",
    "DESALINEACION_X3_P",
    "SECUENCIA_P_INVALIDA",
    "INCOMPATIBLE_EQUIVALENTE",
    "EXPANSION_BLOQUEADA_TEMPRANA",
    "INCONSISTENCIA_PROPAGACION_GLOBAL",
    "DESBALANCE_EJES",
    "TRANSFORMACION_INVALIDA",
    "INCOHERENCIA_SERIE_BASE",
    "SERIE_INCOMPLETA",
}


# ---------------------------------------------------------------------------
# 3. Pesos
# ---------------------------------------------------------------------------

def peso(codigo: str) -> int:
    pesos = {
        "COHERENCIA_TRIADA": 3,
        "PAREJA_TABLA_A": 2,
        "PAREJA_TABLA_B": 2,
        "EXTENSIBILIDAD": 4,
        "COMPLETITUD": 1,
        "SUMA_PIVOTE": 2,
        "SUMA_PLAN": 2,
        "COHERENCIA_Y3_Y4": 4,
        "BLOQUEO_PROPAGACION_X": 3,
        "EXPANSION_INVALIDA": 3,
        "DENSIDAD_INSUFICIENTE": 2,
        "DESALINEACION_X3_P": 3,
        "SECUENCIA_P_INVALIDA": 2,
        "INCOMPATIBLE_EQUIVALENTE": 4,
        "EXPANSION_BLOQUEADA_TEMPRANA": 5,
        "INCONSISTENCIA_PROPAGACION_GLOBAL": 5,
        "DESBALANCE_EJES": 4,
        "TRANSFORMACION_INVALIDA": 6,
        "INCOHERENCIA_SERIE_BASE": 5,
        "SERIE_INCOMPLETA": 4,
    }
    return pesos.get(codigo, 1)


# ---------------------------------------------------------------------------
# 4. Wrapper de evaluación
# ---------------------------------------------------------------------------


@dataclass
class Evaluacion:
    def __init__(
        self,
        ok: bool,
        falla_dura: bool,
        penalizacion: int,
        fallos: list,
    ):
        self.ok = ok
        self.falla_dura = falla_dura
        self.penalizacion = penalizacion
        self.fallos = fallos


def evaluar(grid: Grid) -> Evaluacion:
    res = es_consistente(grid, completo=False)

    falla_dura = False
    penalizacion = 0

    for c in res.contradicciones:
        if c.codigo in DURAS:
            falla_dura = True
        elif c.codigo in SUAVES:
            penalizacion += peso(c.codigo)

    return Evaluacion(
        ok=not falla_dura,
        falla_dura=falla_dura,
        penalizacion=penalizacion,
        fallos=res.contradicciones,
    )


# ---------------------------------------------------------------------------
# 5. Selección de candidato
# ---------------------------------------------------------------------------


def seleccionar_mejor(candidatos: List[Grid]):
    """
    1) Filtra por validación fuerte (es_valido).
    2) Si un solo candidato pasa, es el elegido.
    3) Si varios pasan, desempate por penalización (evaluar) y desempatar().
    4) Si ninguno pasa la validación fuerte, se usa el conjunto completo (fallback)
       con el mismo criterio de penalización que antes.
    """
    validos = [g for g in candidatos if es_valido(g)]
    pool: List[Grid] = validos if validos else list(candidatos)

    if len(validos) == 1:
        return validos[0]

    mejores: List[Tuple[Grid, Evaluacion]] = []
    mejor_score = float("inf")

    for g in pool:
        ev = evaluar(g)

        if ev.falla_dura:
            continue

        if ev.penalizacion < mejor_score:
            mejor_score = ev.penalizacion
            mejores = [(g, ev)]
        elif ev.penalizacion == mejor_score:
            mejores.append((g, ev))

    if not mejores:
        raise RuntimeError("No hay candidatos válidos")

    if len(mejores) == 1:
        return mejores[0][0]

    return desempatar(mejores)


# ---------------------------------------------------------------------------
# 6. Desempate (adaptado al Grid del motor: tensor escalar, sin filas x/y)
# ---------------------------------------------------------------------------


def _celdas_rellenas_tensor(g: Grid) -> int:
    """Cuenta dígitos presentes en la cruz x2,x3,x4,y2,y3,y4."""
    campos = (g.x2, g.x3, g.x4, g.y2, g.y3, g.y4)
    return sum(1 for v in campos if v is not None)


def desempatar(lista: List[Tuple[Grid, Evaluacion]]) -> Grid:
    """
    Prefiere el grid con más celdas del tensor rellenas (equivalente al spec:
    más masa en las filas de la cruz). Empate final: orden de letra a-f.
    """

    def score_extra(item: Tuple[Grid, Evaluacion]) -> Tuple[int, int]:
        g = item[0]
        filled = _celdas_rellenas_tensor(g)
        letter_rank = "abcdef".find(g.letra.lower())
        if letter_rank < 0:
            letter_rank = 99
        # sort ascending: más filled primero (-filled menor como en el spec original)
        return (-filled, letter_rank)

    ordenada = sorted(lista, key=score_extra)
    return ordenada[0][0]


# ---------------------------------------------------------------------------
# 7. Debug
# ---------------------------------------------------------------------------


def debug_caso(candidatos: List[Grid]) -> None:
    for g in candidatos:
        ev = evaluar(g)
        p_val = g.y3  # en motor.Grid, P es el tensor y3 (= y3[4] en la fila lógica)

        print(f"\nLetra: {g.letra} | P={p_val}")
        print("Validacion fuerte (es_valido):", es_valido(g))
        print("Falla dura:", ev.falla_dura)
        print("Penalizacion:", ev.penalizacion)

        for c in ev.fallos:
            print(f" - {c.codigo} | {c.donde} | {c.detalle}")


# ---------------------------------------------------------------------------
# Generación de candidatos (plan X igual que index.html; sin tocar motor.py)
# ---------------------------------------------------------------------------

LETTERS = ["a", "b", "c", "d", "e", "f"]

EQUIVALENCIA_MAP: Dict[int, int] = {
    0: 0,
    1: 9,
    2: 8,
    3: 7,
    4: 6,
    5: 5,
    6: 4,
    7: 3,
    8: 2,
    9: 1,
}

# Misma excepción documentada que la app V17.3
EQUIVALENT_SEED_OVERRIDE: Dict[str, Tuple[int, int, int]] = {
    "9072": (3, 6, 1),
}


def _sanitize4(v: str) -> str:
    return "".join(ch for ch in str(v) if ch.isdigit()).zfill(4)[-4:]


def _rotate_digit(d: int, step: int) -> int:
    return (d + step) % 10


def _build_matrix_from_4_digits(digits: List[int]) -> List[List[int]]:
    return [[_rotate_digit(d, r) for d in digits] for r in range(10)]


def _select_strict_row(matrix: List[List[int]]) -> Optional[Tuple[int, Tuple[int, int, int], int]]:
    row20 = None
    row10 = None
    for i, row in enumerate(matrix):
        tern = (row[1], row[2], row[3])
        s = sum(tern)
        if s == 20 and row20 is None:
            row20 = (i, tern, 20)
        if s == 10 and row10 is None:
            row10 = (i, tern, 10)
    pick = row20 or row10
    return pick


def compute_equivalent(seed4: str) -> Tuple[Tuple[int, int, int], int, int]:
    s4 = _sanitize4(seed4)
    if s4 in EQUIVALENT_SEED_OVERRIDE:
        eq = EQUIVALENT_SEED_OVERRIDE[s4]
        return eq, -1, 20
    digits = [int(c) for c in s4]
    matrix = _build_matrix_from_4_digits(digits)
    selected = _select_strict_row(matrix)
    if not selected:
        return (0, 0, 0), -1, 0
    _idx, tern, sum_val = selected
    equivalent = tuple(EQUIVALENCIA_MAP[d] for d in tern)
    return equivalent, selected[0], sum_val


def _generate_unique_pairs_for_target(pivot: int, target_sum: int) -> List[Dict[str, int]]:
    needed = target_sum - pivot
    pairs: List[Dict[str, int]] = []
    for x in range(9, -1, -1):
        y = needed - x
        if y < 0 or y > 9:
            continue
        if x < y:
            continue
        pairs.append({"x3": x, "y3": y, "total": target_sum})
    return pairs


def build_x_plan(pivot: int) -> List[Dict[str, Optional[int]]]:
    p20 = _generate_unique_pairs_for_target(pivot, 20)
    p10 = _generate_unique_pairs_for_target(pivot, 10)
    queue: List[Dict[str, Optional[int]]] = p20 + p10
    while len(queue) < 6:
        queue.append({"x3": None, "y3": None, "total": 0})
    return queue[:6]


def generar_candidatos(
    semilla: str,
    equivalente: Optional[Tuple[int, int, int]] = None,
    *,
    incluir_anclas: bool = True,
) -> List[Grid]:
    """
    Seis cuadrículas (a-f) con el plan X de la app: pares (x3,y3) y suma_objetivo.

    incluir_anclas: rellena ancla_y3_2 / ancla_y4_3 para activar validación de anclajes
    en es_consistente (coherente con la propagación real).
    """
    s = _sanitize4(semilla)
    if equivalente is None:
        equivalente, _, _ = compute_equivalent(s)
    pivot = int(equivalente[1])
    plan = build_x_plan(pivot)
    out: List[Grid] = []
    an_y32 = esperado_y3_2(s, equivalente) if incluir_anclas else None
    an_y43 = int(equivalente[1]) if incluir_anclas else None

    for i, letter in enumerate(LETTERS):
        p = plan[i]
        x3 = p["x3"]
        y3 = p["y3"]
        ts = p["total"]
        out.append(
            Grid(
                semilla=s,
                equivalente=tuple(int(x) for x in equivalente),
                letra=letter,
                x2=None,
                x3=x3,
                x4=None,
                y2=None,
                y3=y3,
                y4=None,
                suma_objetivo=ts if ts else None,
                ancla_y3_2=an_y32,
                ancla_y4_3=an_y43,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Propagación tensor (brazos x₂–x₄, y₂–y₄) desde el número ganador — sin tocar selección
# ---------------------------------------------------------------------------


def series10_rotaciones_desde_base4(base4: str) -> List[str]:
    """Misma rotación que index.html / serve_motor.build_series_10_from_4."""
    s = _sanitize4(base4)
    digits = [int(c) for c in s]
    out: List[str] = []
    for step in range(10):
        out.append("".join(str((d + step) % 10) for d in digits))
    return out


def _target_suma_plan(grid: Grid) -> Optional[int]:
    if grid.suma_objetivo is not None and int(grid.suma_objetivo) > 0:
        return int(grid.suma_objetivo)
    if grid.x3 is None or grid.y3 is None:
        return None
    return int(grid.x3) + int(grid.pivote) + int(grid.y3)


def _slot_fits_tensor(cur: Optional[int], dig: int) -> bool:
    if cur is None:
        return True
    return int(cur) % 10 == int(dig) % 10


def _y3_desde_pivote(ts: int, pivot: int, s1: int) -> int:
    return int(ts) - int(pivot) - int(s1)


def series_encaja_eje_x(grid: Grid, ser: str, terminal: int, pivot: int) -> bool:
    """Encaje eje X: (x₂,x₃,x₄,T) con y₃ derivada = suma_plan − pivote − x₃(serie)."""
    s = [int(c) for c in ser]
    if int(terminal) != s[3]:
        return False
    if not _slot_fits_tensor(grid.x2, s[0]):
        return False
    if not _slot_fits_tensor(grid.x3, s[1]):
        return False
    if not _slot_fits_tensor(grid.x4, s[2]):
        return False
    ts = _target_suma_plan(grid)
    if ts is None:
        return False
    y3n = _y3_desde_pivote(ts, pivot, s[1])
    if not (0 <= y3n <= 9):
        return False
    if not _slot_fits_tensor(grid.y3, y3n):
        return False
    return True


def series_encaja_eje_y(grid: Grid, ser: str, terminal: int, pivot: int) -> bool:
    """Encaje eje Y: misma cadena 4 dígitos; (y₂,y₃,y₄,T) con y₃ coherente con pivote."""
    s = [int(c) for c in ser]
    if int(terminal) != s[3]:
        return False
    ts = _target_suma_plan(grid)
    if ts is None:
        return False
    y3n = _y3_desde_pivote(ts, pivot, s[1])
    if not (0 <= y3n <= 9):
        return False
    if not _slot_fits_tensor(grid.y2, s[0]):
        return False
    if not _slot_fits_tensor(grid.y3, y3n):
        return False
    if not _slot_fits_tensor(grid.y4, s[2]):
        return False
    return True


def _tensor_desde_serie_encaje(grid: Grid, ser: str) -> Grid:
    """
    Cierra brazos laterales a partir de la variación encajada (alineado a
    completeForensicTensor en la app: x₂/s₀, x₄/s₂, gemelos A/B en y₂,y₄).
    x₃, y₃ (P) del plan no se modifican.
    """
    s0, _s1, s2, _s3 = (int(ser[0]), int(ser[1]), int(ser[2]), int(ser[3]))
    y2 = partner_a(s0, grid.map_a_x_to_y)
    y4 = partner_b(s2, grid.map_b_x_to_y)
    return replace(grid, x2=s0, x4=s2, y2=y2, y4=y4)


def propagar_tensor_desde_ganador(grid: Grid, ganador4: str) -> Tuple[Grid, List[str]]:
    """
    Rellena x₂,x₄,y₂,y₄ buscando una variación del sorteo que encaje en eje X o Y
    (vacío = comodín), coherente con pivote, T y suma del plan.

    Devuelve (grid_actualizado, líneas de bitácora).
    """
    log: List[str] = []
    piv = int(grid.pivote)
    term = int(grid.terminal)
    antes = (grid.x2, grid.x3, grid.x4, grid.y2, grid.y3, grid.y4)
    log.append("ANTES: x2=%r x3=%r x4=%r y2=%r y3=%r y4=%r" % antes)
    ts = _target_suma_plan(grid)
    log.append("suma_plan(objetivo) = %r | pivote=%s terminal(T)=%s" % (ts, piv, term))

    g4 = _sanitize4(ganador4)
    if len(g4) != 4 or not g4.isdigit():
        log.append("ganador4 invalido: no se propaga")
        return grid, log

    if grid.x3 is None or grid.y3 is None:
        log.append("sin x3 o P en el grid: no se propaga")
        return grid, log

    def probar_rotaciones(origen: str, series: List[str]) -> Optional[Tuple[str, str]]:
        for idx, ser in enumerate(series):
            if series_encaja_eje_x(grid, ser, term, piv):
                log.append(
                    "eje X encaja con variacion %s indice %s/10 (origen %s): %s -> x2=%s x4=%s"
                    % (ser, idx + 1, origen, ser, ser[0], ser[2])
                )
                log.append(
                    "y2 = gemelo A(x2) = %s | y4 = gemelo B(x4) = %s"
                    % (
                        partner_a(int(ser[0]), grid.map_a_x_to_y),
                        partner_b(int(ser[2]), grid.map_b_x_to_y),
                    )
                )
                return ser, "X"
            if series_encaja_eje_y(grid, ser, term, piv):
                log.append(
                    "eje Y encaja con variacion %s indice %s/10 (origen %s): %s -> y2=%s y4=%s"
                    % (ser, idx + 1, origen, ser, ser[0], ser[2])
                )
                log.append(
                    "x2/s0=%s x4/s2=%s → y2=gA(x2)=%s y4=gB(x4)=%s"
                    % (
                        ser[0],
                        ser[2],
                        partner_a(int(ser[0]), grid.map_a_x_to_y),
                        partner_b(int(ser[2]), grid.map_b_x_to_y),
                    )
                )
                return ser, "Y"
        return None

    hit = probar_rotaciones("sorteo", series10_rotaciones_desde_base4(g4))
    if hit is None:
        base_struct = _sanitize4("%s%s%s%s" % (grid.x3, piv, grid.y3, term))
        log.append(
            "sin encaje en rotaciones del sorteo; probando base estructural x3-pivote-P-T = %s" % base_struct
        )
        hit = probar_rotaciones("x3-pivote-P-T", series10_rotaciones_desde_base4(base_struct))

    if hit is None:
        log.append("DESPUES: sin encaje estructural; tensor sin cambios")
        return grid, log

    ser, _eje = hit
    nuevo = _tensor_desde_serie_encaje(grid, ser)
    log.append(
        "DESPUES: x2=%r x3=%r x4=%r y2=%r y3=%r y4=%r"
        % (nuevo.x2, nuevo.x3, nuevo.x4, nuevo.y2, nuevo.y3, nuevo.y4)
    )
    return nuevo, log


def debug_propagacion(grid: Grid, ganador4: str) -> str:
    """Texto listo para consola o campo API (ANTES / decisiones / DESPUÉS)."""
    _g, lines = propagar_tensor_desde_ganador(grid, ganador4)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prueba obligatoría (semillas solicitadas)
# ---------------------------------------------------------------------------

_PRUEBA_SEMILLAS = ("5816", "5264", "1409", "9428", "5497")


def _run_prueba_obligatoria() -> None:
    print("=== Prueba motor_ext: debug_caso + seleccionar_mejor ===")
    for seed in _PRUEBA_SEMILLAS:
        eq, _, _ = compute_equivalent(seed)
        print(f"\n{'='*60}\nSemilla {seed} | equivalente {eq}\n{'='*60}")
        candidatos = generar_candidatos(seed, incluir_anclas=True)
        debug_caso(candidatos)
        try:
            mejor = seleccionar_mejor(candidatos)
            otros = [g for g in candidatos if g.letra != mejor.letra]
            print(f"\n>>> Seleccionado: letra {mejor.letra} | P={mejor.y3}")
            print(
                ">>> Descartados (no ganan desempate / penalizacion > mejor): "
                f"{', '.join(o.letra for o in otros)}"
            )
            ev_m = evaluar(mejor)
            for o in otros:
                ev_o = evaluar(o)
                if ev_o.falla_dura:
                    motivo = "excluido: falla dura (no entra en seleccion)"
                elif ev_o.penalizacion > ev_m.penalizacion:
                    motivo = f"penalizacion {ev_o.penalizacion}>{ev_m.penalizacion}"
                else:
                    motivo = "empate en penalizacion; pierde desempate"
                print(f"    [{o.letra}] {motivo}")
        except RuntimeError as e:
            print(f"\n>>> {e}")


if __name__ == "__main__":
    _run_prueba_obligatoria()
