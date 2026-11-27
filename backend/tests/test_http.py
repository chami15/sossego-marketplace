"""Testes da camada de coleta educada. Sem rede: relógio e transporte falsos."""

from __future__ import annotations

import random
from collections import defaultdict

import pytest

from config import ConfigColeta
from coleta.estado import Estado
from coleta.http import (
    BloqueadaPorRobots,
    ClienteEducado,
    ColetaPausada,
    FalhaTransitoria,
    LojaDesligada,
    LojaEmPausa,
    MoldeQuebrado,
    OrcamentoEsgotado,
    Resposta,
    SinalDeBloqueio,
    UrlProibida,
)

HTML_OK = b"<html><body>" + b"dixit " * 2000 + b"</body></html>"


class RelogioFalso:
    def __init__(self, inicio: float = 1_800_000_000.0):
        self.t = inicio
        self.dormidas: list[float] = []

    def agora(self) -> float:
        return self.t

    async def dormir(self, s: float) -> None:
        self.dormidas.append(s)
        self.t += max(0.0, s)


class TransporteFalso:
    """Responde por URL; uma fila de respostas por URL (a última se repete)."""

    def __init__(self, relogio: RelogioFalso, robots: str = ""):
        self.relogio = relogio
        self.rotas: dict[str, list] = defaultdict(list)
        self.chamadas: list[tuple[float, str, dict]] = []
        self.robots = robots

    def em(self, url: str, *respostas):
        self.rotas[url].extend(respostas)
        return self

    async def get(self, url, cabecalhos, timeout):
        self.chamadas.append((self.relogio.agora(), url, cabecalhos))
        if url.endswith("/robots.txt") and url not in self.rotas:
            return Resposta(200, {}, self.robots.encode(), url)
        fila = self.rotas.get(url) or [Resposta(200, {}, HTML_OK, url)]
        r = fila.pop(0) if len(fila) > 1 else fila[0]
        if isinstance(r, Exception):
            raise r
        return r

    def urls(self):
        return [u for _, u, _ in self.chamadas]

    def sem_robots(self):
        return [c for c in self.chamadas if not c[1].endswith("/robots.txt")]


def r(status, corpo=HTML_OK, **cab):
    return Resposta(status, {k.replace("_", "-"): v for k, v in cab.items()}, corpo, "https://x")


@pytest.fixture
def relogio():
    return RelogioFalso()


@pytest.fixture
def transporte(relogio):
    return TransporteFalso(relogio)


def cliente(relogio, transporte, pausada=lambda: False, **cfg):
    return ClienteEducado(
        estado=Estado(":memory:"),
        transporte=transporte,
        cfg=ConfigColeta(**cfg),
        relogio=relogio,
        rng=random.Random(42),
        pausada=pausada,
    )


# ---------------------------------------------------------------------------
# Obrigatórios
# ---------------------------------------------------------------------------
async def test_duas_chamadas_seguidas_no_mesmo_dominio_respeitam_intervalo(relogio, transporte):
    c = cliente(relogio, transporte)
    await c.obter("https://loja.com/busca?q=a", tipo="busca")
    await c.obter("https://loja.com/busca?q=b", tipo="busca")
    tempos = [t for t, _, _ in transporte.chamadas]  # robots, a, b
    assert len(tempos) == 3
    for antes, depois in zip(tempos, tempos[1:]):
        assert 5.0 <= depois - antes <= 8.0  # 5 s + jitter de 0 a 3 s


async def test_jitter_varia_entre_chamadas(relogio, transporte):
    c = cliente(relogio, transporte)
    for i in range(6):
        await c.obter(f"https://loja.com/p/{i}", tipo="produto")
    tempos = [t for t, _, _ in transporte.chamadas]
    difs = {round(b - a, 3) for a, b in zip(tempos, tempos[1:])}
    assert len(difs) > 1, "intervalo constante = ritmo de robô"


async def test_orcamento_estourado_bloqueia_a_proxima_chamada(relogio, transporte):
    c = cliente(relogio, transporte, orcamento_hora=3)
    await c.obter("https://loja.com/p/1", tipo="produto")  # robots + p1 = 2
    await c.obter("https://loja.com/p/2", tipo="produto")  # 3
    with pytest.raises(OrcamentoEsgotado):
        await c.obter("https://loja.com/p/3", tipo="produto")
    assert len(transporte.chamadas) == 3


