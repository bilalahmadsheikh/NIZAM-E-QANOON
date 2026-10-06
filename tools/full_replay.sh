#!/usr/bin/env bash
# Managed corpus-wide segmentation replay.
#
# A raw ``segment --all --redo`` is intentionally refused by the worker.  A
# full replay regenerates instrument IDs and thereby orphans S7 and TOC review
# decisions even when the new provision trees are correct.  This wrapper makes
# that recovery part of the operation and treats a lower release count (or a
# larger review queue) as a failed replay, never as a successful new baseline.

set -euo pipefail
cd "$(dirname "$0")/.."

if [ "${1:-}" != "--apply" ]; then
    cat <<'EOF'
Managed full replay (no changes made).

This operation will:
  1. record release/S7/TOC baselines and create a database snapshot;
  2. replay every document under the current segmenter;
  3. re-link duplicates and re-materialise reviewed multi-expression sources;
  4. re-attach exact source-verified S7 and TOC decisions;
  5. apply only the citation-preserving, guarded S7 adjudication set;
  6. fail the run if releases fall or either pending queue grows.

Run: ./nz full-replay --apply
EOF
    exit 0
fi
shift
[ "$#" -eq 0 ] || {
    echo "usage: ./nz full-replay --apply" >&2
    exit 2
}

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
run_dir=".artifacts/full-replay/$stamp"
mkdir -p "$run_dir"
minimum_release="${NIZAM_MIN_RELEASE_READY:-4020}"

measure() {
    ./nz psql-clean -At -F '|' -c "
      WITH latest_segmentation AS (
        SELECT DISTINCT ON (r.instrument_id) r.*
          FROM segmentation_run r
          JOIN instrument i ON i.id=r.instrument_id AND i.is_active
         ORDER BY r.instrument_id,r.run_at DESC,r.id DESC),
      itemization_mismatch AS (
        SELECT r.instrument_id
          FROM latest_segmentation r
          LEFT JOIN segmentation_structural_candidate c
            ON c.instrument_id=r.instrument_id
         GROUP BY r.instrument_id,r.detail
        HAVING coalesce((r.detail->>'repeated_labels_demoted')::integer,0)
               <> count(c.id))
      SELECT (SELECT count(*) FROM v_release_instrument),
             (SELECT count(*) FROM v_toc_gap_pending),
             (SELECT count(*) FROM v_structural_adjudication_pending),
             (SELECT count(*) FROM itemization_mismatch);"
}

# The released SET, by durable identity. A count cannot see a swap: on
# 23 Sep 2026 a managed replay held the release count at 4,087 while 24
# instruments left the release and 24 others joined -- expression 1 of the
# Constitution and the Customs Act among those withdrawn. The count gate passed
# it. Instrument UUIDs cannot be compared either, because a replay regenerates
# every one; (document, observation, expression) survives a replay.
released_identities() {
    ./nz psql-clean -At -c "
      SELECT document_id||':'||source_observation_id||':'||coalesce(expression_ordinal,0)
        FROM v_release_instrument;" | LC_ALL=C sort
}
released_identities > "$run_dir/released_before.txt"

IFS='|' read -r before_release before_toc before_s7 before_s7_mismatch < <(measure)
printf 'released\ttoc_pending\ts7_pending\ts7_itemization_mismatches\n%s\t%s\t%s\t%s\n' \
    "$before_release" "$before_toc" "$before_s7" "$before_s7_mismatch" \
    > "$run_dir/baseline.tsv"

echo "baseline: released=$before_release toc=$before_toc s7=$before_s7 s7_mismatch=$before_s7_mismatch"
echo "creating pre-replay snapshot"
# --force: the snapshot's own threshold ("little has changed since the last
# one") is the wrong question here -- the replay is about to change every tree.
# On 23 Sep 2026 it skipped with 251K written, so decisions recorded since the
# previous snapshot were in no restore point at all.
./nz snapshot --force

echo "running managed full replay"
NIZAM_MANAGED_FULL_REPLAY=1 \
    uv run python -m nizam.workers.segment --all --redo 2>&1 \
    | tee "$run_dir/segment.log"

echo "running mandatory post-replay recovery"
./nz post-replay --apply 2>&1 | tee "$run_dir/post-replay.log"

echo "recording the independently guarded, machine-safe S7 subset"
./nz s7-adjudicate --apply 2>&1 | tee "$run_dir/s7-adjudicate.log"

IFS='|' read -r after_release after_toc after_s7 after_s7_mismatch < <(measure)
printf 'released\ttoc_pending\ts7_pending\ts7_itemization_mismatches\n%s\t%s\t%s\t%s\n' \
    "$after_release" "$after_toc" "$after_s7" "$after_s7_mismatch" \
    > "$run_dir/final.tsv"

echo "final:    released=$after_release toc=$after_toc s7=$after_s7 s7_mismatch=$after_s7_mismatch"
failed=0
released_identities > "$run_dir/released_after.txt"
# Every instrument released before must still be released. A new release is
# welcome; a withdrawn one is a regression however the count comes out.
LC_ALL=C comm -23 "$run_dir/released_before.txt" "$run_dir/released_after.txt" \
    > "$run_dir/released_withdrawn.txt"
withdrawn=$(wc -l < "$run_dir/released_withdrawn.txt")
if [ "$withdrawn" -gt 0 ]; then
    echo "REGRESSION: $withdrawn previously released instrument(s) were withdrawn" \
         "(document:observation:expression in $run_dir/released_withdrawn.txt)." >&2
    head -20 "$run_dir/released_withdrawn.txt" | sed 's/^/    /' >&2
    failed=1
fi
if [ "$after_release" -lt "$before_release" ]; then
    echo "REGRESSION: release count fell by $((before_release - after_release))." >&2
    failed=1
fi
if [ "$after_release" -lt "$minimum_release" ]; then
    echo "REGRESSION: release count is below the $minimum_release readiness floor." >&2
    failed=1
fi
if [ "$after_toc" -gt "$before_toc" ]; then
    echo "REGRESSION: TOC pending grew by $((after_toc - before_toc))." >&2
    failed=1
fi
if [ "$after_s7" -gt "$before_s7" ]; then
    echo "REGRESSION: S7 pending grew by $((after_s7 - before_s7))." >&2
    failed=1
fi
if [ "$after_s7_mismatch" -gt "$before_s7_mismatch" ]; then
    echo "REGRESSION: S7 itemization mismatches grew by $((after_s7_mismatch - before_s7_mismatch))." >&2
    failed=1
fi

if [ "$failed" -ne 0 ]; then
    echo "Managed replay did not pass its release gates." >&2
    echo "Evidence: $run_dir" >&2
    echo "The pre-replay snapshot is retained; no automatic destructive restore was attempted." >&2
    exit 1
fi

echo "PASS: release did not fall; TOC, S7 pending, and S7 itemization mismatches did not grow."
echo "Evidence: $run_dir"
