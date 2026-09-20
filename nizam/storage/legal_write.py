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
            SELECT id::text,page_no,match_text,before_text,after_text
              FROM segmentation_curation_patch
             WHERE source_observation_id=%s
               AND review_state IN ('source_verified','human_verified')
               AND retired_at IS NULL
             ORDER BY page_no,created_at,id
        """, (source_observation_id,))
        keys = ("id", "page_no", "match_text", "before_text", "after_text")
        return [dict(zip(keys, row)) for row in cur.fetchall()]


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
               a.resolution, a.review_basis, a.id, a.decided_at, a.decided_by
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
           l.review_basis, l.id::text, l.decided_at, l.decided_by
      FROM latest l
      JOIN settled s
        ON s.source_block_id = l.source_block_id
       AND s.label_key = l.label_key
     WHERE l.resolution IN ('restore_citable','reject_candidate')
     ORDER BY l.source_block_id, l.label_key
"""

_STRUCTURAL_RESOLUTION_KEYS = (
    "source_block_id", "printed_label", "label_key", "resolution",
    "review_basis", "adjudication_id", "decided_at", "decided_by")


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
    which says the parser kept the wrong print, and `reject_candidate`, which
    says the collision is not genuine. `reparent` and `split_instrument` name
    work this function cannot express: no reparent decision in this corpus
    records a target parent, and a split is a document-level operation.

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


def save(inst: SegmentedInstrument, segmenter: str = "nizam.corpus.segment/52") -> str:
    """Append and activate one complete legal-tree revision atomically."""
    with connect() as conn, conn.cursor() as cur:
        # Lock the observation and its current materialisation.  Earlier trees
        # are retired, never deleted; all their provisions, versions, contents
        # entries and block assignments remain queryable proof.
        cur.execute("SELECT id FROM source_observation WHERE id=%s FOR SHARE",
                    (inst.source_observation_id,))
        if cur.fetchone() is None:
            raise ValueError(f"unknown source observation {inst.source_observation_id}")
        cur.execute("""SELECT id FROM instrument
                        WHERE source_observation_id=%s AND is_active FOR UPDATE""",
                    (inst.source_observation_id,))
        previous_rows = cur.fetchall()
        if len(previous_rows) > 1:
            raise ValueError(
                "observation has multiple active legal expressions; use the "
                "source-reviewed multi-expression materializer")
        previous_id = previous_rows[0][0] if previous_rows else None
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
                cur.execute("""
                    INSERT INTO provision_version
                        (provision_id,validity,text_en,text_normalised,operation,
                         amended_by_id,amendment_note,
                         source_toc_disposition_assertion_id)
                    VALUES (%s,daterange(%s,NULL,'[)'),%s,%s,%s,%s,%s,%s)""",
                    (ids[row["key"]],inst.as_at,row["text"],row["text"] or "",
                     row.get("operation", "original"),row.get("amended_by_id"),
                     row.get("amendment_note"),
                     row.get("toc_disposition_assertion_id")))

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
            carried = decision.get("carried_adjudication")
            if carried is not None:
                carried_evidence = dict(carried["evidence"] or {})
                carried_evidence["carried_from_candidate_id"] = carried["candidate_id"]
                carried_evidence["carried_from_adjudication_id"] = carried["id"]
                carried_evidence["exact_tree_revision"] = True
                cur.execute("""
                    INSERT INTO segmentation_structural_adjudication
                        (candidate_id,resolution,review_basis,method,rationale,
                         evidence,decided_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (
                    new_candidate_id,carried["resolution"],carried["review_basis"],
                    "carried_by_exact_tree_revision/1",carried["rationale"],
                    json.dumps(carried_evidence,ensure_ascii=False),
                    "nizam.exact_tree_revision/1",
                ))
        return instrument_id


def save_many(insts: list[SegmentedInstrument], full_blocks: list[dict],
              manifests: list[dict],
              segmenter: str = "nizam.corpus.segment/52+multi/1") -> list[str]:
    """Atomically replace one observation with several legal expressions.

    Source blocks are not copied.  A single active assignment set covers the
    entire observation, while its provision links may point into any of the
    expression trees.  Blocks outside a reviewed legal span remain reachable as
    document-level preface.  Any validation failure rolls back every new tree.
    """
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

        cur.execute("""SELECT id,expression_ordinal
                          FROM instrument_expression_manifest
                         WHERE source_observation_id=%s AND is_active FOR UPDATE""",
                    (observation_id,))
        previous_manifest_by_ordinal = {row[1]:row[0] for row in cur.fetchall()}
        if previous_manifest_by_ordinal:
            cur.execute("""UPDATE instrument_expression_manifest
                               SET is_active=false,retired_at=now()
                             WHERE id=ANY(%s)""",
                        (list(previous_manifest_by_ordinal.values()),))

        instrument_ids: list[str] = []
        provision_ids: dict[int, dict[int, str]] = {}
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
                    cur.execute("""INSERT INTO provision_version
                        (provision_id,validity,text_en,text_normalised,operation,
                         amended_by_id,amendment_note,
                         source_toc_disposition_assertion_id)
                        VALUES (%s,daterange(%s,NULL,'[)'),%s,%s,%s,%s,%s,%s)""",
                        (ids[row["key"]],inst.as_at,row["text"],row["text"] or "",
                         row.get("operation", "original"),row.get("amended_by_id"),
                         row.get("amendment_note"),
                         row.get("toc_disposition_assertion_id")))
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
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (instrument_id,observation_id,document_id,
                     ids[decision["candidate_key"]],ids[decision["canonical_key"]],
                     ids.get(parent_key) if parent_key is not None else None,
                     decision["decision_kind"],decision["original_kind"],
                     decision["printed_label"],decision["source_block_id"],
                     decision["source_page"],decision["canonical_source_block_id"],
                     decision["canonical_source_page"],decision["proposed_resolution"],
                     segmenter,json.dumps(decision["evidence"],ensure_ascii=False)))

        # Resolve each manifest to the corresponding inserted instrument.
        by_ordinal = {inst.expression_ordinal: iid for inst,iid in
                      zip(sorted(insts,key=lambda value: value.expression_ordinal),instrument_ids)}
        for manifest in manifests:
            ordinal = int(manifest["expression_ordinal"])
            cur.execute("""INSERT INTO instrument_expression_manifest
                (source_observation_id,document_id,expression_ordinal,expression_role,
                 start_block_id,end_block_id,detected_title,detected_kind,
                 detected_year,detected_number,review_basis,method,evidence,
                 materialized_instrument_id,supersedes_manifest_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                RETURNING id""",
                (observation_id,document_id,ordinal,manifest["expression_role"],
                 manifest["start_block_id"],manifest["end_block_id"],
                 manifest["detected_title"],manifest["detected_kind"],
                 manifest["detected_year"],manifest.get("detected_number"),
                 manifest["review_basis"],manifest["method"],
                 json.dumps(manifest["evidence"],ensure_ascii=False),by_ordinal[ordinal],
                 previous_manifest_by_ordinal.get(ordinal)))
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