async def test_orcamento_diario_tambem_bloqueia(relogio, transporte):
    c = cliente(relogio, transporte, orcamento_hora=1000, orcamento_dia=4)
    for i in range(3):
        await c.obter(f"https://loja.com/p/{i}", tipo="produto")
    relogio.t += 2 * 3600  # janela de 1 h já passou; a de 24 h não
    with pytest.raises(OrcamentoEsgotado) as e:
        await c.obter("https://loja.com/p/9", tipo="produto")
    assert "dia" in str(e.value)


async def test_403_abre_o_breaker_e_nao_gera_retry(relogio, transporte):
    transporte.em("https://loja.com/p/1", r(403))
    c = cliente(relogio, transporte)
    with pytest.raises(SinalDeBloqueio):
        await c.obter("https://loja.com/p/1", tipo="produto")
    assert transporte.sem_robots() and len(transporte.sem_robots()) == 1
    with pytest.raises(LojaEmPausa):
        await c.obter("https://loja.com/p/2", tipo="produto")
    assert len(transporte.sem_robots()) == 1
    assert c.estado.breaker("loja.com").pausada_ate == pytest.approx(relogio.agora() + 1800, abs=10)


async def test_captcha_detectado_abre_o_breaker(relogio, transporte):
    pagina = b"<html><form action='/errors/validateCaptcha'>Digite os caracteres que voce ve</form></html>"
    transporte.em("https://loja.com/p/1", r(200, pagina))
    c = cliente(relogio, transporte)
    with pytest.raises(SinalDeBloqueio):
        await c.obter("https://loja.com/p/1", tipo="produto")
    with pytest.raises(LojaEmPausa):
        await c.obter("https://loja.com/p/2", tipo="produto")
    assert len(transporte.sem_robots()) == 1


async def test_disallow_do_robots_bloqueia_a_url(relogio):
    t = TransporteFalso(relogio, robots="User-agent: *\nDisallow: /busca\nAllow: /busca/livre\n")
    c = cliente(relogio, t)
    with pytest.raises(BloqueadaPorRobots):
        await c.obter("https://loja.com/busca?q=ps5", tipo="busca")
    await c.obter("https://loja.com/busca/livre", tipo="busca")  # regra mais longa (Allow) vence
    assert t.urls() == ["https://loja.com/robots.txt", "https://loja.com/busca/livre"]


async def test_kill_switch_impede_qualquer_requisicao(relogio, transporte):
    c = cliente(relogio, transporte, pausada=lambda: True)
    with pytest.raises(ColetaPausada):
        await c.obter("https://loja.com/p/1", tipo="produto")
    assert transporte.chamadas == []


# ---------------------------------------------------------------------------
# Complementares
# ---------------------------------------------------------------------------
async def test_kill_switch_ligado_durante_a_espera_para_antes_de_enviar(relogio, transporte):
    estado = {"pausada": False}
    c = cliente(relogio, transporte, pausada=lambda: estado["pausada"])
    await c.obter("https://loja.com/p/1", tipo="produto")
    original = relogio.dormir

    async def dormir_e_pausar(s):
        estado["pausada"] = True
        await original(s)

    relogio.dormir = dormir_e_pausar
    with pytest.raises(ColetaPausada):
        await c.obter("https://loja.com/p/2", tipo="produto")
    assert len(transporte.chamadas) == 2  # robots + p1


async def test_429_abre_breaker_respeitando_retry_after_maior(relogio, transporte):
    transporte.em("https://loja.com/p/1", r(429, retry_after="7200"))
    c = cliente(relogio, transporte)
    with pytest.raises(SinalDeBloqueio):
        await c.obter("https://loja.com/p/1", tipo="produto")
    assert len(transporte.sem_robots()) == 1
    assert c.estado.breaker("loja.com").pausada_ate == pytest.approx(relogio.agora() + 7200, abs=10)


async def test_conteudo_inesperado_pausa_a_loja_como_molde_quebrado(relogio, transporte):
    c = cliente(relogio, transporte)
    with pytest.raises(MoldeQuebrado):
        await c.obter("https://loja.com/p/1", tipo="produto", validar=lambda resp: b"preco" in resp.corpo)
    b = c.estado.breaker("loja.com")
    assert b.tipo_motivo == "molde_quebrado" and b.sinais_seguidos == 0
    assert b.pausada_ate == pytest.approx(relogio.agora() + 1800, abs=10)
    with pytest.raises(LojaEmPausa):
        await c.obter("https://loja.com/p/2", tipo="produto")
    assert len(transporte.sem_robots()) == 1


async def test_bloqueio_registra_tipo_bloqueio(relogio, transporte):
    transporte.em("https://loja.com/p", r(403))
    c = cliente(relogio, transporte)
    with pytest.raises(SinalDeBloqueio):
        await c.obter("https://loja.com/p", tipo="produto")
    assert c.estado.breaker("loja.com").tipo_motivo == "bloqueio"


