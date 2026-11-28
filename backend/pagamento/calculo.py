"""Calculadora Pix × parcelado. Funções puras, só Decimal, sem banco e sem rede.

A pergunta: o dinheiro que fica aplicado enquanto as parcelas vencem rende
mais do que o desconto do Pix? Tudo é trazido a valor de hoje com a taxa
líquida mensal `i` do rendimento:

    i  = (1 + CDI_anual × %CDI × (1 − IR))^(1/12) − 1
    VP = Σ parcela / (1+i)^k    k = 1..n (1ª na fatura, ~30 dias) ou 0..n−1 (no ato)
    custo efetivo do cartão = VP − cashback
    desconto de equilíbrio  = 1 − VP / total parcelado

O IR (tabela regressiva) segue o prazo de cada opção: 10x com a 1ª em 30 dias
deixa o dinheiro aplicado ~300 dias (20%); 2x, ~60 dias (22,5%).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Literal

CENTAVO = Decimal("0.01")
UM = Decimal(1)


def aliquota_ir(dias: int) -> Decimal:
    if dias <= 180:
        return Decimal("0.225")
    if dias <= 360:
        return Decimal("0.20")
    if dias <= 720:
        return Decimal("0.175")
    return Decimal("0.15")


def taxa_mensal_liquida(cdi_anual: Decimal, pct_cdi: Decimal = UM, ir: Decimal = Decimal(0)) -> Decimal:
    """CDI anual em fração (0.149 = 14,9% a.a.); pct_cdi 1 = 100% do CDI."""
    with localcontext() as ctx:
        ctx.prec = 34
        return (UM + cdi_anual * pct_cdi * (UM - ir)) ** (UM / 12) - UM


def valor_presente(parcelas: list[Decimal], i: Decimal, no_ato: bool) -> Decimal:
    inicio = 0 if no_ato else 1
    with localcontext() as ctx:
        ctx.prec = 34
        return sum((p / (UM + i) ** (k + inicio) for k, p in enumerate(parcelas)), Decimal(0))


def desconto_equilibrio(vp: Decimal, total_parcelado: Decimal) -> Decimal:
    """Desconto mínimo no Pix para valer a pena (fração)."""
    return UM - vp / total_parcelado


def tir_mensal(valor_avista: Decimal, parcelas: list[Decimal], no_ato: bool) -> Decimal:
    """Juros mensais embutidos no parcelamento: a taxa que iguala o VP das
    parcelas ao preço à vista. Bisseção (VP é decrescente na taxa)."""
    baixo, alto = Decimal("-0.5"), Decimal(1)
    for _ in range(200):
        meio = (baixo + alto) / 2
        if valor_presente(parcelas, meio, no_ato) > valor_avista:
            baixo = meio
        else:
            alto = meio
    return (baixo + alto) / 2


@dataclass(frozen=True)
class Opcao:
    tipo: Literal["pix", "parcelado"]
    parcelas: int | None                # None = Pix
    valor_parcela: Decimal | None
    total: Decimal
    valor_presente: Decimal
    cashback: Decimal
    custo_efetivo: Decimal
    taxa_mensal: Decimal | None         # rendimento líquido usado para esta opção
    ir: Decimal | None
    desconto_equilibrio: Decimal | None
    juros_mensal: Decimal | None        # só parcelado com juros


@dataclass(frozen=True)
class Simulacao:
    recomendacao: str
    melhor: Opcao
    opcoes: list[Opcao]
    desconto_pix: Decimal               # contra o preço no cartão
    economia: Decimal                   # melhor × 2ª melhor, em valor de hoje
    premissas: dict = field(default_factory=dict)


def _br(x: Decimal, casas: int = 1) -> str:
    q = Decimal(1).scaleb(-casas)
    return f"{(x * 100).quantize(q, ROUND_HALF_UP)}".replace(".", ",")


def simular(*, preco_avista: Decimal, preco_cartao: Decimal, parcelas: int,
            valor_parcela: Decimal | None = None, taxa_mensal: Decimal | None = None,
            cdi_anual: Decimal | None = None, pct_cdi: Decimal = UM, cashback: Decimal = Decimal(0),
            no_ato: bool = False) -> Simulacao:
    """Opções: Pix e, sem juros, 1x..`parcelas`x de `preco_cartao`. Com
    `valor_parcela` cujo total passa do preço no cartão, o parcelamento tem
    juros: aí a comparação é Pix × esse plano.

    `taxa_mensal` (já líquida) vence `cdi_anual`; sem nenhum dos dois, erro:
    a calculadora não inventa rendimento."""
    if preco_avista <= 0 or preco_cartao <= 0 or parcelas < 1:
        raise ValueError("preços devem ser positivos e parcelas ≥ 1")
    if taxa_mensal is None and cdi_anual is None:
        raise ValueError("informe taxa_mensal ou cdi_anual")

    def rendimento(n: int) -> tuple[Decimal, Decimal | None]:
        if taxa_mensal is not None:
            return taxa_mensal, None
        ir = aliquota_ir(30 * (n - 1 if no_ato else n))
        return max(Decimal(0), taxa_mensal_liquida(cdi_anual, pct_cdi, ir)), ir

    com_juros = valor_parcela is not None and valor_parcela * parcelas > preco_cartao + CENTAVO
    if valor_parcela is not None:
        planos = [(parcelas, [valor_parcela] * parcelas)]
    else:
        planos = [(n, _dividir(preco_cartao, n)) for n in range(1, parcelas + 1)]

    pix = Opcao("pix", None, None, preco_avista, preco_avista, Decimal(0), preco_avista.quantize(CENTAVO),
                None, None, None, None)
    opcoes = [pix]
    for n, valores in planos:
        i, ir = rendimento(n)
        total = sum(valores, Decimal(0))
        vp = valor_presente(valores, i, no_ato)
        cb = (total * cashback).quantize(CENTAVO)
        opcoes.append(Opcao(
            "parcelado", n, valores[0], total, vp.quantize(CENTAVO), cb, (vp - cb).quantize(CENTAVO), i, ir,
            desconto_equilibrio(vp, total),
            tir_mensal(preco_avista, valores, no_ato) if com_juros else None))
    # Empate: o Pix vence (mais simples), e menos parcelas antes de mais.
    opcoes.sort(key=lambda o: (o.custo_efetivo, o.tipo != "pix", o.parcelas or 0))
    melhor = opcoes[0]
    segunda = opcoes[1]
    # Desconto do Pix contra o plano que concorre com ele (o melhor parcelado).
    plano = next(o for o in opcoes if o.tipo == "parcelado")
    desconto_pix = UM - preco_avista / plano.total
    economia = (segunda.custo_efetivo - melhor.custo_efetivo).quantize(UM, ROUND_HALF_UP)

    if melhor.tipo == "pix":
        if plano.juros_mensal is not None and plano.juros_mensal > (plano.taxa_mensal or 0):
            frase = (f"Pague no Pix. O parcelamento em {plano.parcelas}x cobra {_br(plano.juros_mensal, 2)}% a.m., "
                     f"acima dos {_br(plano.taxa_mensal, 2)}% que seu dinheiro rende.")
        elif economia > 0:
            frase = (f"Pague no Pix. O desconto de {_br(desconto_pix)}% supera o que o dinheiro renderia "
                     f"parcelado em {plano.parcelas}x (equilíbrio: {_br(plano.desconto_equilibrio)}%). "
                     f"Você economiza ~R$ {economia} em valor de hoje.")
        else:
            frase = "Tanto faz: no valor de hoje, Pix e parcelado custam o mesmo. Pague no Pix, que é mais simples."
    else:
        juros = "sem juros" if melhor.juros_mensal is None else "com juros"
        if desconto_pix <= 0:
            # Sem desconto não há o que comparar: "o desconto é só 0,0%" soava a erro.
            if melhor.parcelas == 1:
                frase = "Sem desconto no Pix: pague no cartão em 1x e deixe o dinheiro rendendo até a fatura."
            else:
                frase = f"Sem desconto no Pix: parcele em {melhor.parcelas}x {juros} e deixe o dinheiro rendendo."
        else:
            frase = (f"Parcele em {melhor.parcelas}x {juros}. O desconto no Pix é só {_br(desconto_pix)}%, abaixo "
                     f"dos {_br(melhor.desconto_equilibrio)}% que seu dinheiro rende no período. "
                     f"Deixe o valor aplicado.")
    return Simulacao(frase, melhor, opcoes, desconto_pix, economia,
                     {"no_ato": no_ato, "cashback": cashback, "pct_cdi": pct_cdi, "cdi_anual": cdi_anual,
                      "taxa_mensal_informada": taxa_mensal})


def _dividir(total: Decimal, n: int) -> list[Decimal]:
    """Parcelas em centavos; a diferença do arredondamento vai na 1ª, como as lojas fazem."""
    base = (total / n).quantize(CENTAVO, rounding="ROUND_DOWN")
    return [total - base * (n - 1)] + [base] * (n - 1)
