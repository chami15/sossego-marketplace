import pytest

from coleta.http import Resposta
from coleta.lojas_mvp import loja_do_host
from coleta.vigiar import imprimir_dry_run, planejar, validador_busca
from config import ConfigColeta


def test_categoria_decide_as_lojas():
    t = planejar([{"termo": "dixit", "categoria": "tabuleiro"}, {"termo": "ps5", "categoria": "eletronicos"}])
    lojas_dixit = {x.loja for x in t if x.termo == "dixit"}
    lojas_ps5 = {x.loja for x in t if x.termo == "ps5"}
    assert {"ludopedia", "ri-happy"} <= lojas_dixit
    assert "ludopedia" not in lojas_ps5 and "ri-happy" not in lojas_ps5


def test_url_direta_vira_tarefa_de_produto_da_loja_certa():
    (t,) = planejar([{"url": "https://www.amazon.com.br/dp/B0GWNKJDCZ"}])
    assert t.loja == "amazon" and t.tipo == "produto"


def test_loja_inativa_fica_fora_do_plano_ate_por_url_direta():
    t = planejar([{"termo": "ps5"}, {"url": "https://www.magazineluiza.com.br/ps5/p/123/"}])
    assert "magalu" not in {x.loja for x in t}


def test_ml_nunca_planeja_html_so_api_oficial():
    t = planejar([{"termo": "ps5"}, {"termo": "dixit", "categoria": "tabuleiro"}])
    assert not any("lista.mercadolivre" in x.url for x in t)
    assert all(x.url.startswith("https://api.mercadolibre.com/") for x in t if x.loja == "mercado-livre")


def test_hosts_da_mesma_loja_dividem_orcamento():
    assert loja_do_host("lista.mercadolivre.com.br") == loja_do_host("produto.mercadolivre.com.br")


def test_filtro_de_lojas_e_sem_duplicatas():
    t = planejar([{"termo": "ps5"}, {"termo": "ps5"}], lojas=["amazon"])
    assert len(t) == 1 and t[0].loja == "amazon"


def test_dry_run_nao_chama_rede(capsys, monkeypatch):
    import coleta.http as http

    def explode(*a, **k):
        raise AssertionError("dry-run tentou criar transporte")

    monkeypatch.setattr(http, "TransporteCurlCffi", explode)
    imprimir_dry_run(planejar([{"termo": "ps5"}]), ConfigColeta())
    saida = capsys.readouterr().out
    assert "nenhuma requisição" in saida and "amazon.com.br/s?k=ps5" in saida


def test_validador_de_busca_recusa_pagina_pequena_ou_sem_termo():
    ok = validador_busca("jogo ito")
    assert not ok(Resposta(200, {}, b"<html>oi</html>", "u"))
    assert not ok(Resposta(200, {}, b"x" * 20_000, "u"))
    assert ok(Resposta(200, {}, b"x" * 20_000 + "Ito - Jogo de Cartas".encode(), "u"))


PAGINA_ML_EXIGE_JS = (
    "<html><head><title>Ps5 | Mercado Livre</title><style>.micro-landing-container{display:flex}"
    + "x" * 15_000 + "</style></head><body><div class='micro-landing-container'>"
    "<button>Continuar</button><noscript>This page requires JavaScript to work. Please enable "
    "JavaScript in your browser to continue.</noscript></div></body></html>"
).encode()


def test_regressao_interstício_que_exige_javascript_passava_como_ok():
    """26/11: o ML devolveu 17 KB de interstício anti-robô com 'Ps5' no
    <title>; o validador aceitou como página de busca boa."""
    from coleta.http import parece_desafio

    r = Resposta(200, {"content-type": "text/html; charset=utf-8"}, PAGINA_ML_EXIGE_JS,
                 "https://lista.mercadolivre.com.br/ps5")
    assert parece_desafio(r) is not None
    assert not validador_busca("ps5")(r)


def test_validador_de_busca_html_exige_precos():
    sem_preco = Resposta(200, {"content-type": "text/html"}, b"x" * 20_000 + b"dixit", "u")
    com_preco = Resposta(200, {"content-type": "text/html"},
                         b"x" * 20_000 + b"dixit R$ 145,50 R$ 60,00 R$ 134,95", "u")
    assert not validador_busca("dixit")(sem_preco)
    assert validador_busca("dixit")(com_preco)


def test_validador_de_busca_json_vtex():
    corpo = b'[{"productName":"Jogo Dixit","items":[{"sellers":[{"commertialOffer":{"Price":149.9}}]}]}]'
    assert validador_busca("dixit")(Resposta(200, {"content-type": "application/json"}, corpo, "u"))
    assert not validador_busca("dixit")(Resposta(200, {"content-type": "application/json"}, b"[]", "u"))


@pytest.mark.parametrize("termo,pagina", [
    ("dixit", "DIXIT ODYSSEY"),
    ("DIXIT", "Dixit"),
    ("macbook", "MacBook Air M3"),
    ("jogo ito", "JÔGO de cartas"),       # acento só na página
    ("pôster", "POSTER gigante"),         # acento só no termo
    ("nintendo switch", "Nintendo Switch 2"),
])
def test_validador_ignora_maiusculas_e_acentos(termo, pagina):
    corpo = b"x" * 20_000 + pagina.encode("utf-8")
    assert validador_busca(termo)(Resposta(200, {}, corpo, "u"))
