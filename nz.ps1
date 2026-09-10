# nz.ps1 -- run ./nz from PowerShell without opening a WSL shell first.
#
#   .\nz.ps1 up
#   .\nz.ps1 status
#   .\nz.ps1 extract --all
#
# Everything runs inside WSL, where Docker and the database live. This only
# forwards the arguments and translates the repository path.

param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Rest)

$ErrorActionPreference = 'Stop'
$Distro = if ($env:NIZAM_WSL_DISTRO) { $env:NIZAM_WSL_DISTRO } else { 'Ubuntu' }

# E:\Nizam_e_Qanoon -> /mnt/e/Nizam_e_Qanoon
$repo = $PSScriptRoot
$drive = $repo.Substring(0, 1).ToLower()
$wslPath = '/mnt/' + $drive + $repo.Substring(2).Replace('\', '/')

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    Write-Error "WSL is not installed. See SETUP.md."
}

# Quote each argument for bash so flags and values survive the hop.
$quoted = ($Rest | ForEach-Object { "'" + ($_ -replace "'", "'\''") + "'" }) -join ' '
& wsl.exe -d $Distro -e bash -lc "cd '$wslPath' && ./nz $quoted"
exit $LASTEXITCODE
