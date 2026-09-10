#!/usr/bin/env bash
# End-to-end check of the local stack. Run it any time; it changes nothing that
# matters (it creates and drops one throwaway table to prove the snapshot
# mechanism notices a write).
#
#   bash infra/scripts/selftest.sh
set -uo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"      # infra/
[ -f .env ] && set -a && . ./.env && set +a
CORPUS_ROOT="${CORPUS_ROOT:-/mnt/e/nizam-data}"
SNAP_DIR="${CORPUS_ROOT}/snapshots"
DB="${NIZAM_TARGET_DB:-${POSTGRES_DB:-nizam_clean}}"; USER_="${POSTGRES_USER:-nizam}"
SAFE_DB=$(printf '%s' "$DB" | tr -c 'A-Za-z0-9_.-' '_')
if [ "$DB" = nizam ]; then PREFIX=nizam; LATEST=latest
else PREFIX="$SAFE_DB"; LATEST="latest-${SAFE_DB}"; fi

pass=0; fail=0
ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; pass=$((pass+1)); }
no()   { printf '  \033[31mFAIL\033[0m  %s%s\n' "$1" "${2:+  -- $2}"; fail=$((fail+1)); }
check(){ if [ "$1" = 0 ]; then ok "$2"; else no "$2" "${3:-}"; fi; }

dc()    { docker compose -f "$(pwd)/compose.yaml" "$@"; }
psql_() { dc exec -T postgres psql -U "$USER_" -d "$DB" -tAc "$1" 2>/dev/null | tr -d '[:space:]'; }

echo "== containers"
for c in nizam-postgres nizam-pgadmin nizam-minio; do
  s=$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null || echo missing)
  [ "$s" = running ] && ok "$c running" || no "$c" "state=$s"
done

echo "== database contract (doc 03 §1)"
v=$(psql_ "SELECT current_setting('server_version_num')::int >= 170000")
[ "$v" = t ] && ok "PostgreSQL >= 17 ($(psql_ "SHOW server_version"))" || no "server version"

col=$(psql_ "SELECT datcollate FROM pg_database WHERE datname=current_database()")
[ "$col" = "en_US.UTF-8" ] && ok "collation en_US.UTF-8 (restore-compatible with the VPS)" \
  || no "collation" "got '$col', expected en_US.UTF-8"

for e in vector pg_search ltree btree_gist pg_trgm; do
  ver=$(psql_ "SELECT extversion FROM pg_extension WHERE extname='$e'")
  [ -n "$ver" ] && ok "extension $e $ver" || no "extension $e" "not installed"
done

# btree_gist must actually reject an overlap -- this is what INV-5 rests on.
dc exec -T postgres psql -U "$USER_" -d "$DB" -q >/dev/null 2>&1 <<'SQL'
CREATE TEMP TABLE _x(k int, v daterange, EXCLUDE USING gist (k WITH =, v WITH &&)) ON COMMIT DROP;
SQL
psql_ "SELECT 1" >/dev/null
dc exec -T postgres psql -U "$USER_" -d "$DB" -v ON_ERROR_STOP=1 -q >/dev/null 2>&1 <<'SQL'
BEGIN;
CREATE TEMP TABLE _x(k int, v daterange, EXCLUDE USING gist (k WITH =, v WITH &&));
INSERT INTO _x VALUES (1, daterange('2020-01-01','2021-01-01'));
INSERT INTO _x VALUES (1, daterange('2020-06-01','2022-01-01'));
COMMIT;
SQL
[ $? -ne 0 ] && ok "btree_gist rejects overlapping validity intervals" \
              || no "btree_gist" "accepted an overlap it should have refused"

q=$(psql_ "SELECT binary_quantize('[1,-1,1,-1]'::vector) <~> binary_quantize('[1,1,1,1]'::vector)")
[ -n "$q" ] && ok "pgvector binary quantise + hamming (distance=$q)" || no "pgvector quantisation"

echo "== corpus"
blobs=$(find "${CORPUS_ROOT}/raw" -type f 2>/dev/null | wc -l)
[ "$blobs" -gt 4000 ] && ok "blob store: ${blobs} files" || no "blob store" "only ${blobs} files"

