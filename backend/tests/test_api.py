from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg
import pytest
from fastapi.testclient import TestClient

from api.app import criar_app, menor_geral
from matching.associar import associar

AGORA = datetime.now(timezone.utc)


def anuncio(url, loja, id_externo, titulo, precos, pix=None, estoque=True, gtin=None):
    """precos: [(horas_atrás, preço)], do mais antigo para o mais novo."""
    with psycopg.connect(url, autocommit=True) as c:
        (loja_id,) = c.execute("SELECT id FROM loja WHERE slug = %s", (loja,)).fetchone()
        primeira, ultima = (AGORA - timedelta(hours=precos[0][0]), AGORA - timedelta(hours=precos[-1][0]))
        (aid,) = c.execute(
            "INSERT INTO anuncio (loja_id, id_externo, url, titulo_original, gtin, primeira_vez_em,"
            " ultima_coleta_em) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (loja_id, id_externo, f"https://{loja}/{id_externo}", titulo, gtin, primeira, ultima)).fetchone()
        for horas, preco in precos:
            c.execute("INSERT INTO preco_snapshot (anuncio_id, coletado_em, preco, preco_pix, em_estoque, origem)"
                      " VALUES (%s, %s, %s, %s, %s, 't')",
                      (aid, AGORA - timedelta(hours=horas), Decimal(preco), pix, estoque))
    return aid


def produto_de(url, id_externo):
    with psycopg.connect(url) as c:
        return c.execute("SELECT produto_id FROM anuncio WHERE id_externo = %s", (id_externo,)).fetchone()[0]


@pytest.fixture
def api(banco, tmp_path):
    with TestClient(criar_app(banco, tmp_path)) as cliente:
        yield cliente


@pytest.fixture
def catalogo(banco):
    anuncio(banco, "kabum", "k-mk8", "Jogo Mario Kart 8 Deluxe, Nintendo Switch - HBCPAABPA",
            [(80, "349.90"), (1, "299.90")], pix="284.90")
    anuncio(banco, "amazon", "a-mk8", "Mario Kart 8 Deluxe - Nintendo Switch", [(2, "319.00")])
    anuncio(banco, "kabum", "k-sf", "Jogo Star Fox para Nintendo Switch 2 - NSCA10000028FGR", [(1, "399.00")])
    anuncio(banco, "kabum", "k-ps5", "Console Sony PlayStation 5 Slim Digital 825GB", [(1, "3499.00")])
    anuncio(banco, "ludopedia", "606", "Dixit", [(1, "199.90")])
    anuncio(banco, "ludopedia", "odyssey", "Dixit: Odyssey", [(1, "229.90")])
    anuncio(banco, "ri-happy", "velho", "Dixit: Odyssey", [(100, "150.00")])          # sumiu há 4 dias
    anuncio(banco, "ri-happy", "sem-estoque", "Jogo Mario Kart 8 Deluxe Nintendo Switch, Físico Nacional",
            [(1, "199.00")], estoque=False)
    associar(banco, [])
    return banco


def perfil(api, **extra):
    corpo = {"faixa_etaria": "25-34", "categorias": ["jogos-tabuleiro"], "lojas": ["kabum"],
             "interesses": ["dixit"], **extra}
    r = api.post("/api/v1/perfis", json=corpo)
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------- catálogo e perfil ----------

def test_lojas_e_categorias(api):
    lojas = api.get("/api/v1/lojas").json()
    assert len(lojas) == 26 and all(lj["icone"] for lj in lojas)
    assert {"slug": "games", "nome": "Games", "icone": "controle"} in api.get("/api/v1/categorias").json()


def test_perfil_criado_lido_e_atualizado(api):
    pid = perfil(api, genero="prefiro-nao-dizer", categorias=["games", "Games", "informatica"])
    p = api.get(f"/api/v1/perfis/{pid}").json()
    assert p["categorias"] == ["games", "informatica"] and p["genero"] == "prefiro-nao-dizer"
    r = api.put(f"/api/v1/perfis/{pid}", json={"faixa_etaria": "60+", "lojas": []})
    assert r.status_code == 200
    assert r.json() == {"id": pid, "faixa_etaria": "60+", "genero": None, "categorias": [], "lojas": [],
                        "interesses": []}


@pytest.mark.parametrize("corpo,trecho", [
    ({"faixa_etaria": "25-34", "categorias": ["games", "casa", "livros", "esporte"]}, "3"),
    ({"faixa_etaria": "25-34", "lojas": ["amazon", "kabum", "magalu", "ludopedia"]}, "3"),
    ({"faixa_etaria": "25-34", "categorias": ["nao-existe"]}, "nao-existe"),
    ({"faixa_etaria": "30"}, "faixa_etaria"),
])
def test_perfil_invalido_e_422(api, corpo, trecho):
    r = api.post("/api/v1/perfis", json=corpo)
    assert r.status_code == 422 and trecho in r.text


def test_perfil_inexistente_e_404(api):
    assert api.get("/api/v1/perfis/00000000-0000-0000-0000-000000000000").status_code == 404
    assert api.put("/api/v1/perfis/00000000-0000-0000-0000-000000000000",
                   json={"faixa_etaria": "25-34"}).status_code == 404


# ---------- busca e card ----------

def test_busca_agrega_lojas_no_card_com_o_menor_preco(api, catalogo):
    r = api.get("/api/v1/busca", params={"q": "mario kart switch"}).json()
    assert r["total"] == 1 and r["fonte"] == "historico"
    c = r["resultados"][0]
    # Ri Happy sem estoque não vira o "menor preço"; a Kabum (299,90) vence a Amazon (319,00).
    assert (c["loja"], c["menor_preco"], c["menor_pix"]) == ("kabum", "299.90", "284.90")
    assert (c["outras_lojas"], c["outras_a_partir"]) == (1, "319.00")
    # Contra o NOSSO histórico: 349,90 há 80 h → 299,90 agora.
    assert c["variacao_pct"] == "-14.3"


def test_busca_entende_plataforma_e_nao_mistura_switch_com_switch_2(api, catalogo):
    titulos = [c["titulo"] for c in api.get("/api/v1/busca", params={"q": "switch 2"}).json()["resultados"]]
    assert titulos == ["Jogo Star Fox para Nintendo Switch 2 - NSCA10000028FGR"]
    assert api.get("/api/v1/busca", params={"q": "PlayStation 5"}).json()["total"] == 1


def test_busca_ignora_oferta_que_sumiu_ha_mais_de_48h(api, catalogo):
    c = api.get("/api/v1/busca", params={"q": "dixit odyssey"}).json()["resultados"][0]
    assert (c["loja"], c["menor_preco"], c["outras_lojas"]) == ("ludopedia", "229.90", 0)


def test_busca_ordena_filtra_e_registra(api, catalogo):
    pid = perfil(api)
    r = api.get("/api/v1/busca", params={"q": "dixit", "ordem": "preco", "perfil": pid}).json()
    assert [c["menor_preco"] for c in r["resultados"]] == ["199.90", "229.90"]
    r = api.get("/api/v1/busca", params={"q": "dixit", "preco_max": "200"}).json()
    assert r["total"] == 1
    assert api.get("/api/v1/busca", params={"q": "mario kart", "loja": "amazon"}).json()["resultados"][0][
        "menor_preco"] == "319.00"
    with psycopg.connect(catalogo) as c:
        assert c.execute("SELECT count(*) FROM busca_log WHERE perfil_id = %s", (pid,)).fetchone()[0] == 1
    assert api.get("/api/v1/busca", params={"q": "x"}).status_code == 422


# ---------- produto ----------

def test_produto_com_ofertas_ordenadas_e_desatualizada_marcada(api, catalogo):
    pid = produto_de(catalogo, "odyssey")
    p = api.get(f"/api/v1/produtos/{pid}").json()
    assert [(o["loja"], o["desatualizada"]) for o in p["ofertas"]] == [("ludopedia", False), ("ri-happy", True)]
    assert p["menor_visto"]["preco"] == "150.00" and p["menor_visto"]["loja"] == "ri-happy"
    assert api.get("/api/v1/produtos/999999").status_code == 404


def test_historico_em_degrau_com_menor_geral(api, catalogo):
    pid = produto_de(catalogo, "k-mk8")
    h = api.get(f"/api/v1/produtos/{pid}/historico", params={"periodo": "tudo"}).json()
    assert {s["loja"] for s in h["series"]} == {"kabum", "amazon", "ri-happy"}
    assert [p["preco"] for p in h["menor_geral"]] == ["349.90", "319.00", "199.00"]
    # 24 h: cada série começa no preço vigente no início da janela.
    h = api.get(f"/api/v1/produtos/{pid}/historico", params={"periodo": "24h"}).json()
    kabum = next(s for s in h["series"] if s["loja"] == "kabum")
    assert [p["preco"] for p in kabum["pontos"]] == ["349.90", "299.90"]


def test_menor_geral_so_emite_quando_o_minimo_muda():
    t = [AGORA + timedelta(hours=i) for i in range(4)]
    pontos = [{"anuncio_id": 1, "em": t[0], "preco": Decimal(10)}, {"anuncio_id": 2, "em": t[0], "preco": Decimal(12)},
              {"anuncio_id": 2, "em": t[1], "preco": Decimal(11)}, {"anuncio_id": 1, "em": t[2], "preco": Decimal(13)},
              {"anuncio_id": 2, "em": t[3], "preco": Decimal(11)}]
    assert [(p.em, p.preco) for p in menor_geral(pontos)] == [(t[0], 10), (t[2], 11)]


def test_parecidos_mesma_categoria_e_faixa_de_preco(api, catalogo):
    pid = produto_de(catalogo, "606")
    assert [c["titulo"] for c in api.get(f"/api/v1/produtos/{pid}/parecidos").json()] == ["Dixit: Odyssey"]
    ps5 = produto_de(catalogo, "k-ps5")
    assert api.get(f"/api/v1/produtos/{ps5}/parecidos").json() == []   # games, mas fora da faixa


# ---------- vigia, início, quedas ----------

def test_vigia_entra_e_sai_e_quedas_com_preco_alvo(api, catalogo):
    pid = perfil(api)
    mk8, sf = produto_de(catalogo, "k-mk8"), produto_de(catalogo, "k-sf")
    assert api.post(f"/api/v1/perfis/{pid}/vigias/{mk8}").status_code == 204
    assert api.post(f"/api/v1/perfis/{pid}/vigias/{sf}", json={"preco_alvo": "400.00"}).status_code == 204
    assert api.post(f"/api/v1/perfis/{pid}/vigias/999999").status_code == 404
    desde = (AGORA - timedelta(hours=48)).isoformat()
    q = {x["produto_id"]: x for x in api.get("/api/v1/vigias/quedas", params={"desde": desde}).json()}
    # Ri Happy a 199,00 está sem estoque: não conta como "caiu".
    assert (q[mk8]["preco_antes"], q[mk8]["preco_agora"]) == ("349.90", "299.90")
    assert q[mk8]["queda_pct"] == "-14.3" and not q[mk8]["alvo_atingido"]
    assert q[sf]["alvo_atingido"] and q[sf]["preco_antes"] is None and "preço-alvo" in q[sf]["motivo"]
    assert api.delete(f"/api/v1/perfis/{pid}/vigias/{sf}").status_code == 204
    assert sf not in {x["produto_id"] for x in api.get("/api/v1/vigias/quedas", params={"desde": desde}).json()}


def test_inicio_com_perfil(api, catalogo):
    pid = perfil(api)
    mk8 = produto_de(catalogo, "k-mk8")
    api.post(f"/api/v1/perfis/{pid}/vigias/{mk8}")
    i = api.get("/api/v1/inicio", params={"perfil": pid}).json()
    assert [c["id"] for c in i["de_olho"]] == [mk8]
    assert i["pra_voce"][0]["titulo"] == "Dixit" and i["pra_voce"][0]["porque"] == "porque você procurou dixit"
    assert i["categorias"][0]["slug"] == "jogos-tabuleiro"
    sem = api.get("/api/v1/inicio").json()
    assert [c["id"] for c in sem["caiu_de_preco"]] == [mk8] and sem["pra_voce"] == []


def test_saude_sem_estado_da_coleta_nao_cai(api):
    s = api.get("/api/v1/saude").json()
    assert s["banco"] == "ok" and not s["worker_vivo"]
    assert {lj["slug"] for lj in s["lojas"]} >= {"kabum", "ludopedia", "ri-happy"}
    assert all(lj["situacao"] == "sem_estado" for lj in s["lojas"])


def test_openapi_tem_as_rotas_do_contrato(api):
    rotas = set(api.get("/openapi.json").json()["paths"])
    assert rotas >= {
        "/api/v1/perfis", "/api/v1/perfis/{pid}", "/api/v1/lojas", "/api/v1/categorias", "/api/v1/busca",
        "/api/v1/produtos/{produto_id}", "/api/v1/produtos/{produto_id}/historico",
        "/api/v1/produtos/{produto_id}/parecidos", "/api/v1/inicio", "/api/v1/perfis/{pid}/vigias/{produto_id}",
        "/api/v1/vigias/quedas", "/api/v1/saude", "/api/v1/pagamento/simular"}


def test_regressao_busca_aproximada_ignorava_plataforma_e_modelo(api, banco):
    """27/11, dados reais: "controle ps5" trazia carregador de Switch 2 e
    "macbook air" trazia MacBook Pro, porque o fuzzy (word_similarity) aceitava
    só "controle"/"macbook". Aproximado só quando nada bate por inteiro, e a
    plataforma nunca é aproximada."""
    anuncio(banco, "kabum", "dock", "Carregador Para Controle Nintendo Switch 2 Charging Dock Gxt1256 Trust",
            [(1, "155.18")])
    anuncio(banco, "kabum", "ds", "Controle Sem Fio Sony DualSense, PlayStation 5, Bluetooth, Branco", [(1, "399.00")])
    anuncio(banco, "kabum", "air", "MacBook Air Apple 13\" Chip M5, 512GB, Estelar", [(1, "8999.00")])
    anuncio(banco, "kabum", "pro", "MacBook Pro Apple 14\" Chip M5 Pro, 24GB, SSD 1TB", [(1, "15999.00")])
    associar(banco, [])
    titulos = lambda q: [c["titulo"][:16] for c in api.get("/api/v1/busca", params={"q": q}).json()["resultados"]]
    assert titulos("controle ps5") == ["Controle Sem Fio"]
    assert titulos("macbook air") == ["MacBook Air Appl"]
    assert titulos("macbok air") == ["MacBook Air Appl"]       # erro de digitação ainda acha
    assert titulos("dualsense switch") == []                    # plataforma não se aproxima


def test_regressao_controle_ps5_trazia_console_e_nao_o_dualsense(api, banco):
    """27/11, dados reais: os termos do produto vinham só do 1º anúncio (Amazon,
    "PlayStation DualSense" sem o 5), e "+ 1 Controle" no título do console
    contava como controle. Termos = união dos anúncios; dualsense implica ps5;
    a busca que diz o tipo ("controle", "console") só traz esse tipo."""
    anuncio(banco, "amazon", "ds-a", "Controle sem fio PlayStation DualSense™ – Midnight Black", [(2, "379.05")])
    anuncio(banco, "kabum", "ds-k", "Controle Sem Fio Sony DualSense, PlayStation 5, Bluetooth, Midnight Black",
            [(1, "399.00")])
    anuncio(banco, "amazon", "ds-cor", "PlayStation DualSense Controle sem fio – Cosmic Red", [(1, "429.00")])
    anuncio(banco, "amazon", "ps5", "Sony PlayStation 5 Edição Digital 825GB 1 Controle", [(1, "4259.00")])
    anuncio(banco, "kabum", "ps5-k", "Console Sony PlayStation 5 Slim, SSD 1TB, Controle Sem Fio DualSense",
            [(1, "4999.00")])
    associar(banco, [])
    r = api.get("/api/v1/busca", params={"q": "controle ps5", "ordem": "preco"}).json()["resultados"]
    assert [(c["menor_preco"], c["outras_lojas"]) for c in r] == [("379.05", 1), ("429.00", 0)]
    # Limite conhecido (backlog): o console da Amazon não diz "console" no título e fica de fora.
    assert [c["menor_preco"] for c in api.get("/api/v1/busca", params={"q": "console ps5"}).json()["resultados"]] \
        == ["4999.00"]


def test_regressao_jogos_no_plural_casava_fone_para_jogos(api, banco):
    """27/11, dados reais: "jogos ps5" achava "Fone de ouvido para jogos ... PS5"
    pela palavra "jogos"; no singular ela já era vitrine."""
    anuncio(banco, "amazon", "fone", "JLab Nightfall Fone de ouvido para jogos com fio para PS5", [(1, "545.34")])
    anuncio(banco, "kabum", "gt7", "Jogo Gran Turismo 7, PS5", [(1, "199.00")])
    associar(banco, [])
    r = api.get("/api/v1/busca", params={"q": "jogos ps5"}).json()["resultados"]
    assert r[0]["titulo"] == "Jogo Gran Turismo 7, PS5"


# ---------- pagamento ----------

def test_simular_com_rendimento_informado(api):
    r = api.post("/api/v1/pagamento/simular", json={
        "preco_avista": "900", "preco_cartao": "1000", "parcelas": 10, "rendimento_mensal_pct": "1.07"})
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["melhor"]["tipo"] == "pix" and s["recomendacao"].startswith("Pague no Pix.")
    assert s["opcoes"][-1]["desconto_equilibrio_pct"] is not None and s["rendimento_fonte"] == "informado"
    assert s["desconto_pix_pct"] == "10.00" and s["economia"] == "44"


def test_simular_usa_o_ultimo_cdi_salvo_e_mostra_a_data(api, banco):
    with psycopg.connect(banco, autocommit=True) as c:
        c.execute("TRUNCATE taxa_referencia")
        assert api.post("/api/v1/pagamento/simular", json={
            "preco_avista": "1000", "preco_cartao": "1000", "parcelas": 3}).status_code == 503
        c.execute("INSERT INTO taxa_referencia (data, cdi_anual) VALUES ('2026-11-20', 13.0), ('2026-11-26', 13.65)")
    s = api.post("/api/v1/pagamento/simular", json={
        "preco_avista": "1000", "preco_cartao": "1000", "parcelas": 3, "pct_cdi": "100"}).json()
    assert (s["rendimento_fonte"], s["cdi_anual_pct"], s["cdi_data"]) == ("cdi_bcb", "13.6500", "2026-11-26")
    assert s["melhor"]["parcelas"] == 3 and s["melhor"]["ir_pct"] == "22.50"


def test_simular_valida_entrada(api):
    assert api.post("/api/v1/pagamento/simular", json={
        "preco_avista": "-1", "preco_cartao": "10", "parcelas": 1, "rendimento_mensal_pct": "1"}).status_code == 422
    assert api.post("/api/v1/pagamento/simular", json={
        "preco_avista": "10", "preco_cartao": "10", "parcelas": 40, "rendimento_mensal_pct": "1"}).status_code == 422
