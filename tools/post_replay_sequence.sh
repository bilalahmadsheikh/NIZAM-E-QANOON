#!/usr/bin/env bash
#
# The repairs a full replay makes necessary, in the only order that works.
#
#     tools/post_replay_sequence.sh              # report what each step would do
#     tools/post_replay_sequence.sh --apply      # actually run them
#
# WHY THIS EXISTS. A replay is not finished when `segment` exits. It retires
# every instrument it touched, and several kinds of record point at instruments
# by an identifier the replay regenerates. Nothing fails loudly when the repairs
# are skipped -- the corpus quietly starts double-counting, or silently drops
# reviewed judgements -- so the failure is discovered later, by a number that
# does not re-derive.
#
# THE ORDERING LAW, learned by doing it backwards and paying for it:
#
#     parser fix  ->  replay  ->  re-attach  ->  adjudicate
#
# Adjudicating before a replay wastes the work. Measured on 19 Sep: of 430
# corrective decisions written before a replay, 242 candidates retired and 118
# -- 49% -- came back as the same collision. Half that reading was done twice
# for nothing.
#
# Re-attaching before the replay finishes is worse: it writes decisions against
# instruments that are about to be retired.

set -euo pipefail
cd "$(dirname "$0")/.."

APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

say() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
run() {
    if [ "$APPLY" = "1" ]; then
        echo "+ $*"
        "$@"
    else
        echo "  would run: $*"
    fi
}

# ---------------------------------------------------------------- step 0
# A segmentation run still holding the advisory lock means the replay is not
# finished. Every step below reads or writes instrument-keyed rows, so running
# now would race the thing that is retiring them.
say "0. is the replay finished?"
if pgrep -f '[n]izam.workers.segment' >/dev/null 2>&1; then
    echo "REFUSING: a segmentation run is still going."
    echo "  see it:  pgrep -af nizam.workers.segment"
    echo "  This sequence must not run until it exits -- every step below keys"
    echo "  on instruments the replay is still retiring."
    exit 1
fi
echo "  no segmentation run active."

# ---------------------------------------------------------------- step 1
# Symptom when skipped: a document carries two active canonical instruments at
# the same expression_ordinal, so one citation resolves to two provisions and
# every count for that document doubles. Measured after the 19 Sep replay:
# documents 2605, 3677, 4139, 4501.
say "1. re-link exact duplicate instruments"
if [ "$APPLY" = "1" ]; then
    uv run python tools/resolve_exact_instrument_duplicates.py --apply
else
    uv run python tools/resolve_exact_instrument_duplicates.py
fi

# ---------------------------------------------------------------- step 2
# Restore the reviewed multi-expression splits the plain segmenter refuses to
# overwrite. These documents error on EVERY full replay by design -- that is a
# guard working, not a failure. Forcing the plain segmenter past it would
# collapse a source-reviewed reading into one tree and silently change what is
# citable.
#
# The tool takes one document at a time, so the curated lists are iterated
# here. They are the two sets at the top of tools/materialize_multi_instrument.py
# -- PRIMARY_DOCUMENTS (an independently citable outer instrument followed by
# appendices) and COMPILATION_DOCUMENTS (editorial compilations, not themselves
# legal instruments). Keep them in step with that file.
say "2. re-materialise the source-reviewed multi-expression documents"
MULTI_DOCS="977 1106 3389 3553 3696 3912 4434 4452 3423 3949 4440 4497 268 691 1822 1626 1839 1970 2063 2146 1973 4428 4347 4367 4378 3464 3392 2985 2404"
for d in $MULTI_DOCS; do
    if [ "$APPLY" = "1" ]; then
        uv run python tools/materialize_multi_instrument.py --document "$d" --apply --summary-only \
            || echo "  document $d: materializer declined (see above)"
    else
        uv run python tools/materialize_multi_instrument.py --document "$d" --summary-only \
            || echo "  document $d: would decline (see above)"
    fi
done

# --------------------------------------------------------------- step 2a
# Source incompleteness is durable at document level, but the duplicate_of
# flag which keeps a truncated copy out of the release view lives on the
# regenerated instrument. Re-derive it after every replay so a partial portal
# PDF cannot silently become the published Act again.
say "2a. re-link declared partial sources to their complete copies"
if [ "$APPLY" = "1" ]; then
    uv run python tools/apply_source_incompleteness.py --apply
else
    uv run python tools/apply_source_incompleteness.py
fi

