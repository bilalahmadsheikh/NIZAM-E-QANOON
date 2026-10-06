"""Materialize source-reviewed internal instruments without copying source text.

This tool is deliberately bounded to documents whose boundary sequences were
reviewed against their immutable text blocks.  Default mode is a read-only
build/report.  ``--apply`` replaces one single-tree interpretation atomically
with disjoint expression trees plus one complete document block ledger.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import time
from collections import Counter

from nizam.storage import legal_write
from nizam.storage.db import connect
from nizam.workers.segment import (SEGMENTER, build, infer_kind, owner_decision_answer,
                                   reviewed_structural_overrides)

METHOD = "nizam.multi_expression_materializer/1"

# A reviewed per-document plan names every expression outright: its block
# spans, title, kind, year, number and role, an optional correction of the
# stored catalogue title/year, and relations between the expressions.  It is
# for a PDF whose principal instrument does not start at block 0 or whose
# parts each carry their own printed title and year (doc 268: a 2003 amending
# notification printed before the 1996 Rules it amends, and a 1998 Order).
# The plan is the source review; nothing in it is inferred.
PLAN_DIRECTORY = pathlib.Path(__file__).resolve().parent / "evidence" / "multi-instrument-plans"
PLAN_SCHEMA = "nizam.multi_expression_plan/1"
INSTRUMENT_KINDS = {"constitution", "act", "ordinance", "order", "regulation",
                    "rules", "sro", "notification"}           # 0004 instrument_kind
# There is no legal_edge table yet (docs/03b).  A relation is carried in the
# plan and in the source expression's manifest evidence until one exists.
PLAN_RELATIONS = {"amends"}


def plan_documents(directory: pathlib.Path = PLAN_DIRECTORY) -> set[int]:
    if not directory.is_dir():
        return set()
    return {int(match.group(1)) for path in directory.glob("doc-*.json")
            if (match := re.fullmatch(r"doc-(\d+)\.json", path.name))}


def load_plan(document_id: int,
              directory: pathlib.Path = PLAN_DIRECTORY) -> dict | None:
    path = directory / f"doc-{document_id}.json"
    if not path.is_file():
        return None
    plan = json.loads(path.read_text(encoding="utf-8-sig"))
    plan["_path"] = str(path)
    return plan


# These have an independently citable outer instrument followed by appendices.
PRIMARY_DOCUMENTS = {977, 1106, 3389, 3553, 3696, 3912, 4434, 4452}
# These are editorial compilations, not themselves legal instruments.
COMPILATION_DOCUMENTS = {3423, 3949, 4440, 4497}
REVIEWED_DOCUMENTS = PRIMARY_DOCUMENTS | COMPILATION_DOCUMENTS | plan_documents()
REJECTED_EDITORIAL_BOUNDARIES = {893415}
# The package contents is outside each legal expression span.  If the parser
# tries to discover a second contents list inside these spans, the opening run
# of enacted sections is itself mistaken for contents and discarded.  This is
# a source-reviewed property of the package, not a general parser heuristic.
NO_LOCAL_CONTENTS_DOCUMENTS = {4440}
# The Finance Act's contents embeds the new Tobacco Act's own section list, and
# the Act itself is inserted before the Finance Act resumes its appendices.
# Both legal expressions therefore own disjoint immutable spans.  These exact
# endpoints partition all 633 blocks and were checked against rendered pages
# 1, 14, 17 and 18; no text is copied or discarded.
REVIEWED_EXPRESSION_SPANS = {
    4452: {
        0: [(816322, 816330), (816332, 816490), (816545, 816954)],
        1: [(816331, 816331), (816491, 816544)],
    },
}
FORCED_EXPRESSION_CONTENTS = {(4452, 1)}
SOURCE_REVIEW_DETAILS = {
    4452: {
        "reviewed_pages": [1, 14, 17, 18],
        "reviewed_on": "2026-09-12",
        "source_facts": [
            "page_1_nests_the_tobacco_act_contents_under_finance_act_section_15",
            "page_14_prints_finance_act_section_15_then_tobacco_act_section_1",
            "page_17_ends_the_tobacco_act_at_section_9",
            "page_18_resumes_finance_act_appendix_I_with_section_3_cross_reference",
        ],
    },
}


def validate_plan(plan: dict, blocks: list[dict], document_id: int,
                  observation_id: int) -> list[dict]:
    """Check a reviewed plan against the document's immutable blocks.

    Returns one specification per expression, ordered by ordinal, with each
    span resolved to reading-order index ranges.  Anything the plan does not
    state exactly is refused rather than guessed.
    """
    if plan.get("schema") != PLAN_SCHEMA:
        raise ValueError(f"plan schema must be {PLAN_SCHEMA!r}")
    if plan.get("document_id") != document_id:
        raise ValueError(f"plan is for document {plan.get('document_id')}, not {document_id}")
    if plan.get("source_observation_id") != observation_id:
        raise ValueError(
            f"plan is for observation {plan.get('source_observation_id')}, "
            f"not the active canonical observation {observation_id}")
    if plan.get("review_basis") not in ("source_verified", "human_verified"):
        raise ValueError("plan review_basis must be source_verified or human_verified")
    expressions = plan.get("expressions") or []
    if not expressions:
        raise ValueError("plan names no expressions")
    ordinals = [value.get("ordinal") for value in expressions]
    if sorted(ordinals) != list(range(len(expressions))):
        raise ValueError(f"plan ordinals must be 0..{len(expressions)-1}, got {ordinals}")
    primaries = [value["ordinal"] for value in expressions if value.get("role") == "primary"]
    if any(value.get("role") not in ("primary", "embedded") for value in expressions):
        raise ValueError("plan expression role must be primary or embedded")
    if len(primaries) > 1 or (primaries and primaries != [0]):
        raise ValueError("a plan has at most one primary expression, at ordinal 0")
    position = {block["id"]: index for index, block in enumerate(blocks)}
    claimed: dict[int, int] = {}
    specs = []
    for value in sorted(expressions, key=lambda item: item["ordinal"]):
        ordinal = value["ordinal"]
        title = (value.get("title") or "").strip()
        if not title:
            raise ValueError(f"plan expression {ordinal} has no title")
        if value.get("kind") not in INSTRUMENT_KINDS:
            raise ValueError(f"plan expression {ordinal} kind {value.get('kind')!r} "
                             "is not an instrument_kind")
        year = value.get("year")
        if type(year) is not int or not 1800 <= year <= 2100:
            raise ValueError(f"plan expression {ordinal} needs an integer year")
        if "number" not in value or not (value["number"] is None
                                         or (isinstance(value["number"], str)
                                             and value["number"].strip())):
            raise ValueError(f"plan expression {ordinal} must state number (null if none)")
        correction = value.get("title_correction")
        if correction is not None and (
                not isinstance(correction, dict)
                or correction.get("to_year") != year
                or not (correction.get("basis") or "").strip()
                or not (correction.get("from_title") or "").strip()):
            raise ValueError(f"plan expression {ordinal} title_correction must give "
                             "from_title, to_year equal to the plan year, and a basis")
        ranges = []
        previous = -1
        for span in value.get("spans") or []:
            first = position.get(span.get("start_block_id"))
            last = position.get(span.get("end_block_id"))
            if first is None or last is None:
                raise ValueError(f"plan expression {ordinal} span {span} names a block "
                                 f"outside document {document_id}")
            if first > last or first <= previous:
                raise ValueError(f"plan expression {ordinal} spans are empty, "
                                 "overlapping or out of reading order")
            for index in range(first, last + 1):
                if index in claimed:
                    raise ValueError(
                        f"block {blocks[index]['id']} is in expressions "
                        f"{claimed[index]} and {ordinal}")
                claimed[index] = ordinal
            ranges.append((first, last))
            previous = last
        if not ranges:
            raise ValueError(f"plan expression {ordinal} has no spans")
        relations = value.get("relations") or []
        for relation in relations:
            if relation.get("type") not in PLAN_RELATIONS:
                raise ValueError(f"plan relation type {relation.get('type')!r} is not "
                                 f"one of {sorted(PLAN_RELATIONS)}")
            target = relation.get("target_ordinal")
            if target not in ordinals or target == ordinal:
                raise ValueError(f"plan expression {ordinal} relation targets "
                                 f"unknown or self ordinal {target}")
            if not (relation.get("effect") or "").strip() or not (
                    relation.get("basis") or "").strip():
                raise ValueError(f"plan expression {ordinal} relation needs effect and basis")
            anchor = relation.get("source_block_id")
            if anchor is not None and claimed.get(position.get(anchor)) != ordinal:
                raise ValueError(f"plan expression {ordinal} relation anchor {anchor} "
                                 "is not inside its own span")
        specs.append({
            "ordinal": ordinal, "role": value["role"], "title": title,
            "kind": value["kind"], "year": year, "number": value["number"],
            "ranges": ranges, "title_correction": correction,
            "relations": relations,
            "detect_contents": bool(value.get("detect_contents", True)),
            "force_opening_contents": bool(value.get("force_opening_contents", False)),
        })
    return specs


def override_block_ids(evidence: dict | None) -> set[int]:
    """Every source block a patch's structural overrides name."""
    found: set[int] = set()

    def walk(key: str, value) -> None:
        if isinstance(value, dict):
            for inner_key, inner in value.items():
                walk(inner_key, inner)
        elif isinstance(value, list):
            for inner in value:
                walk(key, inner)
        elif type(value) is int and (key.endswith("_block") or key.endswith("_blocks")
                                     or key.endswith("_block_id")):
            found.add(value)

    for key, value in ((evidence or {}).get("structural_overrides") or {}).items():
        walk(key, value)
    return found


