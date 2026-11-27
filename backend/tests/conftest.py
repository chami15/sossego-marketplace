import psycopg
import pytest

from config import database_url
from db.recriar import recriar


@pytest.fixture(scope="session")
def banco_url():
    """Banco sossego_test recriado do zero por sessão, com as migrations reais."""
    try:
        return recriar(database_url(teste=True))
    except psycopg.OperationalError as e:
        pytest.fail(f"Postgres de teste indisponível ({e}). Suba com: docker compose up -d db")


@pytest.fixture
def banco(banco_url):
    with psycopg.connect(banco_url, autocommit=True) as c:
        c.execute("TRUNCATE preco_snapshot, anuncio, produto, coleta_execucao, bruto_processado, perfil, busca_log"
                  " RESTART IDENTITY CASCADE")
    return banco_url
