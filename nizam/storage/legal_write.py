"""Persist a segmented instrument — Document 03 §2, the legal core.

One instrument lands in one transaction: the instrument row, its provision tree,
and a current version for every provision. A half-written tree is worse than
none, because a citation would resolve to a provision whose parent is missing.

Re-segmenting an observation appends a new instrument revision and retires the
old active revision.  Its former provision tree and block assignments stay
queryable as evidence; a parser improvement never deletes source-derived data.
"""
from __future__ import annotations

import json
import re

from nizam.shared.corpus_types import SegmentedInstrument
from nizam.storage.db import connect


def documents_needing_segmentation(limit: int | None = None,
                                   source_id: str | None = None,
                                   lane: str | None = None,
                                   redo: bool = False,
                                   retry_errors: bool = False,
                                   include_review: bool = False) -> list[tuple]:
    """Official observations with an active extraction awaiting segmentation.

    One byte-identical PDF may have several official observations.  They remain
    separate expressions until reviewed legal identity resolution; sharing the
    document/text blocks saves storage without discarding portal provenance.
    """
    where = ["1=1"]
    params: list = []
    if source_id:
        where.append("o.source_id = %s")
        params.append(source_id)
    if lane:
        where.append("d.lane = %s")
        params.append(lane)
    if retry_errors:
        where.append("(SELECT r.outcome FROM segmentation_run r "
                     "WHERE r.source_observation_id=o.id "
                     "ORDER BY r.run_at DESC,r.id DESC LIMIT 1) = 'error'")
    if not redo:
        # A current unstructured assignment is a completed, reviewable result,
        # not an endlessly pending segmentation.  It deliberately has no
        # instrument_id, so checking only instrument would reprocess it forever.
        where.append("NOT EXISTS (SELECT 1 FROM block_assignment_set a "
                     "WHERE a.source_observation_id=o.id AND a.document_id=d.id "
                     "AND a.is_active)")
    quality_join = ("" if include_review else
                    "JOIN v_document_quality_status q ON q.document_id=d.id "
                    "AND q.overall_outcome='passed'")
    q = f"""
        SELECT d.id, d.sha256, o.id, o.source_id,
               o.source_metadata->>'title',
               coalesce(o.source_metadata->>'year',o.source_metadata->>'year_or_dept'),
               coalesce(o.source_metadata->>'type',o.source_metadata->>'doc_type'),
               o.canonical_url
          FROM source_observation o
          JOIN document d ON d.sha256=o.sha256 AND d.is_active
          {quality_join}
         WHERE {' AND '.join(where)}
           AND o.outcome='landed'
         ORDER BY d.page_count DESC, o.id
    """
    if limit:
        q += " LIMIT %s"
        params.append(limit)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(q, params)
        return cur.fetchall()


def observed_on(source_observation_id: int) -> str:
    """The date this source was actually fetched from the portal.

    provision_version.validity opens here. Using the wall clock instead was a
    real defect: Python running in WSL (PKT, UTC+5) produced tomorrow's date
    relative to Postgres running in UTC, so every one of 448,684 versions opened
    in the future and `validity @> current_date` matched nothing. INV-5's central
    query returned an empty corpus.

    The fetch date is also the honest answer, not merely a safe one -- it is the
    date on which we can attest the portal published this text.
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT fetched_at::date FROM source_observation
                        WHERE id=%s AND fetched_at IS NOT NULL""",
                    (source_observation_id,))
        row = cur.fetchone()
        if row and row[0]:
            return row[0].isoformat()
    # No observation carried a timestamp: fall back to the database's own today,
    # never the client's, so the two can never disagree about the date again.
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT current_date")
        return cur.fetchone()[0].isoformat()


def blocks_for(document_id: int) -> list[dict]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT t.id, t.text, t.page_no, t.y0, p.height,t.x0,t.x1
              FROM text_block t
              JOIN page p ON p.document_id = t.document_id AND p.page_no = t.page_no
             WHERE t.document_id = %s
             ORDER BY t.reading_order""", (document_id,))
        return [{"id": r[0], "text": r[1], "page_no": r[2],
                 "y0": float(r[3]), "page_height": float(r[4] or 792),
                 "x0": float(r[5]), "x1": float(r[6])}
                for r in cur.fetchall()]


def segmentation_patches_for(source_observation_id: int) -> list[dict]:
    """Approved, rebuild-stable parser-input corrections for one observation."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id::text,page_no,match_text,before_text,after_text,evidence
              FROM segmentation_curation_patch
             WHERE source_observation_id=%s
               AND review_state IN ('source_verified','human_verified')
               AND retired_at IS NULL
             ORDER BY page_no,created_at,id
        """, (source_observation_id,))
        keys = ("id", "page_no", "match_text", "before_text", "after_text",
                "evidence")
        return [dict(zip(keys, row)) for row in cur.fetchall()]


def validate_owner_cited_source_gaps(document_id: int, source_observation_id: int,
                                    overrides: dict | None) -> None:
    """A partial opener can skip only rows in its current source-gap record.

    Fail closed on a stale/superseded record, another source, or an unbound
    opener.  This is a read-only check, shared by curation intake and replay.
    Absence of this optional data leaves every existing build unchanged.
    """
    specs = [v for v in (overrides or {}).get("source_owner_cited_labels", [])
             if "missing_before" in v or "source_incompleteness_id" in v]
    if not specs:
        return
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id,resolution,evidence FROM v_source_incompleteness_latest
                        WHERE document_id=%s AND source_observation_id=%s""",
                    (document_id, source_observation_id))
        record = cur.fetchone()
    for spec in specs:
        binding = {key: spec.get(key) for key in
                   ("cited_label", "source_block_id", "source_prefix", "missing_before")}
        if (not record or record[0] != spec.get("source_incompleteness_id")
                or record[1] != "no_complete_copy_acquired"
                or binding not in record[2].get("parser_partial_openers", [])):
            raise ValueError("partial owner-cited opener lacks its current, exactly bound source-incompleteness record")


def segmentation_profile_for(source_observation_id: int) -> str:
    """The segmentation profile pinned to one observation; 'default' when none.

    Read by every build of the observation, so a document released under a
    profile is replayed under the same profile (docs/SEGMENTATION-PROFILES.md).
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT profile FROM v_segmentation_profile_latest
             WHERE source_observation_id=%s
        """, (source_observation_id,))
        row = cur.fetchone()
        return row[0] if row else "default"


def toc_dispositions_for(source_observation_id: int,
                         expression_ordinal: int = 0) -> list[dict]:
    """Rendered-source disposition assertions that survive tree revisions."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id,source_observation_id,expression_ordinal,toc_entry_ordinal,
                   printed_label,printed_heading,disposition,source_block_id,
                   source_page,amending_instrument_id::text,
                   amending_instrument_citation,evidence,reviewed_by,reviewed_at
              FROM v_toc_disposition_assertion_latest
             WHERE source_observation_id=%s AND expression_ordinal=%s
             ORDER BY toc_entry_ordinal
        """, (source_observation_id, expression_ordinal))
        keys = ("id", "source_observation_id", "expression_ordinal",
                "toc_entry_ordinal", "printed_label", "printed_heading",
                "disposition", "source_block_id", "source_page",
                "amending_instrument_id", "amending_instrument_citation",
                "evidence", "reviewed_by", "reviewed_at")
        return [dict(zip(keys, row)) for row in cur.fetchall()]


# The predicate that decides which reviewed judgements may steer the parser.
# It is a module constant so a test can execute this exact text against a
# machine decision it inserts and rolls back, rather than asserting on the
# shape of the source. Every machine decision in the corpus today happens to be
# `accept_non_citable`, so the resolution filter alone would hide a broken
# basis filter; the two must be provable apart.
_STRUCTURAL_RESOLUTIONS_SQL = """
    WITH reviewed AS (
        SELECT c.source_block_id,
               c.printed_label,
               lower(regexp_replace(c.printed_label,'\\s+','','g')) AS label_key,
               a.resolution, a.review_basis, a.id, a.decided_at, a.decided_by,
               a.evidence
          FROM v_structural_adjudication_latest a
          JOIN segmentation_structural_candidate c ON c.id = a.candidate_id
         WHERE c.document_id = %s
           AND a.review_basis IN ('source_verified','human_verified')
    ), settled AS (
        SELECT source_block_id, label_key
          FROM reviewed
         GROUP BY 1,2
        HAVING count(DISTINCT resolution) = 1
    ), latest AS (
        SELECT DISTINCT ON (source_block_id, label_key) *
          FROM reviewed
         ORDER BY source_block_id, label_key, decided_at DESC, id DESC
    )
    SELECT l.source_block_id, l.printed_label, l.label_key, l.resolution,
           l.review_basis, l.id::text, l.decided_at, l.decided_by,l.evidence
      FROM latest l
      JOIN settled s
        ON s.source_block_id = l.source_block_id
       AND s.label_key = l.label_key
     WHERE l.resolution IN ('restore_citable','reject_candidate')
        OR (l.resolution = 'reparent'
            AND jsonb_typeof(l.evidence #>
                '{structural_overrides,source_reparent_blocks}') = 'array')
     ORDER BY l.source_block_id, l.label_key
"""

_STRUCTURAL_RESOLUTION_KEYS = (
    "source_block_id", "printed_label", "label_key", "resolution",
    "review_basis", "adjudication_id", "decided_at", "decided_by", "evidence")


