import psycopg
import pytest
from psycopg import sql

from config import database_url
from db.migrar import migrar


@pytest.fixture(scope="session")
def banco_url():
    """Banco sossego_test recriado do zero por sessão, com as migrations reais."""
    url = database_url(teste=True)
    nome = psycopg.conninfo.conninfo_to_dict(url)["dbname"]
    admin = psycopg.conninfo.make_conninfo(url, dbname="postgres")
    try:
        with psycopg.connect(admin, autocommit=True, connect_timeout=3) as c:
            c.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(nome)))
            c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(nome)))
    except psycopg.OperationalError as e:
        pytest.fail(f"Postgres de teste indisponível ({e}). Suba com: docker compose up -d db")
    migrar(url, verbose=False)
    return url


@pytest.fixture
def banco(banco_url):
    with psycopg.connect(banco_url, autocommit=True) as c:
        c.execute("TRUNCATE preco_snapshot, anuncio, produto, coleta_execucao, bruto_processado, perfil, busca_log"
                  " RESTART IDENTITY CASCADE")
    return banco_url