async def test_molde_quebrado_escala_mas_nunca_desliga(relogio, transporte):
    c = cliente(relogio, transporte)
    nunca = lambda resp: False  # noqa: E731
    pausas = []
    for i in range(5):
        with pytest.raises(MoldeQuebrado):
            await c.obter(f"https://loja.com/busca?q={i}", tipo="busca", validar=nunca)
        b = c.estado.breaker("loja.com")
        pausas.append(round(b.pausada_ate - relogio.agora()))
        relogio.t = b.pausada_ate + 1
    assert not c.estado.breaker("loja.com").desligada
    assert pausas[:3] == [pytest.approx(1800, abs=10), pytest.approx(7200, abs=10), pytest.approx(21600, abs=10)]


async def test_molde_quebrado_ainda_grava_o_bruto(relogio, transporte, tmp_path):
    c = cliente(relogio, transporte)
    c.dir_bruto = tmp_path
    with pytest.raises(MoldeQuebrado):
        await c.obter("https://loja.com/busca?q=x", tipo="busca", validar=lambda resp: False)
    assert len(list(tmp_path.rglob("*.json.gz"))) == 1


async def test_404_em_busca_e_molde_quebrado_mas_em_produto_nao(relogio, transporte):
    transporte.em("https://loja.com/busca?q=x", r(404)).em("https://loja.com/p/sumiu", r(404))
    c = cliente(relogio, transporte)
    assert (await c.obter("https://loja.com/p/sumiu", tipo="produto")).status == 404
    with pytest.raises(MoldeQuebrado):
        await c.obter("https://loja.com/busca?q=x", tipo="busca", validar=lambda resp: True)


async def test_regressao_206_da_vtex_nao_ia_para_bruto_nem_cache(relogio, transporte, tmp_path):
    """26/11: a API VTEX da Ri Happy responde 206 com o JSON completo; só 200
    era tratado como sucesso, e a resposta se perdia."""
    transporte.em("https://loja.com/api?ft=dixit", r(206, b'[{"productName":"Dixit"}]'))
    c = cliente(relogio, transporte)
    c.dir_bruto = tmp_path
    await c.obter("https://loja.com/api?ft=dixit", tipo="busca", validar=lambda resp: True)
    assert len(list(tmp_path.rglob("*.json.gz"))) == 1
    assert (await c.obter("https://loja.com/api?ft=dixit", tipo="busca")).do_cache
    assert c.estado.ultima_por_classe("loja.com", "ok") is not None


async def test_requisicoes_ficam_classificadas(relogio, transporte):
    transporte.em("https://loja.com/ruim", r(403))
    c = cliente(relogio, transporte)
    await c.obter("https://loja.com/boa", tipo="produto")
    assert c.estado.ultima_por_classe("loja.com", "ok") is not None
    with pytest.raises(SinalDeBloqueio):
        await c.obter("https://loja.com/ruim", tipo="produto")
    assert c.estado.ultima_por_classe("loja.com", "bloqueio") is not None


async def test_escalada_30min_2h_e_desliga_no_terceiro_sinal_seguido(relogio, transporte):
    transporte.em("https://loja.com/p", r(403))
    c = cliente(relogio, transporte)
    pausas = []
    for _ in range(2):
        with pytest.raises(SinalDeBloqueio):
            await c.obter("https://loja.com/p", tipo="produto")
        b = c.estado.breaker("loja.com")
        pausas.append(round(b.pausada_ate - relogio.agora()))
        relogio.t = b.pausada_ate + 1
    assert pausas[0] == pytest.approx(1800, abs=10)
    assert pausas[1] == pytest.approx(7200, abs=10)
    with pytest.raises(SinalDeBloqueio):
        await c.obter("https://loja.com/p", tipo="produto")
    assert c.estado.breaker("loja.com").desligada
    relogio.t += 10 * 86400
    with pytest.raises(LojaDesligada):
        await c.obter("https://loja.com/outra", tipo="produto")


async def test_sucesso_no_meio_zera_sinais_seguidos_mas_reincidencia_sobe_para_6h(relogio, transporte):
    transporte.em("https://loja.com/ruim", r(403))
    c = cliente(relogio, transporte)
    for i in range(3):
        with pytest.raises(SinalDeBloqueio):
            await c.obter("https://loja.com/ruim", tipo="produto")
        b = c.estado.breaker("loja.com")
        ultima_pausa = b.pausada_ate - relogio.agora()
        relogio.t = b.pausada_ate + 1
        await c.obter(f"https://loja.com/boa/{i}", tipo="produto")
    assert not c.estado.breaker("loja.com").desligada
    assert ultima_pausa == pytest.approx(21600, abs=10)