def structural_resolutions_for(document_id: int) -> list[dict]:
    """Source-reviewed S7 decisions that survive tree revisions.

    The third of the three kinds of reviewed judgement the segmenter consults.
    `segmentation_patches_for` corrects the parser's INPUT and
    `toc_dispositions_for` asserts what a contents entry means; this one
    answers the question the parser asks when two siblings print one label.

    KEYED ON (document, source block, printed label), never on candidate id.
    A candidate id is regenerated by every replay -- measured: all 838
    `accept_non_citable` decisions in 63 replayed documents were orphaned in
    one run -- while a block id survives re-segmentation. That is the law
    `tools/reattach_orphaned_adjudications.py` is built on and the reason
    migration 0052 took an ordinal out of a disposition's identity. One block
    can open several colliding units (document 3757 block 468186 opens three),
    so the printed label is part of the key; whitespace and case are stripped
    from it because they are typography, and nothing else is, because ``12.1``
    and ``121`` are different units.

    ONLY REVIEWED DECISIONS STEER THE PARSER. `machine_evidenced` rows are
    excluded: a program approving its own output is not a review, and 11,212
    of the 14,308 decisions in this corpus are machine. Only the two
    resolutions the segmenter can carry out are returned -- `restore_citable`,
    which says the parser kept the wrong print; `reparent`, when its evidence
    names exact source and parent blocks; and `reject_candidate`, which says
    the collision is not genuine. `split_instrument` remains a document-level
    operation handled by the multi-expression materializer.

    A KEY TWO READINGS DISAGREE ABOUT IS NOT RETURNED. Twelve keys across five
    documents carry two different source-verified resolutions recorded against
    different tree revisions. Later is not obviously righter when both readings
    describe the same unchanged page, so the parser does not choose; the row is
    withheld and stays a reviewer's question.
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(_STRUCTURAL_RESOLUTIONS_SQL, (document_id,))
        return [dict(zip(_STRUCTURAL_RESOLUTION_KEYS, row))
                for row in cur.fetchall()]


def _subtree_revision_signature(cur, root_id) -> list:
    """Exact legal-node/text/source-footprint identity for an S7 decision.

    A matching printed label is not enough to carry a non-citable judgement
    across a replay. Both sides of the collision must have the same complete
    provision subtrees and source-block ownership as the reviewed revision.
    Sibling ordinal is intentionally excluded: inserting an unrelated earlier
    provision changes its number without changing this candidate's law.
    """
    cur.execute("""
        SELECT coalesce(jsonb_agg(jsonb_build_array(
                   p.path::text,p.kind::text,p.label,p.heading,p.marginal_note,
                   p.first_page,p.last_page,p.first_block,
                   v.text_en,v.operation,
                   (SELECT coalesce(jsonb_agg(jsonb_build_array(
                               pb.block_id,pb.role::text,pb.chars)
                               ORDER BY pb.block_id),'[]'::jsonb)
                      FROM provision_block pb WHERE pb.provision_id=p.id))
                   ORDER BY p.path::text),'[]'::jsonb)
          FROM provision root
          JOIN provision p ON p.instrument_id=root.instrument_id
                          AND p.path <@ root.path
          LEFT JOIN LATERAL (
              SELECT text_en,operation FROM provision_version
               WHERE provision_id=p.id ORDER BY id DESC LIMIT 1
          ) v ON true
         WHERE root.id=%s
    """, (root_id,))
    return cur.fetchone()[0]


def _matching_prior_acceptance(cur, previous_id, new_candidate_id) -> dict | None:
    """Carry only a uniquely identical accepted S7 judgement, without upgrade."""
    cur.execute("""
        SELECT old.id,a.id,a.resolution,a.review_basis,a.rationale,a.evidence,
               old.candidate_provision_id,old.canonical_provision_id,
               new.candidate_provision_id,new.canonical_provision_id
          FROM segmentation_structural_candidate old
          JOIN v_structural_adjudication_latest a ON a.candidate_id=old.id
          JOIN segmentation_structural_candidate new ON new.id=%s
          JOIN provision oldp ON oldp.id=old.candidate_provision_id
          JOIN provision oldk ON oldk.id=old.canonical_provision_id
          JOIN provision newp ON newp.id=new.candidate_provision_id
          JOIN provision newk ON newk.id=new.canonical_provision_id
         WHERE old.instrument_id=%s
           AND a.resolution='accept_non_citable'
           AND old.source_observation_id=new.source_observation_id
           AND old.source_block_id=new.source_block_id
           AND old.source_page=new.source_page
           AND old.canonical_source_block_id=new.canonical_source_block_id
           AND old.canonical_source_page=new.canonical_source_page
           AND old.printed_label=new.printed_label
           AND old.original_kind=new.original_kind
           AND old.decision_kind=new.decision_kind
           AND old.proposed_resolution=new.proposed_resolution
           AND old.evidence=new.evidence
           -- compared below the three identity labels, which a reviewed identity correction rewrites
           AND nlevel(oldp.path) > 3 AND nlevel(newp.path) > 3 AND nlevel(oldk.path) > 3 AND nlevel(newk.path) > 3
           AND regexp_replace(subpath(oldp.path,3)::text,'_n[0-9]+_[0-9]+','','g')
             = regexp_replace(subpath(newp.path,3)::text,'_n[0-9]+_[0-9]+','','g')
           AND regexp_replace(subpath(oldk.path,3)::text,'_n[0-9]+_[0-9]+','','g')
             = regexp_replace(subpath(newk.path,3)::text,'_n[0-9]+_[0-9]+','','g')
    """, (new_candidate_id, previous_id))
    matches = cur.fetchall()
    if len(matches) != 1:
        return None
    row = matches[0]
    exact_candidate = (_subtree_revision_signature(cur, row[6])
                       == _subtree_revision_signature(cur, row[8]))
    exact_canonical = (_subtree_revision_signature(cur, row[7])
                       == _subtree_revision_signature(cur, row[9]))
    carried = {"candidate_id": str(row[0]), "id": str(row[1]),
               "resolution": row[2], "review_basis": row[3],
               "rationale": row[4], "evidence": row[5]}
    if exact_candidate and exact_canonical:
        return carried
    # Rule `equivalent_candidate_subtree_carry` (stage 3, agent DC): an owner-approved recut INSIDE either subtree
    # does not touch what the accepted judgement rests on -- see _equivalent_carry.
    equivalence = _equivalent_carry(cur, row[6], row[7], row[8], row[9],
                                    exact_candidate, exact_canonical)
    if equivalence is None:
        return None
    carried["equivalence"] = equivalence
    return carried


# A repeated-label collision suffix ('_n92_1') numbers a node by its position among its siblings, so inserting or
# removing an unrelated sibling renumbers it (doc 4451 ch_XVIII.cl_194_n92_1 -> cl_194_n93_1).  It is not identity.
_POSITIONAL_SUFFIX = r"_n[0-9]+_[0-9]+"
_LAW_ROLES = ("body", "heading", "schedule_row", "preamble")

_EQUIVALENCE_SQL = """
SELECT regexp_replace(root.path::text, %(suffix)s, '', 'g'), root.kind::text, root.label, root.heading,
       root.marginal_note, root.first_page, root.first_block,
       (SELECT coalesce(jsonb_agg(jsonb_build_array(pb.block_id, pb.role::text, pb.chars)
                                  ORDER BY pb.block_id, pb.role::text, pb.chars), '[]'::jsonb)
          FROM provision p JOIN provision_block pb ON pb.provision_id=p.id
         WHERE p.instrument_id=root.instrument_id AND p.path <@ root.path),
       (SELECT string_agg(concat_ws(' ', p.label, p.heading, p.marginal_note, v.text_en), ' '
                          ORDER BY p.ordinal)
          FROM provision p
          LEFT JOIN LATERAL (SELECT text_en FROM provision_version
                              WHERE provision_id=p.id ORDER BY id DESC LIMIT 1) v ON true
         WHERE p.instrument_id=root.instrument_id AND p.path <@ root.path),
       (SELECT coalesce(sum(pb.chars), 0)
          FROM provision p JOIN provision_block pb ON pb.provision_id=p.id
         WHERE p.instrument_id=root.instrument_id AND p.path <@ root.path),
       root.instrument_id::text, root.path::text
  FROM provision root WHERE root.id=%(root)s
"""
_WORDS = re.compile(r"[a-z]+")


def _subtree_equivalence_signature(cur, root_id) -> tuple:
    """(root identity, source-block footprint, letter-word sequence, chars, instrument id, path) of a subtree.

    The root is the unit an S7 decision names (its path without positional collision suffixes); the footprint is
    every (block, role, chars) row the subtree owns; the words are the letters of its labels, headings, notes and
    texts in document order.  A cut that moves '(2)' or 'Provided' from a text into a label of the same subtree
    leaves all three unchanged."""
    cur.execute(_EQUIVALENCE_SQL, {"suffix": _POSITIONAL_SUFFIX, "root": root_id})
    r = cur.fetchone()
    return (tuple(r[:7]), [tuple(x) for x in r[7]], _WORDS.findall((r[8] or "").lower()), int(r[9]),
            r[10], r[11])


def _blocks_left_the_law(cur, instrument_id, block_ids: list[int]) -> dict | None:
    """The printed words of blocks the NEW tree assigns to no provision under a law role, or None when any
    of them is still law (a block that moved to another provision is not 'left')."""
    cur.execute("""
        SELECT b.id, b.text,
               EXISTS (SELECT 1 FROM provision_block pb
                         JOIN block_assignment_set s ON s.id=pb.assignment_set_id
                        WHERE s.instrument_id=%s AND pb.block_id=b.id
                          AND pb.provision_id IS NOT NULL AND pb.role::text = ANY(%s))
          FROM text_block b WHERE b.id = ANY(%s)""", (instrument_id, list(_LAW_ROLES), block_ids))
    rows = cur.fetchall()
    if len(rows) != len(set(block_ids)) or any(still_law for _id, _text, still_law in rows):
        return None
    return {int(block_id): _WORDS.findall((text or "").lower()) for block_id, text, _law in rows}


def _candidate_equivalence(cur, old, new) -> dict | None:
    """How the candidate subtree is the same unit holding the same law, or None.

    Equivalent: same root, same footprint, same words.  Or every difference is source blocks that LEFT the law
    (running titles, footnotes, apparatus -- assigned no law role in the new tree): the rest of the footprint is
    identical, nothing was added, and the words lost are exactly those blocks' printed words."""
    if old[0] != new[0]:
        return None
    if old[1:3] == new[1:3]:
        return {"candidate": "equivalent"}
    from collections import Counter
    fo, fn = Counter(old[1]), Counter(new[1])
    if fn - fo:
        return None
    dropped = sorted({row[0] for row in (fo - fn).elements()})
    if any(row[0] in dropped for row in fn):
        return None
    left = _blocks_left_the_law(cur, new[4], dropped)
    if left is None:
        return None
    wo, wn = Counter(old[2]), Counter(new[2])
    if wn - wo or wo - wn != Counter(word for words in left.values() for word in words):
        return None
    remaining = iter(old[2])
    if not all(word in remaining for word in new[2]):
        return None
    return {"candidate": "equivalent_less_non_law_blocks", "blocks_left_the_law": dropped}


