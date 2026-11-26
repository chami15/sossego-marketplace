"""Configuração do Sossego, lida do ambiente e do arquivo .env.

O .env é relido a cada consulta do kill switch (`coleta_pausada`), para que
mudar SOSSEGO_COLETA_PAUSADA=true pare o worker que já está rodando, sem
reiniciar nada.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parent.parent  # raiz do repositório (ou do worktree)


def raiz_principal() -> Path:
    """De onde vêm .env e dados/. O worker roda de um worktree fixo
    (../sossego-worker) com SOSSEGO_RAIZ_PRINCIPAL apontando para o
    repositório principal: bruto, sqlite, lock e kill switch ficam num lugar só."""
    return Path(os.environ.get("SOSSEGO_RAIZ_PRINCIPAL") or RAIZ)


def _valores() -> dict[str, str]:
    # O ambiente do processo vence o .env: facilita teste e override pontual.
    arquivo = raiz_principal() / ".env"
    valores = {k: v for k, v in dotenv_values(arquivo).items() if v is not None}
    valores.update({k: v for k, v in os.environ.items() if k.startswith(("SOSSEGO_", "ML_"))})
    return valores


def _bool(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "sim", "yes", "on"}


def _lista_s(v: str | None, padrao: list[float]) -> list[float]:
    if not v:
        return padrao
    return [float(x) for x in v.split(",") if x.strip()]


@dataclass(frozen=True)
class ConfigColeta:
    intervalo_min_s: float = 5.0
    jitter_max_s: float = 3.0
    orcamento_hora: int = 60
    orcamento_dia: int = 500
    ttl_busca_s: float = 30 * 60
    ttl_produto_s: float = 50 * 60
    ttl_robots_s: float = 24 * 3600
    timeout_s: float = 20.0
    # Pausas do circuit breaker por nível de reincidência (30 min, 2 h, 6 h).
    pausas_breaker_s: list[float] = field(default_factory=lambda: [1800, 7200, 21600])
    sinais_seguidos_para_desligar: int = 3
    # Janela sem sinal após a qual o nível de reincidência volta a zero.
    esquecer_reincidencia_s: float = 24 * 3600
    backoff_retry_s: list[float] = field(default_factory=lambda: [30, 120])
    # Retry-After acima disto não vira espera: vira pausa da loja.
    max_espera_retry_s: float = 600
    dir_dados: Path = RAIZ / "dados"

    @classmethod
    def carregar(cls) -> "ConfigColeta":
        v = _valores()
        padrao = cls()
        return cls(
            intervalo_min_s=float(v.get("SOSSEGO_INTERVALO_MIN_S", padrao.intervalo_min_s)),
            jitter_max_s=float(v.get("SOSSEGO_JITTER_MAX_S", padrao.jitter_max_s)),
            orcamento_hora=int(v.get("SOSSEGO_ORCAMENTO_HORA", padrao.orcamento_hora)),
            orcamento_dia=int(v.get("SOSSEGO_ORCAMENTO_DIA", padrao.orcamento_dia)),
            ttl_busca_s=float(v.get("SOSSEGO_TTL_BUSCA_S", padrao.ttl_busca_s)),
            ttl_produto_s=float(v.get("SOSSEGO_TTL_PRODUTO_S", padrao.ttl_produto_s)),
            timeout_s=float(v.get("SOSSEGO_TIMEOUT_S", padrao.timeout_s)),
            pausas_breaker_s=_lista_s(v.get("SOSSEGO_PAUSAS_BREAKER_S"), padrao.pausas_breaker_s),
            backoff_retry_s=_lista_s(v.get("SOSSEGO_BACKOFF_RETRY_S"), padrao.backoff_retry_s),
            dir_dados=Path(v.get("SOSSEGO_DIR_DADOS") or raiz_principal() / "dados"),
        )


def database_url(teste: bool = False) -> str:
    v = _valores()
    if teste:
        return v.get("SOSSEGO_DATABASE_URL_TESTE", "postgresql://sossego:sossego@127.0.0.1:5434/sossego_test")
    return v.get("SOSSEGO_DATABASE_URL", "postgresql://sossego:sossego@127.0.0.1:5434/sossego")


def coleta_pausada() -> bool:
    """Kill switch: relê .env e ambiente a cada chamada."""
    return _bool(_valores().get("SOSSEGO_COLETA_PAUSADA"))
