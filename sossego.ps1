# Equivalente ao Makefile para Windows sem make.
# Uso: .\sossego.ps1 test | dry-run | coletar | worker | atualizar-worker [ref] | status | orcamento
#                    | parar | retomar | religar <loja> | migrar | historico
param([Parameter(Position = 0)][string]$alvo = "test", [Parameter(Position = 1)][string]$arg)

$backend = Join-Path $PSScriptRoot "backend"
$dados = Join-Path $PSScriptRoot "dados"

Push-Location $backend
try {
    switch ($alvo) {
        "test"      { uv run pytest -q }
        "dry-run"   { uv run python -m coleta.vigiar --dry-run }
        "coletar"   { uv run python -m coleta.vigiar --uma-vez }
        "worker" {
            # O worker roda do worktree fixo, via tarefa agendada: nunca do código
            # desta pasta (que muda a cada checkout). Saída em dados\tarefa.out.
            Start-ScheduledTask -TaskName "Sossego Worker"
            Write-Output "tarefa disparada (se já houver worker vivo, o lock faz a nova sair). Acompanhe: .\sossego.ps1 status"
        }
        "atualizar-worker" {
            # Único jeito de mudar o código do worker: marca uma tag no commit
            # escolhido, põe o worktree nela, roda os testes lá e reinicia.
            $ref = if ($arg) { $arg } else { "fase/02-coleta-e-historico" }
            $wt = Join-Path (Split-Path $PSScriptRoot -Parent) "sossego-worker"
            $commit = git rev-parse --verify "$ref^{commit}"
            if (-not $?) { throw "ref inexistente: $ref" }
            $tag = "worker-" + (Get-Date -Format "yyyyMMdd-HHmm")
            git tag -a $tag $commit -m "worker em produção desde $(Get-Date -Format 'dd/MM HH:mm')"
            $anterior = $null
            if (Test-Path $wt) {
                if (git -C $wt status --porcelain) { throw "worktree $wt tem mudanças locais; não mexo." }
                $anterior = git -C $wt rev-parse HEAD
                git -C $wt checkout -q --detach $tag
            } else {
                git worktree add -q --detach $wt $tag
            }
            Push-Location (Join-Path $wt "backend")
            try {
                uv sync --frozen -q
                uv run pytest -q
                $ok = $?
            } finally { Pop-Location }
            if (-not $ok) {
                if ($anterior) { git -C $wt checkout -q --detach $anterior }
                git tag -d $tag | Out-Null
                throw "testes falharam no worktree: worker continua no commit anterior ($anterior)."
            }
            # Reinicia: mata o worker atual (pid do batimento) e dispara a tarefa.
            $bat = Join-Path $dados "worker.json"
            if (Test-Path $bat) {
                $wpid = (Get-Content $bat -Raw | ConvertFrom-Json).pid
                Stop-Process -Id $wpid -Force -ErrorAction SilentlyContinue
            }
            for ($i = 0; $i -lt 20 -and (Get-ScheduledTask "Sossego Worker").State -eq "Running"; $i++) { Start-Sleep -Milliseconds 500 }
            Start-ScheduledTask -TaskName "Sossego Worker"
            Write-Output "worker agora em $tag ($($commit.Substring(0,7))). Confira: .\sossego.ps1 status"
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