def _equivalent_carry(cur, old_candidate, old_canonical, new_candidate, new_canonical,
                      exact_candidate: bool, exact_canonical: bool) -> dict | None:
    """Evidence for carrying an accepted S7 judgement across a recut subtree, or None.

    CANDIDATE: identical, or equivalent (_candidate_equivalence) -- the demoted unit holds exactly the law it held
    when judged.  CANONICAL: identical, or the same root and not a stub against the candidate on the new sizes
    (tools/adjudicate_citation_preserving.py's two guards) -- the label is still held by the same citable unit
    and the inverted shape the guards exist for cannot have appeared."""
    oc, nc = (_subtree_equivalence_signature(cur, old_candidate),
              _subtree_equivalence_signature(cur, new_candidate))
    ok, nk = (_subtree_equivalence_signature(cur, old_canonical),
              _subtree_equivalence_signature(cur, new_canonical))
    candidate = {"candidate": "exact"} if exact_candidate else _candidate_equivalence(cur, oc, nc)
    if candidate is None:
        return None
    if ok[0] != nk[0]:
        return None
    candidate_chars, canonical_chars = nc[3], nk[3]
    if not exact_canonical and (
            (candidate_chars >= 500 and canonical_chars < candidate_chars * 0.5)
            or (candidate_chars >= 120 and canonical_chars * 3 < candidate_chars)):
        return None
    evidence = {"rule": "equivalent_candidate_subtree_carry", **candidate,
                "canonical": "exact" if exact_canonical else "same_root_not_stub",
                "candidate_chars": candidate_chars, "canonical_chars": canonical_chars,
                "canonical_chars_before": ok[3]}
    if (oc[5], ok[5]) != (nc[5], nk[5]):
        evidence["paths_before"] = [oc[5], ok[5]]
        evidence["paths_after"] = [nc[5], nk[5]]
    return evidence


TOC_GAP_CARRY_TOOL = "nizam.storage.legal_write.save/toc-gap-carry/1"
TOC_GAP_CARRY_NOTE = (
    "\n\n[CARRIED BY REPLAY. The replay recreated this contents entry exactly -- same printed label, printed "
    "heading, entry kind and page, still unresolved, and the same target -- each side matched exactly once, so "
    "this page reading is carried onto the new entry. The original row is untouched; its id and the old and new "
    "entry ids are in evidence.carried_by_replay.]")

# A standing contents-gap decision of the retired tree and the one new entry that is exactly the same printed
# row. The identity is the printed row and its (absent) link, never the source anchor (block, offset), which a
# parser fix may legitimately move (fix K, 11 Oct). Both sides must be unique under that identity.
_TOC_GAP_CARRY_SQL = """
SELECT a.id, a.printed_label, a.resolution, a.source_page, a.evidence, a.rationale, a.decided_by,
       a.toc_entry_id AS old_entry_id, m.ids AS new_entry_ids, mo.n AS old_twins
  FROM v_toc_gap_adjudication_latest a
  JOIN instrument_toc_entry old ON old.id=a.toc_entry_id AND old.instrument_id=a.instrument_id
                               AND old.provision_id IS NULL AND old.printed_label=a.printed_label
  CROSS JOIN LATERAL (
        SELECT coalesce(array_agg(n.id ORDER BY n.id), '{}') AS ids FROM instrument_toc_entry n
         WHERE n.instrument_id=%(new)s AND n.provision_id IS NULL
           AND n.printed_label=old.printed_label
           AND n.printed_heading IS NOT DISTINCT FROM old.printed_heading
           AND n.entry_kind=old.entry_kind
           AND n.source_page IS NOT DISTINCT FROM old.source_page) m
  CROSS JOIN LATERAL (
        SELECT count(*) AS n FROM instrument_toc_entry o
         WHERE o.instrument_id=%(old)s AND o.provision_id IS NULL
           AND o.printed_label=old.printed_label
           AND o.printed_heading IS NOT DISTINCT FROM old.printed_heading
           AND o.entry_kind=old.entry_kind
           AND o.source_page IS NOT DISTINCT FROM old.source_page) mo
 WHERE a.instrument_id=%(old)s AND a.toc_entry_id IS NOT NULL
 ORDER BY a.toc_entry_id
"""


def _carried_gap_target(cur, row: dict, previous_id, instrument_id,
                        successors: dict | None = None) -> tuple[bool, dict]:
    """Whether a decision's target is unchanged by the replay; the evidence fields a carry rewrites.

    `successors` ({retired instrument id: its successor}) names the sibling expressions a multi-expression replay
    replaces in the same transaction: an `other_instrument` decision naming one follows it to the expression rebuilt
    at the same ordinal (doc 3782 E0 contents rows 24-25 name E1; 20 Oct 2026)."""
    evidence = row["evidence"] or {}
    resolution = row["resolution"]
    if resolution == "other_instrument":
        sibling = (successors or {}).get(str(evidence.get("other_instrument_id")))
        if sibling is not None:
            if sibling in (str(previous_id), str(instrument_id)):
                return False, {}
            return True, {"other_instrument_id_before_replay": evidence.get("other_instrument_id"),
                          "other_instrument_id": sibling}
        # The named instrument must be a live one other than the tree being replaced.
        cur.execute("""SELECT EXISTS(SELECT 1 FROM instrument WHERE id::text=%s AND is_active
                                      AND id<>%s AND id<>%s)""",
                    (str(evidence.get("other_instrument_id")), previous_id, instrument_id))
        return bool(cur.fetchone()[0]), {}
    if resolution == "found_elsewhere":
        # The retired provision's exact counterpart: same path, kind, label and first block, exactly once. The path
        # is compared below its three identity labels (jurisdiction.kind.year_number_observation), which a reviewed
        # identity correction rewrites without moving any provision (doc 2479, 20 Oct 2026).
        cur.execute("""
            SELECT n.id::text FROM provision o
              JOIN provision n ON n.instrument_id=%s AND n.kind=o.kind
                              AND nlevel(o.path) > 3 AND nlevel(n.path) = nlevel(o.path)
                              AND subpath(n.path, 3) = subpath(o.path, 3)
                              AND n.label IS NOT DISTINCT FROM o.label
                              AND n.first_block IS NOT DISTINCT FROM o.first_block
             WHERE o.id::text=%s AND o.instrument_id=%s""",
                    (instrument_id, str(evidence.get("found_provision_id")), previous_id))
        hits = cur.fetchall()
        if len(hits) != 1:
            return False, {}
        return True, {"found_provision_id_before_replay": evidence.get("found_provision_id"),
                      "found_provision_id": hits[0][0]}
    if resolution == "source_incomplete":
        # The observation-keyed 0054 record must still stand (the insert trigger checks it again).
        cur.execute("""SELECT EXISTS(SELECT 1 FROM v_source_incompleteness_latest l
                                      WHERE l.id::text=%s AND l.resolution='no_complete_copy_acquired')""",
                    (str(evidence.get("source_incompleteness_id")),))
        return bool(cur.fetchone()[0]), {}
    return True, {}