def assign_patches(blocks: list[dict], patches: list[dict],
                   owner: dict[int, int]) -> tuple[dict[int, list[dict]], list[dict]]:
    """Give each curation patch to the one expression whose span it reads.

    The patches are applied in order over the whole document exactly as the
    segmenter applies them, so a stale or ambiguous locator still fails
    closed; the expression owning the matched block receives the patch.
    Because each patch rewrites only its own block, applying an expression's
    subset in the same order to its span gives the same text.  A patch whose
    block is outside every span (document apparatus) is returned separately.
    The blocks its structural overrides name must belong to the same
    expression -- a reading may not reach across a boundary.
    """
    derived = [dict(block) for block in blocks]
    assigned: dict[int, list[dict]] = {}
    outside: list[dict] = []
    for patch in patches:
        matches = [block for block in derived
                   if block.get("page_no") == patch["page_no"]
                   and patch["match_text"].casefold() in block["text"].casefold()]
        if len(matches) != 1:
            raise ValueError(f"curation patch {patch.get('id')} matched {len(matches)} "
                             "blocks in the document; expected 1")
        block = matches[0]
        if block["text"].count(patch["before_text"]) != 1:
            raise ValueError(f"curation patch {patch.get('id')} before_text is not unique")
        block["text"] = block["text"].replace(patch["before_text"], patch["after_text"], 1)
        ordinal = owner.get(block["id"])
        named = {owner.get(block_id, None) for block_id in
                 override_block_ids(patch.get("evidence"))}
        if named and named != {ordinal}:
            raise ValueError(f"curation patch {patch.get('id')} reads block {block['id']} "
                             f"(expression {ordinal}) but its structural overrides name "
                             f"blocks of expressions {sorted(named, key=str)}")
        if ordinal is None:
            outside.append(patch)
        else:
            assigned.setdefault(ordinal, []).append(patch)
    return assigned, outside


