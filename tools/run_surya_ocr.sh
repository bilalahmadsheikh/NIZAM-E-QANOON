#!/usr/bin/env bash
# Run Surya over the OCR review queue, one document at a time.
#
#   tools/run_surya_ocr.sh /mnt/e/nizam-data/ocr/q1-input /mnt/e/nizam-data/ocr/q1-output
#
# Four properties the first attempt lacked, each of which cost a five-hour run:
#
#   RESUMABLE   Surya writes one results.json per invocation. Pointing it at a
#               directory produces a single file at the very end, so a crash at
#               99% yields nothing. One document per call writes as it goes, and
#               a document that already has results.json is skipped -- so this
#               script can be re-run after any interruption.
#
#   SURVIVABLE  Detached with setsid, so it is not killed when the shell that
#               started it goes away. The first run died exactly that way.
#
#   OBSERVABLE  Every document logs start, finish and duration to a file that is
#               appended, not piped. `| tail` buffers, and a killed process then
#               takes its whole log with it.
#
#   BOUNDED     The warm inference server grows with every page it reads, so a
#               long queue on one server ends in the OOM killer. The server is
#               recycled whenever the next document would not fit -- see the
#               memory guard below.
#
# The inference server is kept warm between documents with --keep_server, so the
# per-document loop does not pay a ~20 second llama-server spawn each time.
set -uo pipefail

IN="${1:?usage: run_surya_ocr.sh INPUT_DIR OUTPUT_DIR}"
OUT="${2:?usage: run_surya_ocr.sh INPUT_DIR OUTPUT_DIR}"
OCR_ROOT="${OCR_ROOT:-/mnt/e/nizam-data/ocr}"
LOG="${SURYA_LOG:-$OUT/run.log}"

export HF_HOME="${HF_HOME:-/mnt/e/nizam-data/model-cache}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/mnt/e/nizam-data/model-cache/xdg}"
export LLAMA_CPP_BINARY="${LLAMA_CPP_BINARY:-/mnt/e/nizam-data/llama-cpp-b10516/llama-b10516/llama-server}"

# Slot count, and why it is 2 rather than Surya's default.
#
# Surya sizes llama-server as PARALLEL x CTX_PER_SLOT. At the default 8 slots
# that is 98,304 tokens of KV cache, and the kernel killed it twice:
#
#   llama-server invoked oom-killer
#   Out of memory: Killed process (llama-server)
#     total-vm 10,764,016 kB   anon-rss 7,357,284 kB
#
# 10.7 GB requested against the 10 GB this WSL VM is given by .wslconfig, which
# doc 09a already divides between Postgres, Docker, pgAdmin and MinIO. Two slots
# put the server near 2.5-3 GB, which fits alongside them.
#
# CTX_PER_SLOT is deliberately NOT reduced: surya/settings.py notes that below
# 12,288 "llama-server silently truncates outputs once a slot fills" -- a
# smaller cache would corrupt long pages instead of failing loudly.
export SURYA_INFERENCE_PARALLEL="${SURYA_INFERENCE_PARALLEL:-2}"
SURYA="$OCR_ROOT/surya-venv/bin/surya_ocr"

# --- memory guard ------------------------------------------------------------
#
# Two slots fit, but they do not stay put. Measured over this queue, a warm
# server starts near 1,960 MB and adds ~140 MB for every page it reads, and it
# never gives any of it back:
#
#   fresh                 1,961 MB
#   after 6 pages (4526)  2,790 MB
#   after ~35 pages       5,750 MB
#
# So the ceiling is not reached by any one document; it is reached by the queue.
# Before each document the guard projects where this server would end up after
# reading it, and recycles the server first if that overshoots. Surya spawns a
# new one on the next call, which costs ~20 seconds and resets the growth.
#
# The ceiling is what llama-server alone may hold, leaving the rest of the VM's
# 10 GB to Postgres, Docker, pgAdmin and MinIO.
SURYA_SERVER_CEILING_MB="${SURYA_SERVER_CEILING_MB:-5000}"
SURYA_MB_PER_PAGE="${SURYA_MB_PER_PAGE:-150}"
SERVER_MATCH="llama-server .*surya-2[.]gguf"

