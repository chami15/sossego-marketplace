from datetime import datetime, timedelta, timezone

import psycopg

from matching.associar import associar

T0 = datetime(2026, 11, 27, 18, 0, tzinfo=timezone.utc)


def anuncio(url, loja, id_externo, titulo, gtin=None, minuto=0):
    t = T0 + timedelta(minutes=minuto)
    with psycopg.connect(url, autocommit=True) as c:
        (loja_id,) = c.execute("SELECT id FROM loja WHERE slug = %s", (loja,)).fetchone()
        c.execute("INSERT INTO anuncio (loja_id, id_externo, url, titulo_original, gtin, primeira_vez_em,"
                  " ultima_coleta_em) VALUES (%s, %s, 'u', %s, %s, %s, %s)",
                  (loja_id, id_externo, titulo, gtin, t, t))


def grupos(url):
    """{id_externo: id_externo do primeiro membro do produto} para comparar agrupamentos."""
    with psycopg.connect(url) as c:
        linhas = c.execute("SELECT id_externo, produto_id, match_metodo FROM anuncio ORDER BY id").fetchall()
    primeiro: dict[int, str] = {}
    return {i: primeiro.setdefault(p, i) for i, p, _ in linhas}, {i: m for i, _, m in linhas}


def test_agrupa_mesmo_jogo_entre_lojas_e_separa_plataforma(banco):
    anuncio(banco, "kabum", "483316", "Jogo Mario Kart 8 Deluxe, Nintendo Switch - HBCPAABPA", minuto=0)
    anuncio(banco, "amazon", "B0BK2RYTYH", "Mario Kart 8 Deluxe - Nintendo Switch", minuto=1)
    anuncio(banco, "amazon", "B0HGHY3BGT", "EA Sports FC 27 - Nintendo Switch", minuto=2)
    anuncio(banco, "amazon", "B0HGHHG3FL", "EA Sports FC 27 para Nintendo Switch 2", minuto=3)
    r = associar(banco, [])
    g, metodo = grupos(banco)
    assert g["B0BK2RYTYH"] == g["483316"] and metodo["B0BK2RYTYH"] == "titulo"
    assert g["B0HGHY3BGT"] != g["B0HGHHG3FL"]
    assert (r.agrupados, r.novos) == (1, 3)


def test_gtin_igual_agrupa_mesmo_com_titulo_bem_diferente(banco):
    anuncio(banco, "ri-happy", "1003176330", "Jogo De Mesa Jogo Do Transito Paki Toys - 1505", "7898676721311")
    anuncio(banco, "ri-happy", "1003037820", "Jogo do Trânsito de Lógica e Deslize p/ Crianças", "7898676721311", 1)
    associar(banco, [])
    g, metodo = grupos(banco)
    assert g["1003037820"] == g["1003176330"] and metodo["1003037820"] == "gtin"


def test_regressao_ean_repetido_juntava_kit_com_avulso_no_banco(banco):
    """27/11: a Ri Happy repete o EAN 3558387010695 no kit e no avulso. Ficam em
    produtos separados, e o GTIN (UNIQUE em produto) fica só com o primeiro."""
    anuncio(banco, "ri-happy", "1003208708", "Dixit Signature Aventura & Mistério Expansão Disney Pixar", "3558387010695")
    anuncio(banco, "ri-happy", "1003208717", "Kit Dixit Expansão Signature Disney Vilões + Aventura", "3558387010695", 1)
    associar(banco, [])
    g, _ = grupos(banco)
    assert g["1003208717"] != g["1003208708"]
    with psycopg.connect(banco) as c:
        assert c.execute("SELECT count(*) FROM produto WHERE gtin = '3558387010695'").fetchone()[0] == 1


