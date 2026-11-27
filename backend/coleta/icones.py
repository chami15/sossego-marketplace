"""Ícones das lojas do onboarding: download único pelo serviço de favicons do Google.

Nenhuma requisição vai para as lojas (decisão do dono, 27/11): só para
www.google.com, pelo ClienteEducado. Ícone pequeno, genérico ou fora do formato
não é salvo; a tela mostra o monograma da loja.

Uso: python -m coleta.icones [--dry-run]
"""

from __future__ import annotations

import asyncio
import struct
import sys
from pathlib import Path
from urllib.parse import quote

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "frontend" / "public" / "lojas"
MOLDE = "https://www.google.com/s2/favicons?domain={dominio}&sz=128"
LADO_MINIMO = 48  # abaixo disso o Google ampliou um favicon de 16 px: fica borrado

PNG = b"\x89PNG\r\n\x1a\n"


def url_do_icone(dominio: str) -> str:
    return MOLDE.format(dominio=quote(dominio, safe=""))


def avaliar(status: int, corpo: bytes) -> tuple[bool, str]:
    """(serve?, motivo). O Google responde 404 com um globo genérico quando não acha."""
    if status != 200:
        return False, f"HTTP {status} (ícone genérico)"
    if not corpo.startswith(PNG) or len(corpo) < 24:
        return False, "não é PNG"
    largura, altura = struct.unpack(">II", corpo[16:24])
    if min(largura, altura) < LADO_MINIMO:
        return False, f"pequeno ({largura}x{altura})"
    return True, f"{largura}x{altura}"


def lojas(url_banco: str) -> list[tuple[str, str]]:
    import psycopg

    with psycopg.connect(url_banco) as c:
        itens = c.execute("SELECT slug, dominio FROM loja ORDER BY slug").fetchall()
    return [(s, DOMINIO_DO_SITE.get(s, d)) for s, d in itens]


# O domínio cadastrado do ML é o da API; o ícone é o do site. Só vira parâmetro
# da URL do Google: nenhuma requisição vai ao ML.
DOMINIO_DO_SITE = {"mercado-livre": "www.mercadolivre.com.br"}


def plano(itens: list[tuple[str, str]]) -> list[str]:
    linhas = ["GET https://www.google.com/robots.txt   (se não estiver em cache)"]
    linhas += [f"GET {url_do_icone(d)}   -> lojas/{s}.png" for s, d in itens]
    return linhas


async def baixar(cliente, itens: list[tuple[str, str]], destino: Path = DESTINO) -> list[tuple[str, bool, str]]:
    destino.mkdir(parents=True, exist_ok=True)
    feitos = []
    for slug, dominio in itens:
        try:
            res = await cliente.obter(url_do_icone(dominio), tipo="produto")
            ok, motivo = avaliar(res.status, res.corpo or b"")
        except Exception as e:  # bloqueio/robots/falha: para tudo, sem insistir
            feitos.append((slug, False, f"{type(e).__name__}: {e}"))
            break
        if ok:
            (destino / f"{slug}.png").write_bytes(res.corpo)
        feitos.append((slug, ok, motivo))
    return feitos


async def _main(argv: list[str]) -> int:
    from config import ConfigColeta, database_url

    itens = lojas(database_url())
    if "--dry-run" in argv:
        print("Ícones das lojas, pelo ClienteEducado (host: www.google.com; nenhuma loja):")
        print("\n".join(f"   {linha}" for linha in plano(itens)))
        print(f"   total: até {len(itens) + 1} requisições, uma por vez, ≥ 5 s + jitter")
        return 0
    from coleta.estado import Estado
    from coleta.http import ClienteEducado, TransporteCurlCffi

    cfg = ConfigColeta.carregar()
    transporte = TransporteCurlCffi()
    try:
        cliente = ClienteEducado(Estado(cfg.dir_dados / "coleta.sqlite3"), transporte, cfg,
                                 dir_bruto=cfg.dir_dados / "bruto")
        for slug, ok, motivo in await baixar(cliente, itens):
            print(f"{'salvo ' if ok else 'monograma'}  {slug:15} {motivo}")
    finally:
        await transporte.fechar()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