# --- long documents in chunks ------------------------------------------------
#
# The guard above acts only BETWEEN documents, and the growth does not wait for
# a document boundary. A long document drives one server past what the VM holds
# on its own: 4593 (93 pp) ran 13 hours with the server at 7.7 GB and a timeout
# every 10-20 minutes, and 4588 (58 pp) did the same until the kernel killed
# WSL's init, taking Postgres down with it (7 Oct). So a document longer than
# SURYA_CHUNK_PAGES is read in page ranges, each on a fresh server -- 15 pages
# keep a server near 1,960 + 15 x 150 = 4,200 MB. Each chunk's results are kept
# under $OUT/.chunks/<stem>/pA-B/, so an interrupted document resumes at its
# next unread chunk. Surya numbers a range's pages from 1, so the merge shifts
# every page back to its place in the PDF and refuses unless the chunks cover
# pages 1..N exactly once, in order.
SURYA_CHUNK_PAGES="${SURYA_CHUNK_PAGES:-15}"

server_rss_mb() {
    # Empty when no server is running.
    ps -eo rss,cmd --no-headers 2>/dev/null \
        | awk '/llama-server .*surya-2[.]gguf/ { print int($1/1024); exit }'
}

page_count() {
    # pdfinfo is cheap and exact. If it cannot read the file, assume a large
    # document so the guard errs toward recycling rather than toward an OOM.
    local n
    n=$(pdfinfo "$1" 2>/dev/null | awk '/^Pages:/ { print $2; exit }')
    if [ -n "$n" ]; then printf '%s' "$n"; else printf '20'; fi
}

stop_server() {
    # SIGTERM is not always prompt: a server mid-inference outlived the three
    # seconds the first version of this waited, and was reported as surviving
    # the kill. Wait for it to actually go, then escalate.
    pkill -f "$SERVER_MATCH" 2>/dev/null
    local i
    for i in $(seq 1 20); do
        if [ -z "$(server_rss_mb)" ]; then return 0; fi
        sleep 1
    done
    pkill -KILL -f "$SERVER_MATCH" 2>/dev/null
    sleep 2
}

merge_chunks() {
    # $1 chunk dir, $2 stem, $3 page count, $4 output results.json
    python3 - "$1" "$2" "$3" "$4" <<'EOF'
import json, pathlib, re, sys
cdir, stem, pages, out = pathlib.Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), pathlib.Path(sys.argv[4])
merged = []
parts = sorted(cdir.glob("p*-*"), key=lambda p: int(re.match(r"p(\d+)-", p.name).group(1)))
for part in parts:
    first, last = map(int, re.match(r"p(\d+)-(\d+)$", part.name).groups())
    result = json.loads((part / stem / "results.json").read_text(encoding="utf-8"))[stem]
    if [r["page"] for r in result] != list(range(1, last - first + 2)):
        sys.exit(f"{part.name}: pages {[r['page'] for r in result]} do not number 1..{last - first + 1}")
    for i, r in enumerate(result):
        r["page"] = first + i
        merged.append(r)
if [r["page"] for r in merged] != list(range(1, pages + 1)):
    sys.exit(f"chunks cover {len(merged)} pages, not 1..{pages}")
out.parent.mkdir(parents=True, exist_ok=True)
tmp = out.with_name(out.name + ".tmp")
tmp.write_text(json.dumps({stem: merged}, ensure_ascii=False), encoding="utf-8")
tmp.replace(out)
print(f"merged {len(merged)} pages from {len(parts)} chunks")
EOF
}

run_chunked() {
    # $1 pdf, $2 stem, $3 page count. Fresh server per chunk; kept chunks are skipped.
    local pdf=$1 stem=$2 pages=$3 cdir="$OUT/.chunks/$2" s e part
    for ((s = 0; s < pages; s += SURYA_CHUNK_PAGES)); do
        e=$((s + SURYA_CHUNK_PAGES - 1)); [ "$e" -ge "$pages" ] && e=$((pages - 1))
        part="$cdir/p$((s + 1))-$((e + 1))"
        if [ -s "$part/$stem/results.json" ]; then say "  skip  $stem pp$((s + 1))-$((e + 1)) (kept)"; continue; fi
        stop_server
        say "  chunk $stem pp$((s + 1))-$((e + 1))"
        if ! "$SURYA" "$pdf" --page_range "$s-$e" --output_dir "$part" --keep_server >>"$LOG" 2>&1 \
           || [ ! -s "$part/$stem/results.json" ]; then
            say "  FAIL  $stem pp$((s + 1))-$((e + 1)); earlier chunks kept"
            rm -rf "$part"; stop_server; return 1
        fi
    done
    stop_server
    merge_chunks "$cdir" "$stem" "$pages" "$OUT/$stem/results.json" 2>&1 | tee -a "$LOG"
    [ -s "$OUT/$stem/results.json" ]
}

