"""Re-attach contents-gap adjudications the replay orphaned.

WHY THIS EXISTS. ``toc_gap_adjudication`` binds a decision to an instrument and
a contents entry -- ``(instrument_id, toc_entry_id, printed_label)``. A replay
retires every ``instrument`` and recreates every ``instrument_toc_entry``, so
both halves of that key are regenerated identifiers and the decision stops
resolving. Measured on 20 Sep 2026 against the restarted ``--all --redo``
replay, which retires every instrument in the corpus: **all 570 standing
decisions are orphaned**, across 143 documents -- 260 ``parser_defect``, 140
``found_elsewhere``, 93 ``absent_in_source`` and the rest. Every one of them is
a reading of a printed page that has not changed.

THE ANCHORING LAW, and it is not this tool's invention. Migration 0052
(``0052_toc_disposition_supersession_not_ordinal``) settled it for
``toc_disposition_assertion``: a printed contents entry is identified by its
**source block, printed label and printed heading**, with ``source_page``
carried along, and NOT by its ordinal or its row id, because "an identifier
this pipeline regenerates cannot anchor evidence across a regeneration it
produced". This tool applies the same identity to ``toc_gap_adjudication``
rather than inventing a second convention for a neighbouring table.

Measured against the 1,501 live pending entry-level gaps, counting how many
entries each of the 570 orphans matches -- none / exactly one / more than one,
and the worst case:

    (document_sha256, printed_label)             277 / 244 / 49   up to  5
    (document_id,     printed_label)             277 / 244 / 49   up to  5
    (document_id, source_block_id)               273 / 221 / 76   up to 18
    (document_id, entry source_page, label)      282 / 279 /  9   up to  3
    (document_id, printed_label, heading)        282 / 281 /  7   up to  3
    (document_id, source_block_id, label)        282 / 281 /  7   up to  3
    0052 identity: block + label + heading       282 / 281 /  7   up to  3
    0052 identity + entry source_page            282 / 281 /  7   up to  3

``document_sha256`` buys nothing over ``document_id``: no two active documents
share a sha256, so those are the same 244 rows, and sha256 is the weaker of the
two because a second copy of the same PDF would make it ambiguous where
``document_id`` stays exact. Label alone cannot separate the repeated labels
migration 0043 was written for -- the CPC prints 1..29 in two contents regions
-- and is ambiguous for 49. ``source_block_id`` alone is far worse here than it
is for S7: an S7 candidate owns its block, whereas one contents block routinely
holds a dozen entries, so it matches up to eighteen.

The block anchor and the heading anchor are each exact and, measured, **agree
on every row where both are unique -- zero disagreements**; the tool computes
both and refuses any row where they diverge, so a future divergence is caught
rather than silently resolved. ``source_page`` is carried because 0052 carries
it, and changes nothing, exactly as 0052's own comment predicts ("redundant
with block equality in every case measured"). Ordinal is deliberately excluded:
it moved under a tenth of the matches, which is the same drift that stranded
nine reviewed dispositions until 0052.

WHAT IT REFUSES, and why each refusal is not a defect but the point:

  excluded          a later page read contradicted the decision. Two classes,
                    listed in EXCLUSIONS below with the page evidence.
  already decided   a standing decision already binds the live entry. The newer
                    reading wins; this tool never stacks a row on top of one.
  ambiguous         the anchor matches more than one live entry, or the block
                    and heading anchors disagree.
  no anchor         the decision has no ``toc_entry_id`` (migration 0043's
                    legacy run-only arm), so there is no contents row behind it
                    and nothing a replay preserves.
  absence recheck   an ``absent_in_source`` whose document now fails check 4 or
                    check 5 of ``tools/review_absent_sections.py`` -- the
                    bracketing entries no longer resolve, or more than a quarter
                    of the contents list is unresolved, which is the truncated-
                    copy shape that check was written to exclude.
  dead pointer      a ``found_elsewhere`` whose ``evidence.found_provision_id``
                    no longer names a live provision and cannot be re-resolved
                    unambiguously. 139 of the 140 orphaned ones point at a
                    retired provision: a replay regenerates provision ids too,
                    so carrying that evidence forward would close a gap with a
                    citation to nothing.
  other_instrument  always refused: its evidence names a regenerated instrument
                    uuid and there is no re-resolution rule for it. None exist
                    today; the refusal is so that none is ever written blind.

and what it reports as FINISHED rather than lost: an orphan whose label the
replay resolved. The work is not re-attachable because there is no gap left.

HOW IT IS SAFE. Every write is an INSERT through
``check_toc_gap_adjudication()`` and the four evidence CHECK constraints, which
re-fire against the CURRENT tree: the entry must still be an unresolved printed
label of that instrument, the document must own the instrument, the page must
be inside the document.

Nothing is superseded, because it cannot be. Migration 0043's guard still
requires a superseding row to carry the same ``toc_entry_id`` -- which is
exactly the rule migration 0052 has just removed from
``check_toc_disposition_assertion()`` for exactly this reason. **The adjudication
table therefore still has the defect the disposition table no longer has**, and
the consistent repair is a sibling migration, drafted and argued but NOT
applied, at ``tools/evidence/0054-proposal-toc-gap-supersession-not-entry-id.sql``.
Until that is decided by the owner of 0052, the repair here is a fresh,
independent row carrying the reading forward with its provenance in
``evidence.reattached_from``; the orphan stays exactly where it is, append-only,
and re-running this tool will not write it twice.

    ./nz toc-reattach                      # dry run: measure, refuse, report
    ./nz toc-reattach --out FILE.json      # choose the manifest path
    ./nz toc-reattach --apply              # write, once the counts have been read

Run it after a replay finishes, never during one: --apply refuses while the
segmentation advisory lock is held.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Iterable

from nizam.storage.db import connect

TOOL = "tools/reattach_orphaned_toc_adjudications.py"

# `nizam/workers/segment.py:_LOCK_KEY` -- "NIZAMSEG". A replay holds it for its
# whole run, and writing adjudications against instruments a replay is in the
# middle of recreating is how an orphan is made, not how one is repaired.
SEGMENT_LOCK_KEY = 0x4E495A414D534547

# `tools/review_absent_sections.py` check 5: above this share of the contents
# list unresolved, the document is a truncated copy and "the source does not
# print this section" is a claim about the FILE, not about the Act.
TRUNCATED_COPY_SHARE = 0.25


# ---------------------------------------------------------------------------
# Decisions a later page read contradicted. These are NOT a list of ids: the
# ids are regenerated by nothing and would survive, but a reader cannot check
# an id. Each entry names the document, the labels, the resolution it refuses
# to carry, and what the page actually prints.
# ---------------------------------------------------------------------------
EXCLUSIONS: tuple[dict[str, Any], ...] = (
    {
        "document_id": 3149,
        "resolution": "absent_in_source",
        "labels": ("14", "15", "16", "18"),
        "reason": (
            "CONTRADICTED BY THE PAGE. Document 3149 (The West Pakistan "
            "Finance Act, 1962) prints these sections; it does not omit them. "
            "Page 6 carries the footnotes 'Section-14 deleted by Khyber "
            "Pakhtunkhwa Adaptation of Laws Order, 1975.', 'Section-15 deleted "
            "by ... 1975.' and 'Sections 16 omitted by Khyber Pakhtunkhwa A. L. "
            "O. 1975.'; page 7 prints the body marker '1[18* * *]' with the "
            "footnote 'Section-18 omitted by Khyber Pakhtunkhwa A. L. O. 1975.' "
            "The section is present and marked deleted, which is a "
            "parser_defect (the bracketed starred repeal marker was not opened "
            "as a section), not absence from the source. The live entries "
            "already carry exactly that decision from "
            "claude.absent-class-page-review/1, so re-attaching here would "
            "stamp a contradicted reading over a correct one."),
    },
    {
        "document_id": 4427,
        "resolution": "absent_in_source",
        "labels": ("5", "6", "16", "17", "18", "19", "20", "21", "22", "23",
                   "24", "25", "42", "42B", "43", "44", "47", "48", "49", "50",
                   "51", "51A", "52", "90", "91"),
        "reason": (
            "CONTESTED READING. Document 4427 (Railways Act, 1890) prints these "
            "sections only inside collective omission markers -- page 15 reads "
            "'16-25. 5[Omitted]' -- and the reviewer (codex.source-review/2) "
            "declined to fabricate an individual provision, recording "
            "absent_in_source with the rationale 'direct review of the cited "
            "official body page shows it only inside an explicit collective "
            "omission marker'. On the natural legal reading the Act DID have "
            "sections 16 to 25 and they were omitted, which is a printed "
            "disposition, not absence from the source. The two readings "
            "disagree about what the page means, so the decision is not carried "
            "across a replay unreviewed. Settle it with a disposition or a "
            "fresh reading; this tool will not choose."),
    },
)


# ---------------------------------------------------------------------------
# Pure core. Everything below operates on plain dicts so it is testable without
# a database, and so the refusal rules can be read without reading SQL.
# ---------------------------------------------------------------------------
def norm(value: str | None) -> str:
    """Anchor comparison. Exactly `btrim` -- no case folding, no punctuation
    stripping: two contents entries that differ only in case or punctuation are
    two entries, and collapsing them would be a guess."""
    return (value or "").strip()


def excluded_reason(document_id: int, printed_label: str,
                    resolution: str,
                    exclusions: Iterable[dict[str, Any]] = EXCLUSIONS
                    ) -> str | None:
    label = norm(printed_label)
    for rule in exclusions:
        if (rule["document_id"] == document_id
                and rule["resolution"] == resolution
                and label in {norm(x) for x in rule["labels"]}):
            return rule["reason"]
    return None


def _refuse(orphan: dict, kind: str, detail: str, tier: str | None = None) -> dict:
    row = {"adjudication_id": str(orphan["id"]),
           "document_id": orphan["document_id"],
           "printed_label": orphan["printed_label"],
           "resolution": orphan["resolution"],
           "decided_by": orphan["decided_by"],
           "kind": kind, "detail": detail}
    if tier:
        row["would_match_at_tier"] = tier
    return row


# The anchor ladder, strongest first. Only T1 is ACCEPTED -- the rest are
# measured and reported, never used, so that "relaxing the anchor would recover
# N rows" is a number on the screen rather than a quiet policy change. Measured
# 20 Sep 2026 over 497 entry-level orphans: T1 recovers 281 and **T2 to T5
# recover nothing at all**, because a row that fails T1 fails it by the label
# being gone from the new contents (209) or genuinely repeated (49), not by a
# field drifting. If a later replay makes T2+ non-empty, this prints it and a
# person decides whether to widen -- it does not widen itself.
TIERS = (
    ("T1 0052 identity: block + label + heading + page", ("block", "head", "page")),
    ("T2 the entry's source_page moved",                 ("block", "head")),
    ("T3 the printed heading moved",                     ("block", "page")),
    ("T4 the source block moved",                        ("head", "page")),
    ("T5 printed label alone",                           ()),
)


def _matches(orphan: dict, live: list[dict], fields: tuple[str, ...]) -> list[dict]:
    label = norm(orphan["printed_label"])
    out = []
    for entry in live:
        if norm(entry["printed_label"]) != label:
            continue
        if "block" in fields and (entry["source_block_id"]
                                  != orphan["old_source_block_id"]):
            continue
        if "head" in fields and (norm(entry["printed_heading"])
                                 != norm(orphan["old_printed_heading"])):
            continue
        if "page" in fields and (entry["source_page"]
                                 != orphan["old_entry_source_page"]):
            continue
        out.append(entry)
    return out


def first_unique_tier(orphan: dict, live: list[dict]) -> str | None:
    """The strongest tier at which this orphan names exactly one live entry."""
    for name, fields in TIERS:
        if len(_matches(orphan, live, fields)) == 1:
            return name
    return None


def plan(orphans: list[dict], entries: list[dict],
         exclusions: Iterable[dict[str, Any]] = EXCLUSIONS,
         recheck_absence: bool = True) -> dict[str, list[dict]]:
    """Decide, for every orphan, one of: rebind, refuse, or finished.

    `entries` are the contents entries of the LIVE instruments of the same
    documents -- every entry, not only the gaps, because two of the absence
    checks are statements about the whole contents list.
    """
    by_document: dict[int, list[dict]] = {}
    for entry in entries:
        by_document.setdefault(entry["document_id"], []).append(entry)

    per_instrument_total: dict[str, int] = {}
    per_instrument_pending: dict[str, int] = {}
    for entry in entries:
        key = str(entry["instrument_id"])
        per_instrument_total[key] = per_instrument_total.get(key, 0) + 1
        if entry["is_pending_gap"]:
            per_instrument_pending[key] = per_instrument_pending.get(key, 0) + 1

    rebind: list[dict] = []
    refused: list[dict] = []
    finished: list[dict] = []

    for orphan in orphans:
        document_id = orphan["document_id"]
        label = norm(orphan["printed_label"])
        resolution = orphan["resolution"]
        live = by_document.get(document_id, [])

        reason = excluded_reason(document_id, label, resolution, exclusions)
        if reason:
            refused.append(_refuse(orphan, "excluded", reason))
            continue

        if orphan["old_source_block_id"] is None:
            same_label = [e for e in live if norm(e["printed_label"]) == label]
            if not same_label:
                finished.append(_refuse(
                    orphan, "finished",
                    "legacy run-only decision (no contents entry behind it); "
                    "the replay no longer reports this label missing"))
            else:
                refused.append(_refuse(
                    orphan, "no_anchor",
                    "no toc_entry_id: migration 0043's run-only arm carries no "
                    "contents row, so there is no printed entry to anchor on. "
                    "Measured: of 73 such orphans 68 are finished and the 5 "
                    "that look recoverable are duplicates of an entry-level "
                    "decision on the same label, which this tool re-attaches "
                    "through the entry arm. Re-derive with "
                    "tools/adjudicate_run_only_gaps.py rather than carrying "
                    "them: those runs overreport missing labels."))
            continue

        # Migration 0052's identity for a printed contents entry: source block,
        # printed label, printed heading, with source_page carried along. Both
        # halves are computed separately so that a future divergence between
        # them is refused rather than silently resolved -- measured, they agree
        # on every row where both are unique.
        heading = norm(orphan["old_printed_heading"])
        page = orphan["old_entry_source_page"]
        by_block = [e for e in live
                    if e["source_block_id"] == orphan["old_source_block_id"]
                    and norm(e["printed_label"]) == label
                    and e["source_page"] == page]
        by_heading = [e for e in live
                      if norm(e["printed_label"]) == label
                      and norm(e["printed_heading"]) == heading
                      and e["source_page"] == page]

        if not by_block and not by_heading:
            same_label = [e for e in live if norm(e["printed_label"]) == label]
            if any(e["resolved"] for e in same_label):
                finished.append(_refuse(
                    orphan, "finished",
                    "the replay resolved this label to a provision; there is "
                    "no gap left to re-attach to"))
            elif same_label:
                refused.append(_refuse(
                    orphan, "no_match",
                    "the label is still in the printed contents but its block "
                    "and heading both changed; a reader must re-anchor it",
                    first_unique_tier(orphan, live)))
            else:
                refused.append(_refuse(
                    orphan, "no_match",
                    "the label is no longer a printed contents entry of the "
                    "live instrument. Measured: this is not a spelling "
                    "problem -- an alphanumeric fold, a leading-zero fold and "
                    "a block+heading match ignoring the label entirely each "
                    "recover zero of these rows"))
            continue

        if len(by_block) != 1 or len(by_heading) != 1:
            refused.append(_refuse(
                orphan, "ambiguous",
                f"block anchor matches {len(by_block)} live "
                f"entr{'y' if len(by_block) == 1 else 'ies'}, heading anchor "
                f"matches {len(by_heading)}; exactly one each is required",
                first_unique_tier(orphan, live)))
            continue

        if by_block[0]["toc_entry_id"] != by_heading[0]["toc_entry_id"]:
            refused.append(_refuse(
                orphan, "ambiguous",
                f"the two anchors disagree: block picks entry "
                f"{by_block[0]['toc_entry_id']}, heading picks "
                f"{by_heading[0]['toc_entry_id']}"))
            continue

        target = by_block[0]

        if target["resolved"]:
            finished.append(_refuse(
                orphan, "finished",
                f"the replay resolved this entry ({target['toc_entry_id']}) to "
                "a provision; there is no gap left to re-attach to"))
            continue

        if target["standing_adjudication_id"]:
            refused.append(_refuse(
                orphan, "already_decided",
                f"live entry {target['toc_entry_id']} already carries a "
                f"standing {target['standing_resolution']} decision by "
                f"{target['standing_decided_by']}; the newer reading stands "
                "and this tool never stacks a row on top of one"))
            continue

        if not target["is_pending_gap"]:
            refused.append(_refuse(
                orphan, "not_a_gap",
                f"live entry {target['toc_entry_id']} is unresolved and "
                "undecided but is not in v_toc_gap_pending; its instrument is "
                "not a live canonical one, so a reader must look"))
            continue

        if resolution == "other_instrument":
            refused.append(_refuse(
                orphan, "regenerated_pointer",
                "evidence.other_instrument_id names an instrument uuid that a "
                "replay regenerates, and there is no re-resolution rule for "
                "it; re-derive this decision rather than carrying it"))
            continue

        if resolution == "found_elsewhere":
            new_provision = orphan.get("reresolved_provision_id")
            if not new_provision:
                refused.append(_refuse(
                    orphan, "dead_pointer",
                    "evidence.found_provision_id names a provision a replay "
                    "retired, and it does not re-resolve to exactly one live "
                    "provision under both (first_block, kind, label) and "
                    "(kind, label); re-derive with "
                    "tools/adjudicate_toc_found_elsewhere.py"))
                continue

        if resolution == "absent_in_source" and recheck_absence:
            instrument = str(target["instrument_id"])
            ordinal = target["ordinal"]
            siblings = [e for e in live
                        if str(e["instrument_id"]) == instrument]
            before = any(e["resolved"] and e["ordinal"] < ordinal
                         for e in siblings)
            after = any(e["resolved"] and e["ordinal"] > ordinal
                        for e in siblings)
            if not (before and after):
                refused.append(_refuse(
                    orphan, "absence_recheck",
                    "review_absent_sections check 4 no longer holds: the "
                    f"contents entries {'before' if not before else 'after'} "
                    "this one do not resolve, so the body no longer "
                    "demonstrably covers the region where this section sits"))
                continue
            total = per_instrument_total.get(instrument, 0)
            pending = per_instrument_pending.get(instrument, 0)
            share = pending / total if total else 1.0
            if share >= TRUNCATED_COPY_SHARE:
                refused.append(_refuse(
                    orphan, "absence_recheck",
                    "review_absent_sections check 5 no longer holds: "
                    f"{pending} of {total} contents entries ({share:.0%}) are "
                    "unresolved, which is the truncated-copy shape -- the "
                    "section would be absent from this FILE, not from the Act"))
                continue

        rebind.append({
            "adjudication_id": str(orphan["id"]),
            "document_id": document_id,
            "printed_label": target["printed_label"],
            "orphan_printed_label": orphan["printed_label"],
            "resolution": resolution,
            "decided_by": orphan["decided_by"],
            "source_page": orphan["source_page"],
            "new_instrument_id": str(target["instrument_id"]),
            "new_toc_entry_id": target["toc_entry_id"],
            "old_toc_entry_id": orphan["old_toc_entry_id"],
            "old_instrument_id": str(orphan["old_instrument_id"]),
            "ordinal_moved": target["ordinal"] != orphan["old_ordinal"],
            "reresolved_provision_id": orphan.get("reresolved_provision_id"),
            "anchor_tier": TIERS[0][0],
        })

    # What relaxing the anchor WOULD recover, over exactly the rows that failed
    # to name one live entry at the strict tier. Reported, never acted on.
    ladder: dict[str, int] = {name: 0 for name, _ in TIERS}
    ladder["no tier is unique"] = 0
    for row in refused:
        if row["kind"] not in ("no_match", "ambiguous"):
            continue
        tier = row.get("would_match_at_tier")
        ladder[tier if tier else "no tier is unique"] += 1

    return {"rebind": rebind, "refused": refused, "finished": finished,
            "ladder": ladder}


def reattached_evidence(evidence: dict, row: dict) -> dict:
    """The orphan's evidence, plus the provenance of the move, plus -- for a
    found_elsewhere -- the re-resolved provision, with the dead id kept so the
    rewrite is auditable rather than silent."""
    out = dict(evidence)
    out["reattached_from"] = {
        "anchor_tier": row.get("anchor_tier"),
        "adjudication_id": row["adjudication_id"],
        "instrument_id": row["old_instrument_id"],
        "toc_entry_id": row["old_toc_entry_id"],
        "printed_label": row["orphan_printed_label"],
        "anchor": "migration 0052's identity for a printed contents entry -- "
                  "source_block_id, printed_label and printed_heading, with "
                  "source_page carried along, scoped to document_id. Measured "
                  "exact and unambiguous where instrument_id, toc_entry_id and "
                  "ordinal are all regenerated by a replay.",
        "ordinal_moved": row["ordinal_moved"],
        "tool": TOOL,
        "note": "The page this reading describes has not changed. Only the "
                "pointer into our own numbering did. Append-only: the original "
                "row is untouched and cannot be superseded, because migration "
                "0043 requires a superseding row to carry the same "
                "toc_entry_id and the entry id is exactly what moved.",
    }
    if row.get("reresolved_provision_id"):
        out["found_provision_id_before_replay"] = evidence.get(
            "found_provision_id")
        out["found_provision_id"] = row["reresolved_provision_id"]
        out["reattached_from"]["provision_reresolved_by"] = (
            "exactly one live provision matching the retired one on "
            "(first_block, kind, normalised label) and on (kind, normalised "
            "label), both unique and agreeing")
    return out


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
ORPHANS_SQL = """
WITH standing AS (
  SELECT a.*
    FROM toc_gap_adjudication a
   WHERE NOT EXISTS (SELECT 1 FROM toc_gap_adjudication l
                      WHERE l.supersedes_id = a.id)
     -- idempotence: a decision this tool already carried forward is done.
     AND NOT EXISTS (
       SELECT 1 FROM toc_gap_adjudication r
        WHERE r.evidence #>> '{reattached_from,adjudication_id}' = a.id::text)
), orphan AS (
  SELECT s.*
    FROM standing s
    JOIN instrument oi ON oi.id = s.instrument_id
   WHERE NOT (oi.is_active AND oi.duplicate_of IS NULL)
)
SELECT o.id, o.document_id, o.instrument_id AS old_instrument_id,
       o.toc_entry_id AS old_toc_entry_id, o.printed_label, o.resolution,
       o.source_page, o.evidence, o.rationale, o.decided_by, o.decided_at,
       e.source_block_id AS old_source_block_id,
       e.printed_heading  AS old_printed_heading,
       e.source_page      AS old_entry_source_page,
       e.ordinal          AS old_ordinal,
       -- A replay regenerates provision ids too. Re-resolve the retired one
       -- against the live tree under two independent rules; the pure planner
       -- refuses the row unless this came back non-null.
       CASE WHEN o.resolution = 'found_elsewhere' THEN (
         SELECT a.pid FROM
           (SELECT max(p.id::text) AS pid FROM provision p
              JOIN instrument i ON i.id = p.instrument_id
             WHERE i.document_id = o.document_id AND i.is_active
               AND i.duplicate_of IS NULL AND p.is_active
               AND p.first_block = op.first_block AND p.kind = op.kind
               AND regexp_replace(lower(p.label), '[^a-z0-9]', '', 'g')
                 = regexp_replace(lower(op.label), '[^a-z0-9]', '', 'g')
            HAVING count(*) = 1) a,
           (SELECT max(p.id::text) AS pid FROM provision p
              JOIN instrument i ON i.id = p.instrument_id
             WHERE i.document_id = o.document_id AND i.is_active
               AND i.duplicate_of IS NULL AND p.is_active
               AND p.kind = op.kind
               AND regexp_replace(lower(p.label), '[^a-z0-9]', '', 'g')
                 = regexp_replace(lower(op.label), '[^a-z0-9]', '', 'g')
            HAVING count(*) = 1) b
          WHERE a.pid = b.pid) END AS reresolved_provision_id
  FROM orphan o
  LEFT JOIN instrument_toc_entry e ON e.id = o.toc_entry_id
  LEFT JOIN provision op ON op.id::text = (o.evidence->>'found_provision_id')
 WHERE (%(document)s::bigint IS NULL OR o.document_id = %(document)s::bigint)
 ORDER BY o.document_id, o.printed_label
"""

# Every contents entry of every LIVE instrument of the documents in play --
# not only the gaps, because two of the absence checks are statements about
# the whole contents list.
ENTRIES_SQL = """
SELECT e.id AS toc_entry_id, i.document_id, e.instrument_id, e.ordinal,
       e.printed_label, e.printed_heading, e.source_block_id, e.source_page,
       (e.provision_id IS NOT NULL) AS resolved,
       (g.toc_entry_id IS NOT NULL) AS is_pending_gap,
       a.id         AS standing_adjudication_id,
       a.resolution AS standing_resolution,
       a.decided_by AS standing_decided_by
  FROM instrument_toc_entry e
  JOIN instrument i ON i.id = e.instrument_id
                   AND i.is_active AND i.duplicate_of IS NULL
  LEFT JOIN v_toc_gap_pending g ON g.toc_entry_id = e.id
  -- The standing decision on this LIVE entry, read straight from the table
  -- rather than through v_toc_gap_pending: the view drops an entry a final
  -- decision has closed, and "already decided" is exactly what must be seen.
  LEFT JOIN LATERAL (
    SELECT x.id, x.resolution, x.decided_by
      FROM toc_gap_adjudication x
     WHERE x.instrument_id = e.instrument_id
       AND x.toc_entry_id = e.id
       AND x.printed_label = e.printed_label
       AND NOT EXISTS (SELECT 1 FROM toc_gap_adjudication l
                        WHERE l.supersedes_id = x.id)
     ORDER BY x.decided_at DESC, x.id DESC LIMIT 1) a ON TRUE
 WHERE i.document_id = ANY(%(documents)s)
"""

INSERT_SQL = """
INSERT INTO toc_gap_adjudication
    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
     source_page, evidence, rationale, decided_by)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id
