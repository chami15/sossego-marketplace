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
    (t,) = planejar([{"url": "https://produto.mercadolivre.com.br/MLB-123-ps5"}])
    assert t.loja == "mercado-livre" and t.tipo == "produto"


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