STRUCTURAL_PATCH_KEYS = (
    "source_body_start_block", "source_apparatus_blocks", "source_reparent_blocks",
    "source_continuation_parent_blocks", "source_unnumbered_section_openers",
    "source_unnumbered_part_headings", "source_schedule_row_openers",
    "source_schedule_form_group")


def unrecorded_readings(readings: list[dict], stored: list[dict],
                        document_id: int) -> list[dict]:
    """Shape not-yet-recorded readings as the patch loader would return them.

    Dry-run only: the recorder (tools/record_curation_patch.py) stores the
    structural keys under evidence.structural_overrides.  A reading already
    recorded (same page, locator and before text) is not applied twice.
    """
    have = {(p["page_no"], p["match_text"], p["before_text"]) for p in stored}
    shaped = []
    for index, reading in enumerate(readings):
        if reading.get("document_id") != document_id:
            raise ValueError(f"reading {index} is for document {reading.get('document_id')}")
        if (reading["page_no"], reading["match_text"], reading["before_text"]) in have:
            continue
        overrides = {key: reading[key] for key in STRUCTURAL_PATCH_KEYS if key in reading}
        # As the recorder does: an opener citing an owner decision must cite
        # an answer the export holds (profile rule `unnumbered_root_provision`).
        for opener in overrides.get("source_unnumbered_section_openers") or []:
            if "owner_decision" in opener:
                owner_decision_answer(opener["owner_decision"], document_id)
        shaped.append({
            "id": f"unrecorded-{index}", "page_no": reading["page_no"],
            "match_text": reading["match_text"], "before_text": reading["before_text"],
            "after_text": reading["after_text"],
            "evidence": {"structural_overrides": overrides} if overrides else {},
        })
    return shaped


def _boundary_rows(observation_id: int) -> list[dict]:
    """Every boundary candidate of the observation with its latest decision."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT c.id::text,c.start_block_id,c.source_page,c.detected_title,
                   c.detected_kind,c.detected_year,c.detected_number,c.confidence,
                   c.method,c.evidence,a.resolution,
                   EXISTS (SELECT 1 FROM instrument i WHERE i.id=c.instrument_id
                            AND i.is_active AND i.duplicate_of IS NULL)
              FROM segmentation_boundary_candidate c
              LEFT JOIN v_boundary_adjudication_latest a ON a.candidate_id=c.id
             WHERE c.source_observation_id=%s
             ORDER BY c.start_block_id,c.created_at,c.id
        """, (observation_id,))
        names = ("candidate_id","start_block_id","source_page","title","kind","year",
                 "number","confidence","detector","evidence","resolution","on_active")
        return [dict(zip(names, row)) for row in cur.fetchall()]


def plan_boundaries(specs: list[dict], blocks: list[dict],
                    rows: list[dict]) -> dict[int, dict | None]:
    """Reconcile recorded boundary evidence with the plan.

    A confirmed split must sit at one of the plan's span starts; an open
    (unadjudicated or needs_review) signal on the live tree must too, since
    applying the plan retires that tree.  A rejected boundary at a plan anchor
    contradicts the plan.  Returns, per ordinal, the confirmed candidate at its
    first span start (None if absent).
    """
    starts = {blocks[first]["id"] for spec in specs for first, _ in spec["ranges"]}
    anchors = {blocks[spec["ranges"][0][0]]["id"]: spec["ordinal"] for spec in specs}
    confirmed: dict[int, dict | None] = {spec["ordinal"]: None for spec in specs}
    for row in rows:
        block = row["start_block_id"]
        resolution = row["resolution"]
        if resolution == "confirmed_split" or (
                row["on_active"] and resolution in (None, "needs_review")):
            if block not in starts:
                raise ValueError(
                    f"boundary candidate {row['candidate_id']} at block {block} "
                    f"({resolution or 'unadjudicated'}) is not a span start of the plan")
            if resolution == "confirmed_split" and block in anchors:
                confirmed[anchors[block]] = confirmed[anchors[block]] or row
        elif resolution in ("not_boundary", "embedded_reference") and block in anchors:
            raise ValueError(f"boundary candidate {row['candidate_id']} at plan anchor "
                             f"{block} was adjudicated {resolution}")
    return confirmed


def _title_tokens(value: str) -> set[str]:
    stop = {"the","of","and","act","ordinance","rule","rules","regulation",
            "regulations","order","notification"}
    return {token.casefold() for token in re.findall(r"[A-Za-z]{3,}",value or "")
            if token.casefold() not in stop}


def _clean_title(value: str) -> str:
    value = re.sub(r"^\s*\d+(?:\.\d+)+\s+", "", value or "")
    value = re.sub(r"\b\d+\*(?=(?:Act|Ordinance|Rules?|Regulations?|Order)\b)","",value,
                   flags=re.I)
    return re.sub(r"\s+"," ",value).strip(" \"'‘’")


