"""Snapshot com dedupe e reprocessamento idempotente, contra Postgres real."""

import gzip
import json
from decimal import Decimal
from pathlib import Path

import psycopg

from coleta.historico import reprocessar

T0 = 1_795_000_000  # 2026-11-19, só para carimbo


def produto_vtex(preco, pix=None, estoque=1, item="1"):
    parcelas = [{"PaymentSystemName": "Visa", "NumberOfInstallments": 5, "Value": round(preco / 5, 2), "InterestRate": 0}]
    if pix:
        parcelas.append({"PaymentSystemName": "Pix", "NumberOfInstallments": 1, "Value": pix, "InterestRate": 0})
    return {"productId": "p" + item, "productName": "Jogo Dixit", "brand": "Galápagos",
            "link": f"https://www.rihappy.com.br/dixit-{item}/p",
            "items": [{"itemId": item, "ean": "3558380073864", "images": [], "variations": [],
                       "sellers": [{"sellerDefault": True, "sellerName": "Ri Happy", "commertialOffer": {
                           "Price": preco, "ListPrice": 299.9, "AvailableQuantity": estoque,
                           "Installments": parcelas}}]}]}


def bruto(dir_, minuto, produtos, loja="ri-happy", corpo=None):
    t = T0 + minuto * 60
    pasta = dir_ / loja / "2026-11-26"
    pasta.mkdir(parents=True, exist_ok=True)
    nome = f"20261126T{minuto // 60:02d}{minuto % 60:02d}00Z_busca_{loja[:6]}.json.gz"
    with gzip.open(pasta / nome, "wt", encoding="utf-8") as f:
        json.dump({"loja": loja, "url": "u", "tipo": "busca", "status": 206, "coletado_em": t,
                   "cabecalhos": {}, "corpo": corpo if corpo is not None else json.dumps(produtos)}, f)


def snapshots(url):
    with psycopg.connect(url) as c:
        return c.execute("SELECT preco, preco_pix, em_estoque FROM preco_snapshot ORDER BY coletado_em").fetchall()


async def test_reprocesso_apos_rodada_grava_e_nunca_derruba_a_coleta(banco, tmp_path, caplog):
    from coleta.historico import ReprocessoAposRodada

    bruto(tmp_path, 0, [produto_vtex(249.99)])
    apos = ReprocessoAposRodada(banco, tmp_path)
    await apos("ri-happy")
    assert len(snapshots(banco)) == 1
    quebrado = ReprocessoAposRodada("postgresql://x:y@127.0.0.1:1/nada", tmp_path)
    await quebrado("ri-happy")  # banco fora do ar: loga e segue, não levanta
    assert any("reprocesso_falhou" in r.message for r in caplog.records)


def test_snapshot_so_quando_algo_muda(banco, tmp_path):
    bruto(tmp_path, 0, [produto_vtex(249.99)])
    bruto(tmp_path, 60, [produto_vtex(249.99)])          # igual: sem snapshot novo
    bruto(tmp_path, 120, [produto_vtex(199.99)])         # caiu
    bruto(tmp_path, 180, [produto_vtex(199.99, pix=189.99)])  # Pix apareceu
    bruto(tmp_path, 240, [produto_vtex(199.99, pix=189.99, estoque=0)])  # esgotou
    bruto(tmp_path, 300, [produto_vtex(249.99)])         # voltou ao original
    r = reprocessar(banco, tmp_path)
    assert r.snapshots == 5 and r.sem_mudanca == 1
    assert [s[0] for s in snapshots(banco)] == [Decimal("249.99"), Decimal("199.99"), Decimal("199.99"),
                                                  Decimal("199.99"), Decimal("249.99")]
    with psycopg.connect(banco) as c:
        (ultima,) = c.execute("SELECT extract(epoch FROM ultima_coleta_em)::bigint FROM anuncio").fetchone()
    assert ultima == T0 + 300 * 60


def test_reprocessar_duas_vezes_nao_duplica(banco, tmp_path):
    bruto(tmp_path, 0, [produto_vtex(249.99)])
    bruto(tmp_path, 60, [produto_vtex(199.99)])
    reprocessar(banco, tmp_path)
    r2 = reprocessar(banco, tmp_path)
    assert r2.pulados == 2 and r2.snapshots == 0
    r3 = reprocessar(banco, tmp_path, tudo=True)  # mesma versão de parser: ainda pula
    assert r3.snapshots == 0
    assert len(snapshots(banco)) == 2


def test_anuncio_unico_por_loja_e_id_externo(banco, tmp_path):
    bruto(tmp_path, 0, [produto_vtex(249.99), produto_vtex(249.99)])  # repetido na mesma página
    bruto(tmp_path, 60, [produto_vtex(249.99, item="2")])
    reprocessar(banco, tmp_path)
    with psycopg.connect(banco) as c:
        assert c.execute("SELECT count(*) FROM anuncio").fetchone()[0] == 2


def test_pix_maior_que_preco_vira_alerta_nao_snapshot(banco, tmp_path):
    bruto(tmp_path, 0, [produto_vtex(100.00, pix=150.00)])
    r = reprocessar(banco, tmp_path)
    assert r.alertas == 1 and snapshots(banco) == []


def test_pagina_sem_estrutura_registra_erro_e_nao_marca_processado(banco, tmp_path):
    bruto(tmp_path, 0, None, corpo='{"nao": "lista"}')
    r = reprocessar(banco, tmp_path)
    assert len(r.erros) == 1
    with psycopg.connect(banco) as c:
        assert c.execute("SELECT status FROM coleta_execucao").fetchone()[0] == "erro"
        assert c.execute("SELECT count(*) FROM bruto_processado").fetchone()[0] == 0


def test_robots_e_token_no_bruto_sao_ignorados(banco, tmp_path):
    pasta = tmp_path / "amazon" / "2026-11-26"
    pasta.mkdir(parents=True)
    with gzip.open(pasta / "20261126T000000Z_robots_x.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"loja": "amazon", "tipo": "robots", "coletado_em": T0, "corpo": "User-agent: *"}, f)
    assert reprocessar(banco, tmp_path).arquivos == 0


def test_fixtures_reais_viram_snapshots(banco, tmp_path):
    fix = Path(__file__).parent / "fixtures"
    for loja, nome in [("amazon", "busca_ps5.html"), ("ludopedia", "busca_dixit.html"), ("ri-happy", "busca_dixit.json")]:
        bruto(tmp_path, 0, None, loja=loja, corpo=gzip.open(fix / loja / f"{nome}.gz", "rt", encoding="utf-8").read())
    r = reprocessar(banco, tmp_path)
    assert r.erros == [] and r.snapshots > 60