"""

REATTACH_NOTE = (
    "\n\n[RE-ATTACHED after a replay. This reading was recorded against an "
    "instrument and a contents entry the replay has since recreated, so its "
    "key no longer resolved; it is carried onto the live entry matched exactly "
    "on document, source block, printed label and printed heading. The printed "
    "page it describes has not changed. The original row is untouched -- "
    "migration 0043 forbids superseding across a changed toc_entry_id -- and "
    "its id is in evidence.reattached_from.]")


def lock_is_held(cur) -> bool:
    cur.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype='advisory'"
        " AND ((classid::bigint << 32) | objid::bigint) = %s::bigint"
        " AND objsubid = 1)", (SEGMENT_LOCK_KEY,))
    return bool(cur.fetchone()[0])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=".artifacts/toc-reattach/reattach.json")
    ap.add_argument("--document", type=int, help="restrict to one document")
    ap.add_argument("--apply", action="store_true",
                    help="write the re-attached decisions (default: dry run)")
    ap.add_argument("--show", type=int, default=12,
                    help="how many refusals of each kind to print")
    ap.add_argument("--no-recheck-absence", action="store_true",
                    help="carry absent_in_source forward without re-firing "
                         "review_absent_sections checks 4 and 5. Unsafe: those "
                         "are the tree-dependent ones a replay can invalidate.")
    args = ap.parse_args()

    with connect() as conn, conn.cursor() as cur:
        held = lock_is_held(cur)
        cur.execute(ORPHANS_SQL, {"document": args.document})
        cols = [d.name for d in cur.description]
        orphans = [dict(zip(cols, r)) for r in cur.fetchall()]

        documents = sorted({o["document_id"] for o in orphans})
        entries: list[dict] = []
        if documents:
            cur.execute(ENTRIES_SQL, {"documents": documents})
            ecols = [d.name for d in cur.description]
            entries = [dict(zip(ecols, r)) for r in cur.fetchall()]

        result = plan(orphans, entries,
                      recheck_absence=not args.no_recheck_absence)
        by_id = {str(o["id"]): o for o in orphans}

        if held:
            print("NOTE: a segmentation run holds the advisory lock, so these "
                  "counts are a moving target and --apply will refuse.\n")
        print(f"orphaned standing contents-gap decisions : {len(orphans)}"
              f"   in {len(documents)} documents")
        counts: dict[str, int] = {}
        for row in result["rebind"]:
            counts[row["resolution"]] = counts.get(row["resolution"], 0) + 1
        print(f"  re-attachable                          : "
              f"{len(result['rebind'])}")
        for name, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"      {name:<20} {n}")
        moved = sum(1 for r in result["rebind"] if r["ordinal_moved"])
        print(f"      (of which the entry ordinal moved: {moved} -- which is "
              "why ordinal is not in the anchor)")
        print(f"  finished by the replay                 : "
              f"{len(result['finished'])}   (no gap left to re-attach to)")
        print(f"  refused                                : "
              f"{len(result['refused'])}")
        kinds: dict[str, int] = {}
        for row in result["refused"]:
            kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
        for kind, n in sorted(kinds.items(), key=lambda kv: -kv[1]):
            print(f"      {kind:<20} {n}")
            shown = [r for r in result["refused"] if r["kind"] == kind]
            for row in shown[:args.show]:
                print(f"        doc {row['document_id']:<6} "
                      f"label {str(row['printed_label']):<8} "
                      f"{row['resolution']:<17} {row['detail'][:96]}")
            if len(shown) > args.show:
                print(f"        ... and {len(shown) - args.show} more "
                      "(the manifest has every one)")

        # How safely each resolution carries across a replay. The four are not
        # equally portable, and the difference is what their evidence points
        # at: a parser_defect names a CLASS and closes nothing (the gap stays
        # pending either way), so carrying it costs the gate nothing; an
        # absent_in_source names a PAGE and closes the gap, so its two
        # tree-dependent checks are re-fired; a found_elsewhere names a
        # PROVISION, which a replay regenerates, so it is refused unless the
        # pointer re-resolves; an other_instrument names an INSTRUMENT uuid,
        # for which there is no re-resolution rule at all.
        print("\nresolution safety -- what each kind of decision points at:")
        for name, note in (
                ("parser_defect", "a defect CLASS; closes no gap, gate "
                                  "unaffected"),
                ("absent_in_source", "a PAGE; closes the gap -- absence "
                                     "checks 4 and 5 re-fired"),
                ("found_elsewhere", "a PROVISION uuid a replay regenerates "
                                    "-- re-resolved or refused"),
                ("other_instrument", "an INSTRUMENT uuid -- always refused")):
            took = sum(1 for r in result["rebind"] if r["resolution"] == name)
            left = sum(1 for r in result["refused"] if r["resolution"] == name)
            done = sum(1 for r in result["finished"] if r["resolution"] == name)
            print(f"      {name:<17} carried {took:<4} refused {left:<4} "
                  f"finished {done:<4} {note}")

        unanchored = sum(1 for r in result["refused"]
                         if r["kind"] in ("no_match", "ambiguous"))
        print(f"\nanchor ladder -- what relaxing the anchor WOULD recover, of "
              f"the {unanchored} that named no single live entry.")
        print("  Measured, reported, and never acted on: only the first tier "
              "is accepted.")
        for name, _ in TIERS[1:]:
            print(f"      {name:<52} {result['ladder'][name]}")
        print(f"      {'no tier is unique (label gone, or repeated)':<52} "
              f"{result['ladder']['no tier is unique']}")

        manifest = {
            "note": "Contents-gap decisions a replay orphaned, and what this "
                    "tool would do with each. Anchored on (document_id, "
                    "source_block_id, printed_label, printed_heading): "
                    "measured exact and unambiguous where instrument_id, "
                    "toc_entry_id, candidate_id and ordinal are all "
                    "regenerated by a replay.",
            "tool": TOOL,
            "recheck_absence": not args.no_recheck_absence,
            "orphans": len(orphans),
            "documents": len(documents),
            "rebind": result["rebind"],
            "finished": result["finished"],
            "refused": result["refused"],
        }
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(manifest, fh, indent=1, ensure_ascii=False, default=str)
        print(f"\nmanifest: {args.out}")

        if not args.apply:
            print("dry run -- pass --apply to write these decisions")
            return 0
        if held:
            print("\nREFUSING TO WRITE: the segmentation advisory lock is "
                  "held, so a replay is running and the instruments these "
                  "decisions would bind to are being recreated underneath us.\n"
                  "  see it:  pgrep -af nizam.workers.segment\n"
                  "Re-run this tool when it has finished; the measurement "
                  "above will have moved.")
            return 1
        if args.no_recheck_absence:
            print("\nREFUSING TO WRITE: --no-recheck-absence is a measurement "
                  "switch. It disables the two tree-dependent guards that "
                  "separate 'the Act omits this section' from 'this copy of "
                  "the PDF is short', and those are exactly the guards a "
                  "replay can invalidate.")
            return 1

        written, failed = 0, []
        for row in result["rebind"]:
            orphan = by_id[row["adjudication_id"]]
            evidence = reattached_evidence(orphan["evidence"], row)
            cur.execute("SAVEPOINT reattach_row")
            try:
                cur.execute(INSERT_SQL, (
                    row["new_instrument_id"], row["document_id"],
                    row["new_toc_entry_id"], row["printed_label"],
                    row["resolution"], row["source_page"],
                    json.dumps(evidence, default=str),
                    orphan["rationale"] + REATTACH_NOTE,
                    orphan["decided_by"]))
                cur.execute("RELEASE SAVEPOINT reattach_row")
                written += 1
            except Exception as exc:  # a guard refused this row; keep the rest
                cur.execute("ROLLBACK TO SAVEPOINT reattach_row")
                failed.append((row, str(exc).strip().splitlines()[0]))
        conn.commit()
        print(f"\nre-attached {written} decisions")
        if failed:
            print(f"{len(failed)} refused by a database guard -- these are the "
                  "guards doing their job, not a bug:")
            for row, why in failed[:args.show]:
                print(f"    doc {row['document_id']:<6} "
                      f"label {str(row['printed_label']):<8} {why[:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
