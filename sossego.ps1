# Equivalente ao Makefile para Windows sem make.
# Uso: .\sossego.ps1 test | dry-run | coletar | worker | atualizar-worker [ref] | status | orcamento
#                    | pausar | retomar | desligar | ligar | religar <loja> | migrar | historico
param([Parameter(Position = 0)][string]$alvo = "test", [Parameter(Position = 1)][string]$arg)

$backend = Join-Path $PSScriptRoot "backend"
$dados = Join-Path $PSScriptRoot "dados"

function Parar-ProcessosWorker {
    # Só o worker, pela linha de comando: nunca por PID solto (pode ter sido
    # reaproveitado). python.exe (cmd/terminal) ou pythonw.exe (tarefa, sem janela);
    # o launcher do venv e o filho têm a mesma linha, os dois saem.
    $procs = @(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
        Where-Object { $_.CommandLine -match 'coleta\.vigiar' -and $_.CommandLine -match '--continuo' })
    foreach ($p in $procs) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "worker encerrado (pid $($p.ProcessId))"
    }
    Remove-Item (Join-Path $dados "worker.json") -ErrorAction SilentlyContinue
    return $procs.Count
}

Push-Location $backend
try {
    switch ($alvo) {
        "test"      { uv run pytest -q }
        "dry-run"   { uv run python -m coleta.vigiar --dry-run }
        "coletar"   { uv run python -m coleta.vigiar --uma-vez }
        "worker" {
            # O worker roda do worktree fixo, via tarefa agendada: nunca do código
            # desta pasta (que muda a cada checkout). Saída em dados\tarefa.out.
            if (Test-Path (Join-Path $dados "DESLIGADO")) { Write-Output "worker DESLIGADO: use .\sossego.ps1 ligar"; return }
            Start-ScheduledTask -TaskName "Sossego Worker"
            Write-Output "tarefa disparada (se já houver worker vivo, o lock faz a nova sair). Acompanhe: .\sossego.ps1 status"
        }
        "atualizar-worker" {
            # Único jeito de mudar o código do worker: marca uma tag no commit
            # escolhido, põe o worktree nela, roda os testes lá e reinicia.
            $ref = if ($arg) { $arg } else { "fase/02-coleta-e-historico" }
            $wt = Join-Path (Split-Path $PSScriptRoot -Parent) "sossego-worker"
            $commit = git rev-parse --verify "$ref^{commit}"
            if ($LASTEXITCODE -ne 0) { throw "ref inexistente: $ref" }
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
            # Não herdar o venv desta pasta; e exit code, não $? (no PS 5.1 um
            # aviso no stderr do uv deixa $? falso mesmo com sucesso).
            $venvAntes = $env:VIRTUAL_ENV; $env:VIRTUAL_ENV = $null
            try {
                uv sync --frozen -q
                $ok = $LASTEXITCODE -eq 0
                if ($ok) { uv run pytest -q; $ok = $LASTEXITCODE -eq 0 }
            } finally { Pop-Location; $env:VIRTUAL_ENV = $venvAntes }
            if (-not $ok) {
                if ($anterior) { git -C $wt checkout -q --detach $anterior }
                git tag -d $tag | Out-Null
                throw "testes falharam no worktree: worker continua no commit anterior ($anterior)."
            }
            if (Test-Path (Join-Path $dados "DESLIGADO")) {
                Write-Output "worktree em $tag ($($commit.Substring(0,7))). Worker DESLIGADO: não reiniciei. Suba com .\sossego.ps1 ligar"
                return
            }
            # Confere a tarefa ANTES de encerrar: sem ela, o worker morreria e não voltaria.
            if (-not (Get-ScheduledTask -TaskName "Sossego Worker" -ErrorAction SilentlyContinue)) {
                throw "worktree em $tag, mas a tarefa 'Sossego Worker' não existe; worker atual NÃO foi tocado. Rode scripts\registrar-worker.ps1 (sem admin)."
            }
            Parar-ProcessosWorker | Out-Null
            for ($i = 0; $i -lt 20 -and (Get-ScheduledTask "Sossego Worker").State -eq "Running"; $i++) { Start-Sleep -Milliseconds 500 }
            Start-ScheduledTask -TaskName "Sossego Worker"
            Write-Output "worker agora em $tag ($($commit.Substring(0,7))). Confira: .\sossego.ps1 status"
        }
        "status"    { uv run python -m coleta.admin status }
        "migrar"    { uv run python -m db.migrar }
        "historico" { uv run python -m coleta.historico }
        "orcamento" { uv run python -m coleta.admin orcamento }
        # pausar/retomar: worker vivo, nenhuma requisição (dados\PARAR).
        { $_ -in "pausar", "parar" } { uv run python -m coleta.admin pausar }
        "retomar"   { uv run python -m coleta.admin retomar }
        # desligar/ligar: flag dados\DESLIGADO + processo encerrado. Com a flag, a
        # tarefa agendada (15 min, boot, logon) sobe e sai na hora. Nada é apagado.
        "desligar" {
            uv run python -m coleta.admin desligar
            $n = Parar-ProcessosWorker
            if ($n -eq 0) { Write-Output "nenhum worker rodando" }
        }
        "ligar" {
            uv run python -m coleta.admin ligar
            try {
                Start-ScheduledTask -TaskName "Sossego Worker" -ErrorAction Stop
                Write-Output "tarefa disparada. Acompanhe: .\sossego.ps1 status"
            } catch {
                Write-Output "não consegui disparar a tarefa ($($_.Exception.Message)); ela sobe sozinha em até 15 min."
            }
        }
        "religar"   { uv run python -m coleta.admin religar $arg }
        default     { Write-Output "alvo desconhecido: $alvo" }
    }
} finally { Pop-Location }
