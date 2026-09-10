#!/usr/bin/env bash
# Nizam-e-Qanoon -- Docker Engine inside WSL2 Ubuntu, plus the snapshot timer.
#
# Docker Engine, not Docker Desktop. Three reasons:
#   1. Docker Desktop 4.41.2 on this machine crashes at startup
#      ("running com.docker.build: exit status 1") against WSL 2.6.3.
#   2. The VPS will run `docker compose` on Ubuntu. This is literally the same
#      thing, so local and production stop being two different stories.
#   3. Docker's data-root is /var/lib/docker inside the Ubuntu ext4 disk. That
#      disk now lives at E:\wsl\Ubuntu, so images, volumes and pgdata are all on
#      E: with no bind mount to a Windows path -- which is what keeps 09a §1.2
#      satisfied (ext4, never the 9p bridge).
#
#   wsl -d Ubuntu
#   cd /mnt/e/Nizam_e_Qanoon && bash infra/wsl/setup-docker.sh
#
# Idempotent. Asks for sudo once. Log out of WSL afterwards (`exit`, then
# `wsl --shutdown` from PowerShell) so the docker group membership takes effect.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SNAP_INTERVAL="${SNAP_INTERVAL:-15min}"
say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

# Runs either as your normal user (prompts for sudo once) or as root, which is
# how WSL can run it unattended: `wsl -d Ubuntu -u root -e bash ...`. When run as
# root, SETUP_USER names the human who should end up in the docker group.
if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
  TARGET_USER="${SETUP_USER:-$(awk -F: '$3==1000{print $1; exit}' /etc/passwd)}"
  [ -n "$TARGET_USER" ] || { echo "set SETUP_USER to the account that should own docker"; exit 1; }
else
  SUDO="sudo"
  TARGET_USER="$USER"
fi

say "0. checking the machine"
. /etc/os-release
[ "${VERSION_CODENAME:-}" = noble ] || { echo "expected Ubuntu 24.04 (noble), got ${VERSION_CODENAME:-?}"; exit 1; }
[ -d /run/systemd/system ] || { echo "systemd is not running in this distro; enable it in /etc/wsl.conf"; exit 1; }
echo "Ubuntu ${VERSION_ID} noble, systemd active, docker user '${TARGET_USER}', ok"

# --- 1. Docker Engine --------------------------------------------------------
say "1. installing Docker Engine and the compose plugin"
# Not `command -v docker`: WSL appends the Windows PATH, so that finds Docker
# Desktop's CLI at /mnt/c/Program Files/... which cannot talk to anything here.
# Ask dpkg whether the Linux engine is actually installed.
if ! dpkg -s docker-ce >/dev/null 2>&1; then
  ${SUDO} apt-get update -qq
  ${SUDO} apt-get install -y -qq ca-certificates curl gnupg
  ${SUDO} install -m 0755 -d /etc/apt/keyrings
  ${SUDO} curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  ${SUDO} chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu noble stable" \
    | ${SUDO} tee /etc/apt/sources.list.d/docker.list >/dev/null
  ${SUDO} apt-get update -qq
  ${SUDO} apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
                             docker-buildx-plugin docker-compose-plugin
else
  echo "docker-ce already installed: $(/usr/bin/docker --version)"
fi

${SUDO} systemctl enable --now docker
${SUDO} usermod -aG docker "${TARGET_USER}"

# --- 2. where Docker keeps its data ------------------------------------------
say "2. confirming Docker's data-root is on E:"
ROOT=$(${SUDO} docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo /var/lib/docker)
echo "data-root: ${ROOT}"
case "$ROOT" in
  /mnt/*) echo "WARNING: data-root is on a Windows mount (9p). Postgres will be slow."; ;;
  *)      echo "inside ext4 -> backed by E:\\wsl\\Ubuntu\\ext4.vhdx. Correct." ;;
esac

# --- 3. the snapshot timer ---------------------------------------------------
# Answers "whenever we populate or update the db, the shared copy follows".
# A systemd timer runs the snapshot script; the script itself is a no-op unless
# the write-ahead log has actually advanced, so an idle database costs nothing.
say "3. installing the auto-snapshot timer (every ${SNAP_INTERVAL})"
${SUDO} tee /etc/systemd/system/nizam-snapshot.service >/dev/null <<UNIT
[Unit]
Description=Nizam-e-Qanoon database snapshot (skips when the WAL has not moved)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
User=${TARGET_USER}
WorkingDirectory=${REPO_ROOT}
ExecStart=/usr/bin/env bash ${REPO_ROOT}/infra/scripts/snapshot.sh
UNIT

${SUDO} tee /etc/systemd/system/nizam-snapshot.timer >/dev/null <<UNIT
[Unit]
Description=Snapshot the Nizam-e-Qanoon database when it changes

[Timer]
OnBootSec=5min
OnUnitActiveSec=${SNAP_INTERVAL}
AccuracySec=1min
Persistent=true

[Install]
WantedBy=timers.target
UNIT

${SUDO} systemctl daemon-reload
${SUDO} systemctl enable --now nizam-snapshot.timer
systemctl list-timers nizam-snapshot.timer --no-pager || true

cat <<EOF

Done.

Docker group membership needs a fresh session. From PowerShell:
    wsl --shutdown
then reopen WSL and bring the stack up:
    cd /mnt/e/Nizam_e_Qanoon && bash infra/up.sh
EOF
