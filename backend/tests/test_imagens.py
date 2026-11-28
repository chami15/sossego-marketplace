"""Imagens de produto: candidatas, URL do CDN, download educado e WebP local."""

from __future__ import annotations

import io
import random
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from PIL import Image

from coleta import imagens
from coleta.estado import Estado
from coleta.http import ClienteEducado, Resposta
from config import ConfigColeta
from matching.associar import associar
from tests.test_http import RelogioFalso, TransporteFalso

AGORA = datetime.now(timezone.utc)
KABUM = "https://images.kabum.com.br/produtos/fotos/1/ps5_1782848212_original.jpg"
KABUM_G = "https://images.kabum.com.br/produtos/fotos/1/ps5_1782848212_g.jpg"


def jpeg(lado=(800, 600)) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", lado, (200, 30, 30)).save(b, "JPEG")
    return b.getvalue()


def anuncio(url, loja, ide, titulo, imagem, horas=1, estoque=True, preco="100.00"):
    with psycopg.connect(url, autocommit=True) as c:
        (lid,) = c.execute("SELECT id FROM loja WHERE slug = %s", (loja,)).fetchone()
        quando = AGORA - timedelta(hours=horas)
        (aid,) = c.execute(
            "INSERT INTO anuncio (loja_id, id_externo, url, titulo_original, imagem, primeira_vez_em,"
            " ultima_coleta_em) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (lid, ide, f"https://{loja}/{ide}", titulo, imagem, quando, quando)).fetchone()
        c.execute("INSERT INTO preco_snapshot (anuncio_id, coletado_em, preco, em_estoque, origem)"
                  " VALUES (%s,%s,%s,%s,'t')", (aid, quando, preco, estoque))


# ---------- URL no CDN: tamanho médio ----------

@pytest.mark.parametrize("original,esperada", [
    (KABUM, KABUM_G),
    (KABUM.replace("_original", "_gg"), KABUM_G),
    ("https://rihappy.vteximg.com.br/arquivos/ids/10019134/17810920431690.jpg?v=639",
     "https://rihappy.vteximg.com.br/arquivos/ids/10019134-400-400/17810920431690.jpg?v=639"),
    ("https://storage.googleapis.com/ludopedia-capas/606_s.jpg",
     "https://storage.googleapis.com/ludopedia-capas/606_s.jpg"),
    ("https://cdn.desconhecido.com/x.jpg", None),  # CDN que não conhecemos: não baixa
])
def test_url_no_cdn_em_tamanho_medio(original, esperada):
    assert imagens.url_no_cdn(original) == esperada


# ---------- candidatas ----------

def test_candidatas_sao_so_as_de_card_e_de_loja_ativa(banco):
    anuncio(banco, "kabum", "k1", "Console PS5 Slim Digital", KABUM, preco="4000.00")
    anuncio(banco, "kabum", "k2", "Console PS5 Slim Digital edição", KABUM.replace("ps5", "ps5b"),
            preco="4100.00")  # mesmo produto, mais caro: não é a imagem do card
    anuncio(banco, "kabum", "k3", "Jogo Dixit", KABUM.replace("ps5", "dixit"), horas=100)  # sumiu
    anuncio(banco, "amazon", "a1", "Kindle 16GB", "https://m.media-amazon.com/images/I/x._AC_UL320_.jpg")
    associar(banco, [])
    assert [c.url for c in imagens.candidatas(banco)] == [KABUM]


def test_candidatas_pulam_url_ja_baixada_e_voltam_se_a_url_mudar(banco):
    anuncio(banco, "kabum", "k1", "Console PS5 Slim Digital", KABUM)
    associar(banco, [])
    with psycopg.connect(banco, autocommit=True) as c:
        c.execute("INSERT INTO imagem_baixada (url, situacao, arquivo) VALUES (%s, 'ok', 'a.webp')", (KABUM,))
    assert imagens.candidatas(banco) == []
    nova = KABUM.replace("1782848212", "1799999999")
    with psycopg.connect(banco, autocommit=True) as c:
        c.execute("UPDATE anuncio SET imagem = %s", (nova,))
    assert [c.url for c in imagens.candidatas(banco)] == [nova]


def test_falha_recente_nao_e_tentada_de_novo(banco):
    anuncio(banco, "kabum", "k1", "Console PS5 Slim Digital", KABUM)
    associar(banco, [])
    with psycopg.connect(banco, autocommit=True) as c:
        c.execute("INSERT INTO imagem_baixada (url, situacao, motivo) VALUES (%s, 'falhou', 'HTTP 404')", (KABUM,))
    assert imagens.candidatas(banco) == []


# ---------- download ----------

def cliente_cdn(transporte, relogio):
    return imagens.cliente_de_imagens(Estado(":memory:"), transporte, ConfigColeta(),
                                      relogio=relogio, rng=random.Random(1), pausada=lambda: False)


async def test_baixa_converte_para_webp_de_ate_400_e_registra(banco, tmp_path):
    anuncio(banco, "kabum", "k1", "Console PS5 Slim Digital", KABUM)
    associar(banco, [])
    relogio = RelogioFalso()
    t = TransporteFalso(relogio).em(KABUM_G, Resposta(200, {"content-type": "image/jpeg"}, jpeg(), KABUM_G))
    feitos = await imagens.baixar(cliente_cdn(t, relogio), banco, tmp_path)
    assert feitos == {"ok": 1, "falhou": 0, "parou": []}
    assert t.urls() == ["https://images.kabum.com.br/robots.txt", KABUM_G]  # nunca a página da loja
    with psycopg.connect(banco) as c:
        arquivo, larg, alt = c.execute("SELECT arquivo, largura, altura FROM imagem_baixada").fetchone()
    with Image.open(tmp_path / arquivo) as img:
        assert img.format == "WEBP" and (img.width, img.height) == (larg, alt) == (400, 300)


async def test_404_vira_placeholder_e_html_para_o_cdn(banco, tmp_path):
    for i in range(3):
        anuncio(banco, "kabum", f"k{i}", f"Produto distinto numero {i} modelo x{i}",
                KABUM.replace("ps5", f"p{i}"), preco=f"{100 + i}.00")
    associar(banco, [])
    relogio = RelogioFalso()
    t = TransporteFalso(relogio)
    urls = [imagens.url_no_cdn(c.url) for c in imagens.candidatas(banco)]
    t.em(urls[0], Resposta(404, {}, b"", urls[0]))
    t.em(urls[1], Resposta(200, {"content-type": "text/html"}, b"<html>desafio</html>", urls[1]))
    feitos = await imagens.baixar(cliente_cdn(t, relogio), banco, tmp_path)
    assert feitos["falhou"] == 1 and feitos["parou"] == ["images.kabum.com.br"]
    assert urls[2] not in t.urls()  # depois do conteúdo inesperado, nada mais daquele CDN


def test_cliente_de_imagens_usa_orcamento_proprio_por_cdn():
    c = imagens.cliente_de_imagens(Estado(":memory:"), None, ConfigColeta())
    assert c.loja_de("images.kabum.com.br") == "cdn:images.kabum.com.br"
    assert c.orcamento_de("cdn:images.kabum.com.br") == (imagens.POR_HORA, imagens.POR_DIA) == (30, 150)


async def test_worker_pausado_nao_baixa_imagem(banco, tmp_path):
    import asyncio

    from coleta.vigiar import imagens_periodicas

    anuncio(banco, "kabum", "k1", "Console PS5 Slim Digital", KABUM)
    associar(banco, [])
    relogio = RelogioFalso()
    t = TransporteFalso(relogio)
    c = imagens.cliente_de_imagens(Estado(":memory:"), t, ConfigColeta(dir_dados=tmp_path), relogio=relogio,
                                   pausada=lambda: True)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(imagens_periodicas(c, banco, checar_s=0.01), timeout=0.05)
    assert t.urls() == []


def test_regressao_dry_run_listava_cdn_desligado_como_se_fosse_baixar():
    # 27/11: o CDN da Kabum foi desligado na mão (robots.txt 403) e o dry-run
    # ainda mostrava "298 imagens, ~2 dias", como se fosse baixar.
    estado = Estado()
    b = estado.breaker("cdn:images.kabum.com.br")
    b.desligada, b.motivo = True, "robots.txt respondeu 403"
    estado.salvar_breaker(b)
    itens = [imagens.Candidata(url="https://images.kabum.com.br/produtos/fotos/1/1_g.jpg", loja="kabum"),
             imagens.Candidata(url="https://rihappy.vteximg.com.br/arquivos/ids/9/x.jpg", loja="ri-happy")]
    linhas = imagens.plano(itens, estado, agora=0.0)
    kabum = next(l for l in linhas if l.startswith("images.kabum.com.br"))
    assert "DESLIGADO" in kabum and "robots.txt respondeu 403" in kabum and "dia(s)" not in kabum
    assert not any("images.kabum.com.br" in l for l in linhas if l.startswith("exemplo"))
    assert any("dia(s)" in l for l in linhas if l.startswith("rihappy.vteximg.com.br"))

# ---------- tentativa manual (Kabum, autorizada pelo dono em 27/11) ----------

def cliente_manual(estado, transporte, relogio, host):
    return imagens.cliente_de_imagens(estado, transporte, imagens.cfg_manual(ConfigColeta()), prefixo="manual",
                                      relogio=relogio,
                                      rng=random.Random(1), pausada=lambda: False,
                                      robots_indisponivel=frozenset({host}))


def desligar_cdn(estado, host):
    b = estado.breaker(f"cdn:{host}")
    b.desligada, b.motivo = True, "robots.txt respondeu 403"
    estado.salvar_breaker(b)


async def test_tentativa_manual_robots_403_e_imagem_403_volta_desligado_com_2_requisicoes(banco, tmp_path):
    anuncio(banco, "kabum", "k1", "Console PS5 Slim Digital", KABUM)
    associar(banco, [])
    relogio, estado = RelogioFalso(), Estado(":memory:")
    desligar_cdn(estado, "images.kabum.com.br")
    t = TransporteFalso(relogio)
    t.em("https://images.kabum.com.br/robots.txt", Resposta(403, {}, b"", "x"))
    t.em(KABUM_G, Resposta(403, {}, b"", KABUM_G))
    texto = await imagens.tentativa_manual(cliente_manual(estado, t, relogio, "images.kabum.com.br"),
                                           estado, banco, tmp_path, "images.kabum.com.br")
    assert t.urls() == ["https://images.kabum.com.br/robots.txt", KABUM_G]  # 1 + 1, sem retry
    b = estado.breaker("cdn:images.kabum.com.br")
    assert b.desligada and "tentativa manual" in b.motivo and "403" in texto
    assert list(tmp_path.iterdir()) == []


async def test_tentativa_manual_robots_403_e_imagem_ok_guarda_a_imagem_e_segue_desligado(banco, tmp_path):
    anuncio(banco, "kabum", "k1", "Console PS5 Slim Digital", KABUM)
    associar(banco, [])
    relogio, estado = RelogioFalso(), Estado(":memory:")
    desligar_cdn(estado, "images.kabum.com.br")
    t = TransporteFalso(relogio)
    t.em("https://images.kabum.com.br/robots.txt", Resposta(403, {}, b"", "x"))
    t.em(KABUM_G, Resposta(200, {"content-type": "image/jpeg"}, jpeg(), KABUM_G))
    texto = await imagens.tentativa_manual(cliente_manual(estado, t, relogio, "images.kabum.com.br"),
                                           estado, banco, tmp_path, "images.kabum.com.br")
    assert len(t.urls()) == 2 and len(list(tmp_path.iterdir())) == 1
    # O worker trataria o robots 403 como bloqueio: segue desligado até o dono decidir.
    b = estado.breaker("cdn:images.kabum.com.br")
    assert b.desligada and "decisão do dono" in b.motivo and "decisão do dono" in texto


async def test_tentativa_manual_com_5xx_nao_repete(banco, tmp_path):
    anuncio(banco, "kabum", "k1", "Console PS5 Slim Digital", KABUM)
    associar(banco, [])
    relogio, estado = RelogioFalso(), Estado(":memory:")
    t = TransporteFalso(relogio)
    t.em("https://images.kabum.com.br/robots.txt", Resposta(503, {}, b"", "x"))
    await imagens.tentativa_manual(cliente_manual(estado, t, relogio, "images.kabum.com.br"),
                                   estado, banco, tmp_path, "images.kabum.com.br")
    assert t.urls() == ["https://images.kabum.com.br/robots.txt"]
    assert estado.breaker("cdn:images.kabum.com.br").desligada

async def test_tentativa_manual_nao_religa_a_chave_do_worker_durante_a_tentativa(banco, tmp_path):
    anuncio(banco, "kabum", "k1", "Console PS5 Slim Digital", KABUM)
    associar(banco, [])
    relogio, estado = RelogioFalso(), Estado(":memory:")
    desligar_cdn(estado, "images.kabum.com.br")
    vistos = []

    class Espiao(TransporteFalso):
        async def get(self, *a, **k):
            vistos.append(estado.breaker("cdn:images.kabum.com.br").desligada)
            return await super().get(*a, **k)

    t = Espiao(relogio)
    t.em("https://images.kabum.com.br/robots.txt", Resposta(403, {}, b"", "x"))
    t.em(KABUM_G, Resposta(403, {}, b"", KABUM_G))
    await imagens.tentativa_manual(cliente_manual(estado, t, relogio, "images.kabum.com.br"),
                                   estado, banco, tmp_path, "images.kabum.com.br")
    assert vistos == [True, True]  # o worker nunca viu a chave dele ligada