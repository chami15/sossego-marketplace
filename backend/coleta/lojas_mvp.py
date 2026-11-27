"""Lojas do MVP: como montar a URL de busca e a cada quanto tempo recoletar.

Recon mínimo de 26/11/2026 (detalhes em docs/fontes/README.md):
- amazon, ludopedia: molde verificado, preço na página de busca.
- ri-happy: busca HTML proibida pelo robots.txt (/*?_q=); usa a API pública VTEX.
- mercado-livre: interstício anti-robô na busca HTML. Inativa até a API oficial.
- magalu: 403 na primeira busca. Inativa: bloqueou = parou.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Callable
from urllib.parse import quote, quote_plus

from coleta import ml_api


@dataclass(frozen=True)
class Loja:
    slug: str
    nome: str
    hosts: tuple[str, ...]             # sufixos de host que pertencem à loja
    url_busca: Callable[[str], str]
    periodo_min: int                   # intervalo entre rodadas de recoleta
    categorias: frozenset[str]         # onde faz sentido buscar
    verificada: bool = False           # molde de URL confirmado no recon?
    ativa: bool = True                 # False = fora do worker
    motivo_inativa: str = ""
    # Termo com espaço deu 400 (Ri Happy, 27/11): fica fora até a codificação ser confirmada.
    so_uma_palavra: bool = False


def _slug_ml(termo: str) -> str:
    return quote(termo.strip().lower().replace(" ", "-"))


LOJAS: dict[str, Loja] = {
    l.slug: l
    for l in [
        # Só API oficial (api.mercadolibre.com). Ativa quando o .env tiver credenciais.
        Loja("mercado-livre", "Mercado Livre", ("mercadolivre.com.br", "mercadolibre.com"),
             ml_api.url_busca, 60,
             frozenset({"eletronicos", "tabuleiro"}), ativa=ml_api.credenciais() is not None,
             motivo_inativa="HTML bloqueado (interstício); aguarda ML_CLIENT_ID/SECRET no .env"),
        Loja("amazon", "Amazon", ("amazon.com.br",),
             lambda t: f"https://www.amazon.com.br/s?k={quote_plus(t)}",
             120,  # mais propensa a captcha: metade da frequência, também na Black Friday
             frozenset({"eletronicos", "tabuleiro"}), verificada=True, ativa=False,
             # 27/11 15:11: desafio Akamai (bm-verify). O dono decidiu desligar, não esperar o breaker.
             motivo_inativa="bloqueio: desafio Akamai na BF (27/11); desligada pelo dono até segunda 30/11"),
        Loja("magalu", "Magalu", ("magazineluiza.com.br",),
             lambda t: f"https://www.magazineluiza.com.br/busca/{quote(t)}/", 60,
             frozenset({"eletronicos", "tabuleiro"}), ativa=False,
             motivo_inativa="bloqueio: HTTP 403 na 1ª busca; nova tentativa só depois da BF"),
        Loja("ri-happy", "Ri Happy", ("rihappy.com.br",),
             # API pública de catálogo VTEX: JSON leve, permitida pelo robots.txt.
             lambda t: f"https://www.rihappy.com.br/api/catalog_system/pub/products/search?ft={quote_plus(t)}&_from=0&_to=19",
             60, frozenset({"tabuleiro"}), so_uma_palavra=True),
        # robots.txt proíbe /busca/*? (com query); /busca/<termo-com-hifens> é permitido.
        # Recon 26/11 19h25 ok (docs/fontes/kabum.md); ligado pelo dono no mesmo dia.
        Loja("kabum", "Kabum", ("kabum.com.br",),
             lambda t: f"https://www.kabum.com.br/busca/{_slug_ml(t)}",
             120, frozenset({"eletronicos"}), verificada=True),
        Loja("ludopedia", "Ludopedia", ("ludopedia.com.br",),
             lambda t: f"https://www.ludopedia.com.br/search?search={quote_plus(t)}", 60,
             frozenset({"tabuleiro"}), verificada=True),
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
