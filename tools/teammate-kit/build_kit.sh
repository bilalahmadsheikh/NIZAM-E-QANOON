#!/usr/bin/env bash
# Build the teammate kit (D-087): one zip that SETUP-NIZAM.ps1 turns into a working replica on a new laptop.
#
#   bash tools/teammate-kit/build_kit.sh [PHYSICAL_EXPORT] [DUMP_EXPORT]
#
# Defaults to the newest physical-* and nizam_clean-* folders in ${CORPUS_ROOT}/snapshots/exports.
# Writes ${CORPUS_ROOT}/teammate-kit/nizam-kit-<date>.zip and SETUP-NIZAM.ps1 beside it.
#
# The zip holds:
#   SETUP-NIZAM.ps1, README.txt
#   payload/kit.json          commit, export names, corpus signature
#   payload/repo.bundle       the git history (main and this branch), so the laptop needs no GitHub access
#   payload/observations.csv  the acquisition record the compose mount expects
#   payload/exports/<physical>/   the exact copy (restored)
#   payload/exports/<dump>/       the logical dump (used only if the exact copy cannot be: a non-x86 laptop)
# Entries are STORED, not deflated: the database files are already gzip/pg_dump compressed.
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
[ -f infra/.env ] && { set -a; . infra/.env; set +a; }
CORPUS_ROOT="${CORPUS_ROOT:-/mnt/e/nizam-data}"
EX="$CORPUS_ROOT/snapshots/exports"
PHYS="${1:-$(ls -td "$EX"/physical-* | head -1 | xargs basename)}"
DUMP="${2:-$(ls -td "$EX"/nizam_clean-* | head -1 | xargs basename)}"
die() { echo "build_kit: $*" >&2; exit 1; }

[ -f "$EX/$PHYS/manifest.json" ] || die "no $EX/$PHYS/manifest.json"
[ -f "$EX/$DUMP/manifest.json" ] || die "no $EX/$DUMP/manifest.json"
sig() { sed -n 's/^ *"signature": *"\(.*\)",\{0,1\}$/\1/p' "$1"; }
[ "$(sig "$EX/$PHYS/manifest.json")" = "$(sig "$EX/$DUMP/manifest.json")" ] \
  || die "$PHYS and $DUMP are not the same database (signatures differ)"
[ -z "$(git status --porcelain --untracked-files=no -- infra nz nizam tools/teammate-kit)" ] \
  || die "commit infra/, nz, nizam/ and tools/teammate-kit first: the kit ships committed code only"
COMMIT=$(git rev-parse HEAD)
[ "${KIT_ALLOW_UNPUSHED:-}" = 1 ] || git merge-base --is-ancestor "$COMMIT" origin/main \
  || die "HEAD $COMMIT is not on origin/main yet: push first, so the laptop's origin matches (KIT_ALLOW_UNPUSHED=1 for a test kit)"

OUT="$CORPUS_ROOT/teammate-kit"; mkdir -p "$OUT"
STAMP=$(date -u +%Y%m%d)
ZIP="$OUT/nizam-kit-$STAMP.zip"
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT

# HEAD and its branch only: a local `main` may not exist or may be stale. The laptop creates main at $COMMIT.
git bundle create -q "$WORK/repo.bundle" HEAD "$(git rev-parse --abbrev-ref HEAD)"
git bundle verify -q "$WORK/repo.bundle" >/dev/null
python3 - "$WORK/kit.json" "$COMMIT" "$PHYS" "$DUMP" "$(sig "$EX/$PHYS/manifest.json")" "$(git remote get-url origin)" <<'PY'
import json, sys, datetime
out, commit, phys, dump, sig, origin = sys.argv[1:7]
json.dump({"built": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "commit": commit, "physical": phys, "dump": dump, "signature": sig, "origin": origin},
          open(out, "w", encoding="utf-8"), indent=2)
PY
cat > "$WORK/README.txt" <<EOF
Nizam-e-Qanoon teammate kit, built $(date -u '+%d %b %Y'), commit ${COMMIT:0:12}.

On the new laptop (Windows 10/11, 20 GB free on one drive, internet for the Ubuntu, Docker and Python downloads):
  1. Put SETUP-NIZAM.ps1 and this zip in the same folder. Do not unzip it.
  2. Open PowerShell in that folder (normal, not administrator) and run:
       powershell -ExecutionPolicy Bypass -File .\SETUP-NIZAM.ps1
  3. If it says to restart, restart and run the same command again. It continues where it stopped.
It ends with the corpus audit passing on the restored database and the API running.
EOF
tr -d '\r' < tools/teammate-kit/SETUP-NIZAM.ps1 | sed 's/$/\r/' > "$WORK/SETUP-NIZAM.ps1"   # CRLF for Windows
sed -i 's/$/\r/' "$WORK/README.txt"

python3 - "$ZIP" "$WORK" "$EX" "$PHYS" "$DUMP" "$CORPUS_ROOT/observations.csv" <<'PY'
import os, sys, zipfile
zpath, work, ex, phys, dump, obs = sys.argv[1:7]
entries = [(f"{work}/SETUP-NIZAM.ps1", "SETUP-NIZAM.ps1"), (f"{work}/README.txt", "README.txt"),
           (f"{work}/kit.json", "payload/kit.json"), (f"{work}/repo.bundle", "payload/repo.bundle"),
           (obs, "payload/observations.csv")]
for name in (phys, dump):
    for f in sorted(os.listdir(f"{ex}/{name}")):
        entries.append((f"{ex}/{name}/{f}", f"payload/exports/{name}/{f}"))
tmp = zpath + ".part"
with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
    for src, arc in entries:
        z.write(src, arc)
with zipfile.ZipFile(tmp) as z:
    bad = z.testzip()
    if bad: sys.exit(f"build_kit: CRC check failed on {bad}")
    print(f"  {len(z.infolist())} entries, CRC checked")
os.replace(tmp, zpath)
PY
cp "$WORK/SETUP-NIZAM.ps1" "$OUT/SETUP-NIZAM.ps1"
( cd "$OUT" && sha256sum "$(basename "$ZIP")" > "$(basename "$ZIP").sha256" )
echo "build_kit: wrote $ZIP ($(du -h "$ZIP" | cut -f1)), commit ${COMMIT:0:12}"
echo "           and $OUT/SETUP-NIZAM.ps1"
echo "           sha256 $(cut -c1-16 "$ZIP.sha256")..."
