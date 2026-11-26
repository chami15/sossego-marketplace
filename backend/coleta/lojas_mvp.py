"""Lojas do MVP: como montar a URL de busca e a cada quanto tempo recoletar.

ATENÇÃO: os moldes de URL abaixo são HIPÓTESES ainda não verificadas
(26/11/2026). Serão confirmados no reconhecimento (Fase 0) com uma única
requisição por loja, e só então documentados em docs/fontes/<loja>.md.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Callable
from urllib.parse import quote, quote_plus


@dataclass(frozen=True)
class Loja:
    slug: str
    nome: str
    hosts: tuple[str, ...]             # sufixos de host que pertencem à loja
    url_busca: Callable[[str], str]
    periodo_min: int                   # intervalo entre rodadas de recoleta
    categorias: frozenset[str]         # onde faz sentido buscar
    verificada: bool = False           # molde de URL confirmado no recon?


def _slug_ml(termo: str) -> str:
    return quote(termo.strip().lower().replace(" ", "-"))


LOJAS: dict[str, Loja] = {
    l.slug: l
    for l in [
        Loja("mercado-livre", "Mercado Livre", ("mercadolivre.com.br",),
             lambda t: f"https://lista.mercadolivre.com.br/{_slug_ml(t)}", 60,
             frozenset({"eletronicos", "tabuleiro"})),
        Loja("amazon", "Amazon", ("amazon.com.br",),
             lambda t: f"https://www.amazon.com.br/s?k={quote_plus(t)}",
             120,  # mais propensa a captcha: metade da frequência das outras
             frozenset({"eletronicos", "tabuleiro"})),
        Loja("magalu", "Magalu", ("magazineluiza.com.br",),
             lambda t: f"https://www.magazineluiza.com.br/busca/{quote(t)}/", 60,
             frozenset({"eletronicos", "tabuleiro"})),
        Loja("ri-happy", "Ri Happy", ("rihappy.com.br",),
             lambda t: f"https://www.rihappy.com.br/{quote(t)}?_q={quote_plus(t)}&map=ft", 60,
             frozenset({"tabuleiro"})),
        Loja("ludopedia", "Ludopedia", ("ludopedia.com.br",),
             lambda t: f"https://www.ludopedia.com.br/search?search={quote_plus(t)}", 60,
             frozenset({"tabuleiro"})),
    ]
}


def loja_do_host(host: str) -> str:
    """Breaker e orçamento são por LOJA, não por host: lista.mercadolivre e
    produto.mercadolivre são o mesmo dono e contam juntos."""
    for loja in LOJAS.values():
        if any(host == h or host.endswith("." + h) for h in loja.hosts):
            return loja.slug
    return host.removeprefix("www.")


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()
