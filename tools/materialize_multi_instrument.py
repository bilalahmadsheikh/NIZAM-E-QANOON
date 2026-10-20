"""Materialize source-reviewed internal instruments without copying source text.

This tool is deliberately bounded to documents whose boundary sequences were
reviewed against their immutable text blocks.  Default mode is a read-only
build/report.  ``--apply`` replaces one single-tree interpretation atomically
with disjoint expression trees plus one complete document block ledger.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import pathlib
import re
import time
from collections import Counter

from nizam.storage import legal_write
from nizam.storage.db import connect
from nizam.workers.segment import (APPENDIX_OPENER_CHOICES, NAMED_SCHEDULE_ROW_CHOICES, ORDER_SUFFIX_CHOICES,
                                   OWNER_CITED_LABEL_CHOICES,
                                   SCHEDULE_GROUP_CAPTION_CHOICES, SECTION_GROUP_CAPTION_CHOICES, SEGMENTER,
                                   SUBSTITUTED_SCHEDULE_CHOICES,
                                   DF_BLOCK_KEYS, build, infer_kind, same_blob_observation_problem,
                                   owner_decision_answer, reviewed_structural_overrides,
                                   run_identity)

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
# docs/03b edge vocabulary; `empowers`: a section authorises the rules made under it (doc 4428 s.26 -> the
# Sindh Public Procurement Rules, 2010; lead decision 11 Oct 2026).
PLAN_RELATIONS = {"amends", "empowers"}
# 0004 jurisdiction enum: a plan expression may state its own (doc 4347 E3; lead decision 12 Oct 2026)
PLAN_JURISDICTIONS = ("fed", "punjab", "sindh", "kp", "balochistan", "ict", "ajk", "gb")


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
# 1106 left this list on 8 Oct 2026: it is materialised from its reviewed plan
# (tools/evidence/multi-instrument-plans/doc-1106.json; owner export -e q1 split).
# 4434 stays on this list while its split is PAUSED (lead 13 Oct, pending the owner on the e3/e10/e20/e39
# boundary corrections): its reviewed plan is held as doc-4434-DRAFT.json; it leaves this list when that plan is
# renamed and materialised (test_document_4434_is_materialised_from_its_plan, skipped until then).
# 3389 left this list on 14 Oct 2026: it is materialised from its reviewed plan (doc-3389.json; agent JB, owner
# export j; E1 anchored at its printed title by split-doc-3389-boundaries.sql, the archived candidate cited).
# 4434 left for agent K5's reviewed 46-expression plan (lead 15-16 Oct; builder BZ, 16 Oct 2026)
# 3696 left for agent K4's realigned six-expression plan (delegated q2 'split-and-realign'; lead 16 Oct: a
# released change, the 128 path moves approved; builder BZ, 16 Oct 2026)
# 3912 uses its reviewed disjoint-span plan (Act pp21-24, Rules before and after).
PRIMARY_DOCUMENTS = {977, 3553, 4452}
# The owner's answer that lets a plan expression carry no year (migration 0063;
# doc 1973 q3 'undated', export -i).  A closed set: the database CHECK pins the
# same one choice.
UNDATED_CHOICES = frozenset({"undated"})
# The owner's answer that lets a plan expression be a dated HISTORICAL text,
# never current law (migration 0064; doc 4434 q3 'historical-expression',
# export k).  A closed set: the database CHECK pins the same one choice.
HISTORICAL_CHOICES = frozenset({legal_write.HISTORICAL_CHOICE})
# These are editorial compilations, not themselves legal instruments.
# 3423 left for its reviewed three-expression plan (agent K3; builder BZ, 16 Oct 2026)
# 3949 left for agent JF's reviewed five-expression plan (owner export m, 17 Oct answers; builder BZ, 17 Oct 2026)
COMPILATION_DOCUMENTS = {4440, 4497}
REVIEWED_DOCUMENTS = PRIMARY_DOCUMENTS | COMPILATION_DOCUMENTS | plan_documents()
# 885517 (agent DC, doc 4497 E1): 'Note:- The schedule to the Resolution has also been superseded by the Schedule
# attached to the Civil Service of Pakistan (Composition and Cadre) Rules,1954.' -- a note citing the next item's
# title; re-materialising from the active manifest re-ran _expanded_start and took it as E1's title block.
REJECTED_EDITORIAL_BOUNDARIES = {893415, 885517}
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


def resolve_current_expression(document_id: int, expression_ordinal: int) -> dict | None:
    """The active canonical instrument a historical expression names as the
    current expression of its work: {instrument_id, source_observation_id,
    earliest_version, historical}, or None unless exactly one resolves.  The
    stable key stored is (source_observation_id, expression_ordinal); the
    revision id is only reported (migration 0064)."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT i.id::text, i.source_observation_id,
                   (SELECT min(lower(v.validity)) FROM provision p
                      JOIN provision_version v ON v.provision_id=p.id
                     WHERE p.instrument_id=i.id)::text,
                   EXISTS (SELECT 1 FROM instrument_expression_manifest m
                            WHERE m.source_observation_id=i.source_observation_id
                              AND m.expression_ordinal=i.expression_ordinal
                              AND m.is_active AND m.historical_validity IS NOT NULL)
              FROM instrument i
             WHERE i.document_id=%s AND i.expression_ordinal=%s
               AND i.is_active AND i.duplicate_of IS NULL""",
                    (document_id, expression_ordinal))
        rows = cur.fetchall()
    if len(rows) != 1:
        return None
    instrument_id, observation, earliest, historical = rows[0]
    return {"instrument_id": instrument_id, "source_observation_id": observation,
            "earliest_version": earliest, "historical": historical}


def _iso_date(value, what: str):
    from datetime import date
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{what} {value!r} is not an ISO date") from None


def validate_historical(value: dict, ordinal: int, document_id: int, observation_id: int,
                        resolve_current=resolve_current_expression, today=None) -> dict | None:
    """Migration 0064: a plan expression's `version_validity` and
    `current_expression`, both or neither.  Refused unless the owner's
    'historical-expression' answer is cited (checked against the export by
    owner_decision_answer), from < to <= today, a historical_basis is given,
    and the current expression resolves to exactly one active, canonical,
    non-historical instrument that is not this expression and whose earliest
    version starts at or after `to`.  Returns the spec fields, or None."""
    from datetime import date
    validity, current = value.get("version_validity"), value.get("current_expression")
    if validity is None and current is None:
        return None
    if not isinstance(validity, dict) or not isinstance(current, dict):
        raise ValueError(f"plan expression {ordinal}: version_validity and current_expression "
                         "come together (a historical expression names the current one)")
    start = _iso_date(validity.get("from"), f"plan expression {ordinal} version_validity.from")
    end = _iso_date(validity.get("to"), f"plan expression {ordinal} version_validity.to")
    today = today or date.today()
    if not start < end <= today:
        raise ValueError(f"plan expression {ordinal}: version_validity needs from < to <= today "
                         f"({start} .. {end}, today {today})")
    citation = validity.get("owner_decision")
    choice = owner_decision_answer(citation, document_id).get("choice")
    if choice not in HISTORICAL_CHOICES:
        raise ValueError(f"plan expression {ordinal} version_validity owner_decision "
                         f"{citation.get('question_id')} choice {choice!r}, not one of "
                         f"{sorted(HISTORICAL_CHOICES)}")
    basis = validity.get("historical_basis")
    if not isinstance(basis, dict) or not basis:
        raise ValueError(f"plan expression {ordinal}: version_validity needs a historical_basis "
                         "citing the source of each bound")
    target_document, target_ordinal = current.get("document_id"), current.get("expression_ordinal")
    if type(target_document) is not int or type(target_ordinal) is not int or target_ordinal < 0:
        raise ValueError(f"plan expression {ordinal}: current_expression needs integer "
                         "document_id and expression_ordinal")
    if (target_document, target_ordinal) == (document_id, ordinal):
        raise ValueError(f"plan expression {ordinal}: current_expression names itself")
    resolved = resolve_current(target_document, target_ordinal)
    if resolved is None:
        raise ValueError(f"plan expression {ordinal}: current_expression document {target_document} "
                         f"expression {target_ordinal} does not resolve to exactly one active "
                         "canonical instrument")
    if (resolved["source_observation_id"], target_ordinal) == (observation_id, ordinal):
        raise ValueError(f"plan expression {ordinal}: current_expression resolves to itself")
    if resolved["historical"]:
        raise ValueError(f"plan expression {ordinal}: current_expression document {target_document} "
                         f"expression {target_ordinal} is itself historical")
    if resolved["earliest_version"] is not None and \
            _iso_date(resolved["earliest_version"], "earliest version") < end:
        raise ValueError(f"plan expression {ordinal}: the current expression's text opens "
                         f"{resolved['earliest_version']}, inside the historical window ending {end}")
    return {
        "version_validity": (start.isoformat(), end.isoformat()),
        "historical_owner_decision": dict(citation, choice=choice),
        "historical_basis": basis,
        "current_expression": {"document_id": target_document, "expression_ordinal": target_ordinal,
                               "source_observation_id": resolved["source_observation_id"],
                               "instrument_id_at_review": resolved["instrument_id"]},
    }


def validate_plan(plan: dict, blocks: list[dict], document_id: int,
                  observation_id: int, *, resolve_current=resolve_current_expression,
                  today=None) -> list[dict]:
    """Check a reviewed plan against the document's immutable blocks.

    Returns one specification per expression, ordered by ordinal, with each
    span resolved to reading-order index ranges.  Anything the plan does not
    state exactly is refused rather than guessed.  `resolve_current` and
    `today` are injectable for the historical-expression checks (0064).
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
        year_owner_decision = None
        if year is None:
            # Migration 0063: no year only on the owner's 'undated' for this
            # document, cited as {export, document_id, question_id} and checked
            # against the export here; never a year inferred from the text.
            if value.get("year_status") != "undated":
                raise ValueError(f"plan expression {ordinal} has no year: it needs "
                                 "year_status 'undated' and the owner's decision")
            citation = value.get("owner_decision")
            choice = owner_decision_answer(citation, document_id).get("choice")
            if choice not in UNDATED_CHOICES:
                raise ValueError(f"plan expression {ordinal} owner_decision "
                                 f"{citation.get('question_id')} choice {choice!r}, "
                                 f"not one of {sorted(UNDATED_CHOICES)}")
            if value.get("title_correction") is not None:
                raise ValueError(f"plan expression {ordinal} is undated: a "
                                 "title_correction (which sets a year) is refused")
            year_owner_decision = dict(citation, choice=choice)
        elif type(year) is not int or not 1800 <= year <= 2100:
            raise ValueError(f"plan expression {ordinal} needs an integer year")
        elif "year_status" in value:
            raise ValueError(f"plan expression {ordinal} has year {year}: "
                             "year_status is only for an undated expression")
        jurisdiction = value.get("jurisdiction")
        if jurisdiction is not None and (
                jurisdiction not in PLAN_JURISDICTIONS
                or not (value.get("jurisdiction_basis") or "").strip()):
            raise ValueError(f"plan expression {ordinal} jurisdiction {jurisdiction!r} must be one of "
                             f"{list(PLAN_JURISDICTIONS)} and carry a jurisdiction_basis")
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
        # Printed oddities the owner kept as printed (doc 1106: 'LORICULTURE',
        # '17th April, 1996', the bare '4.'); each names a block of this
        # expression and says what is printed and why it stands.
        anomalies = value.get("source_anomalies") or []
        for anomaly in anomalies:
            anchor = anomaly.get("source_block_id") if isinstance(anomaly, dict) else None
            if (anchor is None or claimed.get(position.get(anchor)) != ordinal
                    or not (anomaly.get("printed") or "").strip()
                    or not (anomaly.get("note") or "").strip()):
                raise ValueError(f"plan expression {ordinal} source anomaly {anomaly!r} needs a "
                                 "source_block_id inside its own span, printed and note")
        historical = validate_historical(value, ordinal, document_id, observation_id,
                                         resolve_current, today)
        specs.append({
            "historical": historical,
            "ordinal": ordinal, "role": value["role"], "title": title,
            "kind": value["kind"], "year": year, "number": value["number"],
            "year_owner_decision": year_owner_decision,
            "jurisdiction": jurisdiction, "jurisdiction_basis": value.get("jurisdiction_basis"),
            "ranges": ranges, "title_correction": correction,
            "relations": relations, "source_anomalies": anomalies,
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
    "source_schedule_form_group",
    # profile rules `unlabelled_schedule_opener`, `quoted_table_row_text` (doc
    # 691) and `printed_heading_override` (docs 1003, 999)
    "source_unlabelled_schedule_openers", "source_quoted_table_row_blocks",
    "source_printed_headings",
    # profile rule `order_suffix_label` (doc 999)
    "source_order_suffix_labels",
    # profile rule `named_schedule_row` (docs 1078, 1121)
    "source_named_schedule_rows",
    # profile rule `reviewed_contents_alignment` (doc 1368)
    "source_contents_row_links",
    # profile rule `schedule_group_caption` (doc 1106)
    "source_schedule_group_captions",
    # profile rule `owner_cited_label` (doc 1225)
    "source_owner_cited_labels",
    # profile rules `substituted_schedule_items`, `not_running_header_blocks`,
    # `level_cell_blocks` (doc 1431)
    "source_substituted_schedule_items", "source_not_running_header_blocks",
    "source_level_cell_blocks",
    # profile rule `half_paren_clause_label` (doc 1626)
    "source_half_paren_clause_blocks",
    # rules `contents_marker_block`, `heading_scan_section_only` (stage 3, agent DB)
    "source_contents_marker_blocks", "source_heading_scan_section_only",
    # rules `reviewed_decimal_cut`, `reviewed_table_row_blocks`, `reviewed_division_continues`,
    # `reviewed_marked_label_cut` (stage 3, agent DF)
    *DF_BLOCK_KEYS,
    # rule `decoded_underscore_dash` (stage 3, agent DE)
    "source_decoded_underscore_dash",
    # rule `reviewed_long_suffix_section` (stage 3, agent DE)
    "source_long_suffix_section_openers",
    # rules `reviewed_schedule_heading`, `reviewed_repeal_stub_cut` (stage 3, agent DC round 2, doc 2703)
    "source_schedule_heading_blocks", "source_repeal_stub_cut_blocks",
    # rules `reviewed_figure_subsections` (agent JE, doc 4521) and `reviewed_margin_note_pieces` (agent JE, doc 4426)
    "source_figure_subsections", "source_margin_note_pieces",
    # export j ports (13 Oct 2026, builder BZ): agents JE (rules 4, 5), JB (D flag, F, G, H, I), JA (C, E, F, G, H)
    "source_list_text_sections", "source_text_units", "source_division_openers", "source_division_captions",
    # rule `reviewed_contents_region` (agent JE, rule 6; docs 4400, 4137)
    "source_contents_region",
    # export j group 5 ports (agent JD)
    "source_chapter_line_blocks",
    "source_marked_dash_section_blocks",
    "source_subsection_line_cut_blocks",
    "source_contents_named_divisions",
    # export j group 6 ports (agent JD)
    "source_division_line_blocks",
    # export j group 7 ports (agent JD)
    "source_dotted_letter_item_blocks",
    "source_schedule_paragraph_headings",
    # export j/l group 8 ports (agent JD)
    "source_owner_schedule_parts",
    # group 10 ports (16 Oct): JE rules 8-12, K4, K5, K3
    # group 14 (agent JD)
    "source_clause_repeal_stub_blocks",
    # group 15 (agent K2 rule3)
    "source_table_close_blocks",
    # group 17 (agent K4 G-M)
    "source_half_paren_roman_blocks",
    "source_bare_half_paren_subrule_blocks",
    "source_inserted_row_blocks",
    "source_bare_serial_row_blocks",
    "source_form_code_openers",
    # group 18 (agent K2 rule4)
    "source_bound_notes",
    # group 38 (agent K6 reviewed_bracketed_rule)
    "source_bracketed_rules",
    # group 37 (agent K6 reviewed_lettered_head)
    "source_lettered_head_blocks",
    # group 33 (agent K6 reviewed_block_order, section_group_caption)
    "source_block_order_moves",
    "source_section_group_captions",
    # group 32 (agent K6 reviewed_division_series)
    "source_division_series_blocks",
    # group 29 (agent JF E)
    "source_decoded_quote_cut_blocks",
    # group 28 (agent K6 H)
    "source_inline_margin_notes",
    # group 27 (agent JF D)
    "source_schedule_row_cells",
    "source_unit_moves", "source_reviewed_grid_rows",
    # group 26 (agent JF A)
    "source_long_romanette_cut_blocks",
    # group 24 (agent K6 F)
    "source_hyphen_first_subsection_blocks",
    # group 23 (agent K6 E)
    "source_digit_led_clause_labels",
    # group 22 (agent K6 D)
    "source_fused_margin_tails",
    # group 19-20 (agent K4 Q, U, V; agent K6 C)
    "source_part_line_blocks",
    "source_dotted_serial_row_blocks",
    "source_division_unit_openers",
    "source_division_note_blocks",
    # group 11 (agent K2)
    "source_quoted_insertion_spans",
    "source_label_moves",
    "source_half_paren_subrule_blocks",
    "source_contents_page_column",
    "source_unstopped_contents_rows",
    "source_chapter_opener_blocks",
    "source_dash_label_section_blocks",
    "source_heading_line_stub_blocks",
    "source_heading_lines",
    "source_hyphen_rule_numbers",
    "source_marked_subsection_cut_blocks",
    "source_note_owner_blocks",
    "source_paired_repeal_stubs",
    "source_percent_clause_blocks",
    "source_printed_rule_openers",
    "source_quote_span_end_blocks",
    "source_quoted_appendix_labels",
    "source_section_word_part_blocks",
    "source_set_aside_units",
    "source_statute_row_headings",
    "source_explanation_of_heading",
    "source_no_cut_blocks",
    "source_margin_heading_owners",
    "source_root_reparent_blocks",
    "source_chapter_over_part",
    "source_contents_schedule_rows",
    "source_form_text_blocks",
    "source_lettered_part_blocks",
    "source_unheaded_section_blocks")
# The recorder's reading keys that carry no parser override (tools/record_curation_patch.py READING_KEYS minus its
# STRUCTURAL_KEYS; a test holds the two lists equal).  A reading or recorded patch naming any other key is REFUSED,
# never silently dropped (lead 13 Oct, after agent JE's doc 4431: a dry-run build without the reading's new key is a
# different tree from the one the recorded reading will build).
NON_STRUCTURAL_READING_KEYS = frozenset({
    "document_id", "page_no", "match_text", "before_text", "after_text", "observed", "defect", "fixes", "render",
    "render_sha256", "additional_render", "additional_render_sha256", "extracted_number", "printed_number",
    "all_observations", "owner_decision", "evidence", "id", "exact_block_locator", "source_block_id"})


def unknown_patch_key_problem(patches: list[dict], *, structural_allowed: bool = True) -> str | None:
    """Why a build must refuse these recorded patches, or None: a structural override key this materializer does not
    know (it would be dropped), or -- on the legacy route, which carries none -- any structural override at all."""
    for patch in patches:
        keys = set(((patch.get("evidence") or {}).get("structural_overrides") or {}))
        unknown = sorted(keys - set(STRUCTURAL_PATCH_KEYS))
        if unknown:
            return (f"curation patch {patch.get('id')} carries structural override key(s) {unknown} "
                    "the materializer does not know")
        if keys and not structural_allowed:
            return (f"curation patch {patch.get('id')} carries structural overrides {sorted(keys)}, which the "
                    "legacy route does not apply; the document needs a reviewed plan")
    return None


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
        unknown = sorted(set(reading) - set(STRUCTURAL_PATCH_KEYS) - NON_STRUCTURAL_READING_KEYS)
        if unknown:
            raise ValueError(f"reading {index} carries key(s) {unknown} the materializer does not know; "
                             "refused rather than dropped")
        overrides = {key: reading[key] for key in STRUCTURAL_PATCH_KEYS if key in reading}
        # As the recorder does: an opener citing an owner decision must cite
        # an answer the export holds (profile rule `unnumbered_root_provision`).
        for opener in (list(overrides.get("source_unnumbered_section_openers") or [])
                       + list(overrides.get("source_unlabelled_schedule_openers") or [])
                       + list(overrides.get("source_printed_headings") or [])
                       + list(overrides.get("source_order_suffix_labels") or [])
                       + list(overrides.get("source_contents_row_links") or [])):
            if "owner_decision" in opener:
                owner_decision_answer(opener["owner_decision"], document_id)
        for row in overrides.get("source_named_schedule_rows") or []:
            choice = owner_decision_answer(row["owner_decision"], document_id).get("choice")
            if choice not in NAMED_SCHEDULE_ROW_CHOICES:
                raise ValueError(f"reading {index} named schedule row cites choice {choice!r}, "
                                 "not one asking for rows by post name")
        for opener in overrides.get("source_unlabelled_schedule_openers") or []:
            if opener.get("label") == "APPENDIX":
                choice = owner_decision_answer(opener["owner_decision"], document_id).get("choice")
                if choice not in APPENDIX_OPENER_CHOICES:
                    raise ValueError(f"reading {index} unlabelled APPENDIX opener cites choice {choice!r}, "
                                     "not one asking for appendix rows")
        for group in overrides.get("source_order_suffix_labels") or []:
            choice = owner_decision_answer(group["owner_decision"], document_id).get("choice")
            if choice not in ORDER_SUFFIX_CHOICES:
                raise ValueError(f"reading {index} order suffix cites choice {choice!r}, not 'keep-both'")
        for span in overrides.get("source_substituted_schedule_items") or []:
            choice = owner_decision_answer(span["owner_decision"], document_id).get("choice")
            if choice not in SUBSTITUTED_SCHEDULE_CHOICES:
                raise ValueError(f"reading {index} substituted schedule cites choice {choice!r}, "
                                 "not 's2-text'")
        for cited in overrides.get("source_owner_cited_labels") or []:
            choice = owner_decision_answer(cited["owner_decision"], document_id).get("choice")
            if choice not in OWNER_CITED_LABEL_CHOICES:
                raise ValueError(f"reading {index} owner cited label cites choice {choice!r}, "
                                 "not the contents numbering")
        for caption in overrides.get("source_schedule_group_captions") or []:
            choice = owner_decision_answer(caption["owner_decision"], document_id).get("choice")
            if choice not in SCHEDULE_GROUP_CAPTION_CHOICES:
                raise ValueError(f"reading {index} schedule group caption cites choice {choice!r}, "
                                 "not one asking for rows by group caption")
        for caption in overrides.get("source_section_group_captions") or []:   # agent K6 section_group_caption (group 33)
            choice = owner_decision_answer(caption["owner_decision"], document_id).get("choice")
            if choice not in SECTION_GROUP_CAPTION_CHOICES:
                raise ValueError(f"reading {index} section group caption cites choice {choice!r}, "
                                 "not one asking for the section's caption divisions")
        patch_evidence = {"structural_overrides": overrides} if overrides else {}
        if "exact_block_locator" in reading:
            if (reading["exact_block_locator"] is not True or type(reading.get("source_block_id")) is not int
                    or reading["match_text"] != reading["before_text"]):
                raise ValueError(f"reading {index} has a malformed exact-block locator")
            patch_evidence.update(exact_block_locator=True, source_block_id=reading["source_block_id"])
        shaped.append({
            "id": f"unrecorded-{index}", "page_no": reading["page_no"],
            "match_text": reading["match_text"], "before_text": reading["before_text"],
            "after_text": reading["after_text"],
            "evidence": patch_evidence,
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


# Doc 4497 (ESTACODE, Edition 2021) prints a running title on every page, carrying the chapter and the page
# number in either order: 'CHAPTER-2 ESTACODE (EDITION-2021) Page -17', 'Page - 18 ESTACODE (EDITION-2021)
# CHAPTER-2', and 'INDEX ESTACODE (EDITION-2021) Page-968' / 'Page-969 ESTACODE (EDITION-2021) INDEX'.  No two are
# equal, so the segmenter's repetition proof never makes them running headers, and the 'CHAPTER-2 ...' form opens
# a Chapter.  The exact printed shapes, whole block, this document only (agent DC, stage 3).
_ESTACODE_RUNNING_TITLE = re.compile(
    r"\s*(?:(?:CHAPTER\s*-\s*\d{1,2}|INDEX)\s+ESTACODE\s+\(EDITION\s*-\s*2021\)\s+Page\s*-\s*\d{1,4}"
    r"|Page\s*-\s*\d{1,4}\s+ESTACODE\s+\(EDITION\s*-\s*2021\)\s+(?:CHAPTER\s*-\s*\d{1,2}|INDEX))\s*")


def _estacode_running_titles(document_id: int, span: list[dict], patches: list[dict]) -> dict | None:
    # Doc 4497 only: its running titles, plus the structural keys of its own reviewed readings (this legacy path
    # passes none otherwise; 4497 records none today, so only new readings are affected).
    if document_id != 4497:
        return None
    overrides = dict(reviewed_structural_overrides([], patches) or {})
    ids = [block["id"] for block in span if _ESTACODE_RUNNING_TITLE.fullmatch(block["text"] or "")]
    if ids:
        overrides["source_running_header_blocks"] = ids
    return overrides or None


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


_HISTORICAL_KEYS = ("ordinal", "id", "start_block_id", "valid_from", "valid_to",
                    "current_source_observation_id", "current_expression_ordinal", "evidence")


def active_historical_manifests(observation_id: int) -> dict[int, dict]:
    """The observation's active manifests that declare a historical window (0064), by ordinal."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT expression_ordinal, id::text, start_block_id,
                   lower(historical_validity)::text, upper(historical_validity)::text,
                   current_source_observation_id, current_expression_ordinal, evidence
              FROM instrument_expression_manifest
             WHERE source_observation_id=%s AND is_active
               AND historical_validity IS NOT NULL""", (observation_id,))
        return {row[0]: dict(zip(_HISTORICAL_KEYS, row)) for row in cur.fetchall()}


def apply_historical(inst, manifest: dict, fields: dict):
    """Write one expression's reviewed historical window onto its instrument (bounded versions) and its
    manifest (the three 0064 columns and the evidence the CHECK requires). Returns the new instrument."""
    current = fields["current_expression"]
    manifest["historical_validity"] = list(fields["version_validity"])
    manifest["current_source_observation_id"] = current["source_observation_id"]
    manifest["current_expression_ordinal"] = current["expression_ordinal"]
    manifest["evidence"]["historical_basis"] = fields["historical_basis"]
    manifest["evidence"]["historical_owner_decision"] = fields["historical_owner_decision"]
    manifest["evidence"]["current_expression"] = current
    return dataclasses.replace(inst, version_validity=tuple(fields["version_validity"]))


def carry_historical(insts: list, manifests: list[dict], active: dict[int, dict]) -> list:
    """The listed-document path (no plan): carry each active historical manifest's window forward onto the
    rebuilt expression of the same ordinal and first block, or refuse -- a replay never writes a historical
    text as open-ended current law (migration 0064, schema review hazard A)."""
    rebuilt = {inst.expression_ordinal for inst in insts}
    lost = sorted(set(active) - rebuilt)
    if lost:
        raise ValueError(f"historical expressions {lost} are not rebuilt by this materialisation; "
                         "withdraw them explicitly first (0064)")
    carried = []
    for inst, manifest in zip(insts, manifests):
        row = active.get(inst.expression_ordinal)
        if row is None:
            carried.append(inst)
            continue
        if manifest["start_block_id"] != row["start_block_id"]:
            raise ValueError(
                f"expression {inst.expression_ordinal} is historical (manifest {row['id']}) but now starts at "
                f"block {manifest['start_block_id']}, not {row['start_block_id']}; refused rather than "
                "carrying the window onto a different expression")
        evidence = row["evidence"] or {}
        current = dict(evidence.get("current_expression") or {},
                       source_observation_id=row["current_source_observation_id"],
                       expression_ordinal=row["current_expression_ordinal"])
        inst = apply_historical(inst, manifest, {
            "version_validity": (row["valid_from"], row["valid_to"]),
            "historical_basis": evidence.get("historical_basis"),
            "historical_owner_decision": evidence.get("historical_owner_decision"),
            "current_expression": current})
        manifest["evidence"]["historical_carried_from_manifest_id"] = row["id"]
        carried.append(inst)
    return carried


def pending_owner_choices(manifests: list[dict]) -> list[tuple[int, str]]:
    """Historical windows whose basis still marks an owner choice open (historical_basis.pending_owner):
    reportable in a dry run, refused by --apply."""
    return [(int(m["expression_ordinal"]), str(m["evidence"]["historical_basis"]["pending_owner"]))
            for m in manifests
            if isinstance(m["evidence"].get("historical_basis"), dict)
            and m["evidence"]["historical_basis"].get("pending_owner")]


def s7_itemization_detail(seg, structural_decisions: list) -> dict:
    """The run detail S7 reads: `repeated_labels_demoted` is the ITEMIZED count -- one per candidate row written; a
    collision settled by review writes none (nizam/workers/segment.py does the same) -- with the raw parser count kept
    beside it as a diagnostic (S7 itemization mismatches on docs 3392, 3782, 3949, 4431; agent BZ, 17 Oct 2026)."""
    return {"repeated_labels_demoted": len(structural_decisions),
            "repeated_labels_demoted_raw": seg.repeated_labels_demoted}


def twin_observation_problem(document_id: int,observation_id: int,plan_observation_id) -> str | None:
    """Why `observation_id` may NOT be built from the plan reviewed for `plan_observation_id`, or None.

    Allowed only for a same-blob twin: both observations landed the document's own file, the twin's every active
    instrument is a recorded duplicate (it publishes nothing), and the plan's observation holds the document's
    active canonical expressions. Readings and profile parity is checked before any build by
    same_blob_observation_problem (doc 4419)."""
    if type(plan_observation_id) is not int:
        return f"document {document_id}: the plan names no source observation"
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT o.id, o.outcome::text, o.sha256 = d.sha256
              FROM source_observation o, document d
             WHERE d.id=%s AND d.is_active AND o.id = ANY(%s)""",
                    (document_id,[observation_id,plan_observation_id]))
        rows = {row[0]: row[1:] for row in cur.fetchall()}
        cur.execute("""
            SELECT count(*) FILTER (WHERE duplicate_of IS NULL), count(*)
              FROM instrument WHERE document_id=%s AND is_active AND source_observation_id=%s""",
                    (document_id,observation_id))
        twin_canonical,twin_total = cur.fetchone()
        cur.execute("""
            SELECT count(*) FROM instrument
             WHERE document_id=%s AND is_active AND duplicate_of IS NULL AND source_observation_id=%s""",
                    (document_id,plan_observation_id))
        plan_canonical = cur.fetchone()[0]
    for obs in (observation_id,plan_observation_id):
        if rows.get(obs) != ("landed",True):
            return (f"plan is for observation {plan_observation_id}, not {observation_id}: observation {obs} "
                    f"did not land document {document_id}'s own file")
    if twin_total == 0 or twin_canonical:
        return (f"plan is for observation {plan_observation_id}, not {observation_id}: a twin observation is "
                "rebuilt from its canonical's plan only while every active instrument of it is a recorded duplicate")
    if plan_canonical == 0:
        return f"plan observation {plan_observation_id} holds no active canonical expression of document {document_id}"
    return None


def prepare_from_plan(document_id: int,plan: dict,observation_id: int | None = None,
                      extra_readings: list[dict] | None = None,
                      profile: str | None = None,
                      allow_empty: bool = False) -> tuple[list, list, list, list]:
    """Build every expression a reviewed plan names (see PLAN_DIRECTORY)."""
    outer = _outer(document_id,observation_id)
    observation = outer["source_observation_id"]
    if observation != plan.get("source_observation_id"):
        # A same-blob twin observation (S8: readings are recorded on every observation of one file, doc 4497/
        # 1038 and 616) is rebuilt from its canonical observation's plan; nothing else may borrow a plan.
        problem = twin_observation_problem(document_id,observation,plan.get("source_observation_id"))
        if problem:
            raise ValueError(problem)
        plan = dict(plan,source_observation_id=observation)
    blocks = legal_write.blocks_for(document_id)
    specs = validate_plan(plan,blocks,document_id,observation)
    owner = {blocks[index]["id"]: spec["ordinal"] for spec in specs
             for first,last in spec["ranges"] for index in range(first,last + 1)}
    boundary = plan_boundaries(specs,blocks,_boundary_rows(observation))
    stored = legal_write.segmentation_patches_for(observation)
    problem = unknown_patch_key_problem(stored)
    if problem:
        raise ValueError(f"document {document_id}: {problem}")
    patches = stored + unrecorded_readings(extra_readings or [],stored,document_id)
    assigned,outside = assign_patches(blocks,patches,owner)
    resolutions = legal_write.structural_resolutions_for(document_id)
    as_at = legal_write.observed_on(observation)
    active_historical = active_historical_manifests(observation)
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
            # meta_year is unused beside a reviewed identity; None, never 'None'.
            None if spec["year"] is None else str(spec["year"]),
            outer["source_url"],span,as_at,span_patches,
            toc_dispositions=legal_write.toc_dispositions_for(observation,ordinal),
            structural_resolutions=span_resolutions,
            structural_overrides=overrides,
            detect_contents=spec["detect_contents"],
            force_opening_contents=spec["force_opening_contents"],
            expression_ordinal=ordinal,expression_role=spec["role"],profile=profile,
            reviewed_identity={"kind": spec["kind"],"year": spec["year"],
                               "number": spec["number"],
                               "jurisdiction": spec["jurisdiction"]})
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
        if spec["year_owner_decision"] is not None:
            # The shape migration 0063's CHECK requires of a NULL detected_year.
            if inst.year is not None:
                raise ValueError(f"expression {ordinal} is undated by the owner but "
                                 f"built with year {inst.year}")
            evidence["year_status"] = "undated"
            evidence["year_owner_decision"] = spec["year_owner_decision"]
        if spec["jurisdiction"] is not None:
            evidence["jurisdiction"] = {"value": spec["jurisdiction"],
                                        "basis": spec["jurisdiction_basis"]}
        if spec["title_correction"]:
            evidence["title_correction"] = spec["title_correction"]
        if spec.get("source_anomalies"):
            evidence["source_anomalies"] = spec["source_anomalies"]
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
        if spec["historical"] is not None:
            # Migration 0064: the owner's historical expression -- bounded versions, a windowed manifest.
            insts[-1] = apply_historical(insts[-1], manifests[-1], spec["historical"])
        elif ordinal in active_historical:
            raise ValueError(
                f"plan expression {ordinal} has no version_validity, but its active manifest "
                f"{active_historical[ordinal]['id']} declares it historical "
                f"[{active_historical[ordinal]['valid_from']}, {active_historical[ordinal]['valid_to']}); "
                "carry the window in the plan, or withdraw it explicitly by migration (0064)")
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
    # The legacy route applies recorded structural overrides only for doc 4497 (_estacode_running_titles); any
    # other legacy document's reviewed structural reading would be dropped, so it is refused (lead 13 Oct).
    problem = unknown_patch_key_problem(patches, structural_allowed=document_id == 4497)
    if problem:
        raise ValueError(f"document {document_id}: {problem}")
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
        # The listed documents are materialised, so every expression's year is
        # its stored manifest/instrument year.  A missing one is refused, never
        # filled from the catalogue's year (that fallback would infer a year;
        # INV-1): an undated expression needs a reviewed plan (migration 0063).
        if spec["year"] is None:
            raise ValueError(f"expression {ordinal} ({spec['title']!r}) has no year; "
                             "an undated expression is built only from a reviewed plan")
        inst,seg = build(
            document_id,outer["sha256"],outer["source_observation_id"],
            outer["source_id"],spec["title"],
            str(spec["year"]),outer["source_url"],
            span,as_at,assigned.get(ordinal,[]),expression_ordinal=ordinal,
            # agent DC, doc 4497: its page-numbered running titles are running headers (M2).
            structural_overrides=_estacode_running_titles(document_id,span,assigned.get(ordinal,[])),
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
    # Migration 0064: a historical expression keeps its reviewed window through a listed replay, or the replay
    # is refused (never written as open-ended current law).
    insts = carry_historical(insts,manifests,
                             active_historical_manifests(outer["source_observation_id"]))
    return insts,segs,manifests,blocks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document",type=int,action="append",required=True)
    parser.add_argument("--observation",type=int,
                        help="materialize one provenance observation of a shared blob")
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--require-all-released",action="store_true",
                        help="--apply: require every rebuilt expression to pass the release view before commit")
    parser.add_argument("--summary-only",action="store_true")
    parser.add_argument("--unrecorded-readings",
                        help="plan documents, report mode only: a readings JSON "
                             "(tools/record_curation_patch.py format) applied as if recorded")
    parser.add_argument("--approve-release-change",metavar="REASON",
                        default=os.environ.get("NIZAM_APPROVE_RELEASE_CHANGE"),
                        help="--apply only: replace RELEASED expressions although the rebuild "
                             "differs: '<reason; owner approval ref>', recorded in each changed "
                             "manifest's evidence and run detail (identical rebuilds pass)")
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
        # Fail closed BEFORE building: same-blob observations must carry the same readings and profile (doc 4419).
        same_blob = same_blob_observation_problem(document_id)
        if same_blob:
            raise ValueError(same_blob)
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
            pending = pending_owner_choices(manifests)
            if pending:
                raise ValueError(
                    f"document {document_id}: historical windows still await the owner's choice "
                    f"{pending}; resolve historical_basis.pending_owner in the plan before --apply")
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
                    "title_correction","relations","source_anomalies","source_spans",
                    "historical_basis","current_expression")
                   if key in manifest["evidence"]},
                **({"version_validity": list(inst.version_validity)}
                   if inst.version_validity is not None else {}),
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
            save_report: dict = {}
            ids = legal_write.save_many(insts,blocks,manifests,writer,
                                        approve_release_change=args.approve_release_change,
                                        report=save_report,
                                        require_all_released=args.require_all_released)
            identity = run_identity(profile)
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
                            **s7_itemization_detail(seg,inst.structural_decisions),
                            "schedule_sections_retyped":seg.schedule_sections_retyped,
                            "detached_heading_bodies_merged":seg.detached_heading_bodies_merged,
                            "curation_patches_applied":seg.curation_patches_applied,
                            "multi_expression":True,
                            "expression_ordinal":inst.expression_ordinal,
                            **identity,
                            # the run's approval reason whenever given (a newly released expression included;
                            # tools/released_count_guard.py reads it, 12 Oct 2026)
                            **({"release_change_approval":" ".join(args.approve_release_change.split())}
                               if args.approve_release_change else {}),
                            **({"release_change":save_report["release_changes"][inst.expression_ordinal],
                                "release_change_approval":save_report["release_change_approval"]}
                               if inst.expression_ordinal in save_report.get("release_changes",{})
                               else {})},
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