async def test_retry_so_em_5xx_com_backoff_30s_e_2min(relogio, transporte):
    transporte.em("https://loja.com/p", r(503), r(502), r(500))
    c = cliente(relogio, transporte)
    with pytest.raises(FalhaTransitoria):
        await c.obter("https://loja.com/p", tipo="produto")
    assert len(transporte.sem_robots()) == 3  # 1 + 2 retries
    assert 30 in relogio.dormidas and 120 in relogio.dormidas


async def test_timeout_gera_retry_e_depois_sucesso(relogio, transporte):
    transporte.em("https://loja.com/p", TimeoutError(), r(200))
    c = cliente(relogio, transporte)
    res = await c.obter("https://loja.com/p", tipo="produto")
    assert res.status == 200 and len(transporte.sem_robots()) == 2


async def test_retry_after_longo_em_503_vira_pausa_sem_retry(relogio, transporte):
    transporte.em("https://loja.com/p", r(503, retry_after="3600"))
    c = cliente(relogio, transporte)
    with pytest.raises(FalhaTransitoria):
        await c.obter("https://loja.com/p", tipo="produto")
    assert len(transporte.sem_robots()) == 1
    with pytest.raises(LojaEmPausa):
        await c.obter("https://loja.com/q", tipo="produto")


async def test_cache_dentro_do_ttl_nao_vai_a_rede(relogio, transporte):
    c = cliente(relogio, transporte)
    await c.obter("https://loja.com/busca?q=a", tipo="busca")
    relogio.t += 29 * 60
    res = await c.obter("https://loja.com/busca?q=a", tipo="busca")
    assert res.do_cache and len(transporte.sem_robots()) == 1
    relogio.t += 2 * 60  # passou dos 30 min
    await c.obter("https://loja.com/busca?q=a", tipo="busca")
    assert len(transporte.sem_robots()) == 2


async def test_ttl_de_produto_e_50_min(relogio, transporte):
    c = cliente(relogio, transporte)
    await c.obter("https://loja.com/p", tipo="produto")
    relogio.t += 49 * 60
    assert (await c.obter("https://loja.com/p", tipo="produto")).do_cache


async def test_requisicao_condicional_com_etag_e_304(relogio, transporte):
    transporte.em("https://loja.com/p", r(200, etag='"v1"', last_modified="Wed, 25 Nov 2026 10:00:00 GMT"), r(304, b""))
    c = cliente(relogio, transporte)
    await c.obter("https://loja.com/p", tipo="produto")
    relogio.t += 3600
    res = await c.obter("https://loja.com/p", tipo="produto")
    cab = transporte.sem_robots()[-1][2]
    assert cab["If-None-Match"] == '"v1"' and "If-Modified-Since" in cab
    assert res.corpo == HTML_OK and res.do_cache


async def test_crawl_delay_maior_que_o_intervalo_prevalece(relogio):
    t = TransporteFalso(relogio, robots="User-agent: *\nCrawl-delay: 20\n")
    c = cliente(relogio, t)
    await c.obter("https://loja.com/a", tipo="produto")
    await c.obter("https://loja.com/b", tipo="produto")
    tempos = [x for x, _, _ in t.chamadas]
    assert 20 <= tempos[2] - tempos[1] <= 23


async def test_lojas_diferentes_nao_esperam_uma_pela_outra(relogio, transporte):
    c = cliente(relogio, transporte)
    await c.obter("https://a.com/p", tipo="produto")
    fim_a = relogio.agora()
    await c.obter("https://b.com/p", tipo="produto")
    # robots.txt de b.com sai na hora: o intervalo de a.com não se aplica a b.com.
    inicio_b = next(t for t, u, _ in transporte.chamadas if u.startswith("https://b.com"))
    assert inicio_b == fim_a


async def test_concorrencia_1_por_loja(relogio):
    import asyncio

    ativas = {"agora": 0, "max": 0}

    class Lento(TransporteFalso):
        async def get(self, url, cab, timeout):
            ativas["agora"] += 1
            ativas["max"] = max(ativas["max"], ativas["agora"])
            await asyncio.sleep(0)
            ativas["agora"] -= 1
            return await super().get(url, cab, timeout)

    c = cliente(relogio, Lento(relogio))
    await asyncio.gather(*(c.obter(f"https://loja.com/p/{i}", tipo="produto") for i in range(4)))
    assert ativas["max"] == 1