def _expanded_start(blocks: list[dict], start: int, title: str) -> int:
    """Include a nearby printed title split from its formula anchor."""
    wanted = _title_tokens(title)
    if not wanted:
        return start
    best = start
    wanted_year = re.search(r"\b(?:18|19|20)\d{2}\b",title or "")
    for index in range(start-1,max(-1,start-8),-1):
        text = blocks[index]["text"] or ""
        if blocks[index]["id"] in REJECTED_EDITORIAL_BOUNDARIES:
            continue
        letters = [char for char in text if char.isalpha()]
        uppercase = (sum(char.isupper() for char in letters) / len(letters)
                     if letters else 0.0)
        have = _title_tokens(text)
        overlap = len(wanted & have) / len(wanted)
        title_like = uppercase >= 0.52 or (len(text) <= 180 and overlap >= 0.75)
        if (len(text) > 240 or not title_like
                or re.search(r"\b(?:in exercise|whereas|subject to)\b",text,re.I)):
            continue
        printed_year = re.search(r"\b(?:18|19|20)\d{2}\b",text)
        if (wanted_year and printed_year
                and wanted_year.group(0) != printed_year.group(0)):
            continue
        if (re.search(r"\b(?:act|ordinance|rules?|regulations?|order)\b",text,re.I)
                and overlap >= 0.55):
            best = index
            break
    return best


def _source_title(blocks: list[dict], start: int, detected: str) -> str:
    printed = re.sub(r"\s+"," ",blocks[start]["text"] or "").strip()
    printed = re.sub(r"^\d+(?=[A-Za-z])","",printed).strip()
    letters = [char for char in printed if char.isalpha()]
    uppercase = (sum(char.isupper() for char in letters) / len(letters)
                 if letters else 0.0)
    printed_tokens = _title_tokens(printed)
    detected_tokens = _title_tokens(detected)
    if (len(printed) <= 240 and uppercase >= 0.52
            and re.search(r"\b(?:act|ordinance|rules?|regulations?|order)\b",printed,re.I)
            and re.search(r"\b(?:18|19|20)\d{2}\b",printed)
            and len(printed_tokens & detected_tokens)
                / max(len(detected_tokens),1) >= 0.55
            and (len(printed_tokens) >= 0.7 * len(detected_tokens)
                 or "constitution" not in detected_tokens
                 or "constitution" in printed_tokens)):
        return printed
    return detected


def _same_nearby_expression(left: dict,right: dict) -> bool:
    if right["start"]-left["start"] > 2:
        return False
    if infer_kind(left["title"]) != infer_kind(right["title"]):
        return False
    left_year = re.findall(r"\b(?:18|19|20)\d{2}\b",left["title"])
    right_year = re.findall(r"\b(?:18|19|20)\d{2}\b",right["title"])
    if left_year and right_year and left_year[-1] != right_year[-1]:
        return False
    a,b = _title_tokens(left["title"]),_title_tokens(right["title"])
    return bool(a and b and len(a & b)/min(len(a),len(b)) >= 0.75)


def _next_estacode_item(blocks: list[dict],start: int,ceiling: int) -> int | None:
    for index in range(start+1,ceiling+1):
        raw = blocks[index]["text"] or ""
        if re.match(r"^\s*\d{1,2}\.\d{1,2}\s+",raw):
            return index
    return None


