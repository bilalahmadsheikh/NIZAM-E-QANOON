<#
SETUP-NIZAM.ps1 -- set up Nizam-e-Qanoon on a new Windows laptop from the teammate kit (D-087).

  1. Put this file and nizam-kit-<date>.zip in the same folder (Downloads is fine).
  2. Open PowerShell in that folder (not as administrator) and run:
       powershell -ExecutionPolicy Bypass -File .\SETUP-NIZAM.ps1
  3. If it says "restart and run this again", do exactly that. It carries on from where it stopped.

What it does, each step skipped when already done:
  - turns on WSL (Windows asks for permission once, then a restart);
  - writes C:\Users\<you>\.wslconfig so WSL keeps the database running;
  - installs Ubuntu 24.04 onto the data drive and creates your Linux account (asks for a password);
  - unpacks the kit: the code at <drive>:\Nizam_e_Qanoon, the database copy under <drive>:\nizam-data;
  - installs Docker Engine and Python tooling inside Ubuntu;
  - starts Postgres, restores the exact database copy, checks it matches the sender's record counts,
    runs the 41-criterion corpus audit, and starts the library API.

Options (all optional):
  -Zip <path>        the kit zip, if it is not next to this file
  -Root <D:\>        the drive or folder to install into (default: E:\, else D:\, else C:\, needing 20 GB free)
  -Distro <name>     use an existing WSL distribution instead of Ubuntu-24.04 (must be Ubuntu 24.04)
  -DistroFile <f>    install Ubuntu from a local .wsl file instead of downloading it
  -SkipUserEnv       do not record the distribution name in the user environment
#>
param(
    [string]$Zip = '',
    [string]$Root = '',
    [string]$Distro = '',
    [string]$DistroFile = '',
    [switch]$SkipUserEnv
)

# Continue, not Stop: Windows PowerShell 5.1 turns any stderr line of a native program (wsl.exe, apt, git) into a
# terminating error under Stop. Failures are caught explicitly instead: exit codes, and try/catch on file steps.
$ErrorActionPreference = 'Continue'
$env:WSL_UTF8 = '1'          # wsl.exe's own messages in UTF-8, not UTF-16
$Here = $PSScriptRoot
$NeedGB = 20

function Say([string]$m) { Write-Host ''; Write-Host "== $m" -ForegroundColor Cyan }
function Note([string]$m) { Write-Host "   $m" }
function Stop-Setup([string]$m) { Write-Host ''; Write-Host $m -ForegroundColor Red; exit 1 }
function Done-Setup([string]$m) { Write-Host ''; Write-Host $m -ForegroundColor Yellow; exit 0 }
function Clean([object]$o) { (($o | Out-String) -replace "`0", '').Trim() }
function FreeGB([string]$path) {
    $d = Get-PSDrive -Name $path.Substring(0, 1) -ErrorAction SilentlyContinue
    if ($null -eq $d) { return 0 }
    [math]::Floor($d.Free / 1GB)
}
function ToWsl([string]$p) {
    $full = [IO.Path]::GetFullPath($p).TrimEnd('\')
    '/mnt/' + $full.Substring(0, 1).ToLower() + $full.Substring(2).Replace('\', '/')
}
function Lines([object]$o) { (Clean $o) -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ } }
function Distros { Lines (& wsl.exe -l -q) }
# Run a command in the distribution, its output to the console, and return only the exit code. Arguments are
# plain tokens (paths without spaces): Windows PowerShell 5.1 does not pass embedded quotes to native programs intact.
function InWsl([string]$user, [string[]]$cmd) {
    & wsl.exe -d $script:Distro -u $user -e @cmd | Out-Host
    return $LASTEXITCODE
}

# ---------------------------------------------------------------- the Linux half, written out as a file
$StageSh = @'
#!/usr/bin/env bash
# Written by SETUP-NIZAM.ps1. Modes: root-prep | root-user | root-docker | user-clone | user-main
set -euo pipefail
mode="$1"; shift
say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
die() { printf '\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

case "$mode" in
root-prep)
  . /etc/os-release
  [ "${VERSION_CODENAME:-}" = noble ] || die "this distribution is Ubuntu ${VERSION_ID:-?}; the project needs 24.04 (noble)"
  if [ ! -d /run/systemd/system ]; then
    if ! grep -qs '^systemd *= *true' /etc/wsl.conf; then
      printf '\n[boot]\nsystemd=true\n' >> /etc/wsl.conf
    fi
    echo "SYSTEMD_ENABLED_RESTART"; exit 0
  fi
  missing=""
  for p in git curl python3 ca-certificates; do dpkg -s "$p" >/dev/null 2>&1 || missing="$missing $p"; done
  if [ -n "$missing" ]; then
    say "installing$missing"
    apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $missing
  fi
  echo "  Ubuntu ${VERSION_ID}, systemd running, git/curl/python3 present"
  ;;
root-user)          # root-user NAME ; password on stdin
  name="$1"
  id "$name" >/dev/null 2>&1 || useradd -m -s /bin/bash -G sudo "$name"
  pw=$(head -n1 | tr -d '\r\n')
  [ -n "$pw" ] || die "empty password"
  printf '%s:%s\n' "$name" "$pw" | chpasswd
  echo "  Linux account '$name' ready (in the sudo group)"
  ;;