@pytest.mark.parametrize("url", [
    "https://loja.com/carrinho",
    "https://loja.com/checkout/pagamento",
    "https://www.amazon.com.br/gp/cart/view.html",
    "https://loja.com/minha-conta",
    "ftp://loja.com/x",
])
async def test_urls_que_exigem_sessao_sao_proibidas(relogio, transporte, url):
    c = cliente(relogio, transporte)
    with pytest.raises(UrlProibida):
        await c.obter(url, tipo="produto")
    assert transporte.chamadas == []


async def test_robots_403_e_sinal_de_bloqueio(relogio, transporte):
    transporte.em("https://loja.com/robots.txt", r(403))
    c = cliente(relogio, transporte)
    with pytest.raises(SinalDeBloqueio):
        await c.obter("https://loja.com/p", tipo="produto")
    assert transporte.urls() == ["https://loja.com/robots.txt"]


async def test_robots_404_libera_e_fica_em_cache_24h(relogio, transporte):
    transporte.em("https://loja.com/robots.txt", r(404))
    c = cliente(relogio, transporte)
    await c.obter("https://loja.com/a", tipo="produto")
    relogio.t += 23 * 3600
    await c.obter("https://loja.com/b", tipo="produto")
    assert transporte.urls().count("https://loja.com/robots.txt") == 1


async def test_estado_sobrevive_a_novo_cliente(relogio, transporte, tmp_path):
    """Reiniciar o worker não zera breaker nem orçamento."""
    caminho = tmp_path / "estado.sqlite3"
    transporte.em("https://loja.com/p", r(403))
    c1 = ClienteEducado(Estado(caminho), transporte, ConfigColeta(), relogio, random.Random(1), pausada=lambda: False)
    with pytest.raises(SinalDeBloqueio):
        await c1.obter("https://loja.com/p", tipo="produto")
    c2 = ClienteEducado(Estado(caminho), transporte, ConfigColeta(), relogio, random.Random(1), pausada=lambda: False)
    with pytest.raises(LojaEmPausa):
        await c2.obter("https://loja.com/q", tipo="produto")


async def test_regressao_desafio_akamai_da_amazon_era_molde_quebrado(relogio, transporte):
    """27/11 15:11 (Black Friday): a Amazon devolveu 200 com o desafio do Akamai
    Bot Manager (bm-verify, POST /_sec/verify, prova de trabalho). Virou
    molde_quebrado, que nunca desliga; é bloqueio, e tem que escalar."""
    import gzip
    from pathlib import Path

    corpo = gzip.open(Path(__file__).parent / "fixtures" / "amazon" / "desafio_akamai_bm_verify.html.gz").read()
    transporte.em("https://loja.com/s?k=jogo+ito", Resposta(200, {"content-type": "text/html"}, corpo, "https://loja.com/s?k=jogo+ito"))
    c = cliente(relogio, transporte)
    with pytest.raises(SinalDeBloqueio):
        await c.obter("https://loja.com/s?k=jogo+ito", tipo="busca", validar=lambda resp: False)
    b = c.estado.breaker("loja.com")
    assert b.tipo_motivo == "bloqueio" and b.sinais_seguidos == 1


async def test_regressao_400_em_busca_repetia_toda_hora_sem_aviso(relogio, transporte):
    """27/11: a Ri Happy respondeu 400 (37 bytes) à busca 'jogo ito' em toda rodada.
    Como 400 não contava como molde, ninguém pausava nem avisava."""
    transporte.em("https://loja.com/api?ft=jogo+ito", r(400, b'{"error":"bad"}'))
    c = cliente(relogio, transporte)
    with pytest.raises(MoldeQuebrado):
        await c.obter("https://loja.com/api?ft=jogo+ito", tipo="busca", validar=lambda resp: True)
    assert c.estado.breaker("loja.com").tipo_motivo == "molde_quebrado"


async def test_regressao_304_sem_cache_virava_resposta_vazia(relogio, transporte):
    """27/11, API do Banco Central: 304 sem termos mandado If-None-Match (nada
    em cache). O cliente devolvia corpo vazio como se fosse resposta boa.
    Sem cópia em cache, 304 é falha transitória: sem retry, sem breaker."""
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json"
    transporte.em(url, Resposta(304, {}, b"", url))
    c = cliente(relogio, transporte)
    with pytest.raises(FalhaTransitoria):
        await c.obter(url, tipo="produto")
    assert len(transporte.sem_robots()) == 1
    b = c.estado.breaker("api.bcb.gov.br")
    assert not b.desligada and b.pausada_ate == 0
