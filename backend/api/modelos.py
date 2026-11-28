"""Contrato da API (/api/v1). O OpenAPI sai daqui: mudar campo é mudar contrato.

Dinheiro é Decimal e vai no JSON como string ("4289.00"), nunca float.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

FaixaEtaria = Literal["ate-17", "18-24", "25-34", "35-44", "45-59", "60+"]
Genero = Literal["feminino", "masculino", "outro", "prefiro-nao-dizer"]
Dinheiro = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


def _sem_repetir(v: list[str]) -> list[str]:
    return list(dict.fromkeys(x.strip().lower() for x in v if x.strip()))


class PerfilEntrada(BaseModel):
    faixa_etaria: FaixaEtaria
    genero: Genero | None = None
    categorias: list[str] = Field(default_factory=list, max_length=3, description="slugs, máx. 3")
    lojas: list[str] = Field(default_factory=list, max_length=3,
                             description="slugs, máx. 3; vazio = sem preferência")
    interesses: list[Annotated[str, Field(max_length=60)]] = Field(
        default_factory=list, max_length=20, description='termos livres: "ps5", "dixit"')

    _limpa = field_validator("categorias", "lojas", "interesses")(_sem_repetir)


class Perfil(PerfilEntrada):
    id: UUID


class Loja(BaseModel):
    slug: str
    nome: str
    dominio: str
    icone: str | None
    coleta_ativa: bool


class Categoria(BaseModel):
    slug: str
    nome: str
    icone: str


class Card(BaseModel):
    """Produto no formato do card: o menor preço agora e de onde ele vem."""
    id: int
    titulo: str
    imagem: str | None
    imagem_local: str | None = Field(None, description="cópia local (WebP) servida pela API; null = placeholder")
    categoria: str | None
    menor_preco: Decimal
    loja: str
    loja_nome: str
    loja_icone: str | None
    url: str
    menor_pix: Decimal | None
    outras_lojas: int = Field(description='para "+N lojas a partir de R$ X"')
    outras_a_partir: Decimal | None
    variacao_pct: Decimal | None = Field(
        description="contra o NOSSO menor preço do dia mais antigo dos últimos 7 dias (não o 'de' da loja); "
                    "null se só temos o dia de hoje")
    variacao_desde: date | None
    menor_visto: Decimal | None
    menor_visto_em: date | None


class Recomendacao(Card):
    porque: str


class ResultadoBusca(BaseModel):
    q: str
    categoria: str | None = None
    ordem: str
    total: int
    resultados: list[Card]
    fonte: Literal["historico"] = Field(
        "historico", description="lê o que o coletor já gravou; a busca não dispara requisição a loja")


class Oferta(BaseModel):
    anuncio_id: int
    loja: str
    loja_nome: str
    loja_icone: str | None
    url: str
    titulo_original: str
    vendedor: str | None
    variacao: dict
    imagem: str | None
    imagem_local: str | None = None
    preco_de: Decimal | None
    preco: Decimal
    preco_pix: Decimal | None
    parcelas_max: int | None
    parcela_valor: Decimal | None
    parcelas_sem_juros: int | None
    frete: Decimal | None
    em_estoque: bool | None
    coletado_em: datetime
    ultima_coleta_em: datetime
    desatualizada: bool = Field(description="a loja não mostra este anúncio há mais de 48 h")


class PrecoVisto(BaseModel):
    preco: Decimal
    em: datetime
    loja: str


class Produto(BaseModel):
    id: int
    titulo: str
    marca: str | None
    modelo: str | None
    gtin: str | None
    imagem: str | None
    descricao: str | None
    especificacoes: dict
    categoria: str | None
    a_confirmar: bool = Field(description="grupo manual com edição ainda a confirmar")
    ofertas: list[Oferta]
    menor_visto: PrecoVisto | None


class Ponto(BaseModel):
    em: datetime
    preco: Decimal
    preco_pix: Decimal | None = None


class Serie(BaseModel):
    anuncio_id: int
    loja: str
    titulo: str
    pontos: list[Ponto]


class Historico(BaseModel):
    produto_id: int
    periodo: str
    desde: datetime | None
    series: list[Serie] = Field(description="uma por anúncio; desenhar em degrau (stepAfter)")
    menor_geral: list[Ponto] = Field(description="menor preço entre todas as séries, em degrau")
    menor_visto: PrecoVisto | None


class VigiaEntrada(BaseModel):
    preco_alvo: Dinheiro | None = None


class Vigia(BaseModel):
    produto_id: int
    preco_alvo: Decimal | None


class Queda(BaseModel):
    """Pronto para virar card em outro sistema (hubbia), sem LLM."""
    perfil_id: UUID
    produto_id: int
    titulo: str
    preco_antes: Decimal | None
    preco_agora: Decimal
    queda_pct: Decimal | None
    preco_alvo: Decimal | None
    alvo_atingido: bool
    motivo: str
    loja: str
    loja_nome: str
    url: str


class Inicio(BaseModel):
    de_olho: list[Card]
    pra_voce: list[Recomendacao]
    caiu_de_preco: list[Card]
    categorias: list[Categoria] = Field(description="as do perfil primeiro")


class SaudeLoja(BaseModel):
    slug: str
    nome: str
    situacao: str = Field(description="ok, atrasada, bloqueio, molde_quebrado, desligada, inativa, sem_estado")
    texto: str
    ultima_ok: datetime | None = Field(description="última requisição ok (estado da coleta)")
    ultima_execucao_ok: datetime | None = Field(description="último bruto processado ok (Postgres)")


class Saude(BaseModel):
    banco: Literal["ok", "erro"]
    worker_vivo: bool
    worker_batimento_em: datetime | None
    lojas: list[SaudeLoja]


Porcento = Annotated[Decimal, Field(ge=0, le=100, max_digits=7, decimal_places=4)]


class SimulacaoEntrada(BaseModel):
    """Percentuais em % (1.07 = 1,07%). Sem `rendimento_mensal_pct`, usa o CDI
    salvo do Banco Central × `pct_cdi`, com IR regressivo pelo prazo."""
    preco_avista: Dinheiro = Field(description="Pix/boleto")
    preco_cartao: Dinheiro
    parcelas: int = Field(ge=1, le=24, description="máximo sem juros, ou o nº do plano com juros")
    valor_parcela: Dinheiro | None = Field(None, description="só para parcelado com juros")
    rendimento_mensal_pct: Porcento | None = Field(None, description="líquido; vence o CDI")
    pct_cdi: Annotated[Decimal, Field(gt=0, le=300)] = Decimal(100)
    cashback_pct: Porcento = Decimal(0)
    primeira_parcela: Literal["30d", "ato"] = "30d"


class OpcaoPagamento(BaseModel):
    tipo: Literal["pix", "parcelado"]
    parcelas: int | None
    valor_parcela: Decimal | None
    total: Decimal
    valor_presente: Decimal
    cashback: Decimal
    custo_efetivo: Decimal = Field(description="valor de hoje: VP das parcelas − cashback")
    rendimento_mensal_pct: Decimal | None
    ir_pct: Decimal | None
    desconto_equilibrio_pct: Decimal | None = Field(description="desconto mínimo no Pix para valer a pena")
    juros_mensal_pct: Decimal | None


class Simulacao(BaseModel):
    recomendacao: str
    melhor: OpcaoPagamento
    opcoes: list[OpcaoPagamento] = Field(description="ordenadas pelo custo efetivo")
    desconto_pix_pct: Decimal
    economia: Decimal = Field(description="melhor × 2ª opção, em reais de hoje")
    rendimento_fonte: Literal["informado", "cdi_bcb"]
    cdi_anual_pct: Decimal | None
    cdi_data: date | None = Field(description="data da taxa usada; pode ser antiga se o BCB estiver fora")
