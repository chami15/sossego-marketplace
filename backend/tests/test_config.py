"""O worker roda de um worktree fixo, mas .env e dados/ são um lugar só."""

from config import ConfigColeta, coleta_pausada


def test_raiz_principal_define_env_e_dados_compartilhados(tmp_path, monkeypatch):
    principal = tmp_path / "sossego-marketplace"
    principal.mkdir()
    (principal / ".env").write_text("SOSSEGO_COLETA_PAUSADA=true\n", encoding="utf-8")
    monkeypatch.delenv("SOSSEGO_COLETA_PAUSADA", raising=False)
    monkeypatch.delenv("SOSSEGO_DIR_DADOS", raising=False)
    monkeypatch.setenv("SOSSEGO_RAIZ_PRINCIPAL", str(principal))
    assert ConfigColeta.carregar().dir_dados == principal / "dados"
    assert coleta_pausada()  # kill switch do .env principal vale para o worker


def test_dir_dados_explicito_vence_raiz_principal(tmp_path, monkeypatch):
    monkeypatch.setenv("SOSSEGO_RAIZ_PRINCIPAL", str(tmp_path))
    monkeypatch.setenv("SOSSEGO_DIR_DADOS", str(tmp_path / "outro"))
    assert ConfigColeta.carregar().dir_dados == tmp_path / "outro"
