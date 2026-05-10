#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sirve la carpeta del proyecto (index.html) y expone el motor real:

  POST /api/seleccionar  {"seed": "9428"}
  POST /api/seleccionar  {"seed": "9428", "numero": "3207"}   # opcional

  → candidatos = generar_candidatos(semilla, incluir_anclas=True)
  → mejor = seleccionar_mejor(candidatos)

No modifica motor.py ni la funcion seleccionar_mejor en motor_ext.py.

Uso:
  python serve_motor.py
  http://127.0.0.1:8765/
"""

from __future__ import annotations

import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))
# Replit / Railway / Render suelen definir PORT; localmente 8765.
PORT = int(os.environ.get("NUMEROLOTTO_PORT", os.environ.get("PORT", "8765")))
# 0.0.0.0 = accesible desde el móvil en la misma WiFi. 127.0.0.1 = solo este PC.
BIND_HOST = os.environ.get("NUMEROLOTTO_HOST", "0.0.0.0")

ACLARACION_UI = (
    "El motor selecciona la cuadrícula más consistente (A–F). "
    "Las combinaciones de 4 cifras son el espacio de búsqueda dentro de esa cuadrícula."
)


def _json_response(handler: SimpleHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(data)


def _sanitize4(v: Any) -> str:
    return "".join(ch for ch in str(v) if ch.isdigit()).zfill(4)[-4:]


def build_series_10_from_4(base4: str) -> List[str]:
    """Misma rotación que buildSeries10From4 en index.html (sin cambiar el motor)."""
    s = _sanitize4(base4)
    digits = [int(c) for c in s]
    out: List[str] = []
    for step in range(10):
        out.append("".join(str((d + step) % 10) for d in digits))
    return out


def _digito_celda(v: Any) -> bool:
    if v is None:
        return False
    try:
        n = int(v)
    except (TypeError, ValueError):
        return False
    return 0 <= n <= 9


def brazos_estructurales_ok(g: Any) -> bool:
    """x2,x3,x4,y2,y3,y4 deben estar cerrados antes de cualquier serie automática."""
    return all(_digito_celda(v) for v in (g.x2, g.x3, g.x4, g.y2, g.y3, g.y4))


def base4_para_combinaciones_ganador(g: Any) -> Tuple[Optional[str], str]:
    """
    Base de 4 cifras para las 10 combinaciones de la cuadrícula ganadora.
    Solo x2+x3+x4+P(y3) cuando los seis brazos del tensor están completos.
    No se usa pivote/terminal como parche (evita bases artificiales tipo 9833).
    """
    if not brazos_estructurales_ok(g):
        return (None, "incompleto_estructural")
    x2, x3, x4, p = g.x2, g.x3, g.x4, g.y3
    return (_sanitize4(f"{int(x2)}{int(x3)}{int(x4)}{int(p)}"), "x2_x3_x4_P")


def _top_sugeridas(series10: List[str], eq: Tuple[int, ...], _penalizacion: int) -> List[Dict[str, Any]]:
    """Ranking simple sin fórmulas pesadas: proximidad de suma de dígitos al equivalente + dispersión local."""
    if not series10:
        return []
    target = int(eq[0]) + int(eq[1]) + int(eq[2])
    scored: List[Tuple[int, int, int, str]] = []
    for i, s in enumerate(series10):
        sd = sum(int(c) for c in s)
        dist = abs(sd - target)
        spread = sum(abs(int(s[j]) - int(s[j + 1])) for j in range(3))
        scored.append((dist, spread, i, s))
    scored.sort(key=lambda t: (t[0], t[1], t[2]))
    out: List[Dict[str, Any]] = []
    for dist, spread, i, s in scored[:3]:
        out.append(
            {
                "combinacion": s,
                "variacion": i + 1,
                "delta_suma_digitos": dist,
                "dispersion_adyacente": spread,
            }
        )
    return out


def _run_seleccion(seed: str, numero: Optional[str] = None) -> Dict[str, Any]:
    os.chdir(ROOT)
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from motor import es_valido  # noqa: WPS433
    from motor_ext import (
        compute_equivalent,
        evaluar,
        generar_candidatos,
        propagar_tensor_desde_ganador,
        seleccionar_mejor,
    )

    s = _sanitize4(seed)
    num_in: Optional[str] = None
    if numero is not None and str(numero).strip() != "":
        num_in = _sanitize4(numero)

    candidatos = generar_candidatos(s, incluir_anclas=True)
    mejor = seleccionar_mejor(candidatos)
    propagacion_log: Optional[str] = None
    propagacion_alternativa: Optional[Dict[str, Any]] = None
    if num_in:
        mejor, log_lines = propagar_tensor_desde_ganador(mejor, num_in)
        propagacion_log = "\n".join(log_lines)
        if mejor.x2 is None:
            for g in candidatos:
                if g.letra == mejor.letra:
                    continue
                g_alt, alt_log = propagar_tensor_desde_ganador(g, num_in)
                if g_alt.x2 is not None:
                    propagacion_alternativa = {
                        "letra": g_alt.letra,
                        "x2": g_alt.x2,
                        "x3": g_alt.x3,
                        "x4": g_alt.x4,
                        "y2": g_alt.y2,
                        "y3": g_alt.y3,
                        "y4": g_alt.y4,
                        "suma_objetivo": g_alt.suma_objetivo,
                        "log": "\n".join(alt_log),
                    }
                    propagacion_log = (
                        propagacion_log
                        + "\n\n--- Encaje del sorteo en otra cuadricula (referencia, sin cambiar la seleccion del motor) ---\n"
                        + propagacion_alternativa["log"]
                    )
                    break

    eq, _, _ = compute_equivalent(s)
    eq_list = list(eq)
    ev_mejor = evaluar(mejor)

    filas = []
    for g in candidatos:
        ev = evaluar(g)
        filas.append(
            {
                "letra": g.letra,
                "penalizacion": ev.penalizacion,
                "falla_dura": ev.falla_dura,
                "es_valido": es_valido(g),
                "n_fallos": len(ev.fallos),
                "x3": g.x3,
                "y3": g.y3,
                "suma_objetivo": g.suma_objetivo,
                "codigos_fallo": [c.codigo for c in ev.fallos],
            }
        )

    base4, tipo_base = base4_para_combinaciones_ganador(mejor)
    series10: List[str] = build_series_10_from_4(base4) if base4 else []
    estructura_cerrada = brazos_estructurales_ok(mejor)
    series_disponibles = len(series10) == 10
    mensaje_series: Optional[str] = None
    if not estructura_cerrada:
        mensaje_series = (
            "Cuadrícula parcialmente propagada. "
            "Esperando cierre estructural. "
            "Series no disponibles."
        )

    coincidencia = False
    combinacion_encontrada: Optional[str] = None
    # Sin rotación de 10 no se afirma pertenencia ni rechazo frente al sorteo.
    if num_in and series10:
        if num_in in series10:
            coincidencia = True
            combinacion_encontrada = num_in

    top_sugeridas = _top_sugeridas(series10, tuple(eq), ev_mejor.penalizacion)

    return {
        "ok": True,
        "aclaracion": ACLARACION_UI,
        "seed": s,
        "equivalente": eq_list,
        "ganador": {
            "letra": mejor.letra,
            "x2": mejor.x2,
            "x3": mejor.x3,
            "x4": mejor.x4,
            "y2": mejor.y2,
            "y3": mejor.y3,
            "y4": mejor.y4,
            "suma_objetivo": mejor.suma_objetivo,
            "penalizacion": ev_mejor.penalizacion,
        },
        "candidatos": filas,
        "base4_usada": base4,
        "tipo_base": tipo_base,
        "estructura_cerrada": estructura_cerrada,
        "series_disponibles": series_disponibles,
        "mensaje_series": mensaje_series,
        "series10": series10,
        "coincidencia": coincidencia,
        "combinacion_encontrada": combinacion_encontrada,
        "numero_solicitado": num_in,
        "top_sugeridas": top_sugeridas,
        "propagacion_log": propagacion_log,
        "propagacion_alternativa": propagacion_alternativa,
    }


class MotorHTTPRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_OPTIONS(self) -> None:
        if self.path.startswith("/api/"):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
        else:
            super().do_OPTIONS()

    def do_POST(self) -> None:
        if self.path != "/api/seleccionar":
            self.send_error(404)
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(n).decode("utf-8") if n else "{}"
            body = json.loads(raw)
            seed = body.get("seed", "0000")
            numero = body.get("numero")
            if numero is not None and str(numero).strip() == "":
                numero = None
        except (json.JSONDecodeError, ValueError) as e:
            _json_response(self, 400, {"ok": False, "error": str(e)})
            return
        try:
            payload = _run_seleccion(seed, numero)
        except RuntimeError as e:
            _json_response(self, 422, {"ok": False, "error": str(e), "seed": seed})
            return
        except Exception as e:  # noqa: BLE001
            _json_response(self, 500, {"ok": False, "error": str(e)})
            return
        _json_response(self, 200, payload)


def main() -> None:
    os.chdir(ROOT)
    server = HTTPServer((BIND_HOST, PORT), MotorHTTPRequestHandler)
    print("NUMEROLOTTO PRO — motor enlazado")
    print("  Carpeta:", ROOT)
    print("  Escucha: %s:%s (NUMEROLOTTO_HOST / NUMEROLOTTO_PORT)" % (BIND_HOST, PORT))
    print("  En este PC:  http://127.0.0.1:%s/" % PORT)
    if BIND_HOST in ("0.0.0.0", "::"):
        print("  Desde el móvil (misma WiFi): http://IP_DE_ESTE_PC:%s/" % PORT)
        print("    (Sustituye IP_DE_ESTE_PC por la IPv4 que muestre ipconfig; ver README o guía.)")
    print("  API: POST http://127.0.0.1:%s/api/seleccionar" % PORT)
    print("Cierra con Ctrl+C.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")


if __name__ == "__main__":
    main()
