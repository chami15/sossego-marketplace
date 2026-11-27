"""Parse determinístico contra respostas reais salvas em 26/11/2026."""

import gzip
import json
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


KABUM_EM = datetime(2026, 11, 26, 22, 25, tzinfo=timezone.utc)  # hora da coleta real


def test_kabum_pix_e_de_conferidos_na_tela():
    # Tela em 27/11 (dono): Pix 4.274,05 = 0,95 x 4.499; "de" 4.893,76; 10x 449,90.
    # Mesmo padrão no JSON de 26/11: offer.priceWithDiscount = 0,95 x offer.price.
    o = por_id(PARSERS["kabum"](fixture("kabum", "busca_ps5.html"), KABUM_EM))["989702"]
    assert o.preco == Decimal("4599.00")  # 10 x 459,90 == offer.price
    assert o.parcelas_max == 10 and o.parcela_valor == Decimal("459.90")
    assert o.preco_pix == Decimal("4369.05")
    # oldPrice (4.893,76) batia com a tela neste dia, mas não às 16:44 de 27/11: "de" = None.
    assert o.preco_de is None
    assert o.parcelas_sem_juros == 10  # 10 x 459,90 == preço vigente: sem juros
    assert o.em_estoque and o.vendedor == "KaBuM!"
    assert o.url.startswith("https://www.kabum.com.br/produto/989702/")


def test_kabum_descarta_quando_parcelado_nao_bate_com_preco_vigente():
    # Fora da janela da oferta, o vigente vira `price` (4893,76) e 10 x 459,90 não bate.
    depois_da_oferta = datetime(2027, 1, 1, tzinfo=timezone.utc)
    ids = por_id(PARSERS["kabum"](fixture("kabum", "busca_ps5.html"), depois_da_oferta))
    assert "989702" not in ids


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


def _pagina_kabum(produto):
    dados = json.dumps({"catalogServer": {"data": [produto]}})
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps({"props": {"pageProps": {"data": dados}}})}</script>'


def test_regressao_kabum_preco_pelo_parcelado_arredondado_ficava_abaixo_do_pix():
    """27/11: MacBook a R$ 20.097,41 em "10x de R$ 2.009,74" (arredondado para baixo).
    O preço saía 20.097,40, um centavo abaixo do Pix (= preço, sem desconto), e a
    oferta virava alerta em vez de snapshot."""
    p = {"code": 1081920, "name": "Macbook Air M5", "friendlyName": "macbook-air-m5", "available": True,
         "sellerName": "KaBuM!", "price": 20097.41, "oldPrice": 20097.41, "priceWithDiscount": 20097.41,
         "maxInstallment": "10x de R$ 2.009,74", "offer": None}
    (o,) = PARSERS["kabum"](_pagina_kabum(p), KABUM_EM)
    assert o.preco == Decimal("20097.41")
    assert o.preco_pix == Decimal("20097.41")  # Pix = cartão: a tela de 16:44 confirmou que acontece
    assert o.alertas() == []


def test_regressao_kabum_pix_igual_ao_cartao_virava_none_e_de_vinha_errado():
    """27/11 16:15 (bruto) x 16:44 (tela do dono): Pix 4.499 = cartão nos dois, então
    o JSON é confiável e Pix igual ao cartão é Pix. O "de" da tela era 4.893,76, que
    não aparece no bruto; oldPrice dizia 4.649,07. "de" fica None até achar a fonte."""
    p = {"code": 989702, "name": "PS5", "friendlyName": "ps5", "available": True, "sellerName": "KaBuM!",
         "price": 4649.07, "oldPrice": 4649.07, "priceWithDiscount": 4649.07, "maxInstallment": "10x de R$ 449,90",
         "offer": {"price": 4499, "priceWithDiscount": 4499, "startsAt": 0, "endsAt": 4_000_000_000}}
    (o,) = PARSERS["kabum"](_pagina_kabum(p), KABUM_EM)
    assert o.preco == Decimal("4499.00") and o.preco_pix == Decimal("4499.00")
    assert o.preco_de is None
    assert o.parcelas_max == 10 and o.parcelas_sem_juros == 10