root-docker)        # root-docker USER REPO
  user="$1"; repo="$2"
  SETUP_USER="$user" bash "$repo/infra/wsl/setup-docker.sh" || die "infra/wsl/setup-docker.sh failed (output above)"
  dpkg -s docker-ce >/dev/null 2>&1 || die "Docker Engine did not install"
  ;;
user-clone)         # user-clone BUNDLE REPO ORIGIN COMMIT
  bundle="$1"; repo="$2"; origin="$3"; commit="$4"
  if [ ! -d "$repo/.git" ]; then
    say "cloning the code into $repo"
    git clone -q --no-checkout "$bundle" "$repo"
    git -C "$repo" checkout -q -B main "$commit"
    git -C "$repo" remote set-url origin "$origin"
    # best effort: track GitHub's main (needs network, and access if the repository is private)
    if timeout 60 git -C "$repo" fetch -q origin main 2>/dev/null; then
      git -C "$repo" branch -q -u origin/main main
    else
      echo "  (could not reach $origin now; 'git fetch origin' later sets up tracking)"
    fi
  elif ! git -C "$repo" cat-file -e "$commit^{commit}" 2>/dev/null; then
    say "bringing $repo up to the kit's commit"
    git -C "$repo" fetch -q "$bundle" HEAD
    git -C "$repo" merge -q --ff-only "$commit" || die "$repo has its own commits; merge $commit by hand, then run this again"
  fi
  git -C "$repo" merge-base --is-ancestor "$commit" HEAD || die "$repo is not at or after commit $commit; run: git -C $repo checkout main"
  echo "  code at $(git -C "$repo" log --oneline -1)"
  ;;
user-main)          # user-main REPO CORPUS_ROOT PHYSICAL DUMP LOG
  repo="$1"; corpus="$2"; phys="$3"; dump="$4"; log="$5"
  exec > >(tee -a "$log") 2>&1
  cd "$repo"
  export PATH="$HOME/.local/bin:$PATH"
  docker info >/dev/null 2>&1 || die "Docker is not reachable yet (group membership). Run SETUP-NIZAM.ps1 again."

  say "Python tooling (uv)"
  if ! command -v uv >/dev/null; then curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1; fi
  command -v uv >/dev/null || die "uv did not install"
  uv sync -q --frozen --extra api
  echo "  $(uv --version), .venv ready"

  say "configuration (infra/.env)"
  if [ ! -f infra/.env ]; then
    python3 - infra/.env.example infra/.env "$corpus" <<'PY'
