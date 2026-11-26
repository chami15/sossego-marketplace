"""Detecta quais lojas expõem a API pública de catálogo VTEX.

Por loja: 1 robots.txt + 1 GET em /api/catalog_system/pub/products/search
(se o robots permitir). Tudo pelo ClienteEducado. Não liga nada no worker:
só imprime a tabela para decisão do dono.

    python -m coleta.detectar_vtex
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from urllib.parse import quote_plus

from config import ConfigColeta
from coleta.estado import Estado
from coleta.http import (
    BloqueadaPorRobots, ClienteEducado, ColetaRecusada, FalhaTransitoria, MoldeQuebrado,
    SinalDeBloqueio, TransporteCurlCffi,
)

# (slug, domínio, termo de teste coerente com o que a loja vende)
CANDIDATAS = [
    ("pbkids", "www.pbkids.com.br", "dixit"),
    ("centauro", "www.centauro.com.br", "tenis"),
    ("netshoes", "www.netshoes.com.br", "tenis"),
    ("dafiti", "www.dafiti.com.br", "tenis"),
    ("zattini", "www.zattini.com.br", "tenis"),
    ("renner", "www.lojasrenner.com.br", "camiseta"),
    ("riachuelo", "www.riachuelo.com.br", "camiseta"),
    ("cea", "www.cea.com.br", "camiseta"),
    ("carrefour", "www.carrefour.com.br", "notebook"),
    ("fast-shop", "www.fastshop.com.br", "notebook"),
    ("kabum", "www.kabum.com.br", "notebook"),
    ("epoca", "www.epocacosmeticos.com.br", "perfume"),
    ("sephora", "www.sephora.com.br", "perfume"),
    ("beleza-na-web", "www.belezanaweb.com.br", "perfume"),
    ("leroy-merlin", "www.leroymerlin.com.br", "furadeira"),
]


def url_api(dominio: str, termo: str) -> str:
    return f"https://{dominio}/api/catalog_system/pub/products/search?ft={quote_plus(termo)}&_from=0&_to=2"


def _vtex_json(resp) -> bool:
    if "json" not in resp.cabecalhos.get("content-type", ""):
        return False
    try:
        dados = json.loads(resp.corpo)
    except ValueError:
        return False
    return isinstance(dados, list) and len(dados) > 0 and "productId" in dados[0]


async def sondar(cliente: ClienteEducado, slug: str, dominio: str, termo: str) -> dict:
    linha = {"loja": slug, "dominio": dominio, "termo": termo}
    try:
        r = await cliente.obter(url_api(dominio, termo), tipo="recon", validar=_vtex_json)
        dados = json.loads(r.corpo)
        p = dados[0]
        oferta = p["items"][0]["sellers"][0]["commertialOffer"]
        linha.update(resultado="VTEX ok", status=r.status,
                     vtex_header=any(k.startswith("x-vtex") for k in r.cabecalhos),
                     exemplo=f"{p['productName'][:45]} | R$ {oferta['Price']}",
                     ean=bool(p["items"][0].get("ean")))
    except BloqueadaPorRobots:
        linha.update(resultado="robots proíbe a API")
    except MoldeQuebrado as e:
        linha.update(resultado=f"não é VTEX pública ({e})")
    except SinalDeBloqueio as e:
        linha.update(resultado=f"BLOQUEIO ({e})")
    except (ColetaRecusada, FalhaTransitoria) as e:
        linha.update(resultado=f"falhou ({type(e).__name__}: {e})")
    except (KeyError, IndexError, ValueError) as e:
        linha.update(resultado=f"VTEX, mas formato inesperado ({e!r})")
    return linha


async def main() -> int:
    cfg = ConfigColeta.carregar()
    transporte = TransporteCurlCffi()
    cliente = ClienteEducado(Estado(cfg.dir_dados / "coleta.sqlite3"), transporte, cfg,
                             dir_bruto=cfg.dir_dados / "bruto")
    try:
        linhas = await asyncio.gather(*(sondar(cliente, *c) for c in CANDIDATAS))
    finally:
        await transporte.fechar()
    print(json.dumps(linhas, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    cfg = ConfigColeta.carregar()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(cfg.dir_dados / "coleta.log", encoding="utf-8")])
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.exit(asyncio.run(main()))
