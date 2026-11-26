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