import re, secrets, string, sys
alpha = string.ascii_letters + string.digits
src, dst, corpus = sys.argv[1:4]
s = open(src, encoding="utf-8").read()
for key in ("POSTGRES_PASSWORD", "PGADMIN_PASSWORD", "MINIO_ROOT_PASSWORD"):
    s = s.replace(f"{key}=\n", f"{key}=" + "".join(secrets.choice(alpha) for _ in range(20)) + "\n", 1)
s = re.sub(r"(?m)^CORPUS_ROOT=.*$", "CORPUS_ROOT=" + corpus, s)
open(dst, "w", encoding="utf-8", newline="\n").write(s)
PY
    echo "  generated infra/.env with fresh passwords"
  else
    sed -i "s#^CORPUS_ROOT=.*#CORPUS_ROOT=$corpus#" infra/.env
    echo "  infra/.env present"
  fi
  set -a; . infra/.env; set +a
  for k in POSTGRES_PASSWORD PGADMIN_PASSWORD MINIO_ROOT_PASSWORD; do
    [ -n "${!k:-}" ] || die "infra/.env has no $k"
  done

  say "starting the containers (first time downloads about 1.5 GB of images)"
  docker compose -f infra/compose.yaml up -d --quiet-pull
  for i in $(seq 1 100); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' nizam-postgres 2>/dev/null || echo x)" = healthy ] && break
    [ "$i" -eq 100 ] && die "postgres did not become healthy: docker compose -f infra/compose.yaml logs postgres"
    sleep 3
  done
  echo "  postgres healthy"

  ex="$corpus/snapshots/exports"
  want=$(sed -n 's/^ *"signature": *"\(.*\)",\{0,1\}$/\1/p' "$ex/$phys/manifest.json")
  have=$(docker exec -i nizam-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA \
           < infra/scripts/corpus-signature.sql 2>/dev/null | tr -d '\r' || true)
  if [ -n "$want" ] && [ "$have" = "$want" ]; then
    say "database already restored (signature matches the sender's)"
  else
    say "restoring the exact copy $phys"
    vol=$(docker inspect nizam-postgres --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}')
    if ! NIZAM_RESTORE_CONFIRM="$vol" ./nz restore --physical "exports/$phys"; then
      echo "  the exact copy could not be used here (reason above); restoring the dump $dump instead (about 6 minutes)"
      NIZAM_RESTORE_CONFIRM="$POSTGRES_DB" ./nz restore "exports/$dump/$dump.dump" \
        || die "both restores failed; send the output above to the sender"
    fi
  fi

  say "bringing the stack up (verify, migrations, library API)"
  ./nz up >/tmp/nz-up.log 2>&1 || { tail -30 /tmp/nz-up.log; die "./nz up failed"; }
  ./nz api status || ./nz api restart

  say "corpus audit (41 criteria)"
  ./nz audit >/tmp/nz-audit.log 2>&1 || true
  pass=$(grep -cw PASS /tmp/nz-audit.log || true); fail=$(grep -cw FAIL /tmp/nz-audit.log || true)
  echo "  $pass PASS, $fail FAIL"
  [ "$fail" = 0 ] && [ "$pass" -gt 0 ] || { grep -w FAIL /tmp/nz-audit.log || tail -20 /tmp/nz-audit.log; die "the audit did not pass"; }
  echo "AUDIT_OK $pass"
  sleep 1             # let tee finish writing the log before Windows reads it
  ;;
*) die "unknown mode $mode" ;;
esac
'@

