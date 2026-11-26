# Equivalente ao Makefile para Windows sem make.
# Uso: .\sossego.ps1 test | dry-run | coletar | worker | orcamento | parar | retomar | religar <loja>
param([Parameter(Position = 0)][string]$alvo = "test", [Parameter(Position = 1)][string]$arg)

Push-Location (Join-Path $PSScriptRoot "backend")
try {
    switch ($alvo) {
        "test"      { uv run pytest -q }
        "dry-run"   { uv run python -m coleta.vigiar --dry-run }
        "coletar"   { uv run python -m coleta.vigiar --uma-vez }
        "worker"    { uv run python -m coleta.vigiar --continuo }
        "orcamento" { uv run python -m coleta.admin orcamento }
        "parar"     { uv run python -m coleta.admin parar }
        "retomar"   { uv run python -m coleta.admin retomar }
        "religar"   { uv run python -m coleta.admin religar $arg }
        default     { Write-Output "alvo desconhecido: $alvo" }
    }
} finally { Pop-Location }
