"""Contrato comum: toda loja vira uma lista de Oferta. O resto do sistema não
sabe de onde o dado veio."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, Field, field_validator


class Oferta(BaseModel):
    loja: str
    id_externo: str
    url: str
    titulo: str
    imagem: str | None = None
    marca: str | None = None
    gtin: str | None = None
    vendedor: str | None = None
    variacao: dict[str, str] = Field(default_factory=dict)
    preco_de: Decimal | None = None
    preco: Decimal                     # preço cheio no cartão (ou o único informado)
    preco_pix: Decimal | None = None
    parcelas_max: int | None = None
    parcela_valor: Decimal | None = None
    parcelas_sem_juros: int | None = None
    frete: Decimal | None = None       # None = não informado; 0 = grátis
    em_estoque: bool = True
    patrocinado: bool = False
    coletado_em: datetime

    @field_validator("preco")
    @classmethod
    def _preco_positivo(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("preço deve ser > 0")
        return v

    def alertas(self) -> list[str]:
        """Inconsistências que impedem virar snapshot (viram alerta no log)."""
        a = []
        if self.preco_pix is not None and self.preco_pix > self.preco:
            a.append(f"Pix ({self.preco_pix}) maior que o preço cheio ({self.preco})")
        if self.parcelas_max and self.parcela_valor:
            total = self.parcela_valor * self.parcelas_max
            if abs(total - self.preco) / self.preco > Decimal("0.5"):
                a.append(f"{self.parcelas_max}x {self.parcela_valor} longe do preço {self.preco}")
        return a


_RE_BRL = re.compile(r"(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})")


def brl(texto: str | None) -> Decimal | None:
    """'R$ 1.319,13' -> Decimal('1319.13'). Nunca float."""
    if not texto:
        return None
    m = _RE_BRL.search(texto.replace("\xa0", " "))
    if not m:
        return None
    try:
        return Decimal(f"{m.group(1).replace('.', '')}.{m.group(2)}")
    except InvalidOperation:
        return None


def dec(v) -> Decimal | None:
    """Número JSON (VTEX manda float) -> Decimal via str, sem herdar erro binário."""
    if v is None:
        return None
    return Decimal(str(v)).quantize(Decimal("0.01"))
