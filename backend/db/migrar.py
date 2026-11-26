"""Aplica as migrations numeradas de db/migrations em ordem, uma vez cada.

    python -m db.migrar            # banco de SOSSEGO_DATABASE_URL
    python -m db.migrar --status

Migration aplicada nunca se edita: o hash é guardado e uma divergência
para tudo com erro, em vez de seguir com o banco num estado desconhecido.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import psycopg

from config import database_url

PASTA = Path(__file__).parent / "migrations"


def _arquivos() -> list[Path]:
    return sorted(PASTA.glob("[0-9][0-9][0-9]_*.sql"))


def migrar(url: str, verbose: bool = True) -> list[str]:
    aplicadas_agora = []
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migration ("
            " versao TEXT PRIMARY KEY, sha256 TEXT NOT NULL, aplicada_em TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        feitas = dict(conn.execute("SELECT versao, sha256 FROM schema_migration").fetchall())
        for arq in _arquivos():
            sql = arq.read_text(encoding="utf-8")
            h = hashlib.sha256(sql.encode()).hexdigest()
            if arq.stem in feitas:
                if feitas[arq.stem] != h:
                    raise RuntimeError(f"{arq.name} foi editada depois de aplicada. Crie a próxima migration.")
                continue
            with conn.transaction():
                conn.execute(sql)
                conn.execute("INSERT INTO schema_migration (versao, sha256) VALUES (%s, %s)", (arq.stem, h))
            aplicadas_agora.append(arq.stem)
            if verbose:
                print(f"aplicada: {arq.name}")
    return aplicadas_agora


if __name__ == "__main__":
    url = database_url()
    if "--status" in sys.argv:
        with psycopg.connect(url) as c:
            for v, t in c.execute("SELECT versao, aplicada_em FROM schema_migration ORDER BY 1"):
                print(v, t)
    else:
        feitas = migrar(url)
        print("nada a aplicar" if not feitas else f"{len(feitas)} migration(s) aplicada(s)")
