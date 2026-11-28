"""Banco do e2e do frontend: recria *_e2e e grava anúncios fictícios com histórico.

Uso: python -m db.semente_e2e postgresql://.../sossego_e2e
Nada sai para a rede: títulos e preços são inventados no formato dos reais, e
as imagens são desenhadas aqui (Pillow) na pasta de dados do e2e
(SOSSEGO_DIR_DADOS), nunca na dados/ de verdade.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import psycopg

from db.recriar import recriar
from matching.associar import associar

# (loja, id, título, [(horas atrás, preço)], pix, extras)
ANUNCIOS = [
    ("kabum", "e2e-ps5", "Console Sony PlayStation 5 Slim Digital, SSD 825GB",
     [(100, "4499.00"), (30, "4399.00"), (1, "4289.00")], "4289.00",
     {"parcelas_sem_juros": 10, "parcelas_max": 10, "parcela_valor": "428.90", "frete": "0.00",
      "vendedor": "KaBuM!", "cor": "#1f2a5c"}),
    ("amazon", "e2e-ps5-a", "Console Sony PlayStation 5 Slim Digital SSD 825GB",
     [(90, "4599.00"), (2, "4369.05")], None,
     {"parcelas_sem_juros": 12, "parcelas_max": 12, "parcela_valor": "364.09", "frete": "19.90"}),
    ("kabum", "e2e-dualsense", "Controle Sem Fio Sony DualSense, PlayStation 5",
     [(120, "449.00"), (1, "399.00")], "371.07",
     {"variacao": {"cor": "Branco"}, "parcelas_sem_juros": 5, "parcelas_max": 5, "parcela_valor": "79.80",
      "cor": "#e8e9ee"}),
    ("ri-happy", "e2e-dualsense-r", "Controle Sem Fio Sony DualSense PlayStation 5",
     [(5, "429.90")], None, {"variacao": {"cor": "Preto"}, "frete": "15.00", "cor": "#22252c"}),
    ("kabum", "e2e-mk8", "Jogo Mario Kart 8 Deluxe, Nintendo Switch",
     [(80, "349.90"), (1, "299.90")], "284.90", {"cor": "#d8312c"}),
    ("amazon", "e2e-mk8-a", "Mario Kart 8 Deluxe - Nintendo Switch", [(2, "319.00")], None, {}),
    ("ludopedia", "e2e-dixit", "Dixit", [(150, "219.90"), (1, "199.90")], None, {"cor": "#f0b429"}),
    ("ri-happy", "e2e-dixit-r", "Jogo Dixit - Galápagos", [(3, "189.90")], "180.40", {}),
    # Capa de 60 px, como as da busca da Ludopedia (só existe o tamanho _s).
    ("ludopedia", "e2e-ito", "Ito", [(50, "129.90"), (1, "139.90")], None, {"cor": "#3a7d44", "lado": 60}),
    ("ludopedia", "e2e-cascadia", "Cascadia", [(1, "249.90")], None, {}),  # um ponto só: "começamos hoje"
    ("kabum", "e2e-note", "Notebook Lenovo IdeaPad Slim 3, Intel Core i5, 16GB RAM, SSD 512GB, 15.6\"",
     [(60, "3299.00"), (1, "2999.00")], "2849.05", {"cor": "#7b8494"}),
]


def _desenhar(destino: Path, url: str, cor: str, lado: int = 400) -> str:
    """Um "produto" chapado (caixa com sombra) em fundo branco, como foto de loja."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (400, 400), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((92, 300, 316, 316), fill="#dcdde2")
    d.rounded_rectangle((100, 70, 300, 300), radius=10, fill=cor)
    d.rectangle((120, 96, 280, 120), fill="#ffffff")
    if lado != 400:
        img = img.resize((lado, lado))
    nome = hashlib.sha1(url.encode()).hexdigest()[:20] + ".webp"
    destino.mkdir(parents=True, exist_ok=True)
    img.save(destino / nome, "WEBP", quality=80)
    return nome


def semear(url: str, dir_dados: Path | None = None) -> int:
    agora = datetime.now(timezone.utc)
    with psycopg.connect(url, autocommit=True) as c:
        for loja, ide, titulo, precos, pix, extra in ANUNCIOS:
            (loja_id,) = c.execute("SELECT id FROM loja WHERE slug = %s", (loja,)).fetchone()
            imagem = f"https://example.com/img/{ide}.jpg"
            (aid,) = c.execute(
                "INSERT INTO anuncio (loja_id, id_externo, url, titulo_original, vendedor, variacao, imagem,"
                " primeira_vez_em, ultima_coleta_em) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (loja_id, ide, f"https://example.com/{loja}/{ide}", titulo, extra.get("vendedor"),
                 json.dumps(extra.get("variacao", {})), imagem,
                 agora - timedelta(hours=precos[0][0]), agora - timedelta(hours=precos[-1][0]))).fetchone()
            for horas, preco in precos:
                c.execute("INSERT INTO preco_snapshot (anuncio_id, coletado_em, preco, preco_pix, em_estoque,"
                          " parcelas_max, parcela_valor, parcelas_sem_juros, frete, origem)"
                          " VALUES (%s, %s, %s, %s, true, %s, %s, %s, %s, 't')",
                          (aid, agora - timedelta(hours=horas), Decimal(preco), pix, extra.get("parcelas_max"),
                           extra.get("parcela_valor"), extra.get("parcelas_sem_juros"), extra.get("frete")))
            if dir_dados and "cor" in extra:
                lado = extra.get("lado", 400)
                nome = _desenhar(dir_dados / "imagens", imagem, extra["cor"], lado)
                c.execute("INSERT INTO imagem_baixada (url, situacao, arquivo, largura, altura)"
                          " VALUES (%s, 'ok', %s, %s, %s)", (imagem, nome, lado, lado))
        # Calculadora: sem a taxa do BCB a simulação responde 503.
        c.execute("INSERT INTO taxa_referencia (data, cdi_anual, selic_meta, selic_data) VALUES (%s, 13.65, 13.75, %s)",
                  (date.today(), date.today()))
    associar(url, [])
    return len(ANUNCIOS)


if __name__ == "__main__":
    url = recriar(sys.argv[1])
    dados = os.environ.get("SOSSEGO_DIR_DADOS")
    print(f"semeado: {semear(url, Path(dados) if dados else None)} anúncios em {url}")
