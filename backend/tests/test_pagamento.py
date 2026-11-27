from decimal import Decimal as D

import pytest

from pagamento.calculo import (aliquota_ir, desconto_equilibrio, simular, taxa_mensal_liquida, tir_mensal,
                               valor_presente)


def pct(x: D) -> D:
    return (x * 100).quantize(D("0.01"))


# ---------- aceitação (seção 6 do prompt, conferidos à mão) ----------

def test_aceitacao_10x_de_1000_no_ato_equilibrio_4_63():
    vp = valor_presente([D(1000)] * 10, D("0.0107"), no_ato=True)
    assert pct(desconto_equilibrio(vp, D(10000))) == D("4.63")


def test_aceitacao_10x_de_1000_em_30_dias_equilibrio_5_64():
    vp = valor_presente([D(1000)] * 10, D("0.0107"), no_ato=False)
    assert pct(desconto_equilibrio(vp, D(10000))) == D("5.64")


def test_aceitacao_pix_sem_desconto_recomenda_parcelar_sem_juros():
    r = simular(preco_avista=D(1000), preco_cartao=D(1000), parcelas=10, taxa_mensal=D("0.01"))
    assert r.melhor.tipo == "parcelado" and r.melhor.parcelas == 10
    assert r.recomendacao.startswith("Parcele em 10x sem juros.")


def test_aceitacao_parcelado_com_juros_de_3_contra_rendimento_de_1_recomenda_pix():
    parcela = valor_parcela_price(D(1000), D("0.03"), 10)
    r = simular(preco_avista=D(1000), preco_cartao=D(1000), parcelas=10, valor_parcela=parcela,
                taxa_mensal=D("0.01"))
    assert r.melhor.tipo == "pix"
    parcelado = next(o for o in r.opcoes if o.parcelas == 10)
    assert parcelado.juros_mensal is not None and abs(parcelado.juros_mensal - D("0.03")) < D("0.0001")
    assert r.recomendacao.startswith("Pague no Pix.")


def valor_parcela_price(pv: D, i: D, n: int) -> D:
    return (pv * i / (1 - (1 + i) ** -n)).quantize(D("0.01"))


# ---------- peças ----------

def test_frase_do_pix_com_numeros_do_exemplo():
    # 10% de desconto contra 10x sem juros a 1,07% a.m. (equilíbrio 5,64%).
    r = simular(preco_avista=D(900), preco_cartao=D(1000), parcelas=10, taxa_mensal=D("0.0107"))
    assert r.melhor.tipo == "pix"
    assert r.recomendacao == ("Pague no Pix. O desconto de 10,0% supera o que o dinheiro renderia parcelado "
                              "em 10x (equilíbrio: 5,6%). Você economiza ~R$ 44 em valor de hoje.")


def test_frase_do_parcelado_quando_o_desconto_e_pequeno():
    r = simular(preco_avista=D(970), preco_cartao=D(1000), parcelas=10, taxa_mensal=D("0.0107"))
    assert r.recomendacao == ("Parcele em 10x sem juros. O desconto no Pix é só 3,0%, abaixo dos 5,6% que "
                              "seu dinheiro rende no período. Deixe o valor aplicado.")


def test_opcoes_ordenadas_pelo_custo_efetivo_e_cashback_desconta():
    r = simular(preco_avista=D(1000), preco_cartao=D(1000), parcelas=3, taxa_mensal=D("0.01"),
                cashback=D("0.02"))
    custos = [o.custo_efetivo for o in r.opcoes]
    assert custos == sorted(custos)
    assert [o.parcelas for o in r.opcoes] == [3, 2, 1, None]          # Pix (sem cashback) por último
    um = next(o for o in r.opcoes if o.parcelas == 1)
    assert um.custo_efetivo == (D(1000) / D("1.01") - D(20)).quantize(D("0.01"))


def test_taxa_mensal_liquida_do_cdi_com_ir():
    # 100% do CDI a 14,9% a.a., IR 20%: (1 + 0,1192)^(1/12) − 1.
    i = taxa_mensal_liquida(cdi_anual=D("0.149"), pct_cdi=D(1), ir=D("0.20"))
    assert abs(i - (D("1.1192") ** (D(1) / 12) - 1)) < D("1e-12")


@pytest.mark.parametrize("dias,aliquota", [(30, "0.225"), (180, "0.225"), (181, "0.20"), (360, "0.20"),
                                           (361, "0.175"), (720, "0.175"), (721, "0.15")])
def test_ir_regressivo(dias, aliquota):
    assert aliquota_ir(dias) == D(aliquota)


def test_ir_segue_o_prazo_da_opcao():
    r = simular(preco_avista=D(1000), preco_cartao=D(1000), parcelas=10, cdi_anual=D("0.149"))
    dez = next(o for o in r.opcoes if o.parcelas == 10)
    dois = next(o for o in r.opcoes if o.parcelas == 2)
    assert (dez.ir, dois.ir) == (D("0.20"), D("0.225"))              # 300 dias × 60 dias


def test_tir_de_parcelamento_sem_juros_e_zero():
    assert abs(tir_mensal(D(1000), [D(100)] * 10, no_ato=False)) < D("1e-9")


def test_rendimento_zero_empata_e_nao_quebra():
    r = simular(preco_avista=D(1000), preco_cartao=D(1000), parcelas=2, taxa_mensal=D(0))
    assert {o.custo_efetivo for o in r.opcoes} == {D("1000.00")}
    assert r.melhor.tipo == "pix"                                     # empate: o simples vence


@pytest.mark.parametrize("kw", [dict(preco_avista=D(0), preco_cartao=D(10), parcelas=1, taxa_mensal=D(0)),
                                dict(preco_avista=D(10), preco_cartao=D(10), parcelas=0, taxa_mensal=D(0)),
                                dict(preco_avista=D(10), preco_cartao=D(10), parcelas=1)])
def test_entrada_invalida(kw):
    with pytest.raises(ValueError):
        simular(**kw)
