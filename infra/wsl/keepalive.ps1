# Keep the WSL distro alive and the Nizam stack running.
#
# WSL terminates a distribution once its last attached session exits -- and it
# does not count background containers as a reason to stay up. Without something
# holding a session open, Postgres, pgAdmin and MinIO are torn down the moment
# you close your terminal and restarted on your next command, which also means
# the snapshot timer never fires and pgAdmin is unreachable from the browser.
#
# This script holds one long-lived session open and starts the stack. Register it
# to run at logon with:
#     powershell -ExecutionPolicy Bypass -File infra\wsl\keepalive.ps1 -Install
# Remove it with -Uninstall. Run it with no arguments to hold the session in the
# current window.

param(
    [switch]$Install,
    [switch]$Uninstall,
    [string]$Distro   = 'Ubuntu',
    [string]$RepoPath = '/mnt/e/Nizam_e_Qanoon'
)

$TaskName = 'Nizam-WSL-Keepalive'
$Self     = $MyInvocation.MyCommand.Path

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task '$TaskName'. The stack will stop when WSL next idles out."
    return
}

if ($Install) {
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' `
        -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Self`" -Distro $Distro -RepoPath $RepoPath"
    $trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Description 'Holds a WSL session open so the Nizam-e-Qanoon database stack keeps running.' `
        -Force | Out-Null
    Write-Host "Registered '$TaskName' to run at logon."
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Started it now."
    return
}

# --- the keepalive itself ----------------------------------------------------
# `docker compose up -d` is idempotent, so this is safe on every logon. `sleep
# infinity` is what actually holds the distro open; everything else is startup.
& wsl.exe -d $Distro -e bash -lc "cd $RepoPath/infra && docker compose up -d --quiet-pull >/dev/null 2>&1; exec sleep infinity"
