"""Reconhecimento da Fase 9: lojas ainda sem fonte.

Por loja: 1 robots.txt + 1 busca HTML (só se o robots permitir), tudo pelo
ClienteEducado, sem retry. A resposta vai para dados/bruto (vira fixture) e o
leitor diz de onde dá para ler preço. Não liga nada no worker: imprime a
tabela para decisão do dono.

    python -m coleta.recon --dry-run     # URLs e totais, sem rede
    python -m coleta.recon               # só com o "pode" do dono

Fora daqui, por decisão do dono: Magalu, Fast Shop e Carrefour (só com ele
olhando), Amazon (decisão de segunda), Mercado Livre (só API oficial), Época.
PBKids, Riachuelo, C&A e Beleza na Web: o robots.txt já proibiu a API em 26/11;
a busca HTML delas entra aqui só se o robots permitir (o cliente checa).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from dataclasses import dataclass, replace
from urllib.parse import quote, urlsplit

from coleta.http import (
    BloqueadaPorRobots, ColetaRecusada, FalhaTransitoria, MoldeQuebrado, Resposta, SinalDeBloqueio,
    parece_desafio,
)


@dataclass(frozen=True)
class Candidata:
    slug: str
    molde: str  # URL de busca com {q}; formato a confirmar no próprio recon
    termo: str


# Termo coerente com o que a loja vende; moldes de URL de busca públicos.
CANDIDATAS = [
    Candidata("americanas", "https://www.americanas.com.br/busca/{q}", "ps5"),
    Candidata("casas-bahia", "https://www.casasbahia.com.br/{q}/b", "ps5"),
    Candidata("ponto", "https://www.pontofrio.com.br/{q}/b", "ps5"),
    Candidata("shopee", "https://shopee.com.br/search?keyword={q}", "dixit"),
    Candidata("aliexpress", "https://pt.aliexpress.com/w/wholesale-{q}.html", "controle-ps5"),
    Candidata("shein", "https://br.shein.com/pdsearch/{q}/", "camiseta"),
    Candidata("centauro", "https://www.centauro.com.br/busca/{q}", "tenis"),
    Candidata("netshoes", "https://www.netshoes.com.br/busca?q={q}", "tenis"),
    Candidata("dafiti", "https://www.dafiti.com.br/catalog/?q={q}", "tenis"),
    Candidata("zattini", "https://www.zattini.com.br/busca?q={q}", "camiseta"),
    Candidata("renner", "https://www.lojasrenner.com.br/b?Ntt={q}", "camiseta"),
    Candidata("leroy-merlin", "https://www.leroymerlin.com.br/search?term={q}", "furadeira"),
    Candidata("pbkids", "https://www.pbkids.com.br/busca?q={q}", "dixit"),
    Candidata("riachuelo", "https://www.riachuelo.com.br/busca?q={q}", "camiseta"),
    Candidata("cea", "https://www.cea.com.br/busca?q={q}", "camiseta"),
    Candidata("beleza-na-web", "https://www.belezanaweb.com.br/busca?q={q}", "perfume"),
]


def url_busca(c: Candidata) -> str:
    return c.molde.format(q=quote(c.termo))


# Estado embutido de SPA: se existe, o parser lê JSON em vez de HTML.
ESTADOS = ["__NEXT_DATA__", "__PRELOADED_STATE__", "__INITIAL_STATE__", "__APOLLO_STATE__",
           "__NUXT__", "__STATE__", "__RUNTIME_CONFIG__"]
PRECO = re.compile(r"R\$\s*(?:&nbsp;|\xa0)?\s*\d{1,3}(?:\.\d{3})*,\d{2}")
JSON_LD = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)


def ler_pagina(html: str) -> dict:
    """De onde dá para ler preço: estados embutidos, JSON-LD, ou só o HTML."""
    fontes = [e for e in ESTADOS if e in html]
    for bloco in JSON_LD.findall(html):
        if '"Product"' in bloco or '"Offer"' in bloco:
            fontes.append("JSON-LD Product")
            break
    resp = Resposta(200, {}, html.encode("utf-8", "ignore"), "https://x")
    return {"fontes": fontes, "precos_no_html": len(PRECO.findall(html)), "desafio": parece_desafio(resp),
            "tamanho_kb": len(html.encode("utf-8", "ignore")) // 1024}


def plano(candidatas: list[Candidata]) -> list[str]:
    linhas = []
    for c in candidatas:
        host = urlsplit(url_busca(c)).hostname
        linhas += [f"GET https://{host}/robots.txt", f"GET {url_busca(c)}"]
    linhas.append(f"total: no máximo {2 * len(candidatas)} requisições, {len(candidatas)} lojas, "
                  "1 por vez por loja, >= 5 s entre as duas, sem retry")
    return linhas


async def sondar(cliente, c: Candidata) -> dict:
    linha = {"loja": c.slug, "url": url_busca(c)}
    try:
        r = await cliente.obter(url_busca(c), tipo="recon")
        linha.update(status=r.status, **ler_pagina(r.texto()))
    except BloqueadaPorRobots:
        linha.update(resultado="robots.txt proíbe a busca")
    except SinalDeBloqueio as e:
        linha.update(resultado=f"BLOQUEIO: {e}")
    except MoldeQuebrado as e:
        linha.update(resultado=f"molde de URL errado ou conteúdo inesperado: {e}")
    except (ColetaRecusada, FalhaTransitoria) as e:
        linha.update(resultado=f"falhou ({type(e).__name__}: {e})")
    return linha


async def main(argv: list[str]) -> int:
    if "--dry-run" in argv:
        print("Reconhecimento da Fase 9 (pelo ClienteEducado; nada liga no worker):")
        print("\n".join(f"   {l}" for l in plano(CANDIDATAS)))
        return 0
    from config import ConfigColeta
    from coleta.estado import Estado
    from coleta.http import ClienteEducado, TransporteCurlCffi

    cfg = ConfigColeta.carregar()
    transporte = TransporteCurlCffi()
    cliente = ClienteEducado(Estado(cfg.dir_dados / "coleta.sqlite3"), transporte,
                             replace(cfg, backoff_retry_s=()), dir_bruto=cfg.dir_dados / "bruto")
    try:
        linhas = await asyncio.gather(*(sondar(cliente, c) for c in CANDIDATAS))
    finally:
        await transporte.fechar()
    print(json.dumps(linhas, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    from config import ConfigColeta

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(ConfigColeta.carregar().dir_dados / "coleta.log",
                                                      encoding="utf-8")])
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.exit(asyncio.run(main(sys.argv[1:])))
