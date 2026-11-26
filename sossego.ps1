# Equivalente ao Makefile para Windows sem make.
# Uso: .\sossego.ps1 test | dry-run | coletar | worker | status | orcamento | parar | retomar | religar <loja>
param([Parameter(Position = 0)][string]$alvo = "test", [Parameter(Position = 1)][string]$arg)

$backend = Join-Path $PSScriptRoot "backend"
$dados = Join-Path $PSScriptRoot "dados"
$python = Join-Path $backend ".venv\Scripts\python.exe"

Push-Location $backend
try {
    switch ($alvo) {
        "test"      { uv run pytest -q }
        "dry-run"   { uv run python -m coleta.vigiar --dry-run }
        "coletar"   { uv run python -m coleta.vigiar --uma-vez }
        "worker" {
            # Processo próprio, sem janela: sobrevive ao fechar o terminal e à
            # queda da sessão do Claude. Saída em dados\worker.out.
            New-Item -ItemType Directory -Force $dados | Out-Null
            $p = Start-Process -FilePath $python -ArgumentList "-m", "coleta.vigiar", "--continuo" `
                -WorkingDirectory $backend -WindowStyle Hidden -PassThru `
                -RedirectStandardOutput (Join-Path $dados "worker.out") `
                -RedirectStandardError (Join-Path $dados "worker.err")
            Write-Output "worker iniciado (pid $($p.Id)). Acompanhe: .\sossego.ps1 status"
        }
        "status"    { uv run python -m coleta.admin status }
        "migrar"    { uv run python -m db.migrar }
        "historico" { uv run python -m coleta.historico }
        "orcamento" { uv run python -m coleta.admin orcamento }
        "parar"     { uv run python -m coleta.admin parar }
        "retomar"   { uv run python -m coleta.admin retomar }
        "religar"   { uv run python -m coleta.admin religar $arg }
        default     { Write-Output "alvo desconhecido: $alvo" }
    }
} finally { Pop-Location }