def _carry_toc_gap_decisions(cur, previous_id, instrument_id, document_id,
                             successors: dict | None = None) -> dict:
    """Carry each standing contents-gap decision of the replaced tree onto its exactly identical new entry.

    Lead decision 11 Oct (doc 2205; mirrors the S7 carry above): same printed label, printed heading, entry
    kind and page, unresolved on both sides, the same target, and matched exactly once on each side.  Append
    only: a new row on the new entry, the old row untouched.  Anything inexact, ambiguous, or refused by a
    database guard carries nothing, so the release gate judges the new tree exactly as before."""
    cur.execute(_TOC_GAP_CARRY_SQL, {"old": previous_id, "new": instrument_id})
    names = [d.name for d in cur.description]
    rows = [dict(zip(names, r)) for r in cur.fetchall()]
    report = {"carried": [], "refused": []}
    for row in rows:
        if len(row["new_entry_ids"]) != 1 or row["old_twins"] != 1:
            report["refused"].append((row["printed_label"], "not exactly one identical entry"))
            continue
        same_target, rewrites = _carried_gap_target(cur, row, previous_id, instrument_id, successors)
        if not same_target:
            report["refused"].append((row["printed_label"], "target changed"))
            continue
        new_entry = row["new_entry_ids"][0]
        evidence = dict(row["evidence"] or {}, **rewrites)
        evidence["carried_by_replay"] = {
            "adjudication_id": str(row["id"]),
            "instrument_id": str(previous_id),
            "toc_entry_id": row["old_entry_id"],
            "new_instrument_id": str(instrument_id),
            "new_toc_entry_id": new_entry,
            "identity": "printed_label, printed_heading, entry_kind, source_page, unresolved, same target; "
                        "unique in the old and the new tree",
            "tool": TOC_GAP_CARRY_TOOL,
        }
        cur.execute("SAVEPOINT toc_gap_carry")
        try:
            cur.execute("""
                INSERT INTO toc_gap_adjudication
                    (instrument_id, document_id, toc_entry_id, printed_label, resolution,
                     source_page, evidence, rationale, decided_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (instrument_id, document_id, new_entry, row["printed_label"], row["resolution"],
                         row["source_page"], json.dumps(evidence, ensure_ascii=False, default=str),
                         row["rationale"] + TOC_GAP_CARRY_NOTE, row["decided_by"]))
            cur.execute("RELEASE SAVEPOINT toc_gap_carry")
            report["carried"].append(row["printed_label"])
        except Exception as exc:  # a database guard refused it: carry nothing, the gate decides
            cur.execute("ROLLBACK TO SAVEPOINT toc_gap_carry")
            report["refused"].append((row["printed_label"], str(exc).strip().splitlines()[0]))
    return report


# --- Released-tree change guard (owner decision 11 Oct, stage 0) -------------------------------------------------
# 451 released default-profile expressions were found to rebuild differently from what is stored (agent CT, 11 Oct):
# ungated global parser fixes had changed them silently, and nothing compared a replay with the stored tree. A
# released instrument's tree is now replaced only when the rebuild is identical, or when the run carries an
# explicit approval (worker / materializer --approve-release-change "<reason; owner approval ref>"). The identity
# is the one tools/measure_segmenter_against_stored.py compares, plus the contents anchors: a change of anchor
# alone (the 2205/4330 corrections) is a change.

_RELEASED_TREE_SQL = """
SELECT p.path::text, coalesce(parent.path::text,''), p.kind::text, p.label,
       p.ordinal, p.first_page, p.last_page, p.first_block,
       coalesce(v.text_en,v.text_ur,''), coalesce(p.heading,'')
  FROM provision p
  LEFT JOIN provision parent ON parent.id=p.parent_id
  LEFT JOIN LATERAL (
        SELECT text_en,text_ur FROM provision_version pv
         WHERE pv.provision_id=p.id
         ORDER BY lower(pv.validity) DESC,pv.created_at DESC LIMIT 1) v ON true
 WHERE p.instrument_id=%s"""

_RELEASED_TOC_SQL = """
SELECT e.ordinal, e.printed_label, coalesce(e.printed_heading,''), e.entry_kind,
       p.path::text, e.match_method, e.source_block_id, e.source_char_offset, e.source_page
  FROM instrument_toc_entry e LEFT JOIN provision p ON p.id=e.provision_id
 WHERE e.instrument_id=%s"""

TREE_FIELDS = ("path", "parent", "kind", "label", "ordinal", "first_page", "last_page",
               "first_block", "text", "heading")


def _built_identity(inst: SegmentedInstrument) -> tuple[list, list]:
    by_key = {r["key"]: r for r in inst.provisions}
    tree = []
    for r in inst.provisions:
        parent = by_key.get(r["parent_key"])
        tree.append((r["path"], parent["path"] if parent else "", r["kind"], r["label"],
                     r["ordinal"], r["first_page"], r["last_page"], r["first_block"],
                     r["text"] or "", r["heading"] or ""))
    path = {r["key"]: r["path"] for r in inst.provisions}
    toc = []
    for e in inst.toc_entries:
        target = path.get(e["provision_key"]) if e.get("provision_key") is not None else None
        toc.append((e["ordinal"], e["label"], e["heading"] or "", e["kind"], target,
                    e["method"] if target is not None else "unmatched",
                    e.get("source_block_id"), e.get("source_char_offset"), e.get("source_page")))
    return sorted(tree, key=lambda r: (r[4], r[0])), sorted(toc, key=lambda t: t[0])


def released_tree_change(cur, previous_id, inst: SegmentedInstrument) -> dict | None:
    """None when `inst` rebuilds the stored tree of `previous_id` exactly; else a summary of what differs."""
    cur.execute(_RELEASED_TREE_SQL, (previous_id,))
    stored_tree = sorted((tuple(r) for r in cur.fetchall()), key=lambda r: (r[4], r[0]))
    cur.execute(_RELEASED_TOC_SQL, (previous_id,))
    stored_toc = sorted((tuple(r) for r in cur.fetchall()), key=lambda t: t[0])
    built_tree, built_toc = _built_identity(inst)
    if stored_tree == built_tree and stored_toc == built_toc:
        return None
    old = {r[0]: r for r in stored_tree}
    new = {r[0]: r for r in built_tree}
    changed = [{"path": p, "fields": [f for f, x, y in zip(TREE_FIELDS, old[p], new[p]) if x != y]}
               for p in sorted(old.keys() & new.keys()) if old[p] != new[p]]
    # an ordinal that only follows from a node added or removed elsewhere is not listed (it still counts)
    changed = [c for c in changed if c["fields"] != ["ordinal"]]
    so, sn = set(stored_toc), set(built_toc)
    return {
        "previous_instrument_id": str(previous_id),
        "provisions": [len(stored_tree), len(built_tree)],
        "paths_removed": sorted(old.keys() - new.keys())[:20],
        "paths_added": sorted(new.keys() - old.keys())[:20],
        "provisions_changed": len(changed),
        "changed": changed[:20],
        "toc_entries": [len(stored_toc), len(built_toc)],
        "toc_changed": [{"ordinal": t[0], "label": t[1], "stored": list(t[4:]),
                         "built": next((list(b[4:]) for b in built_toc if b[0] == t[0]), None)}
                        for t in stored_toc if t not in sn][:20],
        "toc_added": [list(t[:2]) for t in built_toc if t not in so
                      and not any(s[0] == t[0] for s in stored_toc)][:20],
    }


def _carry_prior_s7_acceptance(cur, previous_id, new_candidate_id, carried: dict | None = None) -> bool:
    """Carry one accepted S7 judgement of the replaced tree onto the replay's matching candidate (append-only,
    no upgrade). Shared by save() and save_many(): before 12 Oct 2026 the multi-expression path carried nothing,
    so a released expression with accepted S7 decisions dropped out of the release on every re-materialisation
    (doc 4497 e12, e25). Returns whether a judgement was carried."""
    exact_whole_tree = carried is not None
    if carried is None and previous_id is not None:
        carried = _matching_prior_acceptance(
            cur, previous_id, new_candidate_id)
    if carried is not None:
        carried_evidence = dict(carried["evidence"] or {})
        carried_evidence["carried_from_candidate_id"] = carried["candidate_id"]
        carried_evidence["carried_from_adjudication_id"] = carried["id"]
        equivalence = carried.get("equivalence")
        if exact_whole_tree:
            carry_key, carry_method, carry_by = (
                "exact_tree_revision", "carried_by_exact_tree_revision/1",
                "nizam.exact_tree_revision/1")
        elif equivalence is None:
            carry_key, carry_method, carry_by = (
                "exact_candidate_subtree_replay", "carried_by_exact_candidate_subtree/1",
                "nizam.exact_candidate_subtree/1")
        else:
            # Rule `equivalent_candidate_subtree_carry`: the same judgement on an equivalent recut.
            carry_key, carry_method, carry_by = (
                "equivalent_candidate_subtree_replay",
                "carried_by_equivalent_candidate_subtree/1",
                "nizam.equivalent_candidate_subtree/1")
        carried_evidence[carry_key] = equivalence if equivalence is not None else True
        cur.execute("""
            INSERT INTO segmentation_structural_adjudication
                (candidate_id,resolution,review_basis,method,rationale,
                 evidence,decided_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            new_candidate_id,carried["resolution"],carried["review_basis"],
            carry_method,
            carried["rationale"],
            json.dumps(carried_evidence,ensure_ascii=False),
            carry_by,
        ))
    return carried is not None


def _release_gate_failure(cur, instrument_id, document_id) -> str | None:
    """None when the instrument passes every release predicate inside the open transaction, else the reason
    ('TOC=.., S7=.., boundary=.., quality=..'). Used by save() and save_many() for previously released expressions."""
    cur.execute("""
        SELECT EXISTS(
            SELECT 1 FROM instrument i
            JOIN v_document_quality_status q ON q.document_id=i.document_id
           WHERE i.id=%s AND i.is_active AND i.duplicate_of IS NULL
             AND q.overall_outcome='passed'
             AND NOT EXISTS (SELECT 1 FROM v_toc_gap_pending t WHERE t.instrument_id=i.id)
             AND NOT EXISTS (SELECT 1 FROM v_structural_adjudication_pending s WHERE s.instrument_id=i.id)
             AND NOT EXISTS (SELECT 1 FROM v_boundary_adjudication_pending b WHERE b.instrument_id=i.id))
    """, (instrument_id,))
    if cur.fetchone()[0]:
        return None
    cur.execute("""
        SELECT (SELECT count(*) FROM v_toc_gap_pending WHERE instrument_id=%s),
               (SELECT count(*) FROM v_structural_adjudication_pending WHERE instrument_id=%s),
               (SELECT count(*) FROM v_boundary_adjudication_pending WHERE instrument_id=%s),
               (SELECT overall_outcome FROM v_document_quality_status WHERE document_id=%s)
    """, (instrument_id, instrument_id, instrument_id, document_id))
    toc_pending, s7_pending, boundary_pending, quality = cur.fetchone()
    return f"TOC={toc_pending}, S7={s7_pending}, boundary={boundary_pending}, quality={quality}"


def _approval(approve_release_change: str | None) -> str | None:
    if approve_release_change is None:
        return None
    reason = " ".join(str(approve_release_change).split())
    if len(reason) < 12:
        raise ValueError("--approve-release-change needs a reason and the owner approval reference")
    return reason


