"""Imagens de produto: baixadas uma vez do CDN da loja e servidas localmente.

Decisão do dono (27/11): exibir a imagem direto do CDN faria o navegador dele
pedir à loja a cada tela. Aqui, o worker baixa depois da coleta, pelo
ClienteEducado, só as imagens que aparecem em card ou em grupo [[produto]], em
tamanho médio, e grava WebP de até 400 px em dados/imagens/. A tela nunca pede
nada ao CDN.

Cada CDN é uma chave própria no cliente (`cdn:<host>`), com orçamento próprio
(30/h, 150/dia) e o mesmo breaker e robots.txt. Loja desligada ou pausada não
tem o CDN tocado. Bloqueio ou conteúdo inesperado = aquele CDN para na hora.

Uso: python -m coleta.imagens [--dry-run]
     python -m coleta.imagens --tentativa-manual <host> [--dry-run]   # só com o "pode" do dono
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import re
import sys
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urlsplit

import psycopg

from coleta.http import (
    BloqueadaPorRobots,
    ClienteEducado,
    ColetaPausada,
    ColetaRecusada,
    FalhaTransitoria,
)

POR_HORA, POR_DIA = 30, 150
LADO = 400
REFAZER_FALHA_DIAS = 7

# Tamanho médio de cada CDN (verificado nos dados crus de 27/11, docs/fontes/imagens.md).
# Kabum publica _p/_m/_g/_gg/_original da mesma foto; VTEX redimensiona por
# /ids/<id>-L-A/; a capa da Ludopedia já vem pequena (_s). CDN fora da lista não baixa.
_KABUM = re.compile(r"_(?:original|gg|g|m|p)(\.(?:jpe?g|png|webp))$", re.I)
_VTEX = re.compile(r"(/arquivos/ids/\d+)(?:-\d+-\d+)?/")


def url_no_cdn(url: str) -> str | None:
    p = urlsplit(url)
    host = p.hostname or ""
    if host == "images.kabum.com.br":
        return _KABUM.sub(r"_g\1", url) if _KABUM.search(p.path) else url
    if host.endswith(".vteximg.com.br"):
        return _VTEX.sub(rf"\1-{LADO}-{LADO}/", url, count=1)
    if host == "storage.googleapis.com" and p.path.startswith("/ludopedia-capas/"):
        return url
    return None


@dataclass
class Candidata:
    url: str
    loja: str


def candidatas(url_banco: str) -> list[Candidata]:
    """Imagem do card (a da melhor oferta viva) e as dos grupos [[produto]], de
    loja com coleta ativa, que ainda não foram baixadas (ou cuja falha é antiga)."""
    with psycopg.connect(url_banco) as c:
        linhas = c.execute(_CANDIDATAS, {"dias": REFAZER_FALHA_DIAS}).fetchall()
    return [Candidata(u, l) for u, l in linhas if url_no_cdn(u)]


_CANDIDATAS = """
WITH viva AS (
    SELECT DISTINCT ON (produto_id) produto_id, imagem, loja
    FROM oferta_atual
    WHERE ultima_coleta_em >= now() - interval '48 hours' AND em_estoque IS NOT FALSE
    ORDER BY produto_id, preco, loja
), alvo AS (
    SELECT coalesce(p.imagem, v.imagem) AS url, v.loja, 0 AS prioridade
    FROM viva v JOIN produto p ON p.id = v.produto_id
    UNION ALL
    SELECT a.imagem, l.slug, 1
    FROM anuncio a JOIN produto p ON p.id = a.produto_id JOIN loja l ON l.id = a.loja_id
    WHERE p.grupo_manual IS NOT NULL
)
SELECT DISTINCT ON (alvo.url) alvo.url, alvo.loja
FROM alvo JOIN loja l ON l.slug = alvo.loja
WHERE alvo.url IS NOT NULL AND l.coleta_ativa
  AND NOT EXISTS (SELECT 1 FROM imagem_baixada b WHERE b.url = alvo.url
                  AND (b.situacao = 'ok' OR b.tentada_em > now() - make_interval(days => %(dias)s)))
