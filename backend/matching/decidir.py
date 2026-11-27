"""Decide se dois anúncios são o mesmo produto, em camadas.

1. GTIN igual nos dois → mesmo, a não ser que o título contradiga (a Ri Happy
   repete EAN entre kit e avulso). GTIN diferente nos dois → diferente.
2. Sem GTIN: conflito duro (tipo, plataforma, capacidade, condição, digital ×
   disco) → diferente. Mesmos tokens identificadores → mesmo.
3. Faixa cinzenta (parecidos, mas sobra palavra de um lado) → parecido, nunca
   agrupado. Precisão > recall: juntar dois produtos é pior que deixar separados.
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

from matching.normalizar import GRUPOS_EXCLUSIVOS, Normalizado, normalizar

LIMIAR_PARECIDO = 75


@dataclass(frozen=True)
class Decisao:
    rotulo: str        # mesmo | parecido | diferente
    metodo: str        # gtin | titulo
    motivo: str
    score: float


def conflito(a: Normalizado, b: Normalizado) -> str | None:
    if a.tipo != b.tipo and "kit" in (a.tipo, b.tipo):
        return f"tipo {a.tipo} × {b.tipo}"
    if a.tipo != b.tipo and "outro" not in (a.tipo, b.tipo):
        return f"tipo {a.tipo} × {b.tipo}"
    if a.plataformas and b.plataformas and a.plataformas != b.plataformas:
        return f"plataforma {sorted(a.plataformas)} × {sorted(b.plataformas)}"
    # RAM pode faltar de um lado ("512GB" × "16GB RAM 512GB"); sobra dos dois lados é conflito.
    if a.capacidades - b.capacidades and b.capacidades - a.capacidades:
        return f"capacidade {sorted(a.capacidades)} × {sorted(b.capacidades)}"
    if a.com_console != b.com_console:
        return "com console × sem console"
    if a.condicao != b.condicao:
        return f"condição {a.condicao} × {b.condicao}"
    for grupo in GRUPOS_EXCLUSIVOS:
        ga, gb = a.tokens & grupo, b.tokens & grupo
        if ga and gb and ga != gb:
            return f"{sorted(ga)} × {sorted(gb)}"
    return None


def decidir(titulo_a: str, gtin_a: str | None, titulo_b: str, gtin_b: str | None) -> Decisao:
    a, b = normalizar(titulo_a), normalizar(titulo_b)
    score = fuzz.token_set_ratio(a.texto, b.texto)
    c = conflito(a, b)
    gtin_a, gtin_b = (gtin_a or "").strip() or None, (gtin_b or "").strip() or None
    if gtin_a and gtin_b:
        if gtin_a != gtin_b:
            return Decisao("diferente", "gtin", "GTIN diferente", score)
        if c:
            return Decisao("diferente", "gtin", f"GTIN igual, mas {c}", score)
        return Decisao("mesmo", "gtin", "GTIN igual", score)
    if c:
        return Decisao("diferente", "titulo", c, score)
    sobra = a.tokens ^ b.tokens
    # Capacidade só de um lado: "PS3 Slim" pode ser qualquer um dos de 120/250/320 GB.
    if bool(a.capacidades) != bool(b.capacidades):
        sobra |= {"capacidade"}
    if a.tokens and not sobra:
        return Decisao("mesmo", "titulo", "mesmos tokens", score)
    if score >= LIMIAR_PARECIDO:
        return Decisao("parecido", "titulo", f"sobra {sorted(sobra)[:4]}", score)
    return Decisao("diferente", "titulo", f"score {score:.0f}", score)
