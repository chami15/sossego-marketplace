"""Pausar (worker vivo, sem requisição) e desligar (worker nem sobe)."""

import random
from types import SimpleNamespace

import pytest

import coleta.vigiar as v
from coleta.admin import main as admin
from config import ConfigColeta


def _cliente(tmp_path, pausada):
    estado = SimpleNamespace(breaker=lambda loja: SimpleNamespace(desligada=False, pausada_ate=0, motivo=""))
    return SimpleNamespace(estado=estado, cfg=ConfigColeta(dir_dados=tmp_path), pausada=pausada)


def _tarefas(n=2):
    return [v.Tarefa("amazon", f"https://www.amazon.com.br/s?k={i}", "busca", str(i)) for i in range(n)]


@pytest.fixture
def feitas(monkeypatch):
    lista = []

    async def falsa(cliente, t, token_ml=None):
        lista.append(t.url)
        return "ok"

    monkeypatch.setattr(v, "executar_tarefa", falsa)
    monkeypatch.setattr(v, "ESPERA_PAUSA_S", 0.001)
    return lista


async def test_pausado_espera_sem_requisitar_e_segue_ao_retomar(tmp_path, feitas):
    checagens = iter([True, True, True])  # pausado nas 3 primeiras checagens

    def pausada():
        p = next(checagens, False)
        if p:
            assert feitas == []  # nada sai enquanto pausado
        return p

    await v.rodada_da_loja(_cliente(tmp_path, pausada), "amazon", _tarefas(), 0, random.Random(1))
    assert len(feitas) == 2


async def test_desligado_encerra_a_rodada_sem_requisitar(tmp_path, feitas):
    (tmp_path / "DESLIGADO").write_text("x", encoding="utf-8")
    with pytest.raises(v.WorkerDesligado):
        await v.rodada_da_loja(_cliente(tmp_path, lambda: False), "amazon", _tarefas(), 0, random.Random(1))
    assert feitas == []


def test_desligado_worker_sai_na_hora_sem_lock_nem_log(tmp_path, monkeypatch):
    def nunca(*a, **k):
        # Se a checagem regredir, isto falha em vez de subir um worker de verdade
        # (com lock e orçamento num tmp, longe dos reais). Aconteceu uma vez, 26/11.
        raise AssertionError("worker subiu com DESLIGADO")

    monkeypatch.setattr(v, "executar", nunca)
    monkeypatch.setenv("SOSSEGO_DIR_DADOS", str(tmp_path))
    (tmp_path / "DESLIGADO").write_text("x", encoding="utf-8")
    assert v.main(["--continuo"]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["DESLIGADO"]


def test_admin_pausar_desligar_ligar_nao_apagam_dados(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SOSSEGO_DIR_DADOS", str(tmp_path))
    (tmp_path / "bruto").mkdir()
    from coleta.estado import Estado

    Estado(tmp_path / "coleta.sqlite3")  # banco de estado real, para o status abrir
    admin(["pausar"])
    assert (tmp_path / "PARAR").exists()
    admin(["retomar"])
    assert not (tmp_path / "PARAR").exists()
    admin(["desligar"])
    assert (tmp_path / "DESLIGADO").exists()
    admin(["status"])
    assert "DESLIGADO" in capsys.readouterr().out
    admin(["ligar"])
    assert not (tmp_path / "DESLIGADO").exists()
    assert (tmp_path / "bruto").is_dir() and (tmp_path / "coleta.sqlite3").exists()
