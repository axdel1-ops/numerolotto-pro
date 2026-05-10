# -*- coding: utf-8 -*-
"""
Motor de consistencia NUMEROLOTTO PRO — solver por descarte (sin fórmula directa de P).

`es_consistente(grid)` valida la cuadrícula contra las mismas relaciones estructurales
que la app (index.html): anclajes, suma pivote 10/20, pares tensor A/B, coherencia de tríadas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

Digit = Optional[int]

# --- Mapas gemelo por defecto (Ley de atracción / fallback de la app V17.3) ---
FALLBACK_PAIR_A: Dict[int, int] = {
    0: 0,
    1: 9,
    2: 8,
    3: 7,
    4: 6,
    5: 9,
    6: 4,
    7: 3,
    8: 2,
    9: 1,
}
FALLBACK_PAIR_B: Dict[int, int] = {
    0: 5,
    1: 3,
    2: 2,
    3: 1,
    4: 1,
    5: 0,
    6: 9,
    7: 8,
    8: 7,
    9: 6,
}
ESPEJO_MAP: Dict[int, int] = {0: 5, 1: 6, 2: 7, 3: 8, 4: 9, 5: 0, 6: 1, 7: 2, 8: 3, 9: 4}


def _digito_ok(d: Digit) -> bool:
    return d is not None and 0 <= int(d) <= 9


def raiz_tríada(a: int, b: int, c: int) -> int:
    return (int(a) + int(b) + int(c)) % 10


def es_gemelo_espejo(rx: int, ry: int) -> bool:
    return ESPEJO_MAP.get(int(rx) % 10, -1) == int(ry) % 10


def partner_a(x: int, map_a_x_to_y: Optional[Dict[int, int]] = None) -> int:
    m = map_a_x_to_y or {}
    if x in m:
        return int(m[x])
    return FALLBACK_PAIR_A[int(x) % 10]


def partner_b(x: int, map_b_x_to_y: Optional[Dict[int, int]] = None) -> int:
    m = map_b_x_to_y or {}
    if x in m:
        return int(m[x])
    return FALLBACK_PAIR_B[int(x) % 10]


def modo_especial_semilla(semilla: str) -> str:
    """
    Disparador de ramas documentadas. '9428' = anclajes distintos al modo normal.
    """
    s = "".join(ch for ch in str(semilla) if ch.isdigit()).zfill(4)[-4:]
    if s == "9428":
        return "9428"
    return "normal"


def _digitos_semilla(semilla: str) -> List[int]:
    s = "".join(ch for ch in str(semilla) if ch.isdigit()).zfill(4)[-4:]
    return [int(c) for c in s]


def _densidad_tensor(grid: Grid) -> int:
    return sum(1 for v in (grid.x2, grid.x3, grid.x4, grid.y2, grid.y3, grid.y4) if v is not None)


def _letter_rank(letra: str) -> int:
    i = "abcdef".find(letra.lower())
    return i if i >= 0 else 9


def esperado_y3_2(semilla: str, equivalente: Tuple[int, int, int]) -> int:
    """
    Dígito fijo en y3[2] (índice 0-based).

    Modo normal: equivalente[0].
    Modo 9428: equivalente[1] (ancla desplazada; mismo corpus que la app).
    """
    e0, e1 = int(equivalente[0]), int(equivalente[1])
    if modo_especial_semilla(semilla) == "9428":
        return e1
    return e0


def _pares_plan_x_por_objetivo(pivot: int, target_sum: int) -> List[Tuple[int, int]]:
    """
    Pares (x3, P) del plan X (misma enumeración que motor_ext / app: x en descenso, x >= y).
    """
    needed = int(target_sum) - int(pivot)
    pairs: List[Tuple[int, int]] = []
    for x in range(9, -1, -1):
        y = needed - x
        if y < 0 or y > 9:
            continue
        if x < y:
            continue
        pairs.append((x, y))
    return pairs


def secuencia_p_plan_x(pivot: int) -> List[Digit]:
    """
    Secuencia ordenada de P (tensor y3) para letras a→f: primero pares suma 20, luego 10, relleno None.
    Alineado con ``motor_ext.build_x_plan``.
    """
    p20 = _pares_plan_x_por_objetivo(pivot, 20)
    p10 = _pares_plan_x_por_objetivo(pivot, 10)
    seq: List[Digit] = [p for _x, p in p20 + p10]
    while len(seq) < 6:
        seq.append(None)
    return seq[:6]


def _continuidad_p_ok(grid: Grid) -> bool:
    """
    CONTINUIDAD_P: P (tensor y3) debe coincidir con la ranura a→f del plan X del generador.
    """
    r = _letter_rank(grid.letra)
    if r < 0 or r > 5:
        return False
    pivot = int(grid.equivalente[1])
    seq = secuencia_p_plan_x(pivot)
    esperado = seq[r]
    got = grid.y3
    if esperado is None:
        return got is None
    if got is None:
        return False
    return int(got) % 10 == int(esperado) % 10


def _modo_especial_9428_ok(grid: Grid) -> bool:
    """
    MODO_ESPECIAL_9428: y3[2] debe tomarse de equivalente[1], no de equivalente[0]
    (rechazo explícito de ancla e0 cuando e0 y e1 distinguen la rama).
    """
    if modo_especial_semilla(grid.semilla) != "9428":
        return True
    e0, e1 = int(grid.equivalente[0]) % 10, int(grid.equivalente[1]) % 10
    if e0 == e1:
        return True
    candidatos_obs: List[Digit] = [grid.ancla_y3_2]
    if grid.y3_fila is not None and len(grid.y3_fila) > 2:
        candidatos_obs.append(grid.y3_fila[2])
    for v in candidatos_obs:
        if v is None:
            continue
        if int(v) % 10 == e0:
            return False
    return True


@dataclass
class Grid:
    """
    Estado de una cuadrícula candidata (una letra a–f).

    `y3` en tensor es P = y3[4] en la fila inferior de la cruz (celda 3,5 en la app).
    Índices fila y3 / y4 son 0-based de longitud 5.
    """

    semilla: str
    equivalente: Tuple[int, int, int]
    letra: str
    # tensor operativo (cruz)
    x2: Digit
    x3: Digit
    x4: Digit
    y2: Digit
    y3: Digit  # P
    y4: Digit
    suma_objetivo: Optional[int] = None  # 10 o 20 del plan de la variación
    map_a_x_to_y: Optional[Dict[int, int]] = field(default=None)
    map_b_x_to_y: Optional[Dict[int, int]] = field(default=None)
    # Si la propagación rellenó la fila completa, úsalo para validar anclas:
    y3_fila: Optional[Tuple[Digit, Digit, Digit, Digit, Digit]] = None
    # Alternativa: solo el dígito observado en y3[2] tras construir la cuadrícula:
    ancla_y3_2: Optional[int] = None
    y4_fila: Optional[Tuple[Digit, Digit, Digit, Digit, Digit]] = None
    ancla_y4_3: Optional[int] = None

    @property
    def pivote(self) -> int:
        return int(self.equivalente[1])

    @property
    def terminal(self) -> int:
        return int(self.equivalente[2])

    def fila_y3(self) -> Tuple[Digit, Digit, int, Digit, Digit]:
        """Representación lógica (c1..c5); ancla y3[2] según modo; P = y3[4]."""
        a2 = esperado_y3_2(self.semilla, self.equivalente)
        return (None, None, a2, None, self.y3)

    def fila_y4(self) -> Tuple[Digit, Digit, Digit, int, Digit]:
        """y4[3] en UI = pivote = equivalente[1]; y4[4] = tensor y4."""
        p = self.pivote
        return (None, None, None, p, self.y4)


@dataclass
class Contradiccion:
    """Una sola ruptura detectada (regla + sitio)."""

    codigo: str
    regla: str
    donde: str
    detalle: str


@dataclass
class ResultadoConsistencia:
    ok: bool
    contradicciones: List[Contradiccion] = field(default_factory=list)

    def primer_fallo(self) -> Optional[Contradiccion]:
        return self.contradicciones[0] if self.contradicciones else None


def _append(
    out: List[Contradiccion],
    codigo: str,
    regla: str,
    donde: str,
    detalle: str,
) -> None:
    out.append(Contradiccion(codigo=codigo, regla=regla, donde=donde, detalle=detalle))


def _check_digitos(grid: Grid, err: List[Contradiccion]) -> None:
    campos = {
        "tensor.x2": grid.x2,
        "tensor.x3": grid.x3,
        "tensor.x4": grid.x4,
        "tensor.y2": grid.y2,
        "tensor.y3 (P)": grid.y3,
        "tensor.y4": grid.y4,
    }
    for nombre, v in campos.items():
        if v is None:
            continue
        if not _digito_ok(v):
            _append(
                err,
                "DOMINIO_DIGITO",
                "Valores deben ser dígitos 0–9 o vacío",
                nombre,
                f"valor inválido: {v!r}",
            )


def _check_anclajes(grid: Grid, err: List[Contradiccion]) -> None:
    exp_y32 = esperado_y3_2(grid.semilla, grid.equivalente)
    piv = grid.pivote

    if grid.y3_fila is not None:
        got = grid.y3_fila[2]
        if got is not None and int(got) != exp_y32:
            _append(
                err,
                "ANCLAJE_Y3_2",
                "Anclaje obligatorio entre equivalente y fila y3",
                "y3[2]",
                f"esperado {exp_y32} (modo {modo_especial_semilla(grid.semilla)}), propagado {got}",
            )
    elif grid.ancla_y3_2 is not None:
        if int(grid.ancla_y3_2) != exp_y32:
            _append(
                err,
                "ANCLAJE_Y3_2",
                "Anclaje obligatorio entre equivalente y fila y3",
                "y3[2]",
                f"esperado {exp_y32} (modo {modo_especial_semilla(grid.semilla)}), observado {grid.ancla_y3_2}",
            )

    if grid.y4_fila is not None:
        gy43 = grid.y4_fila[3]
        if gy43 is not None and int(gy43) != piv:
            _append(
                err,
                "ANCLAJE_Y4_3",
                "Anclaje obligatorio: celda y4[3] = pivote = equivalente[1]",
                "y4[3]",
                f"esperado {piv}, propagado {gy43}",
            )
    elif grid.ancla_y4_3 is not None:
        if int(grid.ancla_y4_3) != piv:
            _append(
                err,
                "ANCLAJE_Y4_3",
                "Anclaje obligatorio: celda y4[3] = pivote = equivalente[1]",
                "y4[3]",
                f"esperado {piv}, observado {grid.ancla_y4_3}",
            )


def _check_suma_pivote(grid: Grid, err: List[Contradiccion]) -> None:
    if grid.x3 is None or grid.y3 is None:
        return
    s = int(grid.x3) + grid.pivote + int(grid.y3)
    if grid.suma_objetivo is not None:
        if s != int(grid.suma_objetivo):
            _append(
                err,
                "SUMA_PLAN",
                "x3 + pivote + P debe coincidir con la suma objetivo del plan (10 o 20)",
                "cruce x3-pivote-y3",
                f"obtenido {s}, plan {grid.suma_objetivo}",
            )
    else:
        if s not in (10, 20):
            _append(
                err,
                "SUMA_PIVOTE",
                "x3 + pivote + P debe ser 10 o 20",
                "cruce x3-pivote-y3",
                f"suma = {s}",
            )


def _check_parejas_tensor(grid: Grid, err: List[Contradiccion]) -> None:
    if grid.x2 is not None and grid.y2 is not None:
        esp = partner_a(int(grid.x2), grid.map_a_x_to_y)
        if int(grid.y2) != esp:
            _append(
                err,
                "PAREJA_TABLA_A",
                "Ley de atracción en eje X (gemelo A): y2 debe corresponder a x2",
                "tensor.y2",
                f"y2={grid.y2}, esperado por mapa A desde x2={grid.x2} -> {esp}",
            )
    if grid.x4 is not None and grid.y4 is not None:
        esp = partner_b(int(grid.x4), grid.map_b_x_to_y)
        if int(grid.y4) != esp:
            _append(
                err,
                "PAREJA_TABLA_B",
                "Ley de atracción en eje Y (gemelo B): y4 debe corresponder a x4",
                "tensor.y4",
                f"y4={grid.y4}, esperado por mapa B desde x4={grid.x4} -> {esp}",
            )


def _check_coherencia_tríadas(grid: Grid, err: List[Contradiccion]) -> None:
    needed = [grid.x2, grid.x3, grid.x4, grid.y2, grid.y3, grid.y4]
    if any(v is None for v in needed):
        return
    rx = raiz_tríada(int(grid.x2), int(grid.x3), int(grid.x4))
    ry = raiz_tríada(int(grid.y2), int(grid.y3), int(grid.y4))
    if rx != ry and not es_gemelo_espejo(rx, ry):
        _append(
            err,
            "COHERENCIA_TRIADA",
            "Raíz digital de la tríada X debe igualar o espejarse con la de Y",
            "patrón global (series X/Y)",
            f"raíz(X)={rx}, raíz(Y)={ry} (no iguales ni gemelas espejo)",
        )


def _check_extensibilidad(grid: Grid, err: List[Contradiccion]) -> None:
    """Si falta una celda que ya tiene una restricción activa, queda no extensible."""
    if grid.x3 is not None and grid.y3 is not None and grid.x2 is None and grid.y2 is not None:
        _append(
            err,
            "EXTENSIBILIDAD",
            "Propagación incompleta: y2 fijado sin x2 gemelo",
            "tensor.x2",
            "no se puede completar el eje X sin x2",
        )


def _ancla_y3_definida(grid: Grid) -> bool:
    return grid.ancla_y3_2 is not None or grid.y3_fila is not None


def _ancla_y4_definida(grid: Grid) -> bool:
    return grid.ancla_y4_3 is not None or grid.y4_fila is not None


def _nivel_avance_y3(grid: Grid) -> int:
    n = 0
    if _ancla_y3_definida(grid):
        n += 1
    if grid.y3 is not None:
        n += 1
    return n


def _nivel_avance_y4(grid: Grid) -> int:
    n = 0
    if _ancla_y4_definida(grid):
        n += 1
    if grid.y4 is not None:
        n += 1
    return n


def _check_coherencia_y3_y4(grid: Grid, err: List[Contradiccion]) -> None:
    """
    REGLA 1 — Coherencia estructural entre rama Y3 y rama Y4 (ancla vs pivote vs P).
    """
    if not (_ancla_y3_definida(grid) and _ancla_y4_definida(grid)):
        return

    motivos: List[str] = []
    if grid.y3 is not None and grid.y4 is None:
        motivos.append("P definido pero tensor.y4 vacío; brazo Y4 incompleto frente a Y3")
    if (
        grid.y4_fila is not None
        and len(grid.y4_fila) > 4
        and grid.y3 is not None
        and grid.y4_fila[4] is None
    ):
        motivos.append("y4[4] (tensor) vacío en fila propagada con P definido")
    if not (grid.y3 is not None and grid.y4 is None):
        if _nivel_avance_y3(grid) > _nivel_avance_y4(grid):
            motivos.append(
                f"avance Y3 ({_nivel_avance_y3(grid)}) mayor que avance Y4 ({_nivel_avance_y4(grid)})"
            )

    if motivos:
        _append(
            err,
            "COHERENCIA_Y3_Y4",
            "Coherencia estructural entre ancla y3[2], pivote y4[3] y ramas tensor",
            "cruce Y3-Y4",
            "; ".join(motivos),
        )


def _check_bloqueo_propagacion_x(grid: Grid, err: List[Contradiccion]) -> None:
    """REGLA 2 — El plan central x3,y3 exige continuidad en x2 y x4."""
    if grid.x3 is None or grid.y3 is None:
        return
    if grid.x2 is None or grid.x4 is None:
        _append(
            err,
            "BLOQUEO_PROPAGACION_X",
            "Con x3 y P fijados, el eje X debe propagarse a x2 y x4",
            "tensor.x2/x4",
            "x2 o x4 vacíos: la transformación no cierra el eje X",
        )


def _check_expansion_invalida(grid: Grid, err: List[Contradiccion]) -> None:
    """REGLA 3 — P activo sin expansión lateral en el tensor."""
    if grid.y3 is None:
        return
    lateral = sum(1 for v in (grid.x2, grid.x4, grid.y2, grid.y4) if v is not None)
    if lateral == 0:
        _append(
            err,
            "EXPANSION_INVALIDA",
            "P definido pero sin ocupación en brazos laterales del tensor",
            "tensor (brazos)",
            "ningún valor en x2,x4,y2,y4 pese a P definido",
        )


def _check_parametro_p_indefinido(grid: Grid, err: List[Contradiccion]) -> None:
    """REGLA 4 — La variante f exige P (y3[4]) materializado en el tensor."""
    if grid.letra.lower() != "f":
        return
    if grid.y3 is None:
        _append(
            err,
            "PARAMETRO_P_INDEFINIDO",
            "La malla f no admite P indefinido",
            "tensor.y3 (P)",
            "letra f requiere parámetro P definido",
        )


def _check_densidad_minima(grid: Grid, err: List[Contradiccion]) -> None:
    """REGLA 5 — Masa mínima en la cruz tensor."""
    n = _densidad_tensor(grid)
    if n < 3:
        _append(
            err,
            "DENSIDAD_INSUFICIENTE",
            "La cruz tensor necesita densidad mínima para un estado extensible",
            "tensor",
            f"celdas ocupadas={n}, mínimo 3",
        )


def _check_desalineacion_x3_p(grid: Grid, err: List[Contradiccion]) -> None:
    """
    REGLA 6 — Meta indexada por letra para el puente modular (x3+P).
    Usa semilla + pivote + posición en la familia a–f (discriminación entre candidatos).
    """
    if grid.x3 is None or grid.y3 is None:
        return
    sd = _digitos_semilla(grid.semilla)
    r = _letter_rank(grid.letra)
    e1 = int(grid.equivalente[1])
    paso = (e1 + sd[3]) % 10
    if paso == 0:
        paso = (sd[1] % 10) or 1
    meta = sum(sd) % 10
    # Desplazamiento por dígito de semilla en la posición r (rompe empates entre letras)
    offset = sd[r % 4]
    esperado_cruce = (meta + r * paso + offset) % 10
    cruce = (int(grid.x3) + int(grid.y3)) % 10
    if cruce != esperado_cruce:
        _append(
            err,
            "DESALINEACION_X3_P",
            "Desalineación estructural entre x3 y P respecto a la malla indexada",
            "tensor.x3 / P",
            f"(x3+P) mod 10 = {cruce}, meta r={r} (incl. offset sd[r%4]) = {esperado_cruce}",
        )


def _check_secuencia_p_invalida(grid: Grid, err: List[Contradiccion]) -> None:
    """
    REGLA 7 — P debe seguir la progresión letra×pivote anclada en el terminal e2.
    """
    if grid.y3 is None:
        return
    e1 = int(grid.equivalente[1])
    e2 = int(grid.equivalente[2])
    r = _letter_rank(grid.letra)
    esperado_p = (r * e1 + e2) % 10
    p = int(grid.y3) % 10
    if p != esperado_p:
        _append(
            err,
            "SECUENCIA_P_INVALIDA",
            "Ruptura de la progresión P frente al pivote y al terminal del equivalente",
            "tensor.y3 (P)",
            f"P={p}, esperado (r*pivote+terminal) mod 10 = {esperado_p} (r={r})",
        )


def _check_incompatible_equivalente(grid: Grid, err: List[Contradiccion]) -> None:
    """
    REGLA 8 — P frente a ancla y3[2]; y cierre modular con x3 y la triple equivalente.
    """
    if grid.y3 is None or grid.x3 is None:
        return
    p = int(grid.y3) % 10
    e0, e1, e2 = (int(grid.equivalente[0]), int(grid.equivalente[1]), int(grid.equivalente[2]))
    ancla = esperado_y3_2(grid.semilla, grid.equivalente) % 10
    r = _letter_rank(grid.letra)
    if p == ancla:
        _append(
            err,
            "INCOMPATIBLE_EQUIVALENTE",
            "P no puede colisionar con el dígito ancla de y3[2]",
            "tensor.y3 (P) vs ancla",
            f"P={p} igual a ancla y3[2]={ancla}",
        )
        return
    sello = (e0 + e1 + e2) % 10
    triple = (p + int(grid.x3) + r) % 10
    if triple != sello:
        _append(
            err,
            "INCOMPATIBLE_EQUIVALENTE",
            "Triple P+x3+r incompatible con la firma del equivalente",
            "tensor / equivalente",
            f"(P+x3+r) mod 10 = {triple}, firma (e0+e1+e2) mod 10 = {sello}",
        )


def _check_expansion_bloqueada_temprana(grid: Grid, err: List[Contradiccion]) -> None:
    """
    REGLA 9 — Slots posteriores bloquean antes si la masa tensor es baja.
    Umbral deducido solo del equivalente (e0+e2 mod 6): letras detrás del umbral
    pagan si aún no hay expansión suficiente.
    """
    d = _densidad_tensor(grid)
    if d >= 4:
        return
    r = _letter_rank(grid.letra)
    e0, _e1, e2 = (int(grid.equivalente[0]), int(grid.equivalente[1]), int(grid.equivalente[2]))
    umbral = (e0 + e2) % 6
    if r > umbral:
        _append(
            err,
            "EXPANSION_BLOQUEADA_TEMPRANA",
            "Menos capacidad de expansión que variantes anteriores al mismo estado tensor",
            "letra / densidad",
            f"densidad={d}, umbral letra={umbral}, rango r={r}",
        )


def _ranura_plan_x_en_letra(pivot: int, r: int) -> Tuple[Optional[int], Optional[int]]:
    """Par (x3, P) del plan X en la letra r (0=a … 5=f), alineado con el generador."""
    pairs = _pares_plan_x_por_objetivo(pivot, 20) + _pares_plan_x_por_objetivo(pivot, 10)
    while len(pairs) < 6:
        pairs.append((None, None))
    if r < 0 or r >= 6:
        return (None, None)
    x, p = pairs[r]
    return (x, p)


def _check_inconsistencia_propagacion_global(grid: Grid, err: List[Contradiccion]) -> None:
    """
    REGLA 10 — Incoherencia entre el núcleo x3–P y cómo el tensor arrastra brazos.
    Sin conteo de densidad: relación estructural entre celdas y ejes.
    """
    x2, x3, x4 = grid.x2, grid.x3, grid.x4
    y2, y3, y4 = grid.y2, grid.y3, grid.y4
    lat_x2 = x2 is not None
    lat_x4 = x4 is not None
    lat_y2 = y2 is not None
    lat_y4 = y4 is not None

    if lat_x2 ^ lat_x4:
        _append(
            err,
            "INCONSISTENCIA_PROPAGACION_GLOBAL",
            "Propagación en X incompleta: un solo brazo ocupado frente a x3",
            "tensor.x2 / tensor.x4",
            "solo uno de x2, x4 tiene valor; el eje X no se expande en par desde el centro",
        )
    if lat_y2 ^ lat_y4:
        _append(
            err,
            "INCONSISTENCIA_PROPAGACION_GLOBAL",
            "Propagación en Y incompleta: un solo brazo ocupado frente a P",
            "tensor.y2 / tensor.y4",
            "solo uno de y2, y4 tiene valor; el eje Y no se expande en par desde P",
        )

    n_lateral = sum((lat_x2, lat_x4, lat_y2, lat_y4))
    if n_lateral == 1:
        _append(
            err,
            "INCONSISTENCIA_PROPAGACION_GLOBAL",
            "Celda lateral aislada sin un cruce mínimo simétrico",
            "tensor (brazos)",
            "una única celda lateral definida; no hay arrastre coherente del resto del tensor",
        )

    if (lat_x2 and lat_x4) and not (lat_y2 or lat_y4) and y3 is not None:
        _append(
            err,
            "INCONSISTENCIA_PROPAGACION_GLOBAL",
            "El eje X cierra x2–x4 pero el eje Y no materializa y2/y4",
            "eje X vs eje Y",
            "x2 y x4 definidos sin brazos Y; P no completa propagación global",
        )
    if (lat_y2 and lat_y4) and not (lat_x2 or lat_x4) and x3 is not None:
        _append(
            err,
            "INCONSISTENCIA_PROPAGACION_GLOBAL",
            "El eje Y cierra y2–y4 pero el eje X no materializa x2/x4",
            "eje Y vs eje X",
            "y2 y y4 definidos sin brazos X; el centro X no arrastra la malla",
        )

    if x3 is not None:
        an = esperado_y3_2(grid.semilla, grid.equivalente)
        if int(x3) == int(an):
            _append(
                err,
                "INCONSISTENCIA_PROPAGACION_GLOBAL",
                "Conflicto de roles: x3 no puede reproducir el anclaje de y3[2]",
                "tensor.x3 vs ancla y3[2]",
                f"x3={x3} coincide con el dígito ancla de la fila Y3 ({an})",
            )


def _check_desbalance_ejes(grid: Grid, err: List[Contradiccion]) -> None:
    """
    REGLA 11 — Desalineación entre la masa en el eje X y la del eje Y.
    """
    mx = sum(1 for v in (grid.x2, grid.x3, grid.x4) if v is not None)
    my = sum(1 for v in (grid.y2, grid.y3, grid.y4) if v is not None)
    if abs(mx - my) >= 2:
        _append(
            err,
            "DESBALANCE_EJES",
            "Un eje concentra mucha más información que el otro",
            "eje X vs eje Y",
            f"celdas ocupadas: X={mx}, Y={my}",
        )

    lat_x = (grid.x2 is not None) or (grid.x4 is not None)
    lat_y = (grid.y2 is not None) or (grid.y4 is not None)
    if lat_y and not lat_x and grid.x3 is not None:
        _append(
            err,
            "DESBALANCE_EJES",
            "Valores en Y sin soporte de brazos en X",
            "tensor Y / tensor X",
            "y2 o y4 definidos pero ningún brazo x2/x4 acompaña el eje X",
        )
    if lat_x and not lat_y and grid.y3 is not None:
        _append(
            err,
            "DESBALANCE_EJES",
            "Valores en X sin soporte de brazos en Y",
            "tensor X / tensor Y",
            "x2 o x4 definidos pero ningún brazo y2/y4 acompaña el eje Y",
        )


def _check_transformacion_invalida(grid: Grid, err: List[Contradiccion]) -> None:
    """
    REGLA 12 — La letra debe ser una transformación coherente con el plan y con el cruce x3–P.
    Sin aritmética modular: igualdad de ranura y ausencia de degeneración x3=P.
    """
    if grid.x3 is None or grid.y3 is None:
        return
    r = _letter_rank(grid.letra)
    if r < 0 or r > 5:
        return
    xe, pe = _ranura_plan_x_en_letra(grid.pivote, r)
    if xe is not None and pe is not None:
        if int(grid.x3) != int(xe) or int(grid.y3) != int(pe):
            _append(
                err,
                "TRANSFORMACION_INVALIDA",
                "La transformación no coincide con la ranura del plan para esta letra",
                "letra / plan X",
                f"grid (x3={grid.x3}, P={grid.y3}) vs ranura ({xe}, {pe}) en r={r}",
            )
            return

    if int(grid.x3) == int(grid.y3):
        _append(
            err,
            "TRANSFORMACION_INVALIDA",
            "Transformación degenerada: x3 y P colapsan el mismo grado de libertad",
            "tensor.x3 / P",
            f"x3=P={grid.x3}; el cruce no distingue parámetros en ejes X/Y",
        )


def _serie_base4(grid: Grid) -> Optional[Tuple[int, int, int, int]]:
    """
    Base de 4 cifras asociada al grid para análisis de serie.
    Regla pedida: [x3, pivote, P, y4].
    """
    if grid.x3 is None or grid.y3 is None or grid.y4 is None:
        return None
    return (int(grid.x3), int(grid.pivote), int(grid.y3), int(grid.y4))


def _check_incoherencia_serie_base(grid: Grid, err: List[Contradiccion]) -> None:
    """
    REGLA 13 — INCOHERENCIA_SERIE_BASE:
    si existe base de 4 cifras [x3,pivote,P,y4], cada dígito debe tener soporte estructural.
    Además, si el soporte total es menor a 4, marca SERIE_INCOMPLETA.
    """
    base = _serie_base4(grid)
    if base is None:
        return

    ancla = esperado_y3_2(grid.semilla, grid.equivalente)
    soporte_x = {int(v) for v in (grid.x2, grid.x3, grid.x4) if v is not None}
    soporte_y = {int(v) for v in (grid.y2, grid.y3, grid.y4, ancla, grid.terminal) if v is not None}
    soporte_xy = soporte_x | soporte_y

    faltantes = sorted({d for d in base if d not in soporte_xy})
    soporte = 4 - len(faltantes)

    if faltantes:
        _append(
            err,
            "INCOHERENCIA_SERIE_BASE",
            "La base de serie contiene dígitos sin correspondencia estructural en ejes X/Y",
            "serie base [x3,pivote,P,y4]",
            f"base={list(base)}; sin soporte X/Y: {faltantes}",
        )

    if soporte < 4:
        _append(
            err,
            "SERIE_INCOMPLETA",
            "La base de serie no alcanza soporte estructural completo",
            "serie base [x3,pivote,P,y4]",
            f"soporte={soporte}/4; base={list(base)}",
        )


def es_consistente(
    grid: Grid,
    *,
    completo: bool = False,
) -> ResultadoConsistencia:
    """
    Evalúa consistencia global del candidato.

    Si ``completo=True``, exige las seis celdas del tensor rellenas (estado terminal).
    """
    err: List[Contradiccion] = []

    _check_digitos(grid, err)
    _check_anclajes(grid, err)
    _check_suma_pivote(grid, err)
    _check_parejas_tensor(grid, err)
    _check_coherencia_tríadas(grid, err)
    _check_extensibilidad(grid, err)
    _check_coherencia_y3_y4(grid, err)
    _check_bloqueo_propagacion_x(grid, err)
    _check_expansion_invalida(grid, err)
    _check_parametro_p_indefinido(grid, err)
    _check_densidad_minima(grid, err)
    _check_desalineacion_x3_p(grid, err)
    _check_secuencia_p_invalida(grid, err)
    _check_incompatible_equivalente(grid, err)
    _check_expansion_bloqueada_temprana(grid, err)
    _check_inconsistencia_propagacion_global(grid, err)
    _check_desbalance_ejes(grid, err)
    _check_transformacion_invalida(grid, err)
    _check_incoherencia_serie_base(grid, err)

    if completo:
        for nombre, v in [
            ("tensor.x2", grid.x2),
            ("tensor.x3", grid.x3),
            ("tensor.x4", grid.x4),
            ("tensor.y2", grid.y2),
            ("tensor.y3 (P)", grid.y3),
            ("tensor.y4", grid.y4),
        ]:
            if v is None:
                _append(
                    err,
                    "COMPLETITUD",
                    "Cuadrícula completa requerida para cierre del sistema",
                    nombre,
                    "celda vacía",
                )

    return ResultadoConsistencia(ok=len(err) == 0, contradicciones=err)


def es_valido(grid: Grid) -> bool:
    """
    Validación fuerte alineada al generador real: anclas (y3[2], y4[3]), núcleo x3–P,
    P obligatorio en variante f, sin colisión P/ancla, continuidad P en el plan a→f,
    y modo 9428 (ancla desde equivalente[1]).

    Desactivado temporalmente (no verificado en corpus): cierre x3+pivote+P ∈ {10,20} /
    suma_objetivo; firma modular (P+x3+r) vs triple equivalente.

    ``es_consistente`` conserva el resto de comprobaciones; aquí solo el filtro duro previo al ranking.
    """
    # --- Dominio ---
    for v in (grid.x2, grid.x3, grid.x4, grid.y2, grid.y3, grid.y4):
        if v is not None and not _digito_ok(v):
            return False

    piv = grid.pivote
    exp_y32 = esperado_y3_2(grid.semilla, grid.equivalente)

    # --- 1) Anclas observables ---
    if grid.ancla_y3_2 is not None and int(grid.ancla_y3_2) != exp_y32:
        return False
    if grid.ancla_y4_3 is not None and int(grid.ancla_y4_3) != piv:
        return False
    if grid.y3_fila is not None and grid.y3_fila[2] is not None:
        if int(grid.y3_fila[2]) != exp_y32:
            return False
    if grid.y4_fila is not None and len(grid.y4_fila) > 3 and grid.y4_fila[3] is not None:
        if int(grid.y4_fila[3]) != piv:
            return False

    if not _modo_especial_9428_ok(grid):
        return False

    # --- Núcleo / variante f ---
    if grid.letra.lower() == "f" and grid.y3 is None:
        return False
    if grid.x3 is None or grid.y3 is None:
        return False

    p = int(grid.y3) % 10

    # --- Colisión funcional P con rol de ancla y3[2] ---
    if p == exp_y32 % 10:
        return False

    # --- CONTINUIDAD_P: ranura letra ↔ P del plan X ---
    if not _continuidad_p_ok(grid):
        return False

    return True


def es_consistente_bool(grid: Grid, *, completo: bool = False) -> bool:
    return es_consistente(grid, completo=completo).ok


def explicar_fallo(res: ResultadoConsistencia) -> str:
    if res.ok:
        return "consistente"
    c = res.contradicciones[0]
    return f"[{c.codigo}] {c.donde}: {c.detalle} — regla: {c.regla}"
