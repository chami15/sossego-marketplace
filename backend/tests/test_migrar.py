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
