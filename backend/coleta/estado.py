"""Estado persistente da coleta educada: log de requisições, orçamento,
circuit breaker, cache HTTP e cache de robots.txt.

Fica em SQLite local (dados/coleta.sqlite3), não no Postgres, de propósito:
a trava de segurança precisa funcionar mesmo com o banco principal fora do
ar, e precisa sobreviver a reinício de processo. Se o worker reiniciar, o
orçamento gasto e o breaker aberto continuam valendo.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS requisicao (
    id          INTEGER PRIMARY KEY,
    loja        TEXT NOT NULL,
    url         TEXT NOT NULL,
    tipo        TEXT NOT NULL,
    inicio      REAL NOT NULL,
    status      INTEGER,
    duracao_ms  INTEGER,
    bytes       INTEGER,
    resultado   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_requisicao_loja_inicio ON requisicao (loja, inicio);

CREATE TABLE IF NOT EXISTS breaker (
    loja              TEXT PRIMARY KEY,
    sinais_seguidos   INTEGER NOT NULL DEFAULT 0,
    nivel             INTEGER NOT NULL DEFAULT 0,
    pausada_ate       REAL NOT NULL DEFAULT 0,
    desligada         INTEGER NOT NULL DEFAULT 0,
    ultimo_sinal_em   REAL,
    motivo            TEXT
);

CREATE TABLE IF NOT EXISTS cache_http (
    url           TEXT PRIMARY KEY,
    obtido_em     REAL NOT NULL,
    status        INTEGER NOT NULL,
    cabecalhos    TEXT NOT NULL,
    corpo         BLOB NOT NULL,
    etag          TEXT,
    last_modified TEXT
);

CREATE TABLE IF NOT EXISTS robots (
    host       TEXT PRIMARY KEY,
    obtido_em  REAL NOT NULL,
    status     INTEGER,
    conteudo   TEXT NOT NULL
);
"""


@dataclass
class EstadoBreaker:
    loja: str
    sinais_seguidos: int = 0
    nivel: int = 0
    pausada_ate: float = 0.0
    desligada: bool = False
    ultimo_sinal_em: float | None = None
    motivo: str | None = None


@dataclass
class EntradaCache:
    url: str
    obtido_em: float
    status: int
    cabecalhos: dict[str, str]
    corpo: bytes
    etag: str | None
    last_modified: str | None


class Estado:
    def __init__(self, caminho: Path | str = ":memory:"):
        if caminho != ":memory:":
            Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(caminho), isolation_level=None, timeout=30)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(ESQUEMA)

    # --- log e orçamento -------------------------------------------------
    def registrar(self, *, loja, url, tipo, inicio, status, duracao_ms, bytes_, resultado) -> None:
        self.db.execute(
            "INSERT INTO requisicao (loja, url, tipo, inicio, status, duracao_ms, bytes, resultado)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (loja, url, tipo, inicio, status, duracao_ms, bytes_, resultado),
        )

    def enviadas_desde(self, loja: str, desde: float) -> int:
        # Só conta o que saiu pela rede: acerto de cache e bloqueio local não gastam orçamento.
        (n,) = self.db.execute(
            "SELECT count(*) FROM requisicao WHERE loja=? AND inicio>=? AND resultado NOT IN"
            " ('cache','bloqueada_local')",
            (loja, desde),
        ).fetchone()
        return n

    def mais_antiga_enviada_desde(self, loja: str, desde: float) -> float | None:
        (t,) = self.db.execute(
            "SELECT min(inicio) FROM requisicao WHERE loja=? AND inicio>=? AND resultado NOT IN"
            " ('cache','bloqueada_local')",
            (loja, desde),
        ).fetchone()
        return t

    def ultima_enviada(self, loja: str) -> float | None:
        (t,) = self.db.execute(
            "SELECT max(inicio) FROM requisicao WHERE loja=? AND resultado NOT IN"
            " ('cache','bloqueada_local')",
            (loja,),
        ).fetchone()
        return t

    def lojas_com_atividade(self) -> list[str]:
        linhas = self.db.execute(
            "SELECT loja FROM requisicao UNION SELECT loja FROM breaker ORDER BY 1"
        ).fetchall()
        return [l for (l,) in linhas]

    # --- breaker ---------------------------------------------------------
    def breaker(self, loja: str) -> EstadoBreaker:
        linha = self.db.execute(
            "SELECT loja, sinais_seguidos, nivel, pausada_ate, desligada, ultimo_sinal_em, motivo"
            " FROM breaker WHERE loja=?",
            (loja,),
        ).fetchone()
        if not linha:
            return EstadoBreaker(loja=loja)
        return EstadoBreaker(*linha[:4], bool(linha[4]), *linha[5:])

    def salvar_breaker(self, b: EstadoBreaker) -> None:
        self.db.execute(
            "INSERT INTO breaker (loja, sinais_seguidos, nivel, pausada_ate, desligada, ultimo_sinal_em, motivo)"
            " VALUES (?,?,?,?,?,?,?) ON CONFLICT(loja) DO UPDATE SET"
            " sinais_seguidos=excluded.sinais_seguidos, nivel=excluded.nivel,"
            " pausada_ate=excluded.pausada_ate, desligada=excluded.desligada,"
            " ultimo_sinal_em=excluded.ultimo_sinal_em, motivo=excluded.motivo",
            (b.loja, b.sinais_seguidos, b.nivel, b.pausada_ate, int(b.desligada), b.ultimo_sinal_em, b.motivo),
        )

    # --- cache HTTP ------------------------------------------------------
    def cache(self, url: str) -> EntradaCache | None:
        linha = self.db.execute(
            "SELECT url, obtido_em, status, cabecalhos, corpo, etag, last_modified FROM cache_http WHERE url=?",
            (url,),
        ).fetchone()
        if not linha:
            return None
        return EntradaCache(linha[0], linha[1], linha[2], json.loads(linha[3]), linha[4], linha[5], linha[6])

    def guardar_cache(self, e: EntradaCache) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO cache_http (url, obtido_em, status, cabecalhos, corpo, etag, last_modified)"
            " VALUES (?,?,?,?,?,?,?)",
            (e.url, e.obtido_em, e.status, json.dumps(e.cabecalhos), e.corpo, e.etag, e.last_modified),
        )

    # --- robots ----------------------------------------------------------
    def robots(self, host: str) -> tuple[float, int | None, str] | None:
        return self.db.execute(
            "SELECT obtido_em, status, conteudo FROM robots WHERE host=?", (host,)
        ).fetchone()

    def guardar_robots(self, host: str, obtido_em: float, status: int | None, conteudo: str) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO robots (host, obtido_em, status, conteudo) VALUES (?,?,?,?)",
            (host, obtido_em, status, conteudo),
        )
