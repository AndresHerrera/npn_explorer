# -*- coding: utf-8 -*-
"""Análisis de No Predial (30 dígitos, desglose por componentes)."""

import json
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

_REF: Optional[dict] = None

# Orden fijo de filas (mismo que index.html)
CAMPOS_NPN_ORDEN = [
    "Departamento",
    "Municipio",
    "Zona U/R",
    "Sector",
    "Comuna",
    "Barrio",
    "Vereda/Manzana",
    "Terreno",
    "Condición",
    "Nº Edificio",
    "Nº Piso",
    "Unidad Predial",
]

MSG_NPN_VACIO_NULO = (
    "No corresponde a un número predial válido: el valor está vacío, nulo o no legible."
)


def _load_reference() -> dict:
    global _REF
    if _REF is None:
        p = os.path.join(os.path.dirname(__file__), "npn_predial_reference.json")
        with open(p, "r", encoding="utf-8") as f:
            _REF = json.load(f)
    return _REF


def _normalize_value_text(raw) -> str:
    """Alinea a cadena; intenta respetar dígitos (capas a veces devuelven float/Decimal)."""
    if raw is None:
        return ""
    s = str(raw).strip()
    if s == "" or s.lower() in ("null", "none", "nan", "undefined"):
        return ""
    m = re.match(r"^(\d+)\.0+$", s)
    if m:
        return m.group(1)
    return s


@dataclass
class NpnAnalisis:
    es_valido: bool
    error: str
    filas: List[Tuple[str, str]]  # (etiqueta, celda: valor o valor - descripcion)


def analizar_npn(codigo: str) -> NpnAnalisis:
    """Replica la tabla `res` y la validación analizar()."""
    codigo = (codigo or "").strip()
    if not codigo:
        return NpnAnalisis(False, "", [])

    if len(codigo) != 30 or not codigo.isdigit():
        if len(codigo) > 0:
            return NpnAnalisis(
                False,
                "Debe ingresar un No Predial de 30 dígitos numéricos según la estructura actual",
                [],
            )
        return NpnAnalisis(False, "", [])

    ref = _load_reference()
    zonas = ref["zonas"]
    condiciones = ref["condiciones"]
    departamentos = ref["departamentos"]
    municipios = ref["municipios"]

    dep_codigo = codigo[0:2]
    mun_codigo = codigo[2:5].zfill(3)
    codigo_mun_completo = dep_codigo + mun_codigo
    zona_valor = codigo[5:7]
    c21 = codigo[21:22]

    res = [
        (
            "Departamento",
            dep_codigo,
            departamentos.get(dep_codigo) or "Sin información",
        ),
        (
            "Municipio",
            mun_codigo,
            municipios.get(codigo_mun_completo) or "Sin información",
        ),
        (
            "Zona U/R",
            zona_valor,
            zonas.get(zona_valor) or "Sin información",
        ),
        ("Sector", codigo[7:9], ""),
        ("Comuna", codigo[9:11], ""),
        ("Barrio", codigo[11:13], ""),
        ("Vereda/Manzana", codigo[13:17], ""),
        ("Terreno", codigo[17:21], ""),
        (
            "Condición",
            c21,
            condiciones.get(c21) or "Sin información",
        ),
        ("Nº Edificio", codigo[22:24], ""),
        ("Nº Piso", codigo[24:26], ""),
        ("Unidad Predial", codigo[26:30], ""),
    ]

    filas: List[Tuple[str, str]] = []
    for label, val, desc in res:
        cell = val
        if desc:
            cell = f"{val} - {desc}"
        filas.append((label, cell))
    return NpnAnalisis(True, "", filas)


def formatear_resultado(filas: List[Tuple[str, str]]) -> str:
    if not filas:
        return ""
    lines = []
    for k, v in filas:
        lines.append(f"{k}\n  {v}")
    return "\n".join(lines)
