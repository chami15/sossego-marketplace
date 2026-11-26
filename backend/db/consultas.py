"""Carrega consultas nomeadas dos arquivos backend/sql/*.sql (`-- name: x`)."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent / "sql"


@cache
def consultas(arquivo: str) -> dict[str, str]:
    texto = (PASTA / f"{arquivo}.sql").read_text(encoding="utf-8")
    partes = re.split(r"^-- name: (\w+)\s*$", texto, flags=re.M)
    return {nome: sql.strip() for nome, sql in zip(partes[1::2], partes[2::2])}
