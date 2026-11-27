import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import psycopg
import pytest

from coleta.http import Resposta
from pagamento.taxas import SERIES, atualizar_se_preciso, ler_sgs, precisa_atualizar, ultima, url_da
from tests.test_http import RelogioFalso, TransporteFalso, cliente


def sgs(data: str, valor: str) -> bytes:
    return json.dumps([{"data": data, "valor": valor}]).encode()


@pytest.fixture
def taxas(banco):
    with psycopg.connect(banco, autocommit=True) as c:
        c.execute("TRUNCATE taxa_referencia")
    return banco


def test_ler_sgs():
    assert ler_sgs(sgs("26/11/2026", "14.90")) == (date(2026, 11, 26), Decimal("14.90"))
    for ruim in (b"<html>manutencao</html>", b"[]", sgs("26/11/2026", "-1"), sgs("2026-11-26", "14.9")):
        with pytest.raises(ValueError):
            ler_sgs(ruim)


def test_series_conferidas():
    # Mudar código de série é mudar o que a calculadora usa: só com docs/fontes/bcb.md atualizado.
    assert SERIES == {"cdi_anual": 4389, "selic_meta": 432}


async def test_atualiza_uma_vez_por_dia_pelo_cliente_educado(taxas):
    relogio = RelogioFalso()
    t = TransporteFalso(relogio)
    t.em(url_da("cdi_anual"), Resposta(200, {}, sgs("26/11/2026", "14.90"), url_da("cdi_anual")))
    t.em(url_da("selic_meta"), Resposta(200, {}, sgs("27/11/2026", "15.00"), url_da("selic_meta")))
    c = cliente(relogio, t)
    assert await atualizar_se_preciso(c, taxas) == "atualizada"
    assert await atualizar_se_preciso(c, taxas) == "em_dia"
    assert sorted(t.urls()) == sorted([url_da("cdi_anual"), url_da("selic_meta"),
                                       "https://api.bcb.gov.br/robots.txt"])
    with psycopg.connect(taxas) as conn:
        u = ultima(conn)
    assert (u["data"], u["cdi_anual"], u["selic_meta"]) == (date(2026, 11, 26), Decimal("14.9000"),
                                                            Decimal("15.0000"))
    assert not precisa_atualizar(taxas)
    assert precisa_atualizar(taxas, datetime.now(timezone.utc) + timedelta(hours=21))


async def test_api_fora_do_ar_nao_derruba_e_mantem_a_ultima_taxa(taxas):
    with psycopg.connect(taxas, autocommit=True) as c:
        c.execute("INSERT INTO taxa_referencia (data, cdi_anual, atualizado_em)"
                  " VALUES ('2026-11-20', 14.8, now() - interval '3 days')")
    relogio = RelogioFalso()
    t = TransporteFalso(relogio).em(url_da("cdi_anual"), Resposta(200, {}, b"<html>fora</html>", "x"))
    assert (await atualizar_se_preciso(cliente(relogio, t), taxas)).startswith("falhou")
    with psycopg.connect(taxas) as conn:
        assert ultima(conn)["data"] == date(2026, 11, 20)


async def test_worker_pausado_nao_pede_taxa(tmp_path):
    import asyncio

    from coleta.vigiar import taxas_diarias

    relogio = RelogioFalso()
    t = TransporteFalso(relogio)
    c = cliente(relogio, t, pausada=lambda: True, dir_dados=tmp_path)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(taxas_diarias(c, checar_s=0.01), timeout=0.05)
    assert t.urls() == []


async def test_regressao_selic_com_304_impedia_salvar_o_cdi(taxas):
    """27/11: a série 432 voltou 304 (sem pedirmos) duas vezes; a 4389 veio boa
    e nada foi salvo. A calculadora só precisa do CDI: Selic fica nula."""
    relogio = RelogioFalso()
    t = TransporteFalso(relogio)
    t.em(url_da("cdi_anual"), Resposta(200, {}, sgs("26/11/2026", "13.65"), url_da("cdi_anual")))
    t.em(url_da("selic_meta"), Resposta(304, {}, b"", url_da("selic_meta")))
    assert await atualizar_se_preciso(cliente(relogio, t), taxas) == "atualizada"
    with psycopg.connect(taxas) as conn:
        u = ultima(conn)
    assert (u["cdi_anual"], u["selic_meta"]) == (Decimal("13.6500"), None)