def _refuse_release_change(inst: SegmentedInstrument, change: dict) -> None:
    raise ValueError(
        f"released instrument {change['previous_instrument_id']} (document {inst.document_id}, expression "
        f"{inst.expression_ordinal}) would change: provisions {change['provisions'][0]}->"
        f"{change['provisions'][1]}, {change['provisions_changed']} changed, "
        f"{len(change['paths_removed'])} paths removed, {len(change['paths_added'])} added, "
        f"{len(change['toc_changed']) + len(change['toc_added'])} contents entries differ; refused without "
        "--approve-release-change \"<reason; owner approval ref>\" (docs/SEGMENTATION-PROFILES.md)")


# --- Version validity: current text, or an owner-declared historical window (migration 0064) ---------------------
# Every provision_version is written by this one statement, from save() and save_many() alike, so the two writers
# cannot disagree about a window. Current consolidated text opens at the observation date and stays open
# (daterange(as_at, NULL)); a historical expression (owner decision 'historical-expression', doc 4434 q3) is bounded
# on both sides by its reviewed window (daterange(from, to, '[)')) and so is never `@> current_date`.
VERSION_INSERT_SQL = """
    INSERT INTO provision_version
        (provision_id,validity,text_en,text_normalised,operation,
         amended_by_id,amendment_note,
         source_toc_disposition_assertion_id)
    VALUES (%s,daterange(%s::date,%s::date,'[)'),%s,%s,%s,%s,%s,%s)"""

# The active manifest's window for one (observation, ordinal); a row means the expression is historical.
_ACTIVE_HISTORICAL_SQL = """
    SELECT id::text, lower(historical_validity)::text, upper(historical_validity)::text
      FROM instrument_expression_manifest
     WHERE source_observation_id=%s AND expression_ordinal=%s AND is_active
       AND historical_validity IS NOT NULL"""

HISTORICAL_CHOICE = "historical-expression"


def version_bounds(inst: SegmentedInstrument) -> tuple[str, str | None]:
    """(lower, upper) of every version `inst` writes: (as_at, None) for current consolidated text, or the
    reviewed historical window (from, to) -- refused unless both are ISO dates and from < to."""
    if inst.version_validity is None:
        return inst.as_at, None
    from datetime import date
    try:
        lower, upper = inst.version_validity
        start, end = date.fromisoformat(lower), date.fromisoformat(upper)
    except (TypeError, ValueError):
        raise ValueError(f"expression {inst.expression_ordinal}: version_validity "
                         f"{inst.version_validity!r} must be two ISO dates (from, to)") from None
    if not start < end:
        raise ValueError(f"expression {inst.expression_ordinal}: version_validity {lower}..{upper} "
                         "is empty or reversed")
    return start.isoformat(), end.isoformat()


def insert_version(cur, inst: SegmentedInstrument, provision_id, row: dict) -> None:
    """Write one provision_version for `row` under `inst`'s validity (VERSION_INSERT_SQL)."""
    lower, upper = version_bounds(inst)
    cur.execute(VERSION_INSERT_SQL,
                (provision_id, lower, upper, row["text"], row["text"] or "",
                 row.get("operation", "original"), row.get("amended_by_id"),
                 row.get("amendment_note"), row.get("toc_disposition_assertion_id")))


def historical_range_literal(window) -> str | None:
    """A manifest's historical_validity as a daterange literal ('[from,to)'), or None for current text."""
    if window is None:
        return None
    lower, upper = window
    return f"[{lower},{upper})"


def check_historical_pair(inst: SegmentedInstrument, manifest: dict) -> None:
    """A manifest and its expression agree: both current, or both historical with the same window, a current-
    expression target that is not themselves, and the owner's 'historical-expression' cited (the shape the 0064
    CHECK pins; refused here first so a whole multi-expression write never reaches the database half-formed)."""
    window = manifest.get("historical_validity")
    target = (manifest.get("current_source_observation_id"), manifest.get("current_expression_ordinal"))
    ordinal = inst.expression_ordinal
    if window is None and inst.version_validity is None:
        if target != (None, None):
            raise ValueError(f"expression {ordinal}: a current expression names no current-expression target")
        return
    if window is None or inst.version_validity is None or tuple(window) != tuple(inst.version_validity):
        raise ValueError(f"expression {ordinal}: manifest window {window!r} and version validity "
                         f"{inst.version_validity!r} must agree")
    version_bounds(inst)
    if None in target or (int(target[0]), int(target[1])) == (inst.source_observation_id, ordinal):
        raise ValueError(f"expression {ordinal}: a historical expression names the current expression of "
                         f"its work, not itself (got {target!r})")
    evidence = manifest.get("evidence") or {}
    decision = evidence.get("historical_owner_decision")
    if not isinstance(evidence.get("historical_basis"), dict) or not isinstance(decision, dict) \
            or decision.get("choice") != HISTORICAL_CHOICE:
        raise ValueError(f"expression {ordinal}: a historical expression needs evidence.historical_basis and "
                         f"the owner's {HISTORICAL_CHOICE!r} answer as evidence.historical_owner_decision")


