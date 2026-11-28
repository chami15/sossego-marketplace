"""Leitor do reconhecimento da Fase 9: diz de onde dá para ler preço numa busca HTML."""

import gzip
from pathlib import Path

from coleta import recon

FIX = Path(__file__).parent / "fixtures"


def html(caminho: str) -> str:
    return gzip.decompress((FIX / caminho).read_bytes()).decode("utf-8", "replace")


def test_kabum_tem_next_data_com_precos():
    r = recon.ler_pagina(html("kabum/busca_ps5.html.gz"))
    assert "__NEXT_DATA__" in r["fontes"]
    assert r["precos_no_html"] > 0 and r["desafio"] is None


def test_mercado_livre_intersticio_e_desafio():
    r = recon.ler_pagina(html("mercado-livre/busca_ps5_intersticio.html.gz"))
    assert r["desafio"] is not None


def test_amazon_desafio_akamai():
    r = recon.ler_pagina(html("amazon/desafio_akamai_bm_verify.html.gz"))
    assert r["desafio"] is not None


def test_amazon_busca_sem_json_le_precos_no_html():
    r = recon.ler_pagina(html("amazon/busca_ps5.html.gz"))
    assert r["desafio"] is None and r["precos_no_html"] > 10
    assert "__NEXT_DATA__" not in r["fontes"]


def test_json_ld_de_produto_e_estado_embutido():
    pagina = """<html><head>
    <script type="application/ld+json">{"@type":"ItemList","itemListElement":[
      {"@type":"Product","name":"X","offers":{"price":"10.00"}}]}</script>
    <script>window.__PRELOADED_STATE__ = {"a":1};</script></head><body>R$ 10,00</body></html>"""
    r = recon.ler_pagina(pagina)
    assert "JSON-LD Product" in r["fontes"] and "__PRELOADED_STATE__" in r["fontes"]


def test_spa_vazia_sem_fonte_nem_preco():
    r = recon.ler_pagina('<html><body><div id="root"></div><script src="/app.js"></script></body></html>')
    assert r["fontes"] == [] and r["precos_no_html"] == 0 and r["desafio"] is None


def test_plano_dry_run_lista_2_requisicoes_por_loja_e_nao_inclui_lojas_vetadas():
    linhas = recon.plano(recon.CANDIDATAS)
    assert sum(l.startswith("GET") for l in linhas) == 2 * len(recon.CANDIDATAS)
    vetadas = {"magalu", "fast-shop", "carrefour", "amazon", "mercado-livre", "epoca"}
    assert not vetadas & {c.slug for c in recon.CANDIDATAS}
    assert not any("lista.mercadolivre" in l for l in linhas)
