# No Windows sem make, use o equivalente: .\sossego.ps1 <alvo>
PY = cd backend && uv run python

.PHONY: test dry-run coletar worker orcamento parar retomar

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

parar:
	$(PY) -m coleta.admin parar

retomar:
	$(PY) -m coleta.admin retomar
