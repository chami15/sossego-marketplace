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
    (t,) = planejar([{"url": "https://www.kabum.com.br/produto/989702/ps5"}])
    assert t.loja == "kabum" and t.tipo == "produto"


def test_loja_inativa_fica_fora_do_plano_ate_por_url_direta():
    t = planejar([{"termo": "ps5"}, {"url": "https://www.magazineluiza.com.br/ps5/p/123/"}])
    assert "magalu" not in {x.loja for x in t}


def test_recon_inclui_so_loja_em_avaliacao_citada(monkeypatch):
    import dataclasses

    import coleta.lojas_mvp as lm

    # Kabum já foi aprovado; a regra continua valendo para a próxima loja em avaliação.
    avaliar = dataclasses.replace(lm.LOJAS["kabum"], ativa=False, motivo_inativa="em avaliação: teste")
    monkeypatch.setitem(lm.LOJAS, "kabum", avaliar)
    alvos = [{"termo": "ps5"}]
    assert "kabum" not in {x.loja for x in planejar(alvos)}
    t = planejar(alvos, lojas=["kabum", "magalu"], recon=True)
    assert {x.loja for x in t} == {"kabum"}  # magalu está inativa por bloqueio, não em avaliação
    assert t[0].url == "https://www.kabum.com.br/busca/ps5"


def test_kabum_ativo_so_com_eletronicos_a_cada_120_min():
    from coleta.vigiar import periodo_min

    alvos = [{"termo": "nintendo switch 2", "categoria": "eletronicos"}, {"termo": "dixit", "categoria": "tabuleiro"}]
    urls = [x.url for x in planejar(alvos) if x.loja == "kabum"]
    assert urls == ["https://www.kabum.com.br/busca/nintendo-switch-2"]
    assert periodo_min("kabum") == 120


def test_amazon_desligada_pelo_dono_ate_segunda_nem_por_url_direta():
    # 27/11: desafio Akamai na BF. O dono desligou até segunda, sem deixar o breaker decidir.
    from coleta.lojas_mvp import LOJAS

    t = planejar([{"termo": "ps5"}, {"url": "https://www.amazon.com.br/dp/B0GWNKJDCZ"}])
    assert "amazon" not in {x.loja for x in t}
    assert not LOJAS["amazon"].ativa and "segunda" in LOJAS["amazon"].motivo_inativa


def test_ml_nunca_planeja_html_so_api_oficial():
    t = planejar([{"termo": "ps5"}, {"termo": "dixit", "categoria": "tabuleiro"}])
    assert not any("lista.mercadolivre" in x.url for x in t)
    assert all(x.url.startswith("https://api.mercadolibre.com/") for x in t if x.loja == "mercado-livre")


def test_hosts_da_mesma_loja_dividem_orcamento():
    assert loja_do_host("lista.mercadolivre.com.br") == loja_do_host("produto.mercadolivre.com.br")


def test_filtro_de_lojas_e_sem_duplicatas():
    t = planejar([{"termo": "ps5"}, {"termo": "ps5"}], lojas=["kabum"])
    assert len(t) == 1 and t[0].loja == "kabum"


def test_dry_run_nao_chama_rede(capsys, monkeypatch):
    import coleta.http as http

    def explode(*a, **k):
        raise AssertionError("dry-run tentou criar transporte")

    monkeypatch.setattr(http, "TransporteCurlCffi", explode)
    imprimir_dry_run(planejar([{"termo": "ps5"}]), ConfigColeta())
    saida = capsys.readouterr().out
    assert "nenhuma requisição" in saida and "kabum.com.br/busca/ps5" in saida


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


async def test_rodada_chama_gancho_no_fim_mesmo_interrompida(monkeypatch, tmp_path):
    import random
    from types import SimpleNamespace

    import coleta.vigiar as v

    feitas, ganchos = [], []

    async def falsa(cliente, t, token_ml=None):
        feitas.append(t.url)
        cliente.estado.pausa = 10**12  # breaker abre depois da 1ª
        return "ok"

    async def gancho(loja):
        ganchos.append(loja)

    estado = SimpleNamespace(pausa=0)
    estado.breaker = lambda loja: SimpleNamespace(desligada=False, pausada_ate=estado.pausa, motivo="x")
    monkeypatch.setattr(v, "executar_tarefa", falsa)
    ts = [v.Tarefa("amazon", f"https://www.amazon.com.br/s?k={i}", "busca", str(i)) for i in range(3)]
    cliente = SimpleNamespace(estado=estado, cfg=ConfigColeta(dir_dados=tmp_path), pausada=lambda: False)
    await v.rodada_da_loja(cliente, "amazon", ts, 0, random.Random(1), apos=gancho)
    assert len(feitas) == 1 and ganchos == ["amazon"]


async def test_regressao_resumo_dizia_ok_para_http_400():
    """27/11: o terminal mostrava 'ok 400 0 KB' para a Ri Happy."""
    from types import SimpleNamespace

    import coleta.vigiar as v

    async def obter(url, **k):
        return SimpleNamespace(do_cache=False, status=400, corpo=b"x" * 37)

    t = v.Tarefa("ri-happy", "https://www.rihappy.com.br/p/1", "produto", None)
    texto = await v.executar_tarefa(SimpleNamespace(obter=obter), t)
    assert not texto.startswith("ok") and "400" in texto


def test_regressao_ri_happy_jogo_ito_dava_400_toda_rodada():
    """27/11: a API VTEX da Ri Happy respondeu 400 a 'jogo+ito' e 206 a 'jogo%20ito'
    (1 requisição de teste liberada pelo dono, 16:48). Espaço vai como %20."""
    alvos = [{"termo": "jogo ito", "categoria": "tabuleiro"}, {"termo": "dixit", "categoria": "tabuleiro"}]
    rh = [x.url for x in planejar(alvos) if x.loja == "ri-happy"]
    assert any("ft=jogo%20ito&" in u for u in rh) and any("ft=dixit&" in u for u in rh)
    assert not any("+" in u for u in rh)
    assert any(x.loja == "ludopedia" and "jogo+ito" in x.url for x in planejar(alvos))