mkdir -p "$OUT"
: >>"$LOG"
# Progress goes to BOTH the log and stdout, and a heartbeat keeps stdout alive
# through the long silence of a single document.
#
# This is not cosmetic. A wsl.exe invocation that produces no output for minutes
# is reaped, and the whole process tree dies with it -- that killed four attempts
# here, each about three minutes into the first document. The one run that
# survived five hours was the one streaming Surya's own progress the whole time.
say() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*" | tee -a "$LOG"; }

heartbeat() { while :; do sleep 30; printf '%s ... working\n' "$(date -u +%H:%M:%S)"; done; }

# Sorted by document id, which is stable and makes a resumed run's skip list
# readable against the previous one. It is not a priority order: the Urdu
# documents led the earlier batches only because their ids happen to be lower.
# Where priority matters -- Tesseract cannot read Nastaliq at all, so Urdu is
# where a second engine changes the answer rather than refining it -- stage the
# input directory accordingly rather than relying on the sort.
mapfile -t FILES < <(ls "$IN"/*.pdf 2>/dev/null | sort)
say "=== start: ${#FILES[@]} document(s) queued"
heartbeat &
HEARTBEAT_PID=$!
trap 'kill "$HEARTBEAT_PID" 2>/dev/null' EXIT

done_n=0 skip_n=0 fail_n=0 recycle_n=0
for pdf in "${FILES[@]}"; do
    stem="$(basename "$pdf" .pdf)"
    if [ -s "$OUT/$stem/results.json" ]; then
        skip_n=$((skip_n + 1)); say "skip  $stem (already has results)"; continue
    fi

    # Recycle the server if this document would push it past the ceiling.
    rss=$(server_rss_mb)
    if [ -n "$rss" ]; then
        pages=$(page_count "$pdf")
        projected=$((rss + pages * SURYA_MB_PER_PAGE))
        if [ "$projected" -gt "$SURYA_SERVER_CEILING_MB" ]; then
            say "recycle server: ${rss} MB + ${pages}p x ${SURYA_MB_PER_PAGE} MB = ${projected} MB > ${SURYA_SERVER_CEILING_MB} MB"
            stop_server
            recycle_n=$((recycle_n + 1))
            say "recycle done"
        fi
    fi

    t0=$(date +%s)
    pages=$(page_count "$pdf")
    if [ "$pages" -gt "$SURYA_CHUNK_PAGES" ]; then
        say "start $stem ($pages pages in chunks of $SURYA_CHUNK_PAGES)"
        if run_chunked "$pdf" "$stem" "$pages"; then
            done_n=$((done_n + 1)); say "done  $stem in $(( $(date +%s) - t0 ))s"
        else
            fail_n=$((fail_n + 1)); say "FAIL  $stem after $(( $(date +%s) - t0 ))s (kept chunks resume on re-run)"
        fi
        continue
    fi
    say "start $stem"
    if "$SURYA" "$pdf" --output_dir "$OUT" --keep_server >>"$LOG" 2>&1; then
        t=$(( $(date +%s) - t0 ))
        if [ -s "$OUT/$stem/results.json" ]; then
            done_n=$((done_n + 1)); say "done  $stem in ${t}s (server $(server_rss_mb) MB)"
        else
            fail_n=$((fail_n + 1)); say "FAIL  $stem produced no results.json after ${t}s"
        fi
    else
        fail_n=$((fail_n + 1)); say "FAIL  $stem exited non-zero after $(( $(date +%s) - t0 ))s"
        # A non-zero exit is often the OOM killer taking the server out from
        # under Surya. Clear the wreckage so the next document starts fresh
        # rather than attaching to a half-dead server.
        stop_server
    fi
done

say "=== finished: $done_n done, $skip_n skipped, $fail_n failed, $recycle_n server recycle(s)"
# The warm server is deliberately left for a follow-up run; stop it explicitly.
stop_server
say "=== inference server stopped"
