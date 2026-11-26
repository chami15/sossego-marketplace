# Rode UMA vez num PowerShell "Executar como administrador":
#   powershell -ExecutionPolicy Bypass -File scripts\registrar-worker-admin.ps1
# Registra o worker para subir na inicialização do Windows, mesmo sem login
# (ex.: reboot do Windows Update de madrugada). Sem admin, o Windows só
# permite o gatilho de logon.
$raiz = Split-Path $PSScriptRoot -Parent
$py = "$raiz\backend\.venv\Scripts\python.exe"
$usuario = "$env:USERDOMAIN\$env:USERNAME"
$acao = New-ScheduledTaskAction -Execute "cmd.exe" `
    -Argument "/c `"`"$py`" -m coleta.vigiar --continuo >> `"$raiz\dados\tarefa.out`" 2>> `"$raiz\dados\tarefa.err`"`"" `
    -WorkingDirectory "$raiz\backend"
$gatilhos = @(
    (New-ScheduledTaskTrigger -AtStartup),
    (New-ScheduledTaskTrigger -AtLogOn -User $usuario),
    # Rede de segurança: se morrer, sobe de novo em até 15 min (o lock impede duplicata).
    (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15))
)
$cfg = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable
# S4U: roda sem você estar logado e sem guardar sua senha.
$pr = New-ScheduledTaskPrincipal -UserId $usuario -LogonType S4U
Register-ScheduledTask -TaskName "Sossego Worker" -Action $acao -Trigger $gatilhos -Settings $cfg -Principal $pr -Force