def save(inst: SegmentedInstrument, segmenter: str = "nizam.corpus.segment/52", *,
         approve_release_change: str | None = None, report: dict | None = None) -> str:
    """Append and activate one complete legal-tree revision atomically.

    A RELEASED tree is replaced only by an identical rebuild, or under an explicit approval
    (`approve_release_change`, a reason with the owner approval reference). `report`, when given, receives
    {"release_change": summary, "release_change_approval": reason} for the caller's run record.

    save() writes current consolidated text only. A historical expression (migration 0064) is written by
    save_many() from a reviewed plan, so save() refuses a version_validity, and refuses to replace an expression
    whose active manifest is historical: the worker and the exact-tree overlays would otherwise write it open-ended,
    as current law."""
    approval = _approval(approve_release_change)
    if inst.version_validity is not None:
        raise ValueError(
            f"document {inst.document_id} expression {inst.expression_ordinal}: save() writes current text only; "
            "a historical expression is materialised by save_many() from a reviewed plan (migration 0064)")
    with connect() as conn, conn.cursor() as cur:
        # Lock the observation and its current materialisation.  Earlier trees
        # are retired, never deleted; all their provisions, versions, contents
        # entries and block assignments remain queryable proof.
        cur.execute("SELECT id FROM source_observation WHERE id=%s FOR SHARE",
                    (inst.source_observation_id,))
        if cur.fetchone() is None:
            raise ValueError(f"unknown source observation {inst.source_observation_id}")
        cur.execute(_ACTIVE_HISTORICAL_SQL, (inst.source_observation_id, inst.expression_ordinal))
        historical = cur.fetchone()
        if historical is not None:
            raise ValueError(
                f"observation {inst.source_observation_id} expression {inst.expression_ordinal} is a historical "
                f"expression in force [{historical[1]}, {historical[2]}) (manifest {historical[0]}); save() would "
                "write it as open-ended current law -- re-materialise it from its reviewed plan (migration 0064)")
        cur.execute("""SELECT id FROM instrument
                        WHERE source_observation_id=%s AND is_active FOR UPDATE""",
                    (inst.source_observation_id,))
        previous_rows = cur.fetchall()
        if len(previous_rows) > 1:
            raise ValueError(
                "observation has multiple active legal expressions; use the "
                "source-reviewed multi-expression materializer")
        previous_id = previous_rows[0][0] if previous_rows else None
        previously_released = False
        if previous_id is not None:
            cur.execute("SELECT EXISTS(SELECT 1 FROM v_release_instrument WHERE id=%s)",
                        (previous_id,))
            previously_released = bool(cur.fetchone()[0])
        if previously_released:
            change = released_tree_change(cur, previous_id, inst)
            if change is not None:
                if approval is None:
                    _refuse_release_change(inst, change)
                if report is not None:
                    report["release_change"] = change
                    report["release_change_approval"] = approval
        if previous_id is not None:
            cur.execute("""UPDATE instrument SET is_active=false,retired_at=now()
                            WHERE id=%s""", (previous_id,))
            # Historical provisions remain immutable and queryable by their
            # instrument. Retiring them only removes repeated revision paths
            # from the active descendant GiST (migration 0017).
            cur.execute("UPDATE provision SET is_active=false WHERE instrument_id=%s",
                        (previous_id,))
            cur.execute("""DELETE FROM provision_ancestor a USING provision p
                            WHERE a.provision_id=p.id AND p.instrument_id=%s""",
                        (previous_id,))
        cur.execute("""SELECT id FROM block_assignment_set
                        WHERE source_observation_id=%s AND is_active FOR UPDATE""",
                    (inst.source_observation_id,))
        previous_set = cur.fetchone()
        previous_set_id = previous_set[0] if previous_set else None
        if previous_set_id is not None:
            cur.execute("""UPDATE block_assignment_set
                               SET is_active=false,retired_at=now() WHERE id=%s""",
                        (previous_set_id,))
        if inst.copy_instrument_id is not None:
            if str(previous_id) != str(inst.copy_instrument_id):
                raise ValueError("exact-tree predecessor is not the active instrument")
            cur.execute("""
                INSERT INTO instrument
                    (jurisdiction,kind,number,year,short_title,long_title,preamble,
                     enacted_on,commenced_on,gazette_ref,status,repealed_on,
                     repealed_by_id,scope,published,source_sha256,document_id,
                     source_url,extraction_conf,duplicate_of,source_observation_id,
                     supersedes_instrument_id,verification_state,
                     expression_ordinal,source_start_block_id,source_end_block_id,
                     expression_role)
                SELECT jurisdiction,kind,number,year,short_title,long_title,preamble,
                       enacted_on,commenced_on,gazette_ref,status,repealed_on,
                       repealed_by_id,scope,published,source_sha256,document_id,
                       source_url,extraction_conf,duplicate_of,source_observation_id,
                       id,verification_state,expression_ordinal,source_start_block_id,
                       source_end_block_id,expression_role
                  FROM instrument WHERE id=%s
                RETURNING id""", (inst.copy_instrument_id,))
        else:
            cur.execute("""
                INSERT INTO instrument (jurisdiction, kind, number, year, short_title,
                                        long_title, preamble, source_sha256, document_id,
                                        source_url, extraction_conf, status,
                                        source_observation_id, supersedes_instrument_id,
                                        expression_ordinal,source_start_block_id,
                                        source_end_block_id,expression_role)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'unknown',%s,%s,%s,%s,%s,%s)
                RETURNING id""",
                (inst.jurisdiction, inst.kind, inst.number, inst.year, inst.short_title,
                 inst.long_title, inst.preamble, inst.sha256, inst.document_id,
                 inst.source_url, inst.confidence, inst.source_observation_id, previous_id,
                 inst.expression_ordinal,inst.source_start_block_id,
                 inst.source_end_block_id,inst.expression_role))
        instrument_id = cur.fetchone()[0]
        cur.execute("""INSERT INTO instrument_source
                        (instrument_id,source_observation_id,role)
                        VALUES (%s,%s,'primary')""",
                    (instrument_id, inst.source_observation_id))
        cur.execute("""INSERT INTO block_assignment_set
                        (document_id,source_observation_id,instrument_id,segmenter,
                         supersedes_set_id)
                        VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                    (inst.document_id, inst.source_observation_id, instrument_id,
                     segmenter, previous_set_id))
        assignment_set_id = cur.fetchone()[0]

        # Insert parents before children so parent_id can be resolved as we go:
        # the tree arrives in document order, which is already topological.
        ids: dict[int, str] = {}
        for row in inst.provisions:
            parent_uuid = ids.get(row["parent_key"]) if row["parent_key"] is not None else None
            cur.execute("""
                INSERT INTO provision (instrument_id, parent_id, path, kind, label,
                                       heading,marginal_note,ordinal,first_page,
                                       last_page,first_block)
                VALUES (%s,%s,%s::ltree,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id""",
                (instrument_id, parent_uuid, row["path"], row["kind"], row["label"],
                 row["heading"],row.get("marginal_note"),row["ordinal"],
                 row["first_page"],row["last_page"],row["first_block"]))
            ids[row["key"]] = cur.fetchone()[0]

            if row["text"] or row.get("operation") != "original":
                # validity opens at the date the source was observed. See the
                # comment on provision_version.validity in migration 0004: we
                # hold consolidated current text, not amendment history, so
                # claiming it applied from the year of enactment would be false.
                # (save() refused a historical window above; version_bounds is
                # shared with save_many so the two cannot drift.)
                insert_version(cur, inst, ids[row["key"]], row)

        # Every block in the document, with its role -- CORPUS-CRITERIA C4/C5.
        # Written in the same transaction as the tree, so a document can never be
        # half-accounted: either the provisions and the ledger both land, or
        # neither does.
        if inst.block_roles:
            with cur.copy("COPY provision_block "
                          "(assignment_set_id, block_id, document_id, provision_id, role, chars) "
                          "FROM STDIN") as cp:
                for block_id, role, node_key, chars in inst.block_roles:
                    pid = ids.get(node_key) if node_key is not None else None
                    # Roles that must resolve to a provision cannot be written
                    # without one; if the node is missing the block is unplaced,
                    # and saying so is the whole point of the ledger.
                    if pid is None and role in ("body", "heading",
                                                "schedule_row", "preamble"):
                        role = "unassigned"
                    if pid is not None and role in ("contents", "preface",
                                                    "running_header",
                                                    "unstructured", "unassigned"):
                        pid = None
                    cp.write_row((assignment_set_id, block_id, inst.document_id,
                                  pid, role, chars))

        # Derived active-subtree accelerator. Build it from the actual parent
        # graph, not every syntactic ltree prefix: the first three path labels
        # identify an observation but are not provisions and cannot be queried
        # as provision ancestors. Canonical paths and parent links remain on
        # provision; this closure is disposable (migrations 0018 and 0027).
        cur.execute("""WITH RECURSIVE ancestry AS (
                            SELECT p.id AS provision_id,
                                   p.id AS ancestor_id,
                                   p.path AS ancestor_path,
                                   0::smallint AS distance
                              FROM provision p
                             WHERE p.instrument_id=%s
                            UNION ALL
                            SELECT a.provision_id,
                                   parent.id,
                                   parent.path,
                                   (a.distance+1)::smallint
                              FROM ancestry a
                              JOIN provision child ON child.id=a.ancestor_id
                              JOIN provision parent ON parent.id=child.parent_id
                        )
                        INSERT INTO provision_ancestor
                            (ancestor_path,provision_id,distance)
                        SELECT ancestor_path,provision_id,distance
                          FROM ancestry""", (instrument_id,))

        # The printed contents list, in printed order (migration 0011). Written
        # in the same transaction as the tree it points at, so the links can
        # never name provisions from a previous run.
        if inst.toc_entries:
            with cur.copy("COPY instrument_toc_entry "
                          "(instrument_id, ordinal, printed_label, printed_heading, "
                          " entry_kind, source_block_id, source_char_offset, "
                          " source_page, provision_id, match_method) "
                          "FROM STDIN") as cp:
                for e in inst.toc_entries:
                    key = e.get("provision_key")
                    pid = ids.get(key) if key is not None else None
                    cp.write_row((instrument_id, e["ordinal"], e["label"],
                                  e["heading"], e["kind"], e.get("source_block_id"),
                                  e.get("source_char_offset"),
                                  e.get("source_page"), pid,
                                  e["method"] if pid is not None else "unmatched"))

        # S7 proposals are first-class evidence, not an integer hidden in a run
        # summary.  They are tied to this immutable tree revision and to the two
        # exact source blocks whose printed labels collided.  An independent
        # adjudication is deliberately a separate append-only event.
        for decision in inst.structural_decisions:
            candidate_id = ids[decision["candidate_key"]]
            canonical_id = ids[decision["canonical_key"]]
            parent_key = decision.get("parent_key")
            parent_id = ids.get(parent_key) if parent_key is not None else None
            cur.execute("""
                INSERT INTO segmentation_structural_candidate
                    (instrument_id,source_observation_id,document_id,
                     candidate_provision_id,canonical_provision_id,parent_provision_id,
                     decision_kind,original_kind,printed_label,source_block_id,
                     source_page,canonical_source_block_id,canonical_source_page,
                     proposed_resolution,segmenter,evidence)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (
                instrument_id,inst.source_observation_id,inst.document_id,
                candidate_id,canonical_id,parent_id,decision["decision_kind"],
                decision["original_kind"],decision["printed_label"],
                decision["source_block_id"],decision["source_page"],
                decision["canonical_source_block_id"],
                decision["canonical_source_page"],
                decision["proposed_resolution"],segmenter,
                json.dumps(decision["evidence"],ensure_ascii=False),
            ))
            new_candidate_id = cur.fetchone()[0]
            _carry_prior_s7_acceptance(cur, previous_id, new_candidate_id,
                                       decision.get("carried_adjudication"))
        if previous_id is not None:
            _carry_toc_gap_decisions(cur, previous_id, instrument_id, inst.document_id)
        if previously_released:
            # record_run() follows save() in the worker. Check every other
            # release predicate here, inside the replacement transaction; the
            # new run row cannot exist until this transaction has committed.
            failure = _release_gate_failure(cur, instrument_id, inst.document_id)
            if failure:
                raise ValueError(
                    "released instrument replay would fail the release gate; "
                    f"rolling back the entire tree replacement ({failure})")
        return instrument_id


def save_many(insts: list[SegmentedInstrument], full_blocks: list[dict],
              manifests: list[dict],
              segmenter: str = "nizam.corpus.segment/52+multi/1", *,
              approve_release_change: str | None = None, report: dict | None = None,
              require_all_released: bool = False) -> list[str]:
    """Atomically replace one observation with several legal expressions.

    Released expressions are guarded as in save(): an identical rebuild, or `approve_release_change`
    (recorded in the manifest evidence of each changed expression as `release_change_approval`).

    A historical expression (migration 0064) carries `version_validity` on the instrument and the same window as
    `historical_validity` on its manifest, with `current_source_observation_id` / `current_expression_ordinal`;
    its versions are written bounded. A replay of an expression whose active manifest is historical must carry
    the window forward (or an explicit `historical_withdrawal`), or the whole write is refused.

    Source blocks are not copied.  A single active assignment set covers the
    entire observation, while its provision links may point into any of the
    expression trees.  Blocks outside a reviewed legal span remain reachable as
    document-level preface.  Any validation failure rolls back every new tree.
    `require_all_released` additionally gates new expressions before commit
    (3912: narrow the released Act only if the Rules release atomically).
    """
    approval = _approval(approve_release_change)
    if not insts:
        raise ValueError("at least one legal expression is required")
    if len(insts) != len(manifests):
        raise ValueError("each expression requires one source manifest")
    observations = {i.source_observation_id for i in insts}
    documents = {i.document_id for i in insts}
    ordinals = [i.expression_ordinal for i in insts]
    if len(observations) != 1 or len(documents) != 1:
        raise ValueError("all expressions must share one observation and document")
    if len(set(ordinals)) != len(ordinals):
        raise ValueError("expression ordinals must be unique")
    if any(i.expression_role not in ("primary", "embedded") for i in insts):
        raise ValueError("invalid expression role")
    # Migration 0064: each manifest and its expression agree on current-vs-historical and on the window.
    for inst, manifest in zip(insts, manifests):
        if int(manifest["expression_ordinal"]) != inst.expression_ordinal:
            raise ValueError(f"manifest ordinal {manifest['expression_ordinal']} is not expression "
                             f"{inst.expression_ordinal}")
        check_historical_pair(inst, manifest)

    observation_id = next(iter(observations))
    document_id = next(iter(documents))
    ordered_block_ids = [b["id"] for b in full_blocks]
    if len(ordered_block_ids) != len(set(ordered_block_ids)):
        raise ValueError("full document block list contains duplicates")
    full_block_set = set(ordered_block_ids)
    block_position = {block_id:index for index,block_id in
                      enumerate(ordered_block_ids)}

    # Validate source ownership before opening the write transaction.  A block
    # may belong to at most one legal expression; gaps are document apparatus.
    claimed: set[int] = set()
    for inst,manifest in zip(insts,manifests):
        ids = [row[0] for row in inst.block_roles]
        if not ids or not set(ids) <= full_block_set:
            raise ValueError(f"expression {inst.expression_ordinal} has an invalid source span")
        overlap = claimed & set(ids)
        if overlap:
            raise ValueError(f"source blocks assigned to multiple expressions: {sorted(overlap)[:5]}")
        spans = manifest.get("spans") or [{
            "start_block_id": manifest["start_block_id"],
            "end_block_id": manifest["end_block_id"],
        }]
        span_ids: list[int] = []
        previous_end = -1
        for span in spans:
            first = block_position.get(span["start_block_id"])
            last = block_position.get(span["end_block_id"])
            if first is None or last is None or first > last:
                raise ValueError(
                    f"expression {inst.expression_ordinal} has an invalid manifest span")
            if first <= previous_end:
                raise ValueError(
                    f"expression {inst.expression_ordinal} has overlapping/out-of-order spans")
            span_ids.extend(ordered_block_ids[first:last + 1])
            previous_end = last
        if (len(span_ids) != len(ids)
                or len(span_ids) != len(set(span_ids))
                or set(span_ids) != set(ids)):
            raise ValueError(
                f"expression {inst.expression_ordinal} manifest spans do not exactly "
                "match its block ledger")
        claimed.update(ids)

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM source_observation WHERE id=%s FOR UPDATE",
                    (observation_id,))
        if cur.fetchone() is None:
            raise ValueError(f"unknown source observation {observation_id}")
        cur.execute("""SELECT id,expression_ordinal FROM instrument
                        WHERE source_observation_id=%s AND is_active FOR UPDATE""",
                    (observation_id,))
        previous_by_ordinal = {row[1]: row[0] for row in cur.fetchall()}
        previous_ids = list(previous_by_ordinal.values())
        released_before: set = set()
        if previous_ids:
            cur.execute("SELECT id FROM v_release_instrument WHERE id=ANY(%s)", (previous_ids,))
            released_before = {row[0] for row in cur.fetchall()}
        # The released-tree change guard (as in save()): every released expression must be rebuilt
        # identically at its ordinal, or the run must carry an approval, recorded in that manifest's evidence.
        if previous_ids:
            cur.execute("SELECT id FROM v_release_instrument WHERE id=ANY(%s)", (previous_ids,))
            released_ids = {row[0] for row in cur.fetchall()}
            by_new_ordinal = {i.expression_ordinal: i for i in insts}
            for ordinal, previous in sorted(previous_by_ordinal.items()):
                if previous not in released_ids:
                    continue
                new_inst = by_new_ordinal.get(ordinal)
                change = ({"previous_instrument_id": str(previous), "provisions": [None, 0],
                           "paths_removed": ["(expression no longer built)"], "paths_added": [],
                           "provisions_changed": 0, "changed": [], "toc_entries": [None, 0],
                           "toc_changed": [], "toc_added": []}
                          if new_inst is None else released_tree_change(cur, previous, new_inst))
                if change is None:
                    continue
                if approval is None:
                    _refuse_release_change(new_inst or insts[0], change)
                if report is not None:
                    report.setdefault("release_changes", {})[ordinal] = change
                    report["release_change_approval"] = approval
                for inst_, manifest_ in zip(insts, manifests):
                    if inst_.expression_ordinal == ordinal:
                        manifest_["evidence"] = dict(manifest_["evidence"] or {},
                                                     release_change_approval={"reason": approval,
                                                                              "change": change})
        if previous_ids:
            cur.execute("""UPDATE instrument SET is_active=false,retired_at=now()
                            WHERE id=ANY(%s)""", (previous_ids,))
            cur.execute("UPDATE provision SET is_active=false WHERE instrument_id=ANY(%s)",
                        (previous_ids,))
            cur.execute("""DELETE FROM provision_ancestor a USING provision p
                            WHERE a.provision_id=p.id AND p.instrument_id=ANY(%s)""",
                        (previous_ids,))

        cur.execute("""SELECT id FROM block_assignment_set
                        WHERE source_observation_id=%s AND is_active FOR UPDATE""",
                    (observation_id,))
        previous_set = cur.fetchone()
        previous_set_id = previous_set[0] if previous_set else None
        if previous_set_id is not None:
            cur.execute("""UPDATE block_assignment_set
                               SET is_active=false,retired_at=now() WHERE id=%s""",
                        (previous_set_id,))
        cur.execute("""INSERT INTO block_assignment_set
                        (document_id,source_observation_id,instrument_id,segmenter,
                         supersedes_set_id)
                        VALUES (%s,%s,NULL,%s,%s) RETURNING id""",
                    (document_id,observation_id,segmenter,previous_set_id))
        assignment_set_id = cur.fetchone()[0]

        cur.execute("""SELECT id,expression_ordinal,historical_validity IS NOT NULL
                          FROM instrument_expression_manifest
                         WHERE source_observation_id=%s AND is_active FOR UPDATE""",
                    (observation_id,))
        previous_manifests = cur.fetchall()
        previous_manifest_by_ordinal = {row[1]:row[0] for row in previous_manifests}
        # A historical declaration is carried forward or explicitly withdrawn, never dropped by a replay
        # (migration 0064; the deferred manifest_historical_retention_guard refuses the same at commit).
        new_manifest_by_ordinal = {int(m["expression_ordinal"]): m for m in manifests}
        for manifest_id, ordinal, historical in previous_manifests:
            successor = new_manifest_by_ordinal.get(ordinal)
            if not historical or successor is None or successor.get("historical_validity") is not None:
                continue
            withdrawal = (successor.get("evidence") or {}).get("historical_withdrawal") or {}
            if withdrawal.get("withdraws_manifest_id") != str(manifest_id):
                raise ValueError(
                    f"expression {ordinal} is historical (manifest {manifest_id}); its replay carries no window. "
                    "Carry the reviewed window forward (plan version_validity), or withdraw it explicitly")
        if previous_manifest_by_ordinal:
            cur.execute("""UPDATE instrument_expression_manifest
                               SET is_active=false,retired_at=now()
                             WHERE id=ANY(%s)""",
                        (list(previous_manifest_by_ordinal.values()),))

        instrument_ids: list[str] = []
        provision_ids: dict[int, dict[int, str]] = {}
        pending_carries: list[tuple] = []
        for inst in sorted(insts, key=lambda value: value.expression_ordinal):
            previous_id = previous_by_ordinal.get(inst.expression_ordinal)
            cur.execute("""
                INSERT INTO instrument
                    (jurisdiction,kind,number,year,short_title,long_title,preamble,
                     source_sha256,document_id,source_url,extraction_conf,status,
                     source_observation_id,supersedes_instrument_id,
                     expression_ordinal,source_start_block_id,source_end_block_id,
                     expression_role)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'unknown',%s,%s,%s,%s,%s,%s)
                RETURNING id""",
                (inst.jurisdiction,inst.kind,inst.number,inst.year,inst.short_title,
                 inst.long_title,inst.preamble,inst.sha256,inst.document_id,
                 inst.source_url,inst.confidence,inst.source_observation_id,
                 previous_id,inst.expression_ordinal,inst.source_start_block_id,
                 inst.source_end_block_id,inst.expression_role))
            instrument_id = cur.fetchone()[0]
            instrument_ids.append(instrument_id)
            cur.execute("""INSERT INTO instrument_source
                            (instrument_id,source_observation_id,role)
                            VALUES (%s,%s,'primary')""",
                        (instrument_id,observation_id))

            ids: dict[int, str] = {}
            for row in inst.provisions:
                parent_id = ids.get(row["parent_key"]) if row["parent_key"] is not None else None
                cur.execute("""
                    INSERT INTO provision
                        (instrument_id,parent_id,path,kind,label,heading,marginal_note,
                         ordinal,first_page,last_page,first_block)
                    VALUES (%s,%s,%s::ltree,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (instrument_id,parent_id,row["path"],row["kind"],row["label"],
                     row["heading"],row.get("marginal_note"),row["ordinal"],
                     row["first_page"],row["last_page"],row["first_block"]))
                ids[row["key"]] = cur.fetchone()[0]
                if row["text"] or row.get("operation") != "original":
                    # Current text opens at as_at; a historical expression is bounded by its window (0064).
                    insert_version(cur, inst, ids[row["key"]], row)
            provision_ids[inst.expression_ordinal] = ids

            cur.execute("""WITH RECURSIVE ancestry AS (
                                SELECT p.id provision_id,p.id ancestor_id,p.path ancestor_path,
                                       0::smallint distance
                                  FROM provision p WHERE p.instrument_id=%s
                                UNION ALL
                                SELECT a.provision_id,parent.id,parent.path,
                                       (a.distance+1)::smallint
                                  FROM ancestry a
                                  JOIN provision child ON child.id=a.ancestor_id
                                  JOIN provision parent ON parent.id=child.parent_id)
                            INSERT INTO provision_ancestor
                                (ancestor_path,provision_id,distance)
                            SELECT ancestor_path,provision_id,distance FROM ancestry""",
                        (instrument_id,))

            if inst.toc_entries:
                with cur.copy("COPY instrument_toc_entry "
                              "(instrument_id,ordinal,printed_label,printed_heading,entry_kind,"
                              "source_block_id,source_char_offset,source_page,"
                              "provision_id,match_method) FROM STDIN") as cp:
                    for entry in inst.toc_entries:
                        key = entry.get("provision_key")
                        pid = ids.get(key) if key is not None else None
                        cp.write_row((instrument_id,entry["ordinal"],entry["label"],
                                      entry["heading"],entry["kind"],
                                      entry.get("source_block_id"),
                                      entry.get("source_char_offset"),
                                      entry.get("source_page"),
                                      pid,entry["method"] if pid is not None else "unmatched"))

            for decision in inst.structural_decisions:
                parent_key = decision.get("parent_key")
                cur.execute("""INSERT INTO segmentation_structural_candidate
                    (instrument_id,source_observation_id,document_id,
                     candidate_provision_id,canonical_provision_id,parent_provision_id,
                     decision_kind,original_kind,printed_label,source_block_id,
                     source_page,canonical_source_block_id,canonical_source_page,
                     proposed_resolution,segmenter,evidence)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id""",
                    (instrument_id,observation_id,document_id,
                     ids[decision["candidate_key"]],ids[decision["canonical_key"]],
                     ids.get(parent_key) if parent_key is not None else None,
                     decision["decision_kind"],decision["original_kind"],
                     decision["printed_label"],decision["source_block_id"],
                     decision["source_page"],decision["canonical_source_block_id"],
                     decision["canonical_source_page"],decision["proposed_resolution"],
                     segmenter,json.dumps(decision["evidence"],ensure_ascii=False)))
                # The same acceptance carry as save() (12 Oct 2026, doc 4497 e12/e25) -- deferred until the
                # block ledger is written: the subtree identity it checks includes each provision's source blocks.
                pending_carries.append((previous_id, cur.fetchone()[0], decision.get("carried_adjudication")))

        # Resolve each manifest to the corresponding inserted instrument.
        by_ordinal = {inst.expression_ordinal: iid for inst,iid in
                      zip(sorted(insts,key=lambda value: value.expression_ordinal),instrument_ids)}
        for manifest in manifests:
            ordinal = int(manifest["expression_ordinal"])
            cur.execute("""INSERT INTO instrument_expression_manifest
                (source_observation_id,document_id,expression_ordinal,expression_role,
                 start_block_id,end_block_id,detected_title,detected_kind,
                 detected_year,detected_number,review_basis,method,evidence,
                 materialized_instrument_id,supersedes_manifest_id,
                 historical_validity,current_source_observation_id,current_expression_ordinal)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::daterange,%s,%s)
                RETURNING id""",
                (observation_id,document_id,ordinal,manifest["expression_role"],
                 manifest["start_block_id"],manifest["end_block_id"],
                 manifest["detected_title"],manifest["detected_kind"],
                 manifest["detected_year"],manifest.get("detected_number"),
                 manifest["review_basis"],manifest["method"],
                 json.dumps(manifest["evidence"],ensure_ascii=False),by_ordinal[ordinal],
                 previous_manifest_by_ordinal.get(ordinal),
                 historical_range_literal(manifest.get("historical_validity")),
                 manifest.get("current_source_observation_id"),
                 manifest.get("current_expression_ordinal")))
            manifest_id = cur.fetchone()[0]
            spans = manifest.get("spans") or [{
                "start_block_id": manifest["start_block_id"],
                "end_block_id": manifest["end_block_id"],
            }]
            for span_ordinal,span in enumerate(spans):
                cur.execute("""INSERT INTO instrument_expression_span
                    (manifest_id,span_ordinal,start_block_id,end_block_id)
                    VALUES (%s,%s,%s,%s)""",
                    (manifest_id,span_ordinal,span["start_block_id"],
                     span["end_block_id"]))

        # Translate each expression-local node key to its new provision UUID.
        ledger: dict[int, tuple[str, str | None, int]] = {}
        for inst in insts:
            ids = provision_ids[inst.expression_ordinal]
            for block_id,role,node_key,chars in inst.block_roles:
                pid = ids.get(node_key) if node_key is not None else None
                if pid is None and role in ("body","heading","schedule_row","preamble"):
                    role = "unassigned"
                if pid is not None and role in (
                        "contents","preface","running_header","unstructured","unassigned"):
                    pid = None
                if block_id in ledger:
                    raise ValueError(f"block {block_id} assigned twice")
                ledger[block_id] = (role,pid,chars)
        chars_by_block = {b["id"]: len(b["text"] or "") for b in full_blocks}
        with cur.copy("COPY provision_block "
                      "(assignment_set_id,block_id,document_id,provision_id,role,chars) "
                      "FROM STDIN") as cp:
            for block_id in ordered_block_ids:
                role,pid,chars = ledger.get(
                    block_id,("preface",None,chars_by_block[block_id]))
                cp.write_row((assignment_set_id,block_id,document_id,pid,role,chars))

        for previous_id, new_candidate_id, carried in pending_carries:
            _carry_prior_s7_acceptance(cur, previous_id, new_candidate_id, carried)

        # As in save(): standing contents-gap decisions carry onto identical entries, and a previously RELEASED
        # expression must still pass every release predicate, or the whole replacement rolls back (12 Oct 2026:
        # before this, doc 4497 e12/e25 silently dropped out of the release).
        failures = []
        ordered = list(zip(sorted(insts, key=lambda value: value.expression_ordinal), instrument_ids))
        # every expression this replay replaces, by its retired id: a decision naming a sibling follows it
        successors = {str(previous_by_ordinal[inst.expression_ordinal]): str(new_id) for inst, new_id in ordered
                      if previous_by_ordinal.get(inst.expression_ordinal) is not None}
        for inst, new_id in ordered:
            previous_id = previous_by_ordinal.get(inst.expression_ordinal)
            if previous_id is not None:
                _carry_toc_gap_decisions(cur, previous_id, new_id, document_id, successors)
            if require_all_released or previous_id in released_before:
                failure = _release_gate_failure(cur, new_id, document_id)
                if failure:
                    failures.append(f"expression {inst.expression_ordinal}: {failure}")
        if failures:
            raise ValueError("expression replay would fail the release gate; rolling back the "
                             "entire multi-expression replacement (" + "; ".join(failures) + ")")
        return instrument_ids


def save_unstructured(document_id: int, source_observation_id: int,
                      blocks: list[dict], segmenter: str) -> int:
    """Account for a document that has text but no provision structure.

    Nine documents in the corpus are like this and none of them is a parser
    defect: a PDF whose only content is "THIS LAW HAS BEEN REPEALED", a set of
    recruitment rules published as a ten-column table, and sources whose text
    layer is unusable. Rejecting them used to leave their blocks in no ledger at
    all -- 733 blocks, 35,086 characters, present in text_block and invisible to
    every completeness query. CORPUS-CRITERIA C4 exists to make that impossible.

    Returns the number of blocks recorded.
    """
    with connect() as conn, conn.cursor() as cur:
        # The newest segmentation result is authoritative for active state even
        # when it finds no legal tree. Retain the earlier tree, but do not leave
        # it active beside a new unstructured assignment.
        cur.execute("""SELECT id FROM instrument
                        WHERE source_observation_id=%s AND is_active FOR UPDATE""",
                    (source_observation_id,))
        old_instruments = cur.fetchall()
        if len(old_instruments) > 1:
            raise ValueError(
                "cannot replace a reviewed multi-expression observation with "
                "an unstructured result")
        old_instrument = old_instruments[0] if old_instruments else None
        if old_instrument is not None:
            cur.execute("""UPDATE instrument SET is_active=false,retired_at=now()
                            WHERE id=%s""", (old_instrument[0],))
            cur.execute("UPDATE provision SET is_active=false WHERE instrument_id=%s",
                        (old_instrument[0],))
            cur.execute("""DELETE FROM provision_ancestor a USING provision p
                            WHERE a.provision_id=p.id AND p.instrument_id=%s""",
                        (old_instrument[0],))
        cur.execute("""SELECT id FROM block_assignment_set
                        WHERE source_observation_id=%s AND is_active FOR UPDATE""",
                    (source_observation_id,))
        previous = cur.fetchone()
        previous_id = previous[0] if previous else None
        if previous_id is not None:
            cur.execute("""UPDATE block_assignment_set
                               SET is_active=false,retired_at=now() WHERE id=%s""",
                        (previous_id,))
        cur.execute("""INSERT INTO block_assignment_set
                        (document_id,source_observation_id,instrument_id,segmenter,
                         supersedes_set_id)
                        VALUES (%s,%s,NULL,%s,%s) RETURNING id""",
                    (document_id, source_observation_id, segmenter, previous_id))
        assignment_set_id = cur.fetchone()[0]
        with cur.copy("COPY provision_block "
                      "(assignment_set_id, block_id, document_id, provision_id, role, chars) "
                      "FROM STDIN") as cp:
            for b in blocks:
                cp.write_row((assignment_set_id, b["id"], document_id, None,
                              "unstructured", len(b["text"])))
        return len(blocks)


def record_run(document_id: int, source_observation_id: int,
               instrument_id: str | None, segmenter: str,
               outcome: str, **kw) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO segmentation_run
                (document_id, source_observation_id, instrument_id, segmenter, outcome, reason, provisions,
                 sections, max_depth, body_starts_page, toc_found, toc_entries,
                 toc_matched, toc_missing, toc_extra, toc_agreement, detail, duration_ms)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (document_id, source_observation_id, instrument_id, segmenter, outcome,
             kw.get("reason"),
             kw.get("provisions", 0), kw.get("sections", 0), kw.get("max_depth", 0),
             kw.get("body_starts_page"), kw.get("toc_found", False),
             kw.get("toc_entries"), kw.get("toc_matched"), kw.get("toc_missing"),
             kw.get("toc_extra"), kw.get("toc_agreement"),
             json.dumps(kw.get("detail", {}), ensure_ascii=False),
             kw.get("duration_ms")))
