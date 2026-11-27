"""Categoria do produto a partir do título e da loja. Regras, sem adivinhar:
na dúvida, None (o produto fica sem categoria e só não entra em "Pra você").
"""

from __future__ import annotations

import re

from coleta.lojas_mvp import sem_acento

# Ordem importa: "Jogo de Tabuleiro" é tabuleiro antes de ser "jogo";
# "Jogo da Memória" é brinquedo, não game.
REGRAS: list[tuple[str, re.Pattern]] = [
    ("jogos-tabuleiro", re.compile(r"\btabuleiro\b|\bjogo de (?:cartas|mesa)\b|\bboard ?game\b|\bdixit\b")),
    ("brinquedos", re.compile(r"\bmemoria\b|\bbrinquedo\b|\bpelucia\b|\bboneca\b|\bquebra[- ]cabeca\b|\blego\b")),
    ("games", re.compile(r"\bps[345]\b|\bplaystation\b|\bnintendo\b|\bswitch\b|\bxbox\b|\bdualsense\b|\bjoy-?con\b")),
    ("informatica", re.compile(r"\bnotebook\b|\bmacbook\b|\bultrabook\b|\bchromebook\b")),
]
# Loja especializada: tudo dela é da categoria.
POR_LOJA = {"ludopedia": "jogos-tabuleiro"}


def categorizar(titulo: str, loja: str | None = None) -> str | None:
    if loja in POR_LOJA:
        return POR_LOJA[loja]
    t = sem_acento(titulo)
    return next((cat for cat, rx in REGRAS if rx.search(t)), None)