def _load(document_id: int,observation_id: int | None = None) -> tuple[dict, list[dict]]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT i.id::text,i.source_observation_id,i.document_id,i.source_sha256,
                   i.jurisdiction::text,i.kind::text,i.number,i.year,i.short_title,
                   i.source_url,o.source_id,
                   coalesce(o.source_metadata->>'year',o.source_metadata->>'year_or_dept')
              FROM instrument i
              JOIN source_observation o ON o.id=i.source_observation_id
             WHERE i.document_id=%s AND i.is_active
               AND (%s::bigint IS NULL AND i.duplicate_of IS NULL
                    OR i.source_observation_id=%s)
             ORDER BY (i.expression_role='primary') DESC,i.expression_ordinal
        """, (document_id,observation_id,observation_id))
        rows = cur.fetchall()
        if not rows:
            raise ValueError(
                f"document {document_id} has no active canonical expression")
        names = ("instrument_id","source_observation_id","document_id","sha256",
                 "jurisdiction","kind","number","year","short_title","source_url",
                 "source_id","meta_year")
        outer = dict(zip(names,rows[0]))
        cur.execute("""SELECT count(*) FROM instrument_expression_manifest
                        WHERE source_observation_id=%s AND is_active""",
                    (outer["source_observation_id"],))
        already_materialized = cur.fetchone()[0] > 0
        if already_materialized:
            cur.execute("""
                SELECT coalesce(c.id::text,m.evidence->>'candidate_id'),
                       m.start_block_id,b.page_no,m.detected_title,
                       m.detected_kind::text,m.detected_year,m.detected_number,
                       coalesce(c.confidence,1.0),m.method,
                       jsonb_build_object(
                         'manifest_id',m.id,
                         'manifest_evidence',m.evidence,
                         'candidate_evidence',c.evidence)
                  FROM instrument_expression_manifest m
                  JOIN text_block b ON b.id=m.start_block_id
                  LEFT JOIN segmentation_boundary_candidate c
                    ON c.id=(m.evidence->>'candidate_id')::uuid
                 WHERE m.source_observation_id=%s AND m.is_active
                   AND m.expression_role='embedded'
                 ORDER BY m.expression_ordinal
            """, (outer["source_observation_id"],))
        else:
            cur.execute("""
            SELECT c.id::text,c.start_block_id,c.source_page,c.detected_title,
                   c.detected_kind,c.detected_year,c.detected_number,c.confidence,
                   c.method,c.evidence
              FROM v_boundary_adjudication_pending c
             WHERE c.instrument_id=%s
             ORDER BY (SELECT reading_order FROM text_block WHERE id=c.start_block_id),c.id
            """, (outer["instrument_id"],))
            if cur.rowcount == 0 and document_id == 4497:
                # A byte-identical official observation gets the same reviewed
                # expression manifest, then exact tree fingerprints decide its
                # duplicate representation.  Provenance is not collapsed.
                cur.execute("""
                    SELECT c.id::text,c.start_block_id,c.source_page,c.detected_title,
                           c.detected_kind,c.detected_year,c.detected_number,c.confidence,
                           c.method,c.evidence
                      FROM instrument_expression_manifest m
                      JOIN segmentation_boundary_candidate c
                        ON c.id=(m.evidence->>'candidate_id')::uuid
                     WHERE m.document_id=%s AND m.is_active
                     ORDER BY m.expression_ordinal
                """, (document_id,))
        boundary_names = ("candidate_id","start_block_id","source_page","title","kind",
                          "year","number","confidence","detector","evidence")
        boundaries = [dict(zip(boundary_names,row)) for row in cur.fetchall()]
        return outer,boundaries


def _repo_path(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return pathlib.Path(path).resolve().relative_to(
            PLAN_DIRECTORY.parent.parent.parent).as_posix()
    except ValueError:
        return pathlib.Path(path).as_posix()


def _outer(document_id: int,observation_id: int | None) -> dict:
    """The canonical observation's identity, before or after materialization."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT i.source_observation_id,i.document_id,i.source_sha256,
                   i.short_title,i.year,i.source_url,o.source_id,
                   coalesce(o.source_metadata->>'year',o.source_metadata->>'year_or_dept')
              FROM instrument i
              JOIN source_observation o ON o.id=i.source_observation_id
             WHERE i.document_id=%s AND i.is_active
               AND (%s::bigint IS NULL AND i.duplicate_of IS NULL
                    OR i.source_observation_id=%s)
             ORDER BY (i.expression_role='primary') DESC,i.expression_ordinal
        """, (document_id,observation_id,observation_id))
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"document {document_id} has no active canonical expression")
    names = ("source_observation_id","document_id","sha256","short_title","year",
             "source_url","source_id","meta_year")
    return dict(zip(names,row))


def prepare_from_plan(document_id: int,plan: dict,observation_id: int | None = None,
                      extra_readings: list[dict] | None = None,
                      profile: str | None = None,
                      allow_empty: bool = False) -> tuple[list, list, list, list]:
    """Build every expression a reviewed plan names (see PLAN_DIRECTORY)."""
    outer = _outer(document_id,observation_id)
    observation = outer["source_observation_id"]
    blocks = legal_write.blocks_for(document_id)
    specs = validate_plan(plan,blocks,document_id,observation)
    owner = {blocks[index]["id"]: spec["ordinal"] for spec in specs
             for first,last in spec["ranges"] for index in range(first,last + 1)}
    boundary = plan_boundaries(specs,blocks,_boundary_rows(observation))
    stored = legal_write.segmentation_patches_for(observation)
    patches = stored + unrecorded_readings(extra_readings or [],stored,document_id)
    assigned,outside = assign_patches(blocks,patches,owner)
    resolutions = legal_write.structural_resolutions_for(document_id)
    as_at = legal_write.observed_on(observation)
    titles = {spec["ordinal"]: spec["title"] for spec in specs}
    insts,segs,manifests = [],[],[]
    for spec in specs:
        ordinal = spec["ordinal"]
        span = [block for first,last in spec["ranges"] for block in blocks[first:last + 1]]
        span_ids = {block["id"] for block in span}
        span_patches = assigned.get(ordinal,[])
        span_resolutions = [row for row in resolutions
                            if row.get("source_block_id") in span_ids]
        overrides = reviewed_structural_overrides(span_resolutions,span_patches) or None
        inst,seg = build(
            document_id,outer["sha256"],observation,outer["source_id"],spec["title"],
            str(spec["year"]),outer["source_url"],span,as_at,span_patches,
            toc_dispositions=legal_write.toc_dispositions_for(observation,ordinal),
            structural_resolutions=span_resolutions,
            structural_overrides=overrides,
            detect_contents=spec["detect_contents"],
            force_opening_contents=spec["force_opening_contents"],
            expression_ordinal=ordinal,expression_role=spec["role"],profile=profile,
            reviewed_identity={"kind": spec["kind"],"year": spec["year"],
                               "number": spec["number"]})
        if not inst.provisions and not allow_empty:
            raise ValueError(
                f"expression {ordinal} ({spec['title']!r}, blocks "
                f"{span[0]['id']}..{span[-1]['id']}, pages "
                f"{span[0]['page_no']}..{span[-1]['page_no']}) produced no provisions")
        candidate = boundary[ordinal]
        source_spans = [{"start_block_id": blocks[first]["id"],
                         "end_block_id": blocks[last]["id"],
                         "first_page": blocks[first]["page_no"],
                         "last_page": blocks[last]["page_no"]}
                        for first,last in spec["ranges"]]
        evidence = {
            "source_review": "reviewed expression plan",
            "plan": {"path": _repo_path(plan.get("_path")),
                     "schema": plan["schema"],"reviewed_on": plan.get("reviewed_on"),
                     "reviewed_by": plan.get("reviewed_by")},
            "owner_decision": plan.get("owner_decision"),
            "reviewed_pages": plan.get("reviewed_pages"),
            "candidate_id": candidate["candidate_id"] if candidate else None,
            "candidate_method": candidate["detector"] if candidate else None,
            # The expression does not open the document, so a recorded
            # confirmed_split must anchor it before --apply (doc 977 precedent).
            "boundary_anchor_required": span[0]["id"] != blocks[0]["id"],
            "curation_patch_ids": [patch["id"] for patch in span_patches],
            "span_block_count": len(span),
            "span_first_page": span[0]["page_no"],
            "span_last_page": span[-1]["page_no"],
            "source_spans": source_spans,
        }
        if spec["title_correction"]:
            evidence["title_correction"] = spec["title_correction"]
        if spec["relations"]:
            # No legal_edge table exists yet (docs/03b); this is where the
            # relation is recorded until one does.
            evidence["relations"] = [
                dict(relation,target_title=titles[relation["target_ordinal"]])
                for relation in spec["relations"]]
        insts.append(inst)
        segs.append(seg)
        manifests.append({
            "expression_ordinal": ordinal,
            "expression_role": spec["role"],
            "start_block_id": span[0]["id"],
            "end_block_id": span[-1]["id"],
            "detected_title": spec["title"],
            "detected_kind": inst.kind,
            "detected_year": inst.year,
            "detected_number": inst.number,
            "review_basis": plan["review_basis"],
            "method": METHOD,
            "evidence": evidence,
            "spans": [{"start_block_id": value["start_block_id"],
                       "end_block_id": value["end_block_id"]} for value in source_spans],
        })
    if outside:
        manifests[0]["evidence"]["curation_patches_outside_spans"] = [
            patch["id"] for patch in outside]
    return insts,segs,manifests,blocks


def prepare(document_id: int,observation_id: int | None = None,*,
            extra_readings: list[dict] | None = None,profile: str | None = None,
            allow_empty: bool = False) -> tuple[list, list, list, list]:
    if document_id not in REVIEWED_DOCUMENTS:
        raise ValueError(f"document {document_id} is not in the source-reviewed allow-list")
    plan = load_plan(document_id)
    if plan is not None:
        if document_id in PRIMARY_DOCUMENTS | COMPILATION_DOCUMENTS:
            raise ValueError(f"document {document_id} has both a plan and a legacy listing")
        return prepare_from_plan(document_id,plan,observation_id,extra_readings,
                                 profile,allow_empty)
    if extra_readings or profile is not None:
        raise ValueError("unrecorded readings and --profile are supported for plan documents only")
    outer,boundaries = _load(document_id,observation_id)
    if not boundaries:
        raise ValueError(f"document {document_id} has no pending source boundary evidence")
    blocks = legal_write.blocks_for(document_id)
    position = {block["id"]: index for index,block in enumerate(blocks)}
    if any(boundary["start_block_id"] not in position for boundary in boundaries):
        raise ValueError("a boundary does not belong to the active document")
    # Collapse multiple detector records anchored to the same immutable block.
    unique: list[dict] = []
    seen: set[int] = set()
    for boundary in boundaries:
        if boundary["start_block_id"] in REJECTED_EDITORIAL_BOUNDARIES:
            continue
        if boundary["start_block_id"] not in seen:
            unique.append(boundary)
            seen.add(boundary["start_block_id"])
    boundaries = unique

    specifications: list[dict] = []
    if document_id in PRIMARY_DOCUMENTS:
        specifications.append({
            "title": outer["short_title"], "year": outer["year"],
            "kind": outer["kind"], "number": outer["number"],
            "start": 0, "role": "primary", "candidate": None,
        })
    for boundary in boundaries:
        start = _expanded_start(blocks,position[boundary["start_block_id"]],
                                boundary["title"])
        specifications.append({
            "title": _clean_title(_source_title(blocks,start,boundary["title"])),
            "year": boundary["year"],
            "kind": infer_kind(boundary["title"]), "number": boundary["number"],
            "start": start,
            "role": "embedded",
            "candidate": boundary,
        })
    specifications.sort(key=lambda value: value["start"])
    collapsed: list[dict] = []
    for spec in specifications:
        if collapsed and collapsed[-1]["start"] == spec["start"]:
            old = collapsed[-1]
            old_confidence = (old["candidate"] or {}).get("confidence",1.0)
            new_confidence = (spec["candidate"] or {}).get("confidence",1.0)
            old_tokens,new_tokens = _title_tokens(old["title"]),_title_tokens(spec["title"])
            prefer_new_title = (
                len(new_tokens) > len(old_tokens)
                or (len(new_tokens) == len(old_tokens)
                    and re.match(r"^\d",old["title"])
                    and not re.match(r"^\d",spec["title"])))
            if prefer_new_title:
                old["title"] = spec["title"]
                old["candidate"] = spec["candidate"]
                old["year"] = spec["year"]
                old["kind"] = spec["kind"]
                old["number"] = spec["number"]
            elif new_confidence > old_confidence:
                old["candidate"] = spec["candidate"]
            continue
        exact_nearby_title = bool(
            collapsed
            and spec["start"]-collapsed[-1]["start"] <= 2
            and re.sub(r"[^a-z0-9]+","",spec["title"].casefold())
                == re.sub(r"[^a-z0-9]+","",collapsed[-1]["title"].casefold()))
        if collapsed and (exact_nearby_title
                          or _same_nearby_expression(collapsed[-1],spec)):
            old = collapsed[-1]
            # Keep the earliest printed-title anchor and the more complete
            # source title.  Both candidate ids remain in the immutable queue;
            # the manifest materialises their one shared legal expression.
            if len(_title_tokens(spec["title"])) > len(_title_tokens(old["title"])):
                old["title"] = spec["title"]
                old["candidate"] = spec["candidate"]
            continue
        collapsed.append(spec)
    specifications = collapsed

    as_at = legal_write.observed_on(outer["source_observation_id"])
    patches = legal_write.segmentation_patches_for(outer["source_observation_id"])
    all_ranges = []
    for ordinal,spec in enumerate(specifications):
        end = (specifications[ordinal + 1]["start"] - 1
               if ordinal + 1 < len(specifications) else len(blocks) - 1)
        if document_id == 4497:
            next_item = _next_estacode_item(blocks,spec["start"],end)
            if next_item is not None:
                end = next_item-1
            # The official contents puts item 2.14 (Postal Group) at printed
            # page 68 / PDF page 75, but its heading is absent from extraction.
            # The preceding Police Rules schedule ends at block 886063; source
            # blocks 886064 onward are editorial apparatus for later items.
            if spec["title"].startswith("Police Service of Pakistan"):
                end = min(end,position[886063])
        reviewed_spans = REVIEWED_EXPRESSION_SPANS.get(document_id, {}).get(ordinal)
        span_ranges = ([(position[first], position[last])
                        for first,last in reviewed_spans]
                       if reviewed_spans else [(spec["start"], end)])
        all_ranges.append(span_ranges)
    # Each expression is parsed with only the curation patches that read its
    # own span; a patch elsewhere in the document would otherwise match no
    # block of the span and fail the whole build.
    owner = {blocks[index]["id"]: ordinal
             for ordinal,span_ranges in enumerate(all_ranges)
             for first,last in span_ranges for index in range(first,last + 1)}
    assigned,_outside = assign_patches(blocks,patches,owner)
    insts = []
    segs = []
    manifests = []
    for ordinal,spec in enumerate(specifications):
        span_ranges = all_ranges[ordinal]
        span = [block for first,last in span_ranges
                for block in blocks[first:last + 1]]
        if not span:
            raise ValueError(f"empty source span for expression {ordinal}")
        inst,seg = build(
            document_id,outer["sha256"],outer["source_observation_id"],
            outer["source_id"],spec["title"],
            str(spec["year"] or outer["meta_year"] or ""),outer["source_url"],
            span,as_at,assigned.get(ordinal,[]),expression_ordinal=ordinal,
            expression_role=spec["role"],
            detect_contents=document_id not in NO_LOCAL_CONTENTS_DOCUMENTS,
            force_opening_contents=(document_id, ordinal)
                in FORCED_EXPRESSION_CONTENTS)
        if not inst.provisions:
            raise ValueError(
                f"expression {ordinal} ({spec['title']!r}, blocks "
                f"{span[0]['id']}..{span[-1]['id']}, pages "
                f"{span[0]['page_no']}..{span[-1]['page_no']}) produced no provisions")
        insts.append(inst)
        segs.append(seg)
        candidate = spec["candidate"]
        evidence = {
            "source_review": "independent legal formula and self-naming section/rule reset",
            "candidate_id": candidate["candidate_id"] if candidate else None,
            "candidate_method": candidate["detector"] if candidate else None,
            "candidate_evidence": candidate["evidence"] if candidate else None,
            "span_block_count": len(span),
            "span_first_page": span[0]["page_no"],
            "span_last_page": span[-1]["page_no"],
            "source_spans": [
                {
                    "start_block_id": blocks[first]["id"],
                    "end_block_id": blocks[last]["id"],
                    "first_page": blocks[first]["page_no"],
                    "last_page": blocks[last]["page_no"],
                }
                for first,last in span_ranges if first <= last
            ],
        }
        evidence.update(SOURCE_REVIEW_DETAILS.get(document_id, {}))
        manifests.append({
            "expression_ordinal": ordinal,
            "expression_role": spec["role"],
            "start_block_id": span[0]["id"],
            "end_block_id": span[-1]["id"],
            "detected_title": spec["title"],
            "detected_kind": inst.kind,
            "detected_year": inst.year,
            "detected_number": inst.number,
            "review_basis": "source_verified",
            "method": METHOD,
            "evidence": evidence,
            "spans": [
                {
                    "start_block_id": blocks[first]["id"],
                    "end_block_id": blocks[last]["id"],
                }
                for first,last in span_ranges if first <= last
            ],
        })
    return insts,segs,manifests,blocks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document",type=int,action="append",required=True)
    parser.add_argument("--observation",type=int,
                        help="materialize one provenance observation of a shared blob")
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--summary-only",action="store_true")
    parser.add_argument("--unrecorded-readings",
                        help="plan documents, report mode only: a readings JSON "
                             "(tools/record_curation_patch.py format) applied as if recorded")
    parser.add_argument("--profile",
                        help="plan documents, report mode only: parse under this "
                             "profile instead of the observation's pin")
    args = parser.parse_args()
    if args.apply and (args.unrecorded_readings or args.profile):
        parser.error("--apply builds only from recorded readings under the pinned "
                     "profile; --unrecorded-readings and --profile are report-only")
    extra = (json.loads(pathlib.Path(args.unrecorded_readings).read_text(encoding="utf-8-sig"))
             if args.unrecorded_readings else None)
    report = []
    for document_id in args.document:
        started = time.time()
        insts,segs,manifests,blocks = prepare(
            document_id,args.observation,extra_readings=extra,profile=args.profile,
            allow_empty=not args.apply)
        if args.apply:
            unanchored = [manifest["expression_ordinal"] for manifest in manifests
                          if manifest["evidence"].get("boundary_anchor_required")
                          and not manifest["evidence"].get("candidate_id")]
            if unanchored:
                raise ValueError(
                    f"document {document_id}: expressions {unanchored} need a recorded "
                    "confirmed_split boundary candidate at their first span start")
        item = {
            "document_id": document_id,
            "source_observation_id": insts[0].source_observation_id,
            "expressions": [{
                "ordinal": inst.expression_ordinal,
                "role": inst.expression_role,
                "title": inst.short_title,
                "kind": inst.kind,
                "year": inst.year,
                "first_block": inst.source_start_block_id,
                "last_block": inst.source_end_block_id,
                "first_page": min((row["first_page"] for row in inst.provisions
                                   if row["first_page"] is not None),default=None),
                "last_page": max((row["last_page"] for row in inst.provisions
                                  if row["last_page"] is not None),default=None),
                "provisions": len(inst.provisions),
                "blocked": ([] if inst.provisions else ["produced no provisions"]),
                "top_level_units": [
                    f"{row['kind']} {row['label']}".strip() for row in inst.provisions
                    if row["parent_key"] is None],
                "provision_kinds": dict(sorted(Counter(
                    row["kind"] for row in inst.provisions
                ).items())),
                "top_level_citable_labels": [
                    row["label"] for row in inst.provisions
                    if row["parent_key"] is None
                    and row["kind"] in {"section", "article"}
                ],
                "s7_candidates": len(inst.structural_decisions),
                "toc_found": seg.toc_found,
                "toc_missing": len(seg.missing) if seg.toc else 0,
                "toc_missing_labels": seg.missing if seg.toc else [],
                "toc_unmatched_entries": [
                    {
                        "ordinal": entry["ordinal"],
                        "label": entry["label"],
                        "heading": entry["heading"],
                        "kind": entry["kind"],
                        "source_page": entry.get("source_page"),
                    }
                    for entry in seg.toc_entries if entry.get("node") is None
                ],
                "unassigned_blocks": sum(1 for row in inst.block_roles
                                         if row[1] == "unassigned"),
                "block_roles": dict(sorted(Counter(
                    row[1] for row in inst.block_roles).items())),
                "toc_entries": len(seg.toc_entries),
                "curation_patches_applied": seg.curation_patches_applied,
                **{key: manifest["evidence"][key] for key in (
                    "curation_patch_ids","boundary_anchor_required","candidate_id",
                    "title_correction","relations","source_spans")
                   if key in manifest["evidence"]},
            } for inst,seg,manifest in zip(insts,segs,manifests)],
            "document_blocks": len(blocks),
            "expression_blocks": sum(len(inst.block_roles) for inst in insts),
            "apparatus_blocks": len(blocks)-sum(len(inst.block_roles) for inst in insts),
            "applied": args.apply,
        }
        if args.apply:
            # build() parsed every expression under the observation's pinned
            # profile; the writer identity says so (docs/SEGMENTATION-PROFILES.md).
            profile = segs[0].profile
            writer = METHOD if profile == "default" else f"{METHOD}+{profile}"
            ids = legal_write.save_many(insts,blocks,manifests,writer)
            for inst,seg,instrument_id in zip(insts,segs,ids):
                legal_write.record_run(
                    document_id,inst.source_observation_id,instrument_id,writer,"segmented",
                    provisions=len(inst.provisions),
                    sections=sum(1 for row in inst.provisions if row["kind"] == "section"),
                    max_depth=max((row["path"].count(".") for row in inst.provisions),default=0),
                    body_starts_page=seg.body_starts_page,toc_found=seg.toc_found,
                    toc_entries=len(seg.toc_entries) or None,
                    toc_matched=seg.matched if seg.toc else None,
                    toc_missing=len(seg.missing) if seg.toc else None,
                    toc_extra=len(seg.extra) if seg.toc else None,
                    toc_agreement=round(seg.agreement,4) if seg.toc else None,
                    detail={"missing":seg.missing[:60],"extra":seg.extra[:60],
                            "blocks_total":len(inst.block_roles),
                            "repeated_labels_demoted":seg.repeated_labels_demoted,
                            "schedule_sections_retyped":seg.schedule_sections_retyped,
                            "detached_heading_bodies_merged":seg.detached_heading_bodies_merged,
                            "curation_patches_applied":seg.curation_patches_applied,
                            "multi_expression":True,
                            "expression_ordinal":inst.expression_ordinal},
                    duration_ms=int((time.time()-started)*1000))
            item["instrument_ids"] = ids
        report.append(item)
    if args.summary_only:
        report = [{
            "document_id":item["document_id"],
            "source_observation_id":item["source_observation_id"],
            "expressions":len(item["expressions"]),
            "provisions":sum(value["provisions"] for value in item["expressions"]),
            "s7_candidates":sum(value["s7_candidates"] for value in item["expressions"]),
            "document_blocks":item["document_blocks"],
            "expression_blocks":item["expression_blocks"],
            "apparatus_blocks":item["apparatus_blocks"],
            "applied":item["applied"],
        } for item in report]
    print(json.dumps(report,ensure_ascii=False,indent=2,default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
