# Registra a tarefa "Sossego Worker" (sem admin; rode num PowerShell normal):
#   powershell -ExecutionPolicy Bypass -File scripts\registrar-worker.ps1
# Gatilhos: no seu logon e, como rede de segurança, a cada 15 min (o lock em
# dados\coleta.lock faz a instância extra sair na hora). A versão "no boot sem
# login" (S4U) exige admin e deu "Acesso negado" em 27/11; ficou de fora.
#
# O worker roda do worktree fixo ..\sossego-worker (criado e atualizado só por
# `.\sossego.ps1 atualizar-worker`), nunca da pasta onde se troca de branch.
# --raiz-principal faz .env e dados\ continuarem vindo daqui.
#
# pythonw.exe, sem cmd: nenhuma janela aparece no logon, e fechar terminal não
# mata o worker. A saída vai para dados\tarefa.out (--saida).

$raiz = Split-Path $PSScriptRoot -Parent
$worktree = Join-Path (Split-Path $raiz -Parent) "sossego-worker"
$pyw = "$worktree\backend\.venv\Scripts\pythonw.exe"
if (-not (Test-Path $pyw)) { throw "Worktree do worker não existe ($pyw). Rode antes: .\sossego.ps1 atualizar-worker" }
$usuario = (Get-CimInstance Win32_ComputerSystem).UserName
$acao = New-ScheduledTaskAction -Execute $pyw `
    -Argument "-m coleta.vigiar --continuo --raiz-principal `"$raiz`" --saida `"$raiz\dados\tarefa.out`"" `
    -WorkingDirectory "$worktree\backend"
# Sem -RepetitionDuration a repetição é indefinida (o XML da tarefa fica sem
# <Duration>, que no Agendador significa "para sempre"). Conferido no build 26200.
$gatilhos = @(
    (New-ScheduledTaskTrigger -AtLogOn -User $usuario),
    (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15))
)
$cfg = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable
$pr = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive
Register-ScheduledTask -TaskName "Sossego Worker" -Action $acao -Trigger $gatilhos -Settings $cfg -Principal $pr -Force