rows=$(psql_ "SELECT count(*) FROM source_observation")
landed=$(psql_ "SELECT count(*) FROM source_observation WHERE outcome='landed'")
[ "${rows:-0}" -gt 4000 ] && ok "source_observation: ${rows} rows, ${landed} landed" \
  || no "source_observation" "${rows:-0} rows"

orphan=$(psql_ "SELECT count(*) FROM source_observation WHERE outcome='landed' AND (sha256 IS NULL OR object_key IS NULL)")
[ "${orphan:-1}" = 0 ] && ok "every landed observation carries bytes and an object key" \
  || no "landed rows without bytes" "$orphan"

echo "== extraction (doc 02 §4)"
docs=$(psql_ "SELECT count(*) FROM document WHERE is_active")
blocks=$(psql_ "SELECT count(*) FROM text_block b JOIN document d ON d.id=b.document_id WHERE d.is_active")
if [ "${docs:-0}" -gt 0 ]; then
  ok "documents extracted: ${docs} (${blocks} text blocks)"

  # A document with no pages or no blocks means save_document did not run
  # atomically -- segmentation would then read a silently incomplete document.
  hollow=$(psql_ "SELECT count(*) FROM document d
                   WHERE d.is_active
                     AND (NOT EXISTS (SELECT 1 FROM page p WHERE p.document_id=d.id)
                      OR NOT EXISTS (SELECT 1 FROM text_block t WHERE t.document_id=d.id))")
  [ "${hollow:-1}" = 0 ] && ok "no document is missing its pages or blocks" \
    || no "documents stored without content" "$hollow"

  # page_count is what the extractor reported; the page rows are what landed.
  mismatch=$(psql_ "SELECT count(*) FROM document d
                     WHERE d.is_active
                       AND d.page_count <> (SELECT count(*) FROM page p WHERE p.document_id=d.id)")
  [ "${mismatch:-1}" = 0 ] && ok "stored page rows match each document's page count" \
    || no "page count mismatch" "$mismatch"

  # Every extraction, good or bad, must have left a record (doc 02 §8).
  attempts=$(psql_ "SELECT count(*) FROM extraction_attempt")
  [ "${attempts:-0}" -ge "${docs:-0}" ] && ok "every extraction recorded an attempt (${attempts})" \
    || no "fewer attempts than documents" "${attempts} < ${docs}"

  # printable_ratio means different things per lane, so the check must too.
  # For E2/E3 it is the share of characters that are not extraction damage, and
  # doc 02 §4 requires >=0.95. For E4 the same column holds tesseract's mean word
  # CONFIDENCE -- a different quantity entirely. Judging OCR against the printable
  # threshold would fail every scan ever read, which is what it just did.
  lowq=$(psql_ "SELECT count(*) FROM document WHERE is_active AND lane IN ('E2','E3') AND printable_ratio < 0.95")
  [ "${lowq:-1}" = 0 ] && ok "every text-layer document meets the E2 printable threshold"     || no "text-layer documents below the acceptance threshold" "$lowq"

  ocr_total=$(psql_ "SELECT count(*) FROM document d WHERE d.is_active AND (d.lane='E4' OR EXISTS (SELECT 1 FROM text_block b WHERE b.document_id=d.id AND b.confidence IS NOT NULL))")
  if [ "${ocr_total:-0}" -gt 0 ]; then
    ocr_flagged=$(psql_ "SELECT count(*) FROM document WHERE is_active AND lane='E4' AND printable_ratio < 0.70")
    ok "OCR: ${ocr_total} documents, ${ocr_flagged} below review threshold (flagged, not hidden)"
    unconf=$(psql_ "SELECT count(*) FROM text_block b JOIN document d ON d.id=b.document_id JOIN page p ON p.document_id=b.document_id AND p.page_no=b.page_no WHERE d.is_active AND (d.lane='E4' OR p.lane='E4') AND b.confidence IS NULL")
    [ "${unconf:-1}" = 0 ] && ok "every OCR block carries a confidence"       || no "OCR blocks without confidence" "$unconf"
  fi

  # Active is an evidentiary/revision state, not a release decision. Production
  # readers and the default segment queue use only the fail-closed release view.
  release_docs=$(psql_ "SELECT count(*) FROM v_release_document")
  release_leaks=$(psql_ "SELECT count(*) FROM v_release_document r JOIN v_document_quality_status q ON q.document_id=r.document_id WHERE q.overall_outcome<>'passed'")
  [ "${release_leaks:-1}" = 0 ] && ok "release view contains only quality-passed documents (${release_docs}/${docs})" \
    || no "quality-review documents leaked into the release view" "$release_leaks"
else
  ok "no documents extracted yet (run: ./nz extract --all)"
fi

echo "== reachability"
for p in "${POSTGRES_PORT:-5433}" "${PGADMIN_PORT:-5050}" "${MINIO_CONSOLE_PORT:-9001}"; do
  (exec 3<>/dev/tcp/127.0.0.1/"$p") 2>/dev/null && { ok "port $p listening"; exec 3<&- ; } || no "port $p"
done
code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PGADMIN_PORT:-5050}/misc/ping" 2>/dev/null)
[ "$code" = 200 ] && ok "pgAdmin answering (HTTP $code)" || no "pgAdmin HTTP" "got $code"

echo "== auto-snapshot"
before=$(ls -1 "${SNAP_DIR}"/${PREFIX}-*.dump 2>/dev/null | wc -l)

# Gate 1: a trivial write must NOT trigger a full dump. An idle PostgreSQL
# nudges the WAL by a few KB on its own, so anything below the threshold is
# noise, not a change worth a snapshot.
#
# Assert on the outcome -- did a file appear -- rather than on the wording.
# Either gate may legitimately be the one that fires: right after a large ingest
# the settle gate catches it first, and matching only "skipping" would call that
# a failure when nothing was dumped.
dc exec -T postgres psql -U "$USER_" -d "$DB" -qc \
  "CREATE TABLE _probe(t text); INSERT INTO _probe VALUES ('x'); DROP TABLE _probe;" >/dev/null 2>&1
n0=$(ls -1 "${SNAP_DIR}"/${PREFIX}-*.dump 2>/dev/null | wc -l)
out=$(bash scripts/snapshot.sh 2>&1)
n1=$(ls -1 "${SNAP_DIR}"/${PREFIX}-*.dump 2>/dev/null | wc -l)
if [ "$n1" -eq "$n0" ]; then
  ok "no dump for a tiny write ($(echo "$out" | tail -1 | cut -c1-60)...)"
else
  no "trivial write produced a dump" "$out"
fi

# Gate 2: a real write is not dumped while it is still in flight.
dc exec -T postgres psql -U "$USER_" -d "$DB" -qc \
  "CREATE TABLE _bulk AS SELECT g, repeat('x',200) FROM generate_series(1,25000) g;" >/dev/null 2>&1
out=$(bash scripts/snapshot.sh 2>&1)
echo "$out" | grep -q "still being written" && ok "defers while the database is being written" \
  || no "did not defer during a write" "$out"

# Drop the probe before the dump so the restore artifact cannot contain test
# state. The drop itself advances WAL, so give the settle gate one observation.
dc exec -T postgres psql -U "$USER_" -d "$DB" -qc "DROP TABLE IF EXISTS _bulk;" >/dev/null 2>&1
out=$(bash scripts/snapshot.sh 2>&1)
if ! echo "$out" | grep -q "wrote"; then
  out=$(bash scripts/snapshot.sh 2>&1)
fi
after=$(ls -1 "${SNAP_DIR}"/${PREFIX}-*.dump 2>/dev/null | wc -l)
echo "$out" | grep -q "wrote" && ok "snapshots once the write settles ($before -> $after files)" \
  || no "no snapshot after the write settled" "$out"

[ -L "${SNAP_DIR}/${LATEST}.dump" ] && ok "${LATEST}.dump points at $(basename "$(readlink "${SNAP_DIR}/${LATEST}.dump")")" \
  || no "${LATEST}.dump pointer"

systemctl is-enabled nizam-snapshot.timer >/dev/null 2>&1 \
  && ok "systemd timer enabled ($(systemctl show nizam-snapshot.timer -p NextElapseUSecRealtime --value | cut -c1-30))" \
  || no "systemd timer not enabled"

echo "== storage location"
root=$(docker info --format '{{.DockerRootDir}}' 2>/dev/null)
case "$root" in /mnt/*) no "docker data-root on a Windows mount" "$root" ;;
                *) ok "docker data-root $root (ext4, backed by E:)" ;; esac

echo
printf '%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ] || exit 1
