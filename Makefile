# No Windows sem make, use o equivalente: .\sossego.ps1 <alvo>
PY = cd backend && uv run python

.PHONY: test dry-run coletar worker orcamento parar pausar retomar desligar ligar migrar historico matching api

test:
	cd backend && uv run pytest -q

dry-run:
	$(PY) -m coleta.vigiar --dry-run

coletar:
	$(PY) -m coleta.vigiar --uma-vez

worker:
	$(PY) -m coleta.vigiar --continuo

orcamento:
	$(PY) -m coleta.admin orcamento

parar pausar:
	$(PY) -m coleta.admin pausar

retomar:
	$(PY) -m coleta.admin retomar

# Só a flag; encerrar e subir o processo é no .\sossego.ps1 desligar / ligar.
desligar:
	$(PY) -m coleta.admin desligar

ligar:
	$(PY) -m coleta.admin ligar

migrar:
	$(PY) -m db.migrar

historico:
	$(PY) -m coleta.historico

matching:
	$(PY) -m matching.associar

# Só em 127.0.0.1: API de uso pessoal, sem autenticação.
api:
	cd backend && uv run uvicorn api.app:app --host 127.0.0.1 --port 8000
