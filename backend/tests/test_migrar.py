import shutil

from db.migrar import migrar


def test_migrations_aplicam_do_zero(banco_url):
    import psycopg

    with psycopg.connect(banco_url) as c:
        assert c.execute("SELECT count(*) FROM loja").fetchone()[0] >= 5
        assert c.execute("SELECT 1 FROM pg_extension WHERE extname='pg_trgm'").fetchone()


def test_migration_editada_depois_de_aplicada_e_recusada(banco_url, tmp_path, monkeypatch):
    import db.migrar as m

    pasta = tmp_path / "migrations"
    shutil.copytree(m.PASTA, pasta)
    monkeypatch.setattr(m, "PASTA", pasta)
    arq = next(pasta.glob("001_*.sql"))
    arq.write_text(arq.read_text(encoding="utf-8") + "\n-- editada\n", encoding="utf-8")
    try:
        migrar(banco_url, verbose=False)
    except RuntimeError as e:
        assert "editada" in str(e)
    else:
        raise AssertionError("aceitou migration editada")


def test_banco_recusa_quarta_categoria_e_quarta_loja_do_perfil(banco):
    import uuid

    import psycopg
    import pytest

    pid = uuid.uuid4()
    with psycopg.connect(banco, autocommit=True) as c:
        c.execute("INSERT INTO perfil (id, faixa_etaria) VALUES (%s, '25-34')", (pid,))
        for slug in ("games", "informatica", "jogos-tabuleiro"):
            c.execute("INSERT INTO perfil_categoria SELECT %s, id FROM categoria WHERE slug = %s", (pid, slug))
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("INSERT INTO perfil_categoria SELECT %s, id FROM categoria WHERE slug = 'casa'", (pid,))
        for slug in ("amazon", "kabum", "ludopedia"):
            c.execute("INSERT INTO perfil_loja SELECT %s, id FROM loja WHERE slug = %s", (pid, slug))
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("INSERT INTO perfil_loja SELECT %s, id FROM loja WHERE slug = 'magalu'", (pid,))


def test_seeds_trazem_as_26_lojas_do_onboarding_e_as_categorias(banco):
    import psycopg

    with psycopg.connect(banco) as c:
        assert c.execute("SELECT count(*) FROM loja").fetchone()[0] == 26
        assert c.execute("SELECT count(*) FROM loja WHERE icone IS NULL").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM categoria").fetchone()[0] >= 10
