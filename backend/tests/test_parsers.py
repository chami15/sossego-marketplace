"""Parse determinístico contra respostas reais salvas em 26/11/2026."""

import gzip
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from coleta.base import brl
from coleta.parsers import PARSERS, SemOfertas

FIX = Path(__file__).parent / "fixtures"
AGORA = datetime(2026, 11, 26, 21, 46, tzinfo=timezone.utc)


def fixture(loja, nome):
    return gzip.open(FIX / loja / f"{nome}.gz", "rt", encoding="utf-8").read()


def por_id(ofertas):
    return {o.id_externo: o for o in ofertas}


def test_amazon_busca_ps5():
    of = PARSERS["amazon"](fixture("amazon", "busca_ps5.html"), AGORA)
    assert len(of) >= 50
    o = por_id(of)["B0GWNKJDCZ"]
    assert o.titulo == "Sony PlayStation 5 Edição Digital 825GB 1 Controle"
    assert o.preco == Decimal("4259.00") and o.url == "https://www.amazon.com.br/dp/B0GWNKJDCZ"
    assert not o.patrocinado


def test_amazon_marca_patrocinado_e_limpa_titulo():
    o = por_id(PARSERS["amazon"](fixture("amazon", "busca_ps5.html"), AGORA))["B017RBNOI4"]
    assert o.patrocinado and o.titulo.startswith("Volante e Pedais Logitech G29")
    assert o.preco == Decimal("1319.13") and o.preco_de == Decimal("1799.90")


def test_ludopedia_busca_dixit():
    o = por_id(PARSERS["ludopedia"](fixture("ludopedia", "busca_dixit.html"), AGORA))
    assert o["606"].titulo == "Dixit" and o["606"].preco == Decimal("145.50")
    assert o["612"].titulo == "Dixit: Odyssey" and o["612"].preco == Decimal("60.00")
    assert o["606"].url == "https://ludopedia.com.br/jogo/dixit"


def test_ri_happy_vtex_com_ean_pix_e_parcelas():
    of = PARSERS["ri-happy"](fixture("ri-happy", "busca_dixit.json"), AGORA)
    assert len(of) == 20 and sum(bool(o.gtin) for o in of) >= 15
    o = next(x for x in of if x.titulo == "Jogo De Tabuleiro - Dixit - Galápagos")
    assert o.preco == Decimal("179.99") and o.preco_de == Decimal("199.99")
    assert o.preco_pix == Decimal("170.99")
    assert o.parcelas_sem_juros == 5 and o.parcela_valor == Decimal("35.99")
    assert o.gtin == "3558387010060"


def test_dinheiro_e_decimal_nunca_float():
    for loja, nome in [("amazon", "busca_ps5.html"), ("ri-happy", "busca_dixit.json")]:
        for o in PARSERS[loja](fixture(loja, nome), AGORA):
            assert isinstance(o.preco, Decimal)


@pytest.mark.parametrize("loja", ["amazon", "ludopedia"])
def test_intersticio_do_ml_nao_vira_oferta_vazia_silenciosa(loja):
    with pytest.raises(SemOfertas):
        PARSERS[loja](fixture("mercado-livre", "busca_ps5_intersticio.html"), AGORA)


@pytest.mark.parametrize("texto,esperado", [
    ("R$ 1.319,13", Decimal("1319.13")), ("R$\xa060,00", Decimal("60.00")),
    ("R$ 4.606,55", Decimal("4606.55")), ("sem preço", None), (None, None),
])
def test_brl(texto, esperado):
    assert brl(texto) == esperado