ORDER BY alvo.url, alvo.prioridade
"""


def cliente_de_imagens(estado, transporte, cfg, prefixo: str = "cdn", **extra) -> ClienteEducado:
    return ClienteEducado(estado, transporte, cfg, loja_de=lambda host: f"{prefixo}:{host}",
                          orcamento_de=lambda chave: (POR_HORA, POR_DIA) if chave.startswith("cdn:") else None,
                          **extra)


def nome_do_arquivo(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:20] + ".webp"


def para_webp(corpo: bytes) -> tuple[bytes, int, int]:
    from PIL import Image

    with Image.open(io.BytesIO(corpo)) as img:
        img.thumbnail((LADO, LADO))  # só reduz, nunca amplia
        img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")
        saida = io.BytesIO()
        img.save(saida, "WEBP", quality=80, method=6)
        return saida.getvalue(), img.width, img.height


def _registrar(url_banco, url, situacao, arquivo=None, largura=None, altura=None, motivo=None):
    with psycopg.connect(url_banco, autocommit=True) as c:
        c.execute("""
            INSERT INTO imagem_baixada (url, situacao, arquivo, largura, altura, motivo)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE SET situacao = excluded.situacao, arquivo = excluded.arquivo,
                largura = excluded.largura, altura = excluded.altura, motivo = excluded.motivo,
                tentada_em = now()""", (url, situacao, arquivo, largura, altura, motivo))


async def baixar(cliente: ClienteEducado, url_banco: str, destino: Path,
                 lojas_paradas: set[str] = frozenset()) -> dict:
    """Baixa as candidatas até o orçamento de cada CDN. Devolve o placar."""
    destino.mkdir(parents=True, exist_ok=True)
    feitos = {"ok": 0, "falhou": 0, "parou": []}
    parados: set[str] = set()
    for cand in candidatas(url_banco):
        if cand.loja in lojas_paradas:
            continue
        alvo = url_no_cdn(cand.url)
        host = urlsplit(alvo).hostname
        if host in parados:
            continue
        try:
            res = await cliente.obter(alvo, tipo="imagem")
        except ColetaPausada:
            raise
        except BloqueadaPorRobots:
            _registrar(url_banco, cand.url, "falhou", motivo="robots.txt proíbe")
            feitos["falhou"] += 1
            continue
        except FalhaTransitoria:
            continue  # 5xx/timeout já com retry: tenta na próxima passada
        except ColetaRecusada:
            # Orçamento, pausa, breaker, bloqueio ou conteúdo inesperado: o CDN para aqui.
            parados.add(host)
            feitos["parou"].append(host)
            continue
        if res.status != 200:
            _registrar(url_banco, cand.url, "falhou", motivo=f"HTTP {res.status}")
            feitos["falhou"] += 1
            continue
        try:
            webp, larg, alt = para_webp(res.corpo)
        except Exception as e:  # imagem corrompida ou formato estranho: placeholder
            _registrar(url_banco, cand.url, "falhou", motivo=f"não abriu: {type(e).__name__}")
            feitos["falhou"] += 1
            continue
        nome = nome_do_arquivo(cand.url)
        (destino / nome).write_bytes(webp)
        _registrar(url_banco, cand.url, "ok", nome, larg, alt)
        feitos["ok"] += 1
    return feitos


def lojas_paradas(estado, agora: float) -> set[str]:
    """Lojas com o breaker aberto ou desligadas: o CDN delas também espera."""
    from coleta.lojas_mvp import LOJAS

    paradas = set()
    for slug in LOJAS:
        b = estado.breaker(slug)
        if b.desligada or b.pausada_ate > agora:
            paradas.add(slug)
    return paradas


def cfg_manual(cfg):
    """Tentativa manual: sem retry (o dono autorizou UMA requisição de cada)."""
    return replace(cfg, backoff_retry_s=())


async def tentativa_manual(cliente: ClienteEducado, estado, url_banco: str, destino: Path, host: str) -> str:
    """1 robots.txt + 1 imagem num CDN desligado, por pedido explícito do dono.

    O cliente vem com `robots_indisponivel={host}`, sem retry e com chave de
    breaker própria (prefixo "manual"): a chave `cdn:<host>` do worker continua
    desligada durante a tentativa e só muda no fim. Se o robots.txt
    não responder normalmente, o CDN volta desligado em qualquer caso: o worker
    trataria o mesmo 403 como bloqueio. Segunda tentativa não há."""
    from coleta.estado import EstadoBreaker

    chave = f"cdn:{host}"
    cand = next((c for c in candidatas(url_banco) if urlsplit(url_no_cdn(c.url)).hostname == host), None)
    if cand is None:
        return f"{host}: nenhuma imagem pendente; nada foi pedido."
    alvo = url_no_cdn(cand.url)
    imagem_ok = False
    try:
        res = await cliente.obter(alvo, tipo="imagem")
        if res.status == 200:
            webp, larg, alt = para_webp(res.corpo)
            nome = nome_do_arquivo(cand.url)
            destino.mkdir(parents=True, exist_ok=True)
            (destino / nome).write_bytes(webp)
            _registrar(url_banco, cand.url, "ok", nome, larg, alt)
            imagem_ok, resultado = True, f"imagem 200 ({larg}x{alt})"
        else:
            resultado = f"imagem HTTP {res.status}"
    except (ColetaRecusada, FalhaTransitoria) as e:
        resultado = f"recusada: {e}"
    except Exception as e:  # imagem que não abre
        resultado = f"imagem não abriu: {type(e).__name__}"
    salvo = estado.robots(host)
    robots_normal = salvo is not None and salvo[1] is not None and salvo[1] < 500
    if imagem_ok and robots_normal:
        estado.salvar_breaker(EstadoBreaker(loja=chave))  # religa para o worker
        return f"{host}: robots.txt {salvo[1]}, {resultado}. CDN ligado: o worker segue com o orçamento de sempre."
    b = estado.breaker(chave)
    b.desligada = True
    if imagem_ok:
        b.motivo = (f"tentativa manual 27/11: robots.txt sem resposta normal, {resultado}; "
                    "decisão do dono para tratar o robots 403 como ausente")
    else:
        b.motivo = f"tentativa manual 27/11: {resultado}; sem segunda tentativa"
    estado.salvar_breaker(b)
    return f"{host}: {resultado}. CDN desligado de novo ({b.motivo})."


def plano(itens: list[Candidata], estado=None, agora: float = 0.0) -> list[str]:
    """Volume por CDN. CDN com breaker aberto ou desligado aparece como parado:
    o worker não manda nada para ele (o breaker recusa antes da rede)."""
    por_host = Counter(urlsplit(url_no_cdn(c.url)).hostname for c in itens)
    parados = {}
    for host in por_host:
        b = estado.breaker(f"cdn:{host}") if estado else None
        if b and b.desligada:
            parados[host] = f"DESLIGADO ({b.motivo}); religar: python -m coleta.admin religar cdn:{host}"
        elif b and b.pausada_ate > agora:
            parados[host] = f"EM PAUSA pelo breaker ({b.motivo})"
    linhas = []
    for host, n in sorted(por_host.items()):
        if host in parados:
            linhas.append(f"{host:<32} {n:>5} imagens   {parados[host]}")
            continue
        dias = -(-n // POR_DIA)
        linhas.append(f"{host:<32} {n:>5} imagens   {POR_HORA}/h, {POR_DIA}/dia -> ~{dias} dia(s)   "
                      f"+ robots.txt")
    exemplo = [c for c in itens if urlsplit(url_no_cdn(c.url)).hostname not in parados][:3]
    linhas += [f"exemplo: GET {url_no_cdn(c.url)}" for c in exemplo]
    return linhas


async def _main(argv: list[str]) -> int:
    from config import ConfigColeta, database_url

    import time

    from coleta.estado import Estado
    from coleta.http import TransporteCurlCffi

    url_banco = database_url()
    itens = candidatas(url_banco)
    cfg = ConfigColeta.carregar()
    estado = Estado(cfg.dir_dados / "coleta.sqlite3")
    if "--tentativa-manual" in argv:
        host = argv[argv.index("--tentativa-manual") + 1]
        cand = next((c for c in itens if urlsplit(url_no_cdn(c.url)).hostname == host), None)
        if "--dry-run" in argv or cand is None:
            print(f"Tentativa manual em {host} (1 + 1, sem retry; robots 401/403 = indisponível só aqui):")
            if cand:
                print(f"   GET https://{host}/robots.txt\n   GET {url_no_cdn(cand.url)}")
            else:
                print("   nada pendente; nenhuma requisição")
            return 0
        transporte = TransporteCurlCffi()
        try:
            cliente = cliente_de_imagens(estado, transporte, cfg_manual(cfg), prefixo="manual",
                                         robots_indisponivel=frozenset({host}))
            print(await tentativa_manual(cliente, estado, url_banco, cfg.dir_dados / "imagens", host))
        finally:
            await transporte.fechar()
        return 0
    if "--dry-run" in argv:
        print("Imagens de produto pelo ClienteEducado (só CDN de imagem; nenhuma página de loja):")
        print("\n".join(f"   {l}" for l in plano(itens, estado, time.time())) or "   nada pendente")
        return 0
    transporte = TransporteCurlCffi()
    try:
        cliente = cliente_de_imagens(estado, transporte, cfg)
        print(await baixar(cliente, url_banco, cfg.dir_dados / "imagens", lojas_paradas(estado, time.time())))
    finally:
        await transporte.fechar()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
