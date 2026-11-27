"""Normalização de título de anúncio para o matching.

O título de loja mistura o produto com ruído: código interno da loja no fim
("- NT000088NSW"), palavras de vitrine ("Jogo", "Edição Standard", "Físico
Nacional"), marketing ("Promoção") e variação (cor). Aqui separamos o que
identifica o produto (tokens, plataforma, capacidade, tipo, condição) do resto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from coleta.lojas_mvp import sem_acento

# Ruído que não distingue produto: some do texto e dos tokens.
VAZIAS = frozenset("""
de da do das dos para com e o a os as em no na nos nas por pra the of and um uma
""".split())
MARKETING = frozenset("""
oferta promocao lancamento envio imediato original lacrado frete gratis novo nova oficial
""".split())
VITRINE = frozenset("""
jogo console nintendo sony apple microsoft playstation edicao edition standard padrao
fisico fisica midia nacional bundle pacote game games cor bluetooth sem fio
galapagos asmodee tabuleiro cartas mesa boardgame
""".split())
CORES = frozenset("""
preto preta branco branca azul vermelho vermelha amarelo amarela cinza prata prateado
prateada verde rosa roxo roxa laranja dourado midnight black white silver gray grey
estelar meia noite sky blue espacial ceu grafite claro escuro cool matte mist citrico
onyx charcoal
""".split())
CONDICAO = {"usado": "usado", "usada": "usado", "recondicionado": "usado", "recondicionada": "usado",
            "seminovo": "usado", "seminova": "usado", "vitrine": "usado"}
# Tipo lido nas primeiras palavras: "Capa Nintendo Switch 2" é capa, não console.
TIPOS = {
    "console": "console", "jogo": "jogo", "kit": "kit",
    "controle": "controle", "dualsense": "controle", "joycon": "controle",
    "notebook": "computador", "macbook": "computador",
    **{p: "acessorio" for p in """capa case estojo bolsa pelicula cabo carregador carregamento
       suporte dock headset fone adaptador camera cartao base grip protetor volante caneta""".split()},
}
PLATAFORMAS = frozenset({"ps5", "ps4", "ps3", "ns1", "ns2", "n3ds"})
# Grupos em que dois valores diferentes nunca são o mesmo produto.
GRUPOS_EXCLUSIVOS = (frozenset({"digital", "disco"}), frozenset({"pro", "slim", "fat"}))

# Código da loja no fim: com dígito ("- 3005767") ou em caixa alta ("- HBCPAABPA").
_CODIGO_NO_FIM = re.compile(r"\s+-\s+(?:[^\s]*\d[^\s]*|[A-Z][A-Z0-9./-]{5,})\s*$")
_CAPACIDADE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(gb|tb)\b")
_ALIASES = [
    (re.compile(r"['’`´]"), ""),
    (re.compile(r"&"), " e "),
    (re.compile(r"[ºª°]"), " "),
    (re.compile(r"\bplaystation\s*5\b|\bps\s?5\b"), " ps5 "),
    (re.compile(r"\bplaystation\s*4\b|\bps\s?4\b"), " ps4 "),
    (re.compile(r"\bplaystation\s*3\b|\bps\s?3\b"), " ps3 "),
    (re.compile(r"\bnintendo\s+3ds\b|\b3ds\b"), " n3ds "),
    # "Switch 2" antes de "Switch": um jogo de Switch não é de Switch 2.
    (re.compile(r"\b(?:nintendo\s+)?switch\s*2\b|\bns2\b"), " ns2 "),
    (re.compile(r"\bswitch\b"), " ns1 "),
    (re.compile(r"\bjoy[\s-]?con\b"), "joycon"),
    (re.compile(r"\bdual\s?sense\b"), "dualsense"),
    (re.compile(r"\bcontroller\b|\bcontroles\b"), "controle"),
    (re.compile(r"\bleitor\s+de\s+(?:discos?|blue?[\s-]?ray)\b|\bdis[ck]o?s?\b|\bdisk\b|\bdisc\b"), " disco "),
    (re.compile(r"\bz-a\b"), "za"),
]


@dataclass(frozen=True)
class Normalizado:
    texto: str                         # tokens que identificam o produto, na ordem
    tokens: frozenset[str]
    plataformas: frozenset[str] = field(default_factory=frozenset)
    capacidades: frozenset[int] = field(default_factory=frozenset)  # em GB
    cores: frozenset[str] = field(default_factory=frozenset)
    tipo: str = "outro"
    condicao: str = "novo"
    com_console: bool = False          # bundle/pacote: console + jogo não é o jogo avulso


def _eh_codigo(t: str) -> bool:
    # SKU da loja: "nsca10000078fgr", "1000049892". Curto como "m5", "a515" fica.
    letras = any(c.isalpha() for c in t)
    digitos = any(c.isdigit() for c in t)
    return (letras and digitos and len(t) >= 7) or (t.isdigit() and len(t) >= 6)


def normalizar(titulo: str) -> Normalizado:
    s = titulo
    for _ in range(2):
        s = _CODIGO_NO_FIM.sub("", s)
    # Antes do sem_acento: o NFKD transforma "™" em "TM" ("dualsensetm").
    s = re.sub(r"[®™©]", " ", s)
    s = sem_acento(s)
    for rx, novo in _ALIASES:
        s = rx.sub(novo, s)

    capacidades = set()
    for valor, unidade in _CAPACIDADE.findall(s):
        gb = float(valor.replace(",", "."))
        capacidades.add(int(gb * 1024 if unidade == "tb" else gb))
    s = _CAPACIDADE.sub(" ", s)

    brutos = [t for t in re.findall(r"[a-z0-9]+", s) if t not in VAZIAS and not _eh_codigo(t)]
    tipo = next((TIPOS[t] for t in brutos[:3] if t in TIPOS), "outro")
    plataformas = {t for t in brutos if t in PLATAFORMAS}
    cores = {t for t in brutos if t in CORES}
    condicao = next((CONDICAO[t] for t in brutos if t in CONDICAO), "novo")
    fora = PLATAFORMAS | CORES | MARKETING | VITRINE | CONDICAO.keys()
    ordem = [t for t in brutos if t not in fora]
    return Normalizado(
        texto=" ".join(dict.fromkeys(ordem)),
        tokens=frozenset(ordem),
        plataformas=frozenset(plataformas),
        capacidades=frozenset(capacidades),
        cores=frozenset(cores),
        tipo=tipo,
        condicao=condicao,
        com_console=any(t in ("console", "bundle", "pacote") for t in brutos),
    )
