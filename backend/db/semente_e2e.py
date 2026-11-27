"""Banco do e2e do frontend: recria *_e2e e grava anúncios fictícios com histórico.

Uso: python -m db.semente_e2e postgresql://.../sossego_e2e
Nada sai para a rede: títulos e preços são inventados no formato dos reais.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg

from db.recriar import recriar
from matching.associar import associar

# (loja, id, título, [(horas atrás, preço)], pix)
ANUNCIOS = [
    ("kabum", "e2e-ps5", "Console Sony PlayStation 5 Slim Digital, SSD 825GB",
     [(100, "4499.00"), (30, "4399.00"), (1, "4289.00")], "4289.00"),
    ("amazon", "e2e-ps5-a", "Console Sony PlayStation 5 Slim Digital SSD 825GB",
     [(90, "4599.00"), (2, "4369.05")], None),
    ("kabum", "e2e-dualsense", "Controle Sem Fio Sony DualSense, PlayStation 5, Branco",
     [(120, "449.00"), (1, "399.00")], "371.07"),
    ("kabum", "e2e-mk8", "Jogo Mario Kart 8 Deluxe, Nintendo Switch",
     [(80, "349.90"), (1, "299.90")], "284.90"),
    ("amazon", "e2e-mk8-a", "Mario Kart 8 Deluxe - Nintendo Switch", [(2, "319.00")], None),
    ("ludopedia", "e2e-dixit", "Dixit", [(150, "219.90"), (1, "199.90")], None),
    ("ri-happy", "e2e-dixit-r", "Jogo Dixit - Galápagos", [(3, "189.90")], "180.40"),
    ("ludopedia", "e2e-ito", "Ito", [(50, "129.90"), (1, "139.90")], None),
    ("kabum", "e2e-note", "Notebook Lenovo IdeaPad Slim 3, Intel Core i5, 16GB RAM, SSD 512GB, 15.6\"",
     [(60, "3299.00"), (1, "2999.00")], "2849.05"),
]


def semear(url: str) -> int:
    agora = datetime.now(timezone.utc)
    with psycopg.connect(url, autocommit=True) as c:
        for loja, ide, titulo, precos, pix in ANUNCIOS:
            (loja_id,) = c.execute("SELECT id FROM loja WHERE slug = %s", (loja,)).fetchone()
            (aid,) = c.execute(
                "INSERT INTO anuncio (loja_id, id_externo, url, titulo_original, primeira_vez_em, ultima_coleta_em)"
                " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (loja_id, ide, f"https://example.com/{loja}/{ide}", titulo,
                 agora - timedelta(hours=precos[0][0]), agora - timedelta(hours=precos[-1][0]))).fetchone()
            for horas, preco in precos:
                c.execute("INSERT INTO preco_snapshot (anuncio_id, coletado_em, preco, preco_pix, em_estoque, origem)"
                          " VALUES (%s, %s, %s, %s, true, 't')",
                          (aid, agora - timedelta(hours=horas), Decimal(preco), pix))
    associar(url, [])
    return len(ANUNCIOS)


if __name__ == "__main__":
    url = recriar(sys.argv[1])
    print(f"semeado: {semear(url)} anúncios em {url}")
