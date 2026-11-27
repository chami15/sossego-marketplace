import time

from config import ConfigColeta
from coleta.admin import status
from coleta.estado import Estado


def test_regressao_status_dizia_ok_para_loja_inativa(tmp_path, capsys):
    """26/11: o ML tinha uma requisição antiga classificada como 'ok' e o
    status mostrava 'ok' para uma loja fora do worker."""
    cfg = ConfigColeta(dir_dados=tmp_path)
    e = Estado(tmp_path / "coleta.sqlite3")
    e.registrar(loja="mercado-livre", url="https://lista.mercadolivre.com.br/ps5", tipo="busca",
                inicio=time.time(), status=200, duracao_ms=1, bytes_=1, resultado="enviada", classe="ok")
    status(cfg)
    linha = next(l for l in capsys.readouterr().out.splitlines() if l.startswith("mercado-livre"))
    assert "INATIVA" in linha and not linha.rstrip().endswith("ok")


def test_regressao_status_dizia_ok_para_loja_so_sondada_fora_do_worker(tmp_path, capsys):
    """26/11: PBKids/Riachuelo (robots proibiu, nada coletado) apareciam como 'ok'."""
    cfg = ConfigColeta(dir_dados=tmp_path)
    e = Estado(tmp_path / "coleta.sqlite3")
    e.registrar(loja="pbkids.com.br", url="https://www.pbkids.com.br/robots.txt", tipo="robots",
                inicio=time.time(), status=200, duracao_ms=1, bytes_=1, resultado="enviada")
    status(cfg)
    linha = next(l for l in capsys.readouterr().out.splitlines() if l.startswith("pbkids"))
    assert "fora do worker" in linha and not linha.rstrip().endswith("ok")


def test_regressao_status_desligado_mandava_usar_worker_em_vez_de_ligar(tmp_path, capsys):
    """26/11: com dados/DESLIGADO, o status sugeria `.\\sossego.ps1 worker`, que não sobe nada."""
    cfg = ConfigColeta(dir_dados=tmp_path)
    Estado(tmp_path / "coleta.sqlite3")
    (tmp_path / "DESLIGADO").write_text("x", encoding="utf-8")
    status(cfg)
    saida = capsys.readouterr().out
    assert "sossego.ps1 ligar" in saida and "sossego.ps1 worker" not in saida


def test_regressao_status_dizia_ok_para_loja_sem_coleta_ha_horas(tmp_path, capsys):
    """27/11: a máquina ficou desligada das 20h às 15h e o status mostrava 'ok'
    para a Amazon com a última coleta de 19 h atrás (período: 120 min)."""
    cfg = ConfigColeta(dir_dados=tmp_path)
    e = Estado(tmp_path / "coleta.sqlite3")
    agora = time.time()
    for loja, idade_h in [("kabum", 19), ("ludopedia", 0.5)]:
        e.registrar(loja=loja, url="https://x/busca", tipo="busca", inicio=agora - idade_h * 3600,
                    status=200, duracao_ms=1, bytes_=1, resultado="enviada", classe="ok")
    status(cfg)
    linhas = {l.split()[0]: l for l in capsys.readouterr().out.splitlines() if l.split()}
    assert "ATRASADA" in linhas["kabum"]
    assert linhas["ludopedia"].rstrip().endswith("ok")


HORA = 3600.0
GRUPO = [{"nome": "Dixit (base)", "edicao_a_confirmar": True,
          "anuncios": [{"loja": "ludopedia", "id": "606"}, {"loja": "ri-happy", "id": "1003181835"}]}]


def test_grupo_destaca_anuncio_que_passou_de_2_rodadas_sem_aparecer():
    from coleta.admin import linhas_grupos
    agora = 100 * HORA
    # Ludopedia (60 min): visto há 30 min, presente. Ri Happy (60 min): a loja coletou
    # ok agora, mas o anúncio não aparece há 2h30 = mais de 2 rodadas.
    visto = {("ludopedia", "606"): agora - 0.5 * HORA, ("ri-happy", "1003181835"): agora - 2.5 * HORA}
    ok = {"ludopedia": agora, "ri-happy": agora}
    linhas, alertas = linhas_grupos(GRUPO, visto, ok, agora)
    texto = "\n".join(linhas)
    assert "Dixit (base)" in texto and "edição a confirmar" in texto
    lu = next(l for l in linhas if "ludopedia" in l)
    rh = next(l for l in linhas if "ri-happy" in l)
    assert "SUMIU" not in lu and "SUMIU" in rh and "2 rodadas" in rh
    assert len(alertas) == 1 and "ri-happy 1003181835" in alertas[0]


def test_grupo_nao_acusa_sumico_quando_a_loja_nao_coletou():
    """Worker parado ou loja inativa não é anúncio sumido: a busca nem rodou."""
    from coleta.admin import linhas_grupos
    agora = 100 * HORA
    grupo = [{"nome": "PS5", "anuncios": [{"loja": "amazon", "id": "B0FPGF9J2J"},
                                           {"loja": "kabum", "id": "989702"}]}]
    visto = {("amazon", "B0FPGF9J2J"): agora - 24 * HORA, ("kabum", "989702"): agora - 10 * HORA}
    ok = {"amazon": agora - 24 * HORA, "kabum": agora - 10 * HORA}
    linhas, alertas = linhas_grupos(grupo, visto, ok, agora)
    assert alertas == []
    assert "loja inativa" in next(l for l in linhas if "amazon" in l)
    assert "SUMIU" not in next(l for l in linhas if "kabum" in l)


def test_grupo_com_anuncio_nunca_visto_avisa():
    from coleta.admin import linhas_grupos
    agora = 100 * HORA
    linhas, alertas = linhas_grupos(GRUPO, {("ludopedia", "606"): agora}, {"ludopedia": agora, "ri-happy": agora}, agora)
    assert "nunca visto" in next(l for l in linhas if "ri-happy" in l)
    assert len(alertas) == 1


def test_ultima_vez_dos_anuncios_vem_do_banco(banco):
    from datetime import datetime, timezone

    import psycopg

    from coleta.admin import ultima_vez_anuncios
    t = datetime(2026, 11, 27, 18, 0, tzinfo=timezone.utc)
    with psycopg.connect(banco, autocommit=True) as c:
        (loja_id,) = c.execute("SELECT id FROM loja WHERE slug = 'ludopedia'").fetchone()
        c.execute("INSERT INTO anuncio (loja_id, id_externo, url, titulo_original, primeira_vez_em, ultima_coleta_em)"
                  " VALUES (%s, '606', 'u', 'Dixit', %s, %s)", (loja_id, t, t))
    visto = ultima_vez_anuncios(banco, GRUPO)
    assert visto == {("ludopedia", "606"): t.timestamp()}
