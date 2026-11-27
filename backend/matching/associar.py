"""Liga cada anúncio a um produto. Local, sem rede, idempotente.

    python -m matching.associar            # só anúncios ainda sem produto
    python -m matching.associar --refazer  # desfaz o automático e refaz (regra mudou)

Ordem: grupos [[produto]] da vigia.toml primeiro (o dono vence o algoritmo);
depois, para cada anúncio sem produto, o primeiro candidato (mesmo GTIN ou
título parecido no pg_trgm) em que o anúncio é "mesmo" que TODOS os membros.
Exigir todos (e não só o mais parecido) é o que impede o efeito corrente:
A≈B e B≈C não pode juntar A com C se A e C não batem.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field

import psycopg

from db.consultas import consultas
from matching.categorizar import categorizar
from matching.decidir import decidir
from matching.normalizar import normalizar, termos_busca

log = logging.getLogger("matching")
Q = consultas("matching")


@dataclass
class ResumoMatching:
    manuais: int = 0
    agrupados: int = 0
    novos: int = 0
    por_metodo: dict[str, int] = field(default_factory=dict)


def _aplicar_manuais(conn, produtos: list[dict], r: ResumoMatching) -> None:
    for p in produtos:
        (pid,) = conn.execute(Q["produto_manual"], {
            "nome": p["nome"], "normalizado": normalizar(p["nome"]).texto,
            "a_confirmar": bool(p.get("edicao_a_confirmar")),
        }).fetchone()
        for a in p["anuncios"]:
            cur = conn.execute(Q["ligar_manual"], {"produto_id": pid, "loja": a["loja"], "id_externo": a["id"],
                                                   "motivo": f"grupo [[produto]] {p['nome']!r}"})
            r.manuais += cur.rowcount


def _produto_que_aceita(conn, titulo: str, gtin: str | None) -> tuple[int, str, str] | None:
    for (pid,) in conn.execute(Q["candidatos"], {"gtin": gtin, "normalizado": normalizar(titulo).texto}):
        membros = conn.execute(Q["membros"], {"produto_id": pid}).fetchall()
        decisoes = [decidir(titulo, gtin, t, g) for t, g in membros]
        if membros and all(d.rotulo == "mesmo" for d in decisoes):
            metodo = "gtin" if any(d.metodo == "gtin" for d in decisoes) else "titulo"
            return pid, metodo, decisoes[0].motivo
    return None


def _atualizar_termos(conn) -> None:
    for pid, atual, tem_categoria, titulos, loja in conn.execute(Q["todos_os_titulos"]).fetchall():
        termos = " ".join(dict.fromkeys(t for titulo in titulos for t in termos_busca(titulo).split()))
        categoria = None if tem_categoria else next(
            (c for c in (categorizar(t, loja) for t in titulos) if c), None)
        if termos != atual or categoria:
            conn.execute(Q["preencher_termos"], {"id": pid, "termos": termos, "categoria": categoria})


def associar(url_banco: str, produtos_manuais: list[dict], refazer: bool = False) -> ResumoMatching:
    r = ResumoMatching()
    with psycopg.connect(url_banco, connect_timeout=10) as conn:
        with conn.transaction():
            if refazer:
                conn.execute(Q["desligar_todos"])
                conn.execute(Q["apagar_produtos_automaticos"])
            _aplicar_manuais(conn, produtos_manuais, r)
            for anuncio_id, titulo, gtin, loja in conn.execute(Q["sem_produto"]).fetchall():
                achado = _produto_que_aceita(conn, titulo, gtin)
                if achado:
                    pid, metodo, motivo = achado
                    r.agrupados += 1
                else:
                    # GTIN é UNIQUE em produto: EAN repetido errado (kit × avulso) fica só no anúncio.
                    livre = gtin and conn.execute(Q["gtin_livre"], {"gtin": gtin}).fetchone()[0]
                    (pid,) = conn.execute(Q["novo_produto"], {
                        "titulo": titulo, "normalizado": normalizar(titulo).texto,
                        "gtin": gtin if livre else None,
                        "termos": termos_busca(titulo), "categoria": categorizar(titulo, loja)}).fetchone()
                    metodo, motivo = "novo", "nenhum produto aceitou"
                    r.novos += 1
                conn.execute(Q["ligar"], {"produto_id": pid, "metodo": metodo, "motivo": motivo,
                                          "anuncio_id": anuncio_id})
                r.por_metodo[metodo] = r.por_metodo.get(metodo, 0) + 1
            # Grupo manual pode ter tirado o único anúncio de um produto automático.
            conn.execute(Q["apagar_produtos_automaticos"])
            _atualizar_termos(conn)
    return r


if __name__ == "__main__":
    from config import database_url
    from coleta.vigiar import ler_produtos

    res = associar(database_url(), ler_produtos(), refazer="--refazer" in sys.argv)
    print(json.dumps({"manuais": res.manuais, "agrupados": res.agrupados, "novos": res.novos,
                      "por_metodo": res.por_metodo}, ensure_ascii=False))