def test_grupo_manual_vence_o_algoritmo_e_marca_a_confirmar(banco):
    anuncio(banco, "ludopedia", "606", "Dixit")
    anuncio(banco, "ri-happy", "1003181835", "Jogo De Tabuleiro - Dixit - Galápagos", "3558387010060", 1)
    anuncio(banco, "amazon", "B0FPGF9J2J", "PlayStation®5 Slim Digital 825GB – Pacote ASTRO BOT e Gran Turismo 7", minuto=2)
    anuncio(banco, "kabum", "989702", "Console Sony PlayStation 5, SSD 825GB, Controle Sem Fio DualSense + 2 Jogos "
            "Digitais, Edição Digital", minuto=3)
    manuais = [
        {"nome": "Dixit (base)", "edicao_a_confirmar": True,
         "anuncios": [{"loja": "ludopedia", "id": "606"}, {"loja": "ri-happy", "id": "1003181835"}]},
        {"nome": "PS5 Digital + Astro Bot e GT7",
         "anuncios": [{"loja": "amazon", "id": "B0FPGF9J2J"}, {"loja": "kabum", "id": "989702"}]},
    ]
    associar(banco, manuais)
    g, metodo = grupos(banco)
    assert g["989702"] == g["B0FPGF9J2J"] and metodo["989702"] == "manual"
    with psycopg.connect(banco) as c:
        assert c.execute("SELECT a_confirmar FROM produto WHERE grupo_manual = 'Dixit (base)'").fetchone() == (True,)


def test_associar_e_idempotente_e_refazer_nao_perde_grupo_manual(banco):
    anuncio(banco, "kabum", "483316", "Jogo Mario Kart 8 Deluxe, Nintendo Switch - HBCPAABPA")
    anuncio(banco, "amazon", "B0BK2RYTYH", "Mario Kart 8 Deluxe - Nintendo Switch", minuto=1)
    anuncio(banco, "ludopedia", "606", "Dixit", minuto=2)
    manuais = [{"nome": "Dixit (base)", "anuncios": [{"loja": "ludopedia", "id": "606"}]}]
    associar(banco, manuais)
    antes, _ = grupos(banco)
    segunda = associar(banco, manuais)
    assert (segunda.agrupados, segunda.novos) == (0, 0)
    associar(banco, manuais, refazer=True)
    depois, metodo = grupos(banco)
    assert depois == antes and metodo["606"] == "manual"
    with psycopg.connect(banco) as c:
        assert c.execute("SELECT count(*) FROM produto").fetchone()[0] == 2


def test_manual_tira_anuncio_de_produto_automatico_sem_deixar_produto_orfao(banco):
    anuncio(banco, "kabum", "483316", "Jogo Mario Kart 8 Deluxe, Nintendo Switch - HBCPAABPA")
    associar(banco, [])
    associar(banco, [{"nome": "MK8", "anuncios": [{"loja": "kabum", "id": "483316"}]}])
    with psycopg.connect(banco) as c:
        assert c.execute("SELECT count(*) FROM produto").fetchone()[0] == 1


def test_produto_novo_ganha_termos_de_busca_e_categoria(banco):
    anuncio(banco, "amazon", "B0X", "Star Fox – Nintendo Switch 2")
    anuncio(banco, "ludopedia", "606", "Dixit", minuto=1)
    associar(banco, [])
    with psycopg.connect(banco) as c:
        linhas = dict(c.execute("SELECT p.termos, c.slug FROM produto p LEFT JOIN categoria c ON c.id = p.categoria_id"))
    assert linhas == {"star fox ns2": "games", "dixit": "jogos-tabuleiro"}


def test_refazer_nao_quebra_nem_perde_produto_vigiado(banco):
    """Fase 4: vigia aponta para produto. O --refazer apagava todo produto
    automático e ia bater na FK (matching inteiro em rollback)."""
    import uuid

    anuncio(banco, "kabum", "483316", "Jogo Mario Kart 8 Deluxe, Nintendo Switch - HBCPAABPA")
    anuncio(banco, "amazon", "B0BK2RYTYH", "Mario Kart 8 Deluxe - Nintendo Switch", minuto=1)
    associar(banco, [])
    pid = uuid.uuid4()
    with psycopg.connect(banco, autocommit=True) as c:
        (produto,) = c.execute("SELECT produto_id FROM anuncio WHERE id_externo = '483316'").fetchone()
        c.execute("INSERT INTO perfil (id, faixa_etaria) VALUES (%s, '25-34')", (pid,))
        c.execute("INSERT INTO vigia (perfil_id, produto_id) VALUES (%s, %s)", (pid, produto))
    associar(banco, [], refazer=True)
    with psycopg.connect(banco) as c:
        ids = {i for (i,) in c.execute("SELECT produto_id FROM anuncio")}
    assert ids == {produto}
