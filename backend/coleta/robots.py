"""Leitura de robots.txt conforme a RFC 9309 (regra mais longa vence).

Não usamos urllib.robotparser porque ele aplica a *primeira* regra que casa,
não a mais longa, e ignora curingas. Isso pode liberar caminho que a loja
proibiu. Como nos apresentamos com User-Agent de navegador, valem os grupos
`User-agent: *`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass
class Robots:
    regras: list[tuple[bool, str, re.Pattern]] = field(default_factory=list)  # (permite, padrao, regex)
    crawl_delay: float | None = None
    bloqueia_tudo: bool = False

    def permite(self, url: str) -> bool:
        if self.bloqueia_tudo:
            return False
        partes = urlsplit(url)
        caminho = (partes.path or "/") + (f"?{partes.query}" if partes.query else "")
        melhor: tuple[int, bool] | None = None
        for permite, padrao, rx in self.regras:
            if rx.match(caminho):
                chave = (len(padrao), permite)  # empate de tamanho: Allow vence
                if melhor is None or chave > melhor:
                    melhor = chave
        return True if melhor is None else melhor[1]


def _regex(padrao: str) -> re.Pattern:
    ancorado = padrao.endswith("$")
    corpo = padrao[:-1] if ancorado else padrao
    rx = "".join(".*" if c == "*" else re.escape(c) for c in corpo)
    return re.compile(rx + ("$" if ancorado else ""))


def analisar(texto: str) -> Robots:
    grupos: list[dict] = []
    atual: dict | None = None
    ultima_foi_agente = False
    for bruta in texto.splitlines():
        linha = bruta.split("#", 1)[0].strip()
        if ":" not in linha:
            continue
        campo, valor = (p.strip() for p in linha.split(":", 1))
        campo = campo.lower()
        if campo == "user-agent":
            if atual is None or not ultima_foi_agente:
                atual = {"agentes": set(), "regras": [], "delay": None}
                grupos.append(atual)
            atual["agentes"].add(valor.lower())
            ultima_foi_agente = True
            continue
        ultima_foi_agente = False
        if atual is None:
            continue
        if campo in ("allow", "disallow") and valor:
            atual["regras"].append((campo == "allow", valor, _regex(valor)))
        elif campo == "crawl-delay":
            try:
                atual["delay"] = float(valor)
            except ValueError:
                pass

    robots = Robots()
    for g in grupos:
        if "*" in g["agentes"]:
            robots.regras.extend(g["regras"])
            if g["delay"] is not None:
                robots.crawl_delay = max(robots.crawl_delay or 0, g["delay"])
    return robots
