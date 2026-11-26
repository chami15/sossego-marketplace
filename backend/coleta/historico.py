"""Reprocessa o bruto (dados/bruto/**.json.gz) em anúncios e snapshots.

    python -m coleta.historico           # processa o que ainda não foi processado
    python -m coleta.historico --tudo    # reprocessa tudo (ex.: parser corrigido)

Regras:
- Idempotente: arquivo já processado com a mesma versão de parser é pulado;
  snapshot é único por (anúncio, instante).
- Snapshot só quando algo muda (preço, Pix, parcelas, estoque). Se nada
  mudou, só `anuncio.ultima_coleta_em` anda: o gráfico em degrau não perde nada.
- Oferta inconsistente (Pix > preço etc.) vira alerta no log, não snapshot.
- Página sem a estrutura esperada vira coleta_execucao com status 'erro'.
"""

from __future__ import annotations

import gzip
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from config import ConfigColeta, database_url
from coleta.base import Oferta
from coleta.parsers import PARSER_VERSAO, PARSERS, SemOfertas
from db.consultas import consultas

log = logging.getLogger("sossego.historico")
Q = consultas("historico")
CAMPOS_DEDUPE = ("preco", "preco_pix", "parcelas_max", "parcela_valor", "parcelas_sem_juros", "em_estoque")


@dataclass
class Resumo:
    arquivos: int = 0
    pulados: int = 0
    ofertas: int = 0
    snapshots: int = 0
    sem_mudanca: int = 0
    alertas: int = 0
    erros: list[str] = field(default_factory=list)


def _arquivos(dir_bruto: Path) -> list[Path]:
    # Nome começa com o carimbo UTC: ordem lexicográfica = ordem temporal,
    # que é o que a regra de dedupe precisa.
    return sorted(dir_bruto.glob("*/*/*.json.gz"), key=lambda p: p.name)


def gravar_oferta(conn, loja_id: int, o: Oferta, origem: str, r: Resumo) -> None:
    alertas = o.alertas()
    if alertas:
        r.alertas += 1
        log.warning(json.dumps({"evento": "oferta_inconsistente", "loja": o.loja,
                                "id_externo": o.id_externo, "alertas": alertas, "origem": origem}))
        return
    (anuncio_id,) = conn.execute(Q["upsert_anuncio"], {
        "loja_id": loja_id, "id_externo": o.id_externo, "url": o.url, "titulo": o.titulo,
        "gtin": o.gtin, "vendedor": o.vendedor, "variacao": Jsonb(o.variacao), "imagem": o.imagem,
        "coletado_em": o.coletado_em,
    }).fetchone()
    anterior = conn.execute(Q["snapshot_anterior"], {"anuncio_id": anuncio_id, "coletado_em": o.coletado_em}).fetchone()
    atual = tuple(getattr(o, c) for c in CAMPOS_DEDUPE)
    if anterior is not None and tuple(anterior) == atual:
        r.sem_mudanca += 1
        return
    cur = conn.execute(Q["inserir_snapshot"], {
        "anuncio_id": anuncio_id, "coletado_em": o.coletado_em, "preco_de": o.preco_de,
        "preco": o.preco, "preco_pix": o.preco_pix, "parcelas_max": o.parcelas_max,
        "parcela_valor": o.parcela_valor, "parcelas_sem_juros": o.parcelas_sem_juros,
        "frete": o.frete, "em_estoque": o.em_estoque, "origem": origem,
    })
    r.snapshots += cur.rowcount


def processar_arquivo(conn, arq: Path, raiz: Path, tudo: bool, r: Resumo) -> None:
    d = json.load(gzip.open(arq, "rt", encoding="utf-8"))
    loja = d["loja"]
    if d.get("tipo") not in ("busca", "produto") or loja not in PARSERS:
        return
    origem = arq.relative_to(raiz).as_posix()
    versao = PARSER_VERSAO[loja]
    feito = conn.execute(Q["ja_processado"], {"arquivo": origem}).fetchone()
    if feito and (feito[0] == versao or not tudo):
        r.pulados += 1
        return
    linha = conn.execute(Q["loja_id"], {"slug": loja}).fetchone()
    if linha is None:
        return
    loja_id = linha[0]
    coletado = datetime.fromtimestamp(d["coletado_em"], tz=timezone.utc)
    r.arquivos += 1
    with conn.transaction():
        try:
            ofertas = PARSERS[loja](d["corpo"], coletado)
        except SemOfertas as e:
            r.erros.append(f"{origem}: {e}")
            conn.execute(Q["registrar_execucao"], {"loja_id": loja_id, "inicio": coletado,
                                                   "status": "erro", "itens": 0, "erro": str(e)})
            return  # não marca como processado: parser corrigido reprocessa sozinho
        # Mesmo anúncio duas vezes na mesma página (ex.: patrocinado + orgânico): uma vez basta.
        unicas = {o.id_externo: o for o in ofertas}
        for o in unicas.values():
            gravar_oferta(conn, loja_id, o, origem, r)
        r.ofertas += len(unicas)
        conn.execute(Q["registrar_execucao"], {"loja_id": loja_id, "inicio": coletado,
                                               "status": "ok", "itens": len(unicas), "erro": None})
        conn.execute(Q["marcar_processado"], {"arquivo": origem, "ofertas": len(unicas), "parser_versao": versao})


def reprocessar(url: str, dir_bruto: Path, tudo: bool = False) -> Resumo:
    r = Resumo()
    with psycopg.connect(url, autocommit=True) as conn:
        for arq in _arquivos(dir_bruto):
            processar_arquivo(conn, arq, dir_bruto, tudo, r)
    return r


if __name__ == "__main__":
    cfg = ConfigColeta.carregar()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(cfg.dir_dados / "historico.log", encoding="utf-8")])
    res = reprocessar(database_url(), cfg.dir_dados / "bruto", tudo="--tudo" in sys.argv)
    print(f"arquivos {res.arquivos} | pulados {res.pulados} | ofertas {res.ofertas} | "
          f"snapshots novos {res.snapshots} | sem mudança {res.sem_mudanca} | alertas {res.alertas}")
    for e in res.erros:
        print("ERRO:", e)
