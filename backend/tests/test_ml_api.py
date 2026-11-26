import json
import random

import pytest

from config import ConfigColeta
from coleta.estado import Estado
from coleta.http import ClienteEducado, LojaDesligada, Resposta, SinalDeBloqueio, UrlProibida
from coleta.lojas_mvp import loja_do_host
from coleta.ml_api import URL_TOKEN, TokenML, url_busca
from coleta.vigiar import validador_busca
from tests.test_http import RelogioFalso, TransporteFalso

TOKEN = b'{"access_token":"APP_USR-segredo","expires_in":21600}'
BUSCA_OK = b'{"query":"ps5","results":[{"id":"MLB1","title":"Console PS5 Slim","price":3999}]}'


class TransporteComPost(TransporteFalso):
    def __init__(self, relogio):
        super().__init__(relogio)
        self.posts = []
        self.resposta_post = Resposta(200, {}, TOKEN, URL_TOKEN)

    async def post(self, url, cab, dados, timeout):
        self.posts.append((url, dados))
        return self.resposta_post


@pytest.fixture
def ambiente(monkeypatch, tmp_path):
    monkeypatch.setenv("ML_CLIENT_ID", "id-teste")
    monkeypatch.setenv("ML_CLIENT_SECRET", "segredo-teste")
    relogio = RelogioFalso()
    t = TransporteComPost(relogio)
    c = ClienteEducado(Estado(":memory:"), t, ConfigColeta(), relogio, random.Random(1),
                       loja_de=loja_do_host, pausada=lambda: False, dir_bruto=tmp_path,
                       estritas=frozenset({"mercado-livre"}))
    return c, t, relogio, tmp_path


async def test_busca_usa_api_oficial_com_bearer_e_token_reaproveitado(ambiente):
    c, t, relogio, _ = ambiente
    token = TokenML(c, relogio)
    for termo in ("ps5", "dixit"):
        url = url_busca(termo)
        assert url.startswith("https://api.mercadolibre.com/sites/MLB/search?q=")
        t.em(url, Resposta(200, {"content-type": "application/json"}, BUSCA_OK, url))
        await c.obter(url, tipo="busca", cabecalhos=await token.cabecalhos())
    assert len(t.posts) == 1
    assert t.sem_robots()[-1][2]["Authorization"] == "Bearer APP_USR-segredo"
    assert not any("lista.mercadolivre" in u for u in t.urls())


async def test_token_nao_vai_para_bruto_nem_cache(ambiente):
    c, t, relogio, bruto = ambiente
    await TokenML(c, relogio).cabecalhos()
    assert list(bruto.rglob("*")) == []
    assert c.estado.cache(URL_TOKEN) is None


async def test_post_so_para_url_de_token_permitida(ambiente):
    c, t, _, _ = ambiente
    with pytest.raises(UrlProibida):
        await c.obter_token("https://api.mercadolibre.com/qualquer", {})
    assert t.posts == []


async def test_403_com_token_desliga_o_ml_no_primeiro_sinal(ambiente):
    c, t, relogio, _ = ambiente
    token = TokenML(c, relogio)
    url = url_busca("ps5")
    t.em(url, Resposta(403, {}, b'{"message":"forbidden"}', url))
    with pytest.raises(SinalDeBloqueio):
        await c.obter(url, tipo="busca", cabecalhos=await token.cabecalhos())
    assert c.estado.breaker("mercado-livre").desligada
    relogio.t += 30 * 86400
    with pytest.raises(LojaDesligada):
        await c.obter(url_busca("dixit"), tipo="busca")


async def test_token_recusado_tambem_desliga(ambiente):
    c, t, relogio, _ = ambiente
    t.resposta_post = Resposta(401, {}, b"{}", URL_TOKEN)
    with pytest.raises(SinalDeBloqueio):
        await TokenML(c, relogio).cabecalhos()
    assert c.estado.breaker("mercado-livre").desligada


def test_validador_recusa_results_vazio_mesmo_com_query_ecoada():
    vazio = json.dumps({"query": "ps5", "results": []}).encode()
    cab = {"content-type": "application/json"}
    assert not validador_busca("ps5")(Resposta(200, cab, vazio, "u"))
    assert validador_busca("ps5")(Resposta(200, cab, BUSCA_OK, "u"))
