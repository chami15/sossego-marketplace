"""Parsers determinísticos: resposta crua (do bruto) -> list[Oferta].

Cada parser tem versão: mudar a lógica sobe a versão, e o reprocessamento
sabe quais arquivos precisam ser lidos de novo.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Callable
from urllib.parse import parse_qs, urlsplit

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from coleta.base import Oferta, brl, dec

PARSER_VERSAO = {"amazon": "1", "ludopedia": "1", "ri-happy": "1", "kabum": "5"}


class SemOfertas(Exception):
    """Página não tem a estrutura esperada (molde quebrado), diferente de
    uma busca legítima sem resultado."""


# --- Amazon (HTML da busca) -------------------------------------------------
def amazon(corpo: str, coletado_em: datetime) -> list[Oferta]:
    arvore = HTMLParser(corpo)
    blocos = arvore.css('div[data-component-type="s-search-result"]')
    if not blocos:
        raise SemOfertas("amazon: nenhum s-search-result")
    ofertas = []
    for b in blocos:
        asin = b.attributes.get("data-asin")
        h2 = b.css_first("h2")
        if not asin or h2 is None:
            continue
        titulo = (h2.attributes.get("aria-label") or h2.text(strip=True)).strip()
        patrocinado = titulo.startswith("Anúncio patrocinado")
        titulo = re.sub(r"^Anúncio patrocinado\s*[–-]\s*", "", titulo)
        # Primeiro a-price fora de "a-text-price" é o preço atual; o riscado é o "de".
        atual = b.css_first("span.a-price:not(.a-text-price) span.a-offscreen")
        preco = brl(atual.text() if atual else None)
        if preco is None:
            continue  # sem preço = indisponível na busca; não vira oferta
        riscado = b.css_first("span.a-price.a-text-price span.a-offscreen")
        img = b.css_first("img.s-image")
        ofertas.append(Oferta(
            loja="amazon", id_externo=asin, url=f"https://www.amazon.com.br/dp/{asin}",
            titulo=titulo, imagem=img.attributes.get("src") if img else None,
            preco=preco, preco_de=brl(riscado.text()) if riscado else None,
            patrocinado=patrocinado, coletado_em=coletado_em,
        ))
    return ofertas


# --- Ludopedia (HTML da busca) ----------------------------------------------
def ludopedia(corpo: str, coletado_em: datetime) -> list[Oferta]:
    arvore = HTMLParser(corpo)
    bloco = arvore.css_first("#bloco-jogos-sm")
    if bloco is None:
        if "Nenhum resultado" in corpo or "nenhum jogo" in corpo.lower():
            return []
        raise SemOfertas("ludopedia: sem #bloco-jogos-sm")
    ofertas = []
    for m in bloco.css("div.media.bord-btm"):
        link = m.css_first("a.full-link")
        h4 = m.css_first("h4")
        valor = m.css_first(".vl_produto_store")
        loja_link = m.css_first('a[href*="/loja?id_jogo="]')
        if link is None or h4 is None or valor is None:
            continue  # jogo sem oferta na Ludostore
        preco = brl(valor.text())
        if preco is None:
            continue
        rotulo = h4.css_first("label")
        titulo = h4.text(strip=True)
        if rotulo is not None:
            titulo = titulo.replace(rotulo.text(strip=True), "").strip()
        id_jogo = None
        if loja_link is not None:
            id_jogo = parse_qs(urlsplit(loja_link.attributes["href"]).query).get("id_jogo", [None])[0]
        slug = link.attributes["href"].rstrip("/").rsplit("/", 1)[-1]
        img = m.css_first("img.img-capa")
        ofertas.append(Oferta(
            loja="ludopedia", id_externo=id_jogo or slug,
            url=link.attributes["href"], titulo=titulo,
            imagem=img.attributes.get("src") if img else None,
            # A busca só mostra o valor "no boleto" (à vista) da Ludostore.
            preco=preco, vendedor="Ludostore", coletado_em=coletado_em,
        ))
    return ofertas


# --- VTEX (API pública de catálogo) -----------------------------------------
def vtex(loja: str) -> Callable[[str, datetime], list[Oferta]]:
    def parse(corpo: str, coletado_em: datetime) -> list[Oferta]:
        try:
            produtos = json.loads(corpo)
        except ValueError as e:
            raise SemOfertas(f"{loja}: JSON inválido") from e
        if not isinstance(produtos, list):
            raise SemOfertas(f"{loja}: esperava lista de produtos")
        ofertas = []
        for p in produtos:
            for item in p.get("items", []):
                sellers = item.get("sellers") or []
                seller = next((s for s in sellers if s.get("sellerDefault")), sellers[0] if sellers else None)
                if not seller:
                    continue
                o = seller["commertialOffer"]
                preco = dec(o.get("Price"))
                if not preco:
                    continue
                parcelas = o.get("Installments") or []
                sem_juros = [i for i in parcelas if not i.get("InterestRate")]
                maior = max(sem_juros, key=lambda i: i["NumberOfInstallments"], default=None)
                pix = [i for i in parcelas if "pix" in (i.get("PaymentSystemName") or "").lower()]
                variacao = {v: (item.get(v) or [""])[0] for v in item.get("variations", [])}
                imgs = item.get("images") or []
                ofertas.append(Oferta(
                    loja=loja, id_externo=str(item["itemId"]), url=p.get("link") or "",
                    titulo=p.get("productName") or item.get("name", ""),
                    imagem=imgs[0]["imageUrl"] if imgs else None,
                    marca=p.get("brand"), gtin=item.get("ean") or None,
                    vendedor=seller.get("sellerName"), variacao=variacao,
                    preco=preco, preco_de=dec(o.get("ListPrice")) if o.get("ListPrice") else None,
                    preco_pix=dec(pix[0]["Value"]) if pix else None,
                    parcelas_sem_juros=maior["NumberOfInstallments"] if maior else None,
                    parcelas_max=maior["NumberOfInstallments"] if maior else None,
                    parcela_valor=dec(maior["Value"]) if maior else None,
                    em_estoque=(o.get("AvailableQuantity") or 0) > 0,
                    coletado_em=coletado_em,
                ))
        return ofertas
    return parse


# --- Kabum (__NEXT_DATA__ da busca) -----------------------------------------
_RE_PARCELA = re.compile(r"(\d+)\s*x\s*de\s*(R\$\s*[\d.]+,\d{2})", re.I)
log = logging.getLogger("sossego.parsers")


def kabum(corpo: str, coletado_em: datetime) -> list[Oferta]:
    """Mapeamento conferido na tela pelo dono em 27/11, antes e depois das 16h
    (docs/fontes/kabum.md): total no cartão = parcelamento literal (tem que bater
    com o preço vigente, logo é sem juros); Pix = priceWithDiscount da oferta ativa
    (ou da raiz), inclusive quando igual ao cartão. "de" = None: oldPrice bateu com
    a tela em 26/11 e não em 27/11 16:44, e o valor da tela não está no JSON."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', corpo, re.S)
    if not m:
        raise SemOfertas("kabum: sem __NEXT_DATA__")
    try:
        dados = json.loads(m.group(1))["props"]["pageProps"]["data"]
        if isinstance(dados, str):
            dados = json.loads(dados)
        itens = dados["catalogServer"]["data"]
    except (ValueError, KeyError, TypeError) as e:
        raise SemOfertas(f"kabum: estrutura inesperada ({e!r})") from e
    agora = coletado_em.timestamp()
    ofertas = []
    for p in itens:
        parc = _RE_PARCELA.search(p.get("maxInstallment") or "")
        if not parc:
            continue
        n, valor = int(parc.group(1)), brl(parc.group(2))
        total = valor * n
        oferta = p.get("offer") or {}
        ativa = oferta.get("price") and (oferta.get("startsAt") or 0) <= agora < (oferta.get("endsAt") or 0)
        vigente = dec(oferta["price"]) if ativa else dec(p.get("price"))
        pix = dec(oferta.get("priceWithDiscount")) if ativa else dec(p.get("priceWithDiscount"))
        # A parcela vem arredondada (até 1 centavo por parcela): o parcelado só
        # confere o preço vigente; quem vai para `preco` é o vigente.
        if vigente is None or abs(total - vigente) > Decimal("0.01") * n:
            log.warning(json.dumps({"evento": "kabum_preco_inconsistente", "code": p.get("code"),
                                    "parcelado": str(total), "vigente": str(vigente)}))
            continue
        img = p.get("image") or (p.get("images") or [None])[0]
        ofertas.append(Oferta(
            loja="kabum", id_externo=str(p["code"]),
            url=f"https://www.kabum.com.br/produto/{p['code']}/{p.get('friendlyName', '')}",
            titulo=p.get("name", ""), imagem=img, marca=(p.get("manufacturer") or {}).get("name"),
            vendedor=p.get("sellerName"), preco=vigente, parcelas_max=n, parcela_valor=valor,
            # n x parcela == vigente (checado acima): o parcelado não tem juros.
            parcelas_sem_juros=n,
            preco_pix=pix if pix and pix <= vigente else None, preco_de=None,
            em_estoque=bool(p.get("available")), coletado_em=coletado_em,
        ))
    return ofertas


PARSERS: dict[str, Callable[[str, datetime], list[Oferta]]] = {
    "kabum": kabum,
    "amazon": amazon,
    "ludopedia": ludopedia,
    "ri-happy": vtex("ri-happy"),
}
