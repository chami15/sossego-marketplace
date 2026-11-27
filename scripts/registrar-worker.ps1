# Rode UMA vez num PowerShell "Executar como administrador":
#   powershell -ExecutionPolicy Bypass -File scripts\registrar-worker-admin.ps1
# Registra o worker para subir na inicialização do Windows, mesmo sem login
# (ex.: reboot do Windows Update de madrugada). Sem admin, o Windows só
# permite o gatilho de logon: use -SemAdmin (logon + rede de 15 min).
#
# O worker roda do worktree fixo ..\sossego-worker (criado e atualizado só por
# `.\sossego.ps1 atualizar-worker`), nunca da pasta onde se troca de branch.
# SOSSEGO_RAIZ_PRINCIPAL faz .env e dados\ continuarem vindo daqui.
param([switch]$SemAdmin)

$raiz = Split-Path $PSScriptRoot -Parent
$worktree = Join-Path (Split-Path $raiz -Parent) "sossego-worker"
$py = "$worktree\backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Worktree do worker não existe ($py). Rode antes: .\sossego.ps1 atualizar-worker" }
$usuario = (Get-CimInstance Win32_ComputerSystem).UserName
$acao = New-ScheduledTaskAction -Execute "cmd.exe" `
    -Argument "/c `"set `"SOSSEGO_RAIZ_PRINCIPAL=$raiz`"&& `"$py`" -m coleta.vigiar --continuo >> `"$raiz\dados\tarefa.out`" 2>> `"$raiz\dados\tarefa.err`"`"" `
    -WorkingDirectory "$worktree\backend"
# Sem -RepetitionDuration a repetição é indefinida (o XML da tarefa fica sem
# <Duration>, que no Agendador significa "para sempre"). Conferido no build 26200.
$rede = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15)
$cfg = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable
if ($SemAdmin) {
    $gatilhos = @((New-ScheduledTaskTrigger -AtLogOn -User $usuario), $rede)
    $pr = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive
} else {
    # Rede de segurança: se morrer, sobe de novo em até 15 min (o lock impede duplicata).
    $gatilhos = @((New-ScheduledTaskTrigger -AtStartup), (New-ScheduledTaskTrigger -AtLogOn -User $usuario), $rede)
    # S4U: roda sem você estar logado e sem guardar sua senha.
    $pr = New-ScheduledTaskPrincipal -UserId $usuario -LogonType S4U
}
Register-ScheduledTask -TaskName "Sossego Worker" -Action $acao -Trigger $gatilhos -Settings $cfg -Principal $pr -Force
