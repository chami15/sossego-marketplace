"""Recria um banco do zero com as migrations reais (testes e e2e do frontend).

Uso: python -m db.recriar postgresql://.../sossego_e2e
Recusa o banco principal: só recria nomes que terminam em _test ou _e2e.
"""

from __future__ import annotations

import sys

import psycopg
from psycopg import sql

from db.migrar import migrar


def recriar(url: str) -> str:
    nome = psycopg.conninfo.conninfo_to_dict(url)["dbname"]
    # Trava contra apagar o histórico real por engano de URL.
    if not nome.endswith(("_test", "_e2e")):
        raise ValueError(f"recuso recriar {nome!r}: só bancos *_test ou *_e2e")
    admin = psycopg.conninfo.make_conninfo(url, dbname="postgres")
    with psycopg.connect(admin, autocommit=True, connect_timeout=3) as c:
        c.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(nome)))
        c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(nome)))
    migrar(url, verbose=False)
    return url


if __name__ == "__main__":
    print("recriado:", recriar(sys.argv[1]))