# --------------------------------------------------------------- step 2b
# Same shape for a same-text copy (migration 0062): a second file of an
# instrument that differs from the canonical document only in page furniture.
# The record is durable at observation level; the duplicate_of flag that keeps
# the copy out of release lives on the regenerated instrument. Runs after step
# 1, whose lineage pass advances a link when the canonical was replayed. Reports
# and exits cleanly while 0062 is not applied.
say "2b. re-link declared same-text copies to their canonical documents"
if [ "$APPLY" = "1" ]; then
    uv run python tools/apply_source_same_text_copy.py --apply
else
    uv run python tools/apply_source_same_text_copy.py
fi

# --------------------------------------------------------------- step 2b2
# Same shape for a non-authoritative file (migration 0065): an unofficial
# translation, or a Bill whose enacted text is held, kept out of release in
# favour of the authoritative document. Reports and exits cleanly while 0065 is
# not applied.
say "2b2. re-link declared non-authoritative files to their authoritative documents"
if [ "$APPLY" = "1" ]; then
    uv run python tools/apply_source_non_authoritative_copy.py --apply
else
    uv run python tools/apply_source_non_authoritative_copy.py
fi

# --------------------------------------------------------------- step 2b3
# Statutory repeals (migration 0066): instrument.status 'repealed' and repealed_by_id are derived from the
# source-level record after every replay (a replay recreates instruments with status 'unknown'). Reports and exits
# cleanly while 0066 is not applied.
say "2b3. re-derive statutory repeal status"
if [ "$APPLY" = "1" ]; then
    uv run python tools/apply_statutory_repeals.py --apply
else
    uv run python tools/apply_statutory_repeals.py
fi

# --------------------------------------------------------------- step 2c
# After every re-link above (duplicates, splits, partial and same-text copies), no document may hold MORE released
# expressions than at the signed baseline unless the rise was declared: a reviewed split plan, or an approval
# reason saying "new released expression". Doc 4419 (12 Oct): a duplicate observation rebuilt without its
# canonical's readings stopped being a duplicate and a second, uncorrected Constitution entered the release; no
# withdrawal check could see it. Read-only; STOPS the sequence (set -e) on an undeclared rise.
say "2c. no undeclared rise in released expressions per document"
uv run python tools/released_count_guard.py

# ---------------------------------------------------------------- step 3
# Only `source_verified` readings are re-attached, and only those carrying an
# `observed` note of 40+ characters. That is deliberate: a machine decision can
# be regenerated by re-running the machine, so it is not worth anchoring. A
# page someone read cannot be.
#
# Measured mid-replay on 20 Sep, of 1,193 orphaned readings: 679 re-anchor
# uniquely, 99 are ambiguous and must be refused, and 415 find no candidate at
# all -- which is a SUCCESS, not a loss: the parser fixes dissolved the
# collision, so there is nothing left to adjudicate.
say "3. re-attach orphaned S7 source readings"
if [ "$APPLY" = "1" ]; then
    ./nz reattach
    ./nz s7-source --readings .artifacts/s7-source/reattach.json --apply
else
    ./nz reattach
fi

# ---------------------------------------------------------------- step 4
# `toc_gap_adjudication` already stores document_id, printed_label and
# source_page beside the volatile instrument_id/toc_entry_id, so the durable
# anchor is in the table. Measured: label alone re-anchors 350 of 570 uniquely
# (138 no-match, 82 ambiguous); adding source_page cuts ambiguity to 20 but
# costs 58 matches, because a page moves between parses more often than a
# printed label does. A tiered anchor that records WHICH tier matched is the
# right shape; the tier is evidence, not noise.
say "4. re-attach orphaned contents-gap decisions"
if [ -f tools/reattach_orphaned_toc_adjudications.py ]; then
    if [ "$APPLY" = "1" ]; then
        uv run python tools/reattach_orphaned_toc_adjudications.py --apply
    else
        uv run python tools/reattach_orphaned_toc_adjudications.py
    fi
else
    echo "  NOT AVAILABLE: tools/reattach_orphaned_toc_adjudications.py does not exist."
    echo "  Until it does, every full replay permanently discards the contents-gap"
    echo "  readings -- 570 latest decisions, all of them orphaned right now."
    echo "  Do NOT rebind them blind when it lands: 29 of 93 absent_in_source"
    echo "  claims are contradicted by later page reads (doc 3149 ss.14/15/16/18,"
    echo "  doc 4427's collapsed range)."
fi

# ---------------------------------------------------------------- step 5
say "5. re-measure -- every pre-replay figure is now suspect"
run ./nz s7-citability
echo "  then, and only then:"
echo "    ./nz s7-adjudicate      # the machine-decidable, citation-preserving batch"
echo "    ./nz s7-source          # source-read what is left"
echo
echo "  and re-derive rather than re-quote:"
echo "    ./nz mislabelled-headings ; ./nz gap-causes ; ./nz audit ; ./nz state ; ./nz test"