# ================================================================ 0. where everything goes
Say 'Nizam-e-Qanoon teammate setup'
if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
    Note "This is a $($env:PROCESSOR_ARCHITECTURE) laptop. The exact copy needs x86-64; the kit's dump is used instead."
}
if (-not $Zip) {
    $z = Get-ChildItem -Path $Here -Filter 'nizam-kit-*.zip' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($z) { $Zip = $z.FullName }
}
if (-not $Root) {
    foreach ($l in 'E', 'D', 'C') {
        if ((Test-Path "${l}:\") -and ((FreeGB "${l}:\") -ge $NeedGB)) { $Root = "${l}:\"; break }
    }
    if (-not $Root) {
        $free = ('E', 'D', 'C' | Where-Object { Test-Path "${_}:\" } | ForEach-Object { "${_}: $(FreeGB "${_}:\") GB" }) -join ', '
        Stop-Setup "No drive has $NeedGB GB free ($free). Free some space, or pass -Root."
    }
}
$Root = [IO.Path]::GetFullPath($Root)
if ($Root -match '\s') { Stop-Setup "The install folder must not contain spaces: $Root" }
$Kit = Join-Path $Root 'nizam-kit'
$Repo = Join-Path $Root 'Nizam_e_Qanoon'
$Data = Join-Path $Root 'nizam-data'
Note "installing into $Root  (code: $Repo, database copy: $Data)"

# ================================================================ 1. unpack the kit
$KitJson = Join-Path $Kit 'payload\kit.json'
if (-not (Test-Path $KitJson)) {
    if (-not $Zip -or -not (Test-Path $Zip)) { Stop-Setup "No nizam-kit-*.zip found next to this file. Put it here, or pass -Zip <path>." }
    $zipGB = [math]::Ceiling((Get-Item $Zip).Length / 1GB)
    if ((FreeGB $Root) -lt ($NeedGB + $zipGB)) { Stop-Setup "$Root needs $($NeedGB + $zipGB) GB free to unpack and install; it has $(FreeGB $Root) GB." }
    Say "unpacking $(Split-Path $Zip -Leaf) (about a minute)"
    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        if (Test-Path $Kit) { Remove-Item -Recurse -Force $Kit -ErrorAction Stop }
        [IO.Compression.ZipFile]::ExtractToDirectory($Zip, $Kit)
    } catch { Stop-Setup "Unpacking failed: $($_.Exception.Message). Is the zip complete? Copy it again." }
    if (-not (Test-Path $KitJson)) { Stop-Setup "$Zip is not a Nizam teammate kit (no payload\kit.json)." }
}
$K = Get-Content -Raw -Encoding UTF8 $KitJson | ConvertFrom-Json
Note "kit built $($K.built) from commit $($K.commit.Substring(0,12)); database: $($K.signature)"

# ================================================================ 2. WSL itself
Say 'WSL'
$wslOk = $false
if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
    & wsl.exe --status *> $null
    $wslOk = ($LASTEXITCODE -eq 0)
}
if (-not $wslOk) {
    Note 'turning WSL on (Windows asks for permission)'
    Start-Process -FilePath wsl.exe -ArgumentList '--install', '--no-distribution' -Verb RunAs -Wait
    Done-Setup 'WSL is being enabled. RESTART the laptop, then run this file again the same way.'
}
& wsl.exe --version *> $null
if ($LASTEXITCODE -ne 0) {
    Note 'updating WSL to the current release'
    & wsl.exe --update
    & wsl.exe --version *> $null
    if ($LASTEXITCODE -ne 0) { Done-Setup 'WSL was updated. RESTART the laptop, then run this file again.' }
}
Note (Lines (& wsl.exe --version) | Select-Object -First 1)

# ================================================================ 3. .wslconfig
$cfg = Join-Path $env:USERPROFILE '.wslconfig'
$ramGB = [math]::Floor((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
$memGB = [math]::Max(4, [math]::Min(10, [math]::Floor($ramGB / 2)))
$cpus = [math]::Min(6, [int](Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors)
$changed = $false
if (-not (Test-Path $cfg)) {
    $text = @"
# WSL settings written by SETUP-NIZAM.ps1 (Nizam-e-Qanoon). Changes need 'wsl --shutdown'.
[wsl2]
# Half the laptop's $ramGB GB. More starves Windows: the owner's laptop crashed at 10 GB of 15.
memory=${memGB}GB
processors=$cpus
# The important one: without it WSL stops the VM, and the database, a minute after the last terminal closes.
vmIdleTimeout=604800000

[experimental]
autoMemoryReclaim=gradual
sparseVhd=true
"@
    [IO.File]::WriteAllText($cfg, $text.Replace("`r`n", "`n"))
    Note "wrote $cfg (memory ${memGB}GB of $ramGB, $cpus processors)"
    $changed = $true
} else {
    $cur = Get-Content -Raw $cfg
    if ($cur -notmatch '(?m)^\s*vmIdleTimeout') {
        if ($cur -match '(?m)^\s*\[wsl2\]') { $cur = $cur -replace '(?m)^(\s*\[wsl2\][^\r\n]*)', "`$1`nvmIdleTimeout=604800000" }
        else { $cur = "[wsl2]`nvmIdleTimeout=604800000`n`n" + $cur }
        [IO.File]::WriteAllText($cfg, $cur)
        Note "added vmIdleTimeout to your existing $cfg"
        $changed = $true
    } else { Note "$cfg already keeps WSL running" }
}
if ($changed) { & wsl.exe --shutdown }

# ================================================================ 4. Ubuntu 24.04 and a Linux account
Say 'Ubuntu 24.04'
$have = @(Distros)
if (-not $Distro) {
    if ($have -contains 'Ubuntu-24.04') { $Distro = 'Ubuntu-24.04' }
    elseif ($have -contains 'Ubuntu') {
        & wsl.exe -d Ubuntu -u root -e grep -q VERSION_CODENAME=noble /etc/os-release
        if ($LASTEXITCODE -eq 0) { $Distro = 'Ubuntu' } else { $Distro = 'Ubuntu-24.04' }
    } else { $Distro = 'Ubuntu-24.04' }
}
$script:Distro = $Distro
if (-not ($have -contains $Distro)) {
    if ($Distro -ne 'Ubuntu-24.04' -and -not $DistroFile) { Stop-Setup "There is no WSL distribution called $Distro." }
    $loc = Join-Path $Root "wsl\$Distro"
    Note "installing $Distro into $loc (downloads about 350 MB)"
    if ($DistroFile) { & wsl.exe --install --from-file $DistroFile --name $Distro --location $loc --no-launch }
    else { & wsl.exe --install $Distro --location $loc --no-launch --web-download }
    if (-not (@(Distros) -contains $Distro)) { Stop-Setup "Installing $Distro failed (output above)." }
}
$stageWin = Join-Path $Kit 'stage.sh'
[IO.File]::WriteAllText($stageWin, $StageSh.Replace("`r`n", "`n"))
$stage = ToWsl $stageWin

$out = Clean (& wsl.exe -d $Distro -u root -e bash $stage root-prep)
Write-Host $out
if ($out -match 'SYSTEMD_ENABLED_RESTART') {
    & wsl.exe --terminate $Distro
    $out = Clean (& wsl.exe -d $Distro -u root -e bash $stage root-prep)
    Write-Host $out
}
if ($out -notmatch 'systemd running') { Stop-Setup 'Preparing Ubuntu failed (output above).' }

$uid = Clean (& wsl.exe -d $Distro -e id -u)
if ($uid -eq '0') {
    $name = ($env:USERNAME.ToLower() -replace '[^a-z0-9]', '')
    if ($name -notmatch '^[a-z]') { $name = 'nizam' }
    Note "creating your Linux account '$name'"
    $pw = $env:NIZAM_SETUP_PASSWORD
    while (-not $pw) {
        $a = Read-Host -AsSecureString "   choose a Linux password for $name (you need it for 'sudo')"
        $b = Read-Host -AsSecureString '   type it again'
        $pa = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($a))
        $pb = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($b))
        if ($pa -and $pa -eq $pb) { $pw = $pa } else { Note 'they did not match, or were empty; again' }
    }
    $pw | & wsl.exe -d $Distro -u root -e bash $stage root-user $name
    if ($LASTEXITCODE -ne 0) { Stop-Setup 'Creating the Linux account failed.' }
    & wsl.exe --manage $Distro --set-default-user $name
    & wsl.exe --terminate $Distro
}
$LinuxUser = Clean (& wsl.exe -d $Distro -e id -un)
if ($LinuxUser -eq 'root' -or -not $LinuxUser) { Stop-Setup "The distribution's default user is root; set one with: wsl --manage $Distro --set-default-user <name>" }
Note "Linux user: $LinuxUser"
if ($Distro -ne 'Ubuntu' -and -not $SkipUserEnv) {
    [Environment]::SetEnvironmentVariable('NIZAM_WSL_DISTRO', $Distro, 'User')
    $env:NIZAM_WSL_DISTRO = $Distro
    Note "recorded NIZAM_WSL_DISTRO=$Distro so .\nz.ps1 finds it"
}

# ================================================================ 5. code and database copy into place
Say 'code and database copy'
$exports = Join-Path $Data 'snapshots\exports'
try {
    New-Item -ItemType Directory -Force -Path $exports, (Join-Path $Data 'raw') -ErrorAction Stop | Out-Null
    foreach ($n in @($K.physical, $K.dump)) {
        $dst = Join-Path $exports $n
        $src = Join-Path $Kit "payload\exports\$n"
        if (-not (Test-Path (Join-Path $dst 'manifest.json'))) {
            if (-not (Test-Path $src)) { Stop-Setup "The kit has no $n. Unpack the zip again: delete $Kit and rerun." }
            if (Test-Path $dst) { Remove-Item -Recurse -Force $dst -ErrorAction Stop }
            Move-Item $src $dst -ErrorAction Stop
        }
        Note "$dst"
    }
    $obs = Join-Path $Data 'observations.csv'
    if (-not (Test-Path $obs)) { Copy-Item (Join-Path $Kit 'payload\observations.csv') $obs -ErrorAction Stop }
} catch { Stop-Setup "Placing the database copy failed: $($_.Exception.Message)" }

$rc = InWsl $LinuxUser @('bash', $stage, 'user-clone', (ToWsl (Join-Path $Kit 'payload\repo.bundle')), (ToWsl $Repo), $K.origin, $K.commit)
if ($rc -ne 0) { Stop-Setup 'Placing the code failed (output above).' }

# ================================================================ 6. Docker Engine
Say 'Docker Engine (inside Ubuntu)'
& wsl.exe -d $Distro -e bash -c 'id -nG | grep -qw docker && docker info >/dev/null 2>&1'
if ($LASTEXITCODE -ne 0) {
    $rc = InWsl 'root' @('bash', $stage, 'root-docker', $LinuxUser, (ToWsl $Repo))
    if ($rc -ne 0) { Stop-Setup 'Installing Docker failed (output above).' }
    & wsl.exe --terminate $Distro          # a fresh session picks up the docker group
} else { Note 'Docker Engine running, user in the docker group' }

# ================================================================ 7. the database
Say 'database'
$log = Join-Path $Kit 'setup-last-run.log'
if (Test-Path $log) { Remove-Item $log }
$rc = InWsl $LinuxUser @('bash', $stage, 'user-main', (ToWsl $Repo), (ToWsl $Data), $K.physical, $K.dump, (ToWsl $log))
if ($rc -ne 0 -or -not (Test-Path $log) -or -not (Select-String -Path $log -Pattern 'AUDIT_OK' -Quiet)) {
    Stop-Setup "Setup stopped (see above, also saved in $log). Fix what it names and run this file again."
}

Say 'done'
Write-Host @"
   Nizam-e-Qanoon is set up on this laptop, as an exact replica of the sender's database.

   Code       $Repo   (git: main, origin GitHub)
   Database   Postgres on localhost:5433, database nizam_clean, user nizam
              password: POSTGRES_PASSWORD in $Repo\infra\.env
   pgAdmin    http://localhost:5050   (login in infra\.env: PGADMIN_EMAIL / PGADMIN_PASSWORD)
   API        http://localhost:8080/v1/law/collections/popular

   Every day:  cd $Repo ;  .\nz.ps1 up      (or inside Ubuntu: cd $(ToWsl $Repo) && ./nz up)
   Check:      .\nz.ps1 status   .\nz.ps1 audit

   The unpacked kit in $Kit can be deleted now (the copies it held are in $exports).
"@ -ForegroundColor Green
