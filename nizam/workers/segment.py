"""Run L1 segmentation over the corpus — Document 02 §5.

    uv run python -m nizam.workers.segment --all
    uv run python -m nizam.workers.segment --document 4624
    uv run python -m nizam.workers.segment --source pk-federal --limit 50

Every run records its table-of-contents agreement in `segmentation_run`, which
is the acceptance test doc 02 §5 names. A document whose contents and body do not
agree is not silently published: it is a queryable defect.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import pathlib
import re
import sys
import time

from nizam.corpus.segment import assign_paths, segment
from nizam.shared.corpus_types import SegmentedInstrument
from nizam.storage import legal_write
from nizam.storage.db import connect

SEGMENTER = "nizam.corpus.segment/59"


def segmenter_identity(profile: str = "default") -> str:
    """The writer identity stored with a tree built under `profile`.

    The default profile keeps the bare SEGMENTER string, so every tree built
    without a pin records exactly what it recorded before profiles existed.
    """
    return SEGMENTER if profile == "default" else f"{SEGMENTER}+{profile}"

# A corpus-wide destructive replay invalidates instrument-keyed review rows.
# It must therefore run through ``./nz full-replay --apply``, which snapshots,
# repairs those rows, re-adjudicates the machine-safe subset, and enforces the
# release/S7/TOC regression gates.  Bounded replays are intentionally exempt.
_MANAGED_FULL_REPLAY_ENV = "NIZAM_MANAGED_FULL_REPLAY"

# Any stable 64-bit number; it only has to match across processes.
_LOCK_KEY = 0x4E495A414D534547        # "NIZAMSEG"


@contextlib.contextmanager
def only_one_run():
    """Refuse to start while another segmentation run is going.

    Two concurrent runs interleave their delete-and-rebuild of the same
    instruments. The first time that happened it produced 456 spurious
    uq_instrument_document violations that read like a code fault; the second
    time it wrote 2,321 documents twice, half of them under stale code, and
    every corpus-wide number was meaningless until both were killed.

    A Postgres advisory lock is the right place for this rather than a lockfile:
    the database drops it when the connection goes, so a killed run never leaves
    a stale lock behind.
    """
    with connect(autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", (_LOCK_KEY,))
        if not cur.fetchone()[0]:
            raise SystemExit(
                "another segmentation run holds the lock -- refusing to start.\n"
                "  see it:   pgrep -af nizam.workers.segment\n"
                "  stop it:  pkill -f 'nizam[.]workers[.]segment'")
        try:
            yield
        finally:
            cur.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_KEY,))

# source_id -> the jurisdiction enum of doc 03 §1.1
JURISDICTION = {"pk-federal": "fed", "pk-punjab": "punjab", "pk-sindh": "sindh",
                "pk-kp": "kp", "pk-balochistan": "balochistan"}

# Instrument kind, decided from the title. Order matters: "Amendment Ordinance"
# is an ordinance, and "Rules" beats "Act" because a title like "Rules made under
# the X Act" is Rules.
KIND_RULES = [
    ("constitution", re.compile(r"\bconstitution\b", re.I)),
    ("rules",        re.compile(r"\brules?\b", re.I)),
    ("regulation",   re.compile(r"\bregulations?\b", re.I)),
    ("ordinance",    re.compile(r"\bordinance\b", re.I)),
    ("order",        re.compile(r"\border\b", re.I)),
    ("notification", re.compile(r"\bnotification\b", re.I)),
    ("sro",          re.compile(r"\bS\.?R\.?O\.?\b", re.I)),
    ("act",          re.compile(r"\bact\b", re.I)),
]

ACT_NUMBER = [
    re.compile(r"\b(?:ACT|ORDINANCE)\s+(?:No\.?\s*)?([IVXLCDM]+|\d{1,3})\s+OF\s+(\d{4})", re.I),
    re.compile(r"\(\s*([IVXLCDM]+|\d{1,3})\s+of\s+(\d{4})\s*\)", re.I),
]
YEAR = re.compile(r"\b(1[89]\d{2}|20[0-4]\d)\b")


def infer_kind(title: str) -> str:
    terminal = re.search(
        r"\b(Act|Ordinance|Rules?|Regulations?|Order|Notification)\b"
        r"\s*,?\s*(?:1[89]\d{2}|20[0-4]\d)?\s*[.)\]]*\s*$",
        re.sub(r"\s+", " ", title or "").strip(), re.I)
    if terminal:
        value = terminal.group(1).lower()
        return {"rule": "rules", "rules": "rules",
                "regulations": "regulation"}.get(value, value)
    for kind, pat in KIND_RULES:
        if pat.search(title or ""):
            return kind
    return "act"


def infer_number(head_text: str, expect_year: int | None = None) -> str | None:
    """This instrument's own number -- not a number it happens to mention.

    Statutes cite each other constantly ("in exercise of the powers conferred by
    section 3 of the West Pakistan Act VIII of 2014..."), and taking the first
    match makes the citation of another Act into this Act's identity. Measured on
    this corpus: 22.5% of numbers extracted that way belonged to a different Act,
    which is how eight unrelated Punjab and Sindh instruments all became
    "rules VIII of 2014".

    The test is the year printed beside the number. An Act's own citation carries
    its own year, so "XIV of 2025" inside a 1965 Ordinance is a reference, not an
    identity. Where no candidate agrees, the number is left NULL: unknown is a
    weaker claim than wrong, and doc 02 §7 already allows identity to rest on
    jurisdiction, type and year with the number added when it is known.
    """
    for pat in ACT_NUMBER:
        for m in pat.finditer(head_text):
            year = int(m.group(2))
            if expect_year is None or year == expect_year:
                return m.group(1).upper()
    return None


def infer_year(title: str, meta_year: str | None, head_text: str) -> int:
    # The terminal year identifies the legal form in titles such as
    # ``Revival of the Constitution of 1973 Order, 1985``.  Taking the first
    # year silently turns a 1985 Order into a 1973 instrument.
    title_text = re.sub(
        r"\([^)]*(?:official website|under review|dated\s+\d{1,2}[-/])[^)]*\)\s*$",
        "", title or "", flags=re.I,
    )
    legal_form_years = re.findall(
        r"\b(?:Act|Ordinance|Rules?|Regulations?|Order|Notification)\b"
        r"\s*,?\s*(1[89]\d{2}|20[0-4]\d)\b",
        title_text, re.I,
    )
    if legal_form_years:
        return int(legal_form_years[-1])
    title_years = YEAR.findall(title_text)
    if title_years:
        return int(title_years[-1])
    for candidate in (meta_year or "", head_text[:1500]):
        m = YEAR.search(str(candidate))
        if m:
            return int(m.group(1))
    return 1900


def build(document_id: int, sha256: str, source_observation_id: int,
          source_id: str, title: str | None, meta_year: str | None,
          source_url: str | None, blocks: list[dict], as_at: str,
          curation_patches: list[dict] | None = None,
          toc_dispositions: list[dict] | None = None,
          structural_resolutions: list[dict] | None = None,
          split_fused_margins: bool = False,
          detect_contents: bool = True,
          force_opening_contents: bool = False,
          structural_overrides: dict | None = None,
          expression_ordinal: int = 0,
          expression_role: str = "primary",
          profile: str | None = None,
          reviewed_identity: dict | None = None) -> tuple:
    # `reviewed_identity` ({"kind", "year", "number"}) is a source-reviewed
    # expression plan's identity (tools/materialize_multi_instrument.py).  A
    # title such as "Notification ... (amending the X Rules, 1996)" infers as
    # Rules of 1996; the plan says a 2003 notification.  Absent, nothing changes.
    # The profile is the observation's pin unless the caller names one, so the
    # worker, the multi-instrument materializer and every stale-tree or
    # fingerprint tool build a pinned document the same way.
    if profile is None:
        profile = legal_write.segmentation_profile_for(source_observation_id)
    # The default parse calls segment() exactly as before profiles existed,
    # which keeps tools that substitute an older segmenter module working.
    profile_kwargs = {} if profile == "default" else {"profile": profile}
    seg = segment(blocks, curation_patches=curation_patches,
                  toc_dispositions=toc_dispositions,
                  structural_resolutions=structural_resolutions,
                  split_fused_margins=split_fused_margins,
                  detect_contents=detect_contents,
                  force_opening_contents=force_opening_contents,
                  structural_overrides=structural_overrides,
                  **profile_kwargs)
    head = " ".join(b["text"] for b in blocks[:40])[:4000]

    # The ltree prefix carries instrument identity, exactly as doc 03 §2.2 writes
    # it: fed.act.1860_45.ch_XVI.s_302.cl_c. It is not decoration -- provision.path
    # is globally UNIQUE, so a shared prefix makes every instrument's "s_1" collide
    # with every other's. Where the act number is unknown (23.6% of the corpus)
    # the document id stands in, which is stable across re-runs because
    # re-segmentation replaces an instrument rather than creating a new one.
    jur = JURISDICTION.get(source_id, "fed")
    kind = infer_kind(title or "")
    year = infer_year(title or "", meta_year, head)
    number = infer_number(head, year)
    if reviewed_identity is not None:
        kind = reviewed_identity["kind"]
        year = int(reviewed_identity["year"])
        number = reviewed_identity["number"]
    # The document id is always present, not only when the number is missing.
    #
    # Doc 03 §2.2 writes the path as fed.act.1860_45..., which assumes one
    # instrument per (jurisdiction, kind, number, year). This corpus does not
    # satisfy that yet: the same Act is published on more than one portal and
    # scraped as different blobs, so 1,004 documents collided on a shared prefix
    # -- "punjab.act.y1908_V" is not unique when two documents both parse as
    # Act V of 1908. Until instruments are deduplicated across sources, the
    # document id is what makes provision.path globally unique. It is stable
    # across re-runs because re-segmenting replaces an instrument in place.
    num = re.sub(r"[^A-Za-z0-9]+", "", number) if number else None
    expression_suffix = f"_e{expression_ordinal}" if expression_ordinal else ""
    ident = (f"{num}_o{source_observation_id}{expression_suffix}" if num else
             f"o{source_observation_id}{expression_suffix}")
    prefix = f"{jur}.{kind}.y{year}_{ident}"
    paths = assign_paths(seg, prefix)
    # Stable per-node keys so the writer can wire parent_id in one pass.
    keys = {id(node): i for i, (node, _) in enumerate(paths)}
    rows = []
    for i, (node, path) in enumerate(paths):
        parent = node.parent
        rows.append({
            "key": i,
            "parent_key": keys.get(id(parent)) if parent is not None and parent.parent is not None
                          or (parent is not None and parent.kind != "instrument") else None,
            "path": path,
            "kind": node.kind,
            "label": node.label[:200],
            "heading": (node.heading or None),
            "marginal_note": (node.marginal_note or None),
            "ordinal": i,
            "first_page": node.first_page,
            "last_page": node.last_page,
            "first_block": node.first_block,
            "text": node.text or None,
            "operation": node.operation,
            "amendment_note": node.amendment_note,
            "amended_by_id": node.amended_by_id,
            "toc_disposition_assertion_id": node.toc_disposition_assertion_id,
        })

    # Translate the segmenter's node-keyed ledger into row keys the writer can
    # resolve to provision ids.
    node_key = {id(node): i for i, (node, _) in enumerate(paths)}
    chars_by_block = {b["id"]: len(b["text"]) for b in blocks if b.get("id") is not None}
    ledger = []
    for block_id, (role, node) in seg.block_roles.items():
        key = node_key.get(id(node)) if node is not None else None
        if role == "body" and key is None:
            role = "unassigned"
        ledger.append((block_id, role, key, chars_by_block.get(block_id, 0)))

    # The contents list, with each entry's node resolved to a row key the writer
    # can turn into a provision id.
    toc_rows = [{"ordinal": e["ordinal"],
                 "label": (e["label"] or "")[:200],
                 "heading": (e["heading"] or None),
                 "kind": e["kind"],
                 "source_block_id": e.get("source_block_id"),
                 "source_char_offset": e.get("source_char_offset"),
                 "source_page": e.get("source_page"),
                 "provision_key": node_key.get(id(e["node"])) if e["node"] is not None else None,
                 "method": e["method"]}
                for e in seg.toc_entries]

    structural_decisions = []
    for decision in seg.repeated_label_decisions:
        # A collision a reviewer settled from the rendered page is not an open
        # question. The tree still demotes the unit exactly as before; what is
        # not written is a fresh candidate row, which `v_structural_
        # adjudication_pending` would hold open forever because migration 0036
        # keeps every resolution but `accept_non_citable`.
        if decision.get("settled_by_review"):
            continue
        candidate = decision["candidate"]
        canonical = decision["canonical"]
        parent = decision["parent"]
        structural_decisions.append({
            "candidate_key": node_key[id(candidate)],
            "canonical_key": node_key[id(canonical)],
            "parent_key": node_key.get(id(parent)) if parent is not None else None,
            "decision_kind": "repeated_sibling_label",
            "original_kind": decision["original_kind"],
            "printed_label": decision["printed_label"],
            "source_block_id": candidate.first_block,
            "source_page": candidate.first_page,
            "canonical_source_block_id": canonical.first_block,
            "canonical_source_page": canonical.first_page,
            "proposed_resolution": "retype_non_citable",
            "evidence": {
                "same_parent": True,
                "candidate_after_canonical": (
                    candidate.first_block is not None
                    and canonical.first_block is not None
                    and candidate.first_block >= canonical.first_block),
                "parent_kind": parent.kind if parent is not None else "instrument",
                "parent_label": parent.label if parent is not None else None,
                "group_size": decision["group_size"],
                "group_ordinal": decision["group_ordinal"],
                "toc_heading": decision["toc_heading"],
                "candidate_heading": candidate.heading,
                "canonical_heading": canonical.heading,
                "candidate_heading_score": decision["candidate_heading_score"],
                "canonical_heading_score": decision["canonical_heading_score"],
                "candidate_carries_law": decision["candidate_carries_law"],
                "canonical_carries_law": decision["canonical_carries_law"],
            },
        })

    preamble = next((n.text for n in seg.flatten() if n.kind == "preamble"), None)
    inst = SegmentedInstrument(
        document_id=document_id, source_observation_id=source_observation_id,
        sha256=sha256,
        jurisdiction=jur, kind=kind, number=number, year=year,
        # A catalogue title arrives as the portal printed it, so it can carry the
        # line breaks of the HTML cell it was read from -- 190 instruments held a
        # raw carriage return mid-title, which is what a user sees. The break is
        # an artefact of the page, never part of the law's name, and the value as
        # scraped stays verbatim in source_observation.source_metadata.
        short_title=" ".join((title or f"document {document_id}").split())[:400],
        long_title=None, preamble=preamble, source_url=source_url,
        as_at=as_at, confidence=round(seg.agreement, 4) if seg.toc_found else None,
        provisions=rows, block_roles=ledger, toc_entries=toc_rows,
        structural_decisions=structural_decisions,
        expression_ordinal=expression_ordinal,
        source_start_block_id=blocks[0]["id"] if blocks else None,
        source_end_block_id=blocks[-1]["id"] if blocks else None,
        expression_role=expression_role)
    return inst, seg


_OPENER_KEYS = frozenset({"source_block_id", "label", "heading", "source_prefix",
                          "after_section_label"})


def unnumbered_opener_shape_ok(item) -> bool:
    """The shape of one reviewed `source_unnumbered_section_openers` entry.

    Every text field is non-empty, except that an opener citing an owner
    decision (`owner_decision`, profile rule `unnumbered_root_provision`) may
    give an empty heading: the paragraph it opens prints none, and none is
    invented.  The segmenter checks the rest against the source."""
    if not (isinstance(item, dict)
            and set(item) in (_OPENER_KEYS, _OPENER_KEYS | {"owner_decision"})
            and type(item["source_block_id"]) is int and item["source_block_id"] > 0
            and all(isinstance(item[name], str) for name in
                    ("label", "heading", "source_prefix", "after_section_label"))):
        return False
    required = ("label", "source_prefix", "after_section_label") + (
        () if "owner_decision" in item else ("heading",))
    return all(item[name].strip() for name in required)


def owner_decision_answer(citation: dict, document_id: int) -> dict:
    """Return the decision-review answer an opener's `owner_decision` cites.

    Checked where a reading enters the system (tools/record_curation_patch.py
    and the multi-instrument dry run), not at replay: the exports live under
    the git-ignored .artifacts/, and the recorded patch row is the durable
    evidence.  Refuses unless the export exists, parses, and holds exactly one
    answer for this document and question."""
    if not (isinstance(citation, dict)
            and set(citation) == {"export", "document_id", "question_id"}):
        raise ValueError(f"owner_decision must name export, document_id, question_id: {citation!r}")
    if citation["document_id"] != document_id:
        raise ValueError(f"owner_decision cites document {citation['document_id']}, "
                         f"not {document_id}")
    path = pathlib.Path(citation["export"])
    if not path.is_file():
        raise ValueError(f"owner_decision export {path} does not exist")
    export = json.loads(path.read_text(encoding="utf-8-sig"))
    answers = [a for a in (export.get("answers") or [])
               if a.get("document_id") == document_id
               and a.get("question_id") == citation["question_id"]]
    if len(answers) != 1:
        raise ValueError(f"owner_decision export {path} holds {len(answers)} answers for "
                         f"document {document_id} {citation['question_id']}")
    return answers[0]


def reviewed_structural_overrides(resolutions: list[dict] | None,
                                  patches: list[dict] | None = None) -> dict:
    """Merge exact source-reviewed parser overrides, refusing disagreement."""
    merged: dict = {}
    for row in resolutions or []:
        evidence = row.get("evidence") or {}
        for key, value in (evidence.get("structural_overrides") or {}).items():
            if key in merged and merged[key] != value:
                raise ValueError(f"conflicting reviewed structural override {key}")
            merged[key] = value
    # A verified observation-scoped curation patch may carry a page-anchored
    # opening boundary or exact source-block reparent when no S7 collision
    # case exists. General S7 decisions still require adjudication. The patch
    # loader excludes unreviewed and retired records, and the segmenter fails
    # closed if either reparent address is absent or ambiguous.
    #
    # It may also name page-read apparatus blocks -- footnotes or endnotes the
    # parser read as law -- where no collision exists to carry an S7 reading
    # (doc 2803's closing amendment notes inside rule 30(3); authorised by the
    # project owner 26 Sep 2026). Each patch anchors to one page, so these
    # lists are united rather than required to agree.
    patch_apparatus: set[int] = set()
    patch_reparents: list[dict] = []
    patch_continuations: list[dict] = []
    patch_unnumbered_openers: list[dict] = []
    patch_unnumbered_parts: list[dict] = []
    patch_schedule_rows: list[dict] = []
    for patch in patches or []:
        evidence = patch.get("evidence") or {}
        for key, value in (evidence.get("structural_overrides") or {}).items():
            if key == "source_apparatus_blocks":
                if not (isinstance(value, list) and value
                        and all(type(item) is int and item > 0 for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_apparatus.update(value)
                continue
            if key == "source_body_start_block":
                valid = type(value) is int and value > 0
            elif key == "source_reparent_blocks":
                valid = (isinstance(value, list) and bool(value)
                         and all(
                             isinstance(item, dict)
                             and type(item.get("source_block_id")) is int
                             and item["source_block_id"] > 0
                             and type(item.get("parent_block_id")) is int
                             and item["parent_block_id"] > 0
                             # provision_kind carries no "item"/"paragraph";
                             # such a spec would fail the replay on insert.
                             and item.get("kind") in (
                                 "clause", "subsection", "explanation", "proviso")
                             for item in value))
                if valid:
                    patch_reparents.extend(value)
                    continue
            elif key == "source_continuation_parent_blocks":
                valid = (isinstance(value, list) and bool(value)
                         and all(isinstance(item, dict)
                                 and set(item) == {"source_block_id", "parent_block_id"}
                                 and type(item["source_block_id"]) is int
                                 and type(item["parent_block_id"]) is int
                                 and item["source_block_id"] > 0
                                 and item["parent_block_id"] > 0
                                 and item["source_block_id"] != item["parent_block_id"]
                                 for item in value))
                if valid:
                    patch_continuations.extend(value)
                    continue
            elif key == "source_unnumbered_section_openers":
                valid = (isinstance(value, list) and bool(value)
                         and all(unnumbered_opener_shape_ok(item) for item in value))
                if valid:
                    patch_unnumbered_openers.extend(value)
                    continue
            elif key == "source_unnumbered_part_headings":
                valid = (isinstance(value, list) and bool(value)
                         and all(isinstance(item, dict)
                                 and set(item) == {"source_block_id", "heading"}
                                 and type(item["source_block_id"]) is int
                                 and item["source_block_id"] > 0
                                 and isinstance(item["heading"], str)
                                 and item["heading"].strip()
                                 for item in value))
                if valid:
                    patch_unnumbered_parts.extend(value)
                    continue
            elif key == "source_schedule_row_openers":
                valid = (isinstance(value, list) and bool(value)
                         and all(isinstance(item, dict)
                                 and set(item) == {"source_block_id", "schedule_block_id",
                                                   "label", "source_text"}
                                 and type(item["source_block_id"]) is int
                                 and type(item["schedule_block_id"]) is int
                                 and item["source_block_id"] > 0
                                 and item["schedule_block_id"] > 0
                                 and item["source_block_id"] != item["schedule_block_id"]
                                 and isinstance(item["label"], str)
                                 and item["label"].strip()
                                 and isinstance(item["source_text"], str)
                                 and item["source_text"].strip()
                                 for item in value))
                if valid:
                    patch_schedule_rows.extend(value)
                    continue
            elif key == "source_schedule_form_group":
                valid = (isinstance(value, dict)
                         and set(value) == {
                             "schedule_block_id", "schedule_label",
                             "first_form_block_id", "first_form_label",
                             "second_form_block_id", "second_form_label"}
                         and all(type(value[name]) is int and value[name] > 0
                                 for name in ("schedule_block_id",
                                              "first_form_block_id",
                                              "second_form_block_id"))
                         and len({value["schedule_block_id"],
                                  value["first_form_block_id"],
                                  value["second_form_block_id"]}) == 3
                         and all(isinstance(value[name], str)
                                 and value[name].strip()
                                 for name in ("schedule_label", "first_form_label",
                                              "second_form_label")))
            else:
                valid = False
            if not valid:
                raise ValueError(f"unsupported curation structural override {key}")
            if key in merged and merged[key] != value:
                raise ValueError(f"conflicting reviewed structural override {key}")
            merged[key] = value
    if patch_apparatus:
        merged["source_apparatus_blocks"] = sorted(
            patch_apparatus | set(merged.get("source_apparatus_blocks") or []))
    if patch_reparents:
        combined = list(merged.get("source_reparent_blocks") or []) + patch_reparents
        unique: dict[tuple, dict] = {}
        for item in combined:
            key = (item["source_block_id"], item.get("source_label"),
                   item.get("source_kind"))
            if key in unique and unique[key] != item:
                raise ValueError(f"conflicting reviewed source reparent {key}")
            unique[key] = item
        merged["source_reparent_blocks"] = list(unique.values())
    if patch_continuations:
        combined = list(merged.get("source_continuation_parent_blocks") or []) + patch_continuations
        unique_continuations: dict[int, dict] = {}
        for item in combined:
            source_id = item["source_block_id"]
            if source_id in unique_continuations and unique_continuations[source_id] != item:
                raise ValueError(f"conflicting reviewed source continuation {source_id}")
            unique_continuations[source_id] = item
        merged["source_continuation_parent_blocks"] = list(unique_continuations.values())
    if patch_unnumbered_openers:
        combined = list(merged.get("source_unnumbered_section_openers") or []) + patch_unnumbered_openers
        unique_openers: dict[int, dict] = {}
        for item in combined:
            source_id = item["source_block_id"]
            if source_id in unique_openers and unique_openers[source_id] != item:
                raise ValueError(f"conflicting reviewed unnumbered section opener {source_id}")
            unique_openers[source_id] = item
        merged["source_unnumbered_section_openers"] = list(unique_openers.values())
    if patch_unnumbered_parts:
        combined = list(merged.get("source_unnumbered_part_headings") or []) + patch_unnumbered_parts
        unique_parts: dict[int, dict] = {}
        for item in combined:
            source_id = item["source_block_id"]
            if source_id in unique_parts and unique_parts[source_id] != item:
                raise ValueError(f"conflicting reviewed unnumbered part {source_id}")
            unique_parts[source_id] = item
        merged["source_unnumbered_part_headings"] = list(unique_parts.values())
    if patch_schedule_rows:
        combined = list(merged.get("source_schedule_row_openers") or []) + patch_schedule_rows
        unique_rows: dict[int, dict] = {}
        for item in combined:
            source_id = item["source_block_id"]
            if source_id in unique_rows and unique_rows[source_id] != item:
                raise ValueError(f"conflicting reviewed schedule row opener {source_id}")
            unique_rows[source_id] = item
        merged["source_schedule_row_openers"] = list(unique_rows.values())
    return merged


def unmanaged_full_replay(args: argparse.Namespace) -> bool:
    """True when a write-all redo would bypass the required recovery lane."""
    return bool(
        args.all
        and args.redo
        and not args.dry_run
        and os.environ.get(_MANAGED_FULL_REPLAY_ENV) != "1"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="L1 segmentation (doc 02 §5)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true")
    g.add_argument("--document", type=int)
    g.add_argument("--observation", type=int,
                   help="re-segment exactly one source observation")
    g.add_argument("--observations",
                   help="comma-separated source observation ids for a bounded replay")
    g.add_argument("--documents",
                   help="comma-separated document ids for a bounded replay")
    g.add_argument("--retry-errors", action="store_true",
                   help="retry observations whose newest run is an error")
    g.add_argument("--duplicate-labels", action="store_true",
                   help="re-segment active instruments with ambiguous sibling labels")
    g.add_argument("--pending-s7", action="store_true",
                   help="re-segment observations with unresolved item-level S7 candidates")
    g.add_argument("--pending-toc", action="store_true",
                   help="target all canonical observations with pending TOC entries")
    g.add_argument("--pending-toc-one-gap", action="store_true",
                   help="target canonical observations with exactly one pending TOC entry")
    g.add_argument("--heading-only", action="store_true",
                   help="replay pending S7 observations only when every non-heading tree field is byte-identical")
    g.add_argument("--detached-heading-body", action="store_true",
                   help="replay /23 pending trees only when /24 merges a detached numbered heading and body")
    g.add_argument("--boundary-changed-from",
                   help="replay observations whose latest run by this segmenter moved the prior body boundary")
    ap.add_argument("--source")
    ap.add_argument("--lane")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--redo", action="store_true", help="re-segment documents already done")
    ap.add_argument("--include-review", action="store_true",
                    help="diagnostic override: include documents quarantined by quality gates")
    ap.add_argument("--dry-run", action="store_true",
                    help="build candidate trees and report totals without writing any row")
    ap.add_argument("--toc-improvements-only", action="store_true",
                    help="dry-run and print only documents with fewer TOC gaps")
    ap.add_argument("--toc-improvements-summary", action="store_true",
                    help="dry-run and print TOC improvements as compact TSV")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--marginal-fusion", action="store_true",
                    help="enable the separately gated geometric margin/body split")
    ap.add_argument("--profile",
                    help="dry-run only: preview a segmentation profile without a "
                         "pin (a written tree takes its profile from the pin)")
    a = ap.parse_args()
    if a.toc_improvements_only or a.toc_improvements_summary:
        a.dry_run = True
    # A written tree's profile comes only from segmentation_profile_pin, where
    # the trigger refuses released observations; this flag is a preview.
    if a.profile is not None and not a.dry_run:
        print("REFUSING --profile without --dry-run: pin the observation with "
              "tools/pin_segmentation_profile.py instead", file=sys.stderr)
        return 2

    if unmanaged_full_replay(a):
        print(
            "REFUSING unmanaged full replay: --all --redo retires instrument "
            "IDs and invalidates S7/TOC review links.\n"
            "Run ./nz full-replay --apply instead; it snapshots, repairs, and "
            "fails if release readiness falls or S7/TOC grows.",
            file=sys.stderr,
        )
        return 2

    if a.observation:
        targets = [t for t in legal_write.documents_needing_segmentation(
                   redo=True, include_review=a.include_review)
                   if t[2] == a.observation]
    elif a.observations:
        observation_ids = {int(value) for value in a.observations.split(",")
                           if value.strip()}
        targets = [t for t in legal_write.documents_needing_segmentation(
                   redo=True, include_review=a.include_review)
                   if t[2] in observation_ids]
    elif a.document:
        targets = [t for t in legal_write.documents_needing_segmentation(
                   redo=True, include_review=a.include_review)
                   if t[0] == a.document]
    elif a.documents:
        document_ids = {int(value) for value in a.documents.split(",") if value.strip()}
        targets = [t for t in legal_write.documents_needing_segmentation(
                   redo=True, include_review=a.include_review)
                   if t[0] in document_ids]
    elif a.duplicate_labels:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT i.source_observation_id
                  FROM instrument i
                  JOIN (
                        SELECT instrument_id,parent_id,kind,label
                          FROM provision
                         WHERE kind IN ('section','article')
                         GROUP BY instrument_id,parent_id,kind,label
                        HAVING count(*) > 1
                       ) repeated ON repeated.instrument_id=i.id
                 WHERE i.is_active""")
            ambiguous = {row[0] for row in cur.fetchall()}
        targets = [t for t in legal_write.documents_needing_segmentation(
                   redo=True, include_review=a.include_review)
                   if t[2] in ambiguous]
    elif a.pending_toc or a.pending_toc_one_gap:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT i.source_observation_id
                  FROM instrument i
                  JOIN v_toc_gap_pending g ON g.instrument_id=i.id
                 WHERE i.is_active AND i.duplicate_of IS NULL
                 GROUP BY i.id,i.source_observation_id
                HAVING %s OR count(*)=1
            """, (a.pending_toc,))
            pending = {row[0] for row in cur.fetchall()}
        targets = [t for t in legal_write.documents_needing_segmentation(
                   redo=True, include_review=a.include_review)
                   if t[2] in pending]
    elif a.pending_s7 or a.heading_only or a.detached_heading_body:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT c.source_observation_id
                  FROM v_structural_adjudication_pending c
                  JOIN segmentation_run r ON r.instrument_id=c.instrument_id
                 WHERE NOT %s OR r.segmenter='nizam.corpus.segment/23'
            """, (a.detached_heading_body,))
            pending = {row[0] for row in cur.fetchall()}
        targets = [t for t in legal_write.documents_needing_segmentation(
                   redo=True, include_review=a.include_review)
                   if t[2] in pending]
    elif a.boundary_changed_from:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("""
                WITH ranked AS (
                    SELECT r.source_observation_id,r.segmenter,r.body_starts_page,
                           row_number() OVER (
                               PARTITION BY r.source_observation_id
                               ORDER BY r.run_at DESC,r.id DESC) AS rn
                      FROM segmentation_run r
                      JOIN document d ON d.id=r.document_id AND d.is_active
                ), compared AS (
                    SELECT source_observation_id,
                           max(segmenter) FILTER (WHERE rn=1) latest_segmenter,
                           max(body_starts_page) FILTER (WHERE rn=1) latest_boundary,
                           max(body_starts_page) FILTER (WHERE rn=2) prior_boundary
                      FROM ranked WHERE rn<=2 GROUP BY source_observation_id
                )
                SELECT source_observation_id FROM compared
                 WHERE latest_segmenter=%s
                   AND latest_boundary IS DISTINCT FROM prior_boundary
            """, (a.boundary_changed_from,))
            changed = {row[0] for row in cur.fetchall()}
        targets = [t for t in legal_write.documents_needing_segmentation(
                   redo=True, include_review=a.include_review)
                   if t[2] in changed]
    else:
        targets = legal_write.documents_needing_segmentation(
            limit=a.limit, source_id=a.source, lane=a.lane,
            redo=(a.redo or a.retry_errors), retry_errors=a.retry_errors,
            include_review=a.include_review)
    if not targets:
        print("nothing to segment")
        return 0

    baseline: dict[int, dict] = {}
    baseline_trees: dict[int, list[tuple]] = {}
    if a.dry_run or a.heading_only:
        observation_ids = [t[2] for t in targets]
        with connect() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ON (source_observation_id)
                       source_observation_id,body_starts_page,toc_found,
                       toc_agreement,toc_missing,provisions,sections,
                       coalesce((detail->>'repeated_labels_demoted')::integer,0)
                  FROM segmentation_run
                 WHERE source_observation_id = ANY(%s)
                 ORDER BY source_observation_id,run_at DESC,id DESC
            """, (observation_ids,))
            baseline = {
                row[0]: dict(zip(
                    ("body_page", "toc_found", "toc_agreement", "toc_missing",
                     "provisions", "sections", "candidates"), row[1:]))
                for row in cur.fetchall()
            }
            cur.execute("""
                SELECT i.source_observation_id,count(*)
                  FROM v_toc_gap_pending g
                  JOIN instrument i ON i.id=g.instrument_id
                 WHERE i.is_active AND i.duplicate_of IS NULL
                   AND i.source_observation_id = ANY(%s)
                 GROUP BY i.source_observation_id
            """, (observation_ids,))
            for observation_id, pending_entries in cur.fetchall():
                baseline.setdefault(observation_id, {})[
                    "pending_entries"] = pending_entries
            # A count-only comparison is not strong enough to authorise a
            # replay: two trees can have the same number of nodes while their
            # labels, parents, pages or text differ.  Capture the complete
            # current tree (plus headings separately) so the dry-run can prove
            # that a parser change is heading-only before anyone writes it.
            cur.execute("""
                SELECT i.source_observation_id,p.path::text,
                       coalesce(parent.path::text,''),p.kind::text,p.label,
                       p.ordinal,p.first_page,p.last_page,p.first_block,
                       coalesce(v.text_en,v.text_ur,''),coalesce(p.heading,'')
                  FROM instrument i
                  JOIN provision p ON p.instrument_id=i.id
                  LEFT JOIN provision parent ON parent.id=p.parent_id
                  LEFT JOIN LATERAL (
                        SELECT text_en,text_ur FROM provision_version pv
                         WHERE pv.provision_id=p.id
                         ORDER BY lower(pv.validity) DESC,pv.created_at DESC
                         LIMIT 1
                  ) v ON true
                 WHERE i.is_active AND i.source_observation_id = ANY(%s)
                 ORDER BY i.source_observation_id,p.ordinal
            """, (observation_ids,))
            for row in cur.fetchall():
                baseline_trees.setdefault(row[0], []).append(tuple(row[1:]))

    print(f"segmenting {len(targets)} document(s)\n")
    done = failed = 0
    candidate_units = 0
    candidate_observations = 0
    zero_candidate_replays: list[dict] = []
    heading_only_replays: list[dict] = []
    newly_proved_toc_replays: list[dict] = []
    toc_improving_replays: list[dict] = []
    agreements: list[float] = []
    started = time.time()

    for n, (doc_id, sha, observation_id, source_id, title, year,
            doc_type, source_url) in enumerate(targets, 1):
        t0 = time.time()
        writer = SEGMENTER
        try:
            # A pinned observation is parsed, saved and recorded under its
            # profile (docs/SEGMENTATION-PROFILES.md); unpinned ones are not
            # touched by any of this.
            profile = (a.profile if a.profile is not None
                       else legal_write.segmentation_profile_for(observation_id))
            writer = segmenter_identity(profile)
            blocks = legal_write.blocks_for(doc_id)
            # There is deliberately no minimum-block guard here. A PyMuPDF block
            # is typographic, not legal: the Punjab Dourine Rules 1952 arrive as
            # two blocks holding seven sections, and a "fewer than 3 blocks"
            # pre-check rejected them before the segmenter -- which subdivides --
            # ever saw them. Judge the result, never the raw block count.
            if not blocks:
                legal_write.record_run(doc_id, observation_id, None, writer, "rejected",
                                       reason="document has no text blocks",
                                       duration_ms=int((time.time() - t0) * 1000))
                failed += 1
                continue
            as_at = legal_write.observed_on(observation_id)
            patches = legal_write.segmentation_patches_for(observation_id)
            toc_dispositions = legal_write.toc_dispositions_for(observation_id)
            # Keyed on the DOCUMENT, not the observation: a decision anchors to
            # a text block, and blocks belong to documents.
            structural_resolutions = legal_write.structural_resolutions_for(doc_id)
            structural_overrides = reviewed_structural_overrides(
                structural_resolutions, patches)
            inst, seg = build(doc_id, sha, observation_id, source_id, title, year,
                              source_url, blocks, as_at, patches,
                              toc_dispositions=toc_dispositions,
                              structural_resolutions=structural_resolutions,
                              structural_overrides=structural_overrides or None,
                              split_fused_margins=a.marginal_fusion,
                              profile=profile)
            # The release queue contains candidate rows the writer will
            # materialize, not every raw collision the segmenter considered.
            # Source-reviewed reject/restore decisions deliberately suppress a
            # fresh candidate while preserving the demoted node and its text.
            # Reporting the raw count made those correctly settled replays
            # fail S7 itemization forever (doc 1150: one reviewed footnote,
            # zero candidate rows, metadata incorrectly expected one).
            new_candidates = len(inst.structural_decisions)
            if (a.detached_heading_body
                    and seg.detached_heading_bodies_merged == 0):
                continue
            old = baseline.get(observation_id, {})
            new_sections = sum(1 for r in inst.provisions
                               if r["kind"] == "section")
            is_heading_only = False
            changed_headings = 0
            if a.dry_run or a.heading_only:
                new_by_key = {r["key"]: r for r in inst.provisions}
                new_tree = []
                for row in inst.provisions:
                    parent = new_by_key.get(row["parent_key"])
                    new_tree.append((
                        row["path"], parent["path"] if parent else "",
                        row["kind"], row["label"], row["ordinal"],
                        row["first_page"], row["last_page"], row["first_block"],
                        row["text"] or "", row["heading"] or "",
                    ))
                old_tree = baseline_trees.get(observation_id, [])
                old_without_headings = [r[:-1] for r in old_tree]
                new_without_headings = [r[:-1] for r in new_tree]
                changed_headings = sum(
                    1 for old_row, new_row in zip(old_tree, new_tree)
                    if old_row[-1] != new_row[-1]
                ) if len(old_tree) == len(new_tree) else 0
                is_heading_only = (
                    old_without_headings == new_without_headings
                    and changed_headings > 0
                )
                if a.dry_run and is_heading_only:
                    heading_only_replays.append({
                        "document_id": doc_id,
                        "source_observation_id": observation_id,
                        "provisions": len(new_tree),
                        "changed_headings": changed_headings,
                        "old_candidates": old.get("candidates"),
                        "new_candidates": new_candidates,
                    })
                if (a.dry_run and seg.toc_found and not old.get("toc_found")
                        and seg.body_starts_page > int(old.get("body_page") or 0)
                        and new_candidates
                            < int(old.get("candidates") or 0)):
                    newly_proved_toc_replays.append({
                        "document_id": doc_id,
                        "source_observation_id": observation_id,
                        "old_body_page": old.get("body_page"),
                        "new_body_page": seg.body_starts_page,
                        "old_sections": old.get("sections"),
                        "new_sections": new_sections,
                        "old_candidates": old.get("candidates"),
                        "new_candidates": new_candidates,
                        "toc_agreement": round(seg.agreement, 4),
                    })
                old_missing = old.get("toc_missing")
                new_missing = len(seg.missing) if seg.toc_found else None
                unmatched_entries = [
                    entry for entry in seg.toc_entries
                    if entry.get("node") is None
                ]
                unmatched_entry_labels = {
                    entry["label"] for entry in unmatched_entries
                    if entry.get("kind") != "schedule"
                }
                new_pending_entries = (
                    len(unmatched_entries)
                    + len(set(seg.missing) - unmatched_entry_labels)
                    if seg.toc_found else None
                )
                old_pending_entries = old.get("pending_entries")
                if (a.dry_run and old_pending_entries is not None
                        and new_pending_entries is not None
                        and new_pending_entries < int(old_pending_entries)):
                    old_node_keys = {(row[2], row[3], row[7]) for row in old_tree}
                    new_node_keys = {(row[2], row[3], row[7]) for row in new_tree}
                    tree_fields = (
                        "path", "parent_path", "kind", "label", "ordinal",
                        "first_page", "last_page", "first_block", "text",
                        "heading",
                    )
                    old_nodes = {(row[2], row[3], row[7]): row
                                 for row in old_tree}
                    new_nodes = {(row[2], row[3], row[7]): row
                                 for row in new_tree}
                    changed_nodes = []
                    changed_field_counts: dict[str, int] = {}
                    for node_key in old_node_keys & new_node_keys:
                        old_row = old_nodes[node_key]
                        new_row = new_nodes[node_key]
                        changes = {}
                        for field, old_value, new_value in zip(
                                tree_fields, old_row, new_row):
                            if old_value == new_value:
                                continue
                            changed_field_counts[field] = (
                                changed_field_counts.get(field, 0) + 1)
                            def display(value):
                                if isinstance(value, str) and len(value) > 180:
                                    return value[:177] + "..."
                                return value
                            changes[field] = {
                                "old": display(old_value),
                                "new": display(new_value),
                            }
                        if changes and len(changed_nodes) < 200:
                            changed_nodes.append({
                                "kind": node_key[0], "label": node_key[1],
                                "block": node_key[2], "changes": changes,
                            })
                    toc_improving_replays.append({
                        "document_id": doc_id,
                        "source_observation_id": observation_id,
                        "old_missing": (int(old_missing)
                                        if old_missing is not None else None),
                        "new_missing": new_missing,
                        "old_pending_entries": int(old_pending_entries),
                        "new_pending_entries": new_pending_entries,
                        "old_matched": None,
                        "new_matched": seg.matched,
                        "old_body_page": old.get("body_page"),
                        "new_body_page": seg.body_starts_page,
                        "old_sections": old.get("sections"),
                        "new_sections": new_sections,
                        "old_candidates": old.get("candidates"),
                        "new_candidates": new_candidates,
                        "tree_identical": new_tree == old_tree,
                        "added_nodes": [
                            {"kind": row[2], "label": row[3],
                             "page": row[5], "block": row[7]}
                            for row in new_tree
                            if (row[2], row[3], row[7]) not in old_node_keys
                        ][:30],
                        "removed_nodes": [
                            {"kind": row[2], "label": row[3],
                             "page": row[5], "block": row[7]}
                            for row in old_tree
                            if (row[2], row[3], row[7]) not in new_node_keys
                        ][:30],
                        "changed_field_counts": changed_field_counts,
                        "changed_nodes": changed_nodes,
                        "new_missing_labels": seg.missing,
                        "expected_dispositions": len(toc_dispositions),
                        "materialised_dispositions": seg.toc_dispositions_materialised,
                    })
            if a.heading_only and not is_heading_only:
                continue
            if a.dry_run:
                done += 1
                candidate_units += new_candidates
                candidate_observations += int(new_candidates > 0)
                agreement_safe = (
                    not old.get("toc_found")
                    or not seg.toc_found
                    or seg.agreement + 0.02 >= float(old.get("toc_agreement") or 0))
                if (new_candidates == 0
                        and int(old.get("candidates") or 0) > 0
                        and new_sections >= int(old.get("sections") or 0)
                        and agreement_safe):
                    zero_candidate_replays.append({
                        "document_id": doc_id,
                        "source_observation_id": observation_id,
                        "old_candidates": old.get("candidates"),
                        "old_sections": old.get("sections"),
                        "new_sections": new_sections,
                        "old_body_page": old.get("body_page"),
                        "new_body_page": seg.body_starts_page,
                        "toc_agreement": round(seg.agreement, 4)
                                         if seg.toc_found else None,
                    })
                if seg.toc_found:
                    agreements.append(seg.agreement)
                if not a.quiet:
                    old_candidates = int(old.get("candidates") or 0)
                    old_sections = int(old.get("sections") or 0)
                    print(f"  {n:>5}/{len(targets)} dry   #{doc_id:<5} "
                          f"{len(inst.provisions):>5} prov  "
                          f"S7={old_candidates}->{new_candidates:<4} "
                          f"sec={old_sections}->{new_sections:<4} "
                          f"body-page={seg.body_starts_page:<4} "
                          f"{(title or '')[:38]}", flush=True)
                continue
            if not inst.provisions:
                # No provision structure -- but the text is real and stays
                # reachable. Every block is recorded as 'unstructured' and the
                # document joins v_unstructured_document with its reason.
                unstructured_count = legal_write.save_unstructured(
                    doc_id, observation_id, blocks, writer)
                legal_write.record_run(doc_id, observation_id, None, writer, "rejected",
                                       reason="no provision structure; "
                                              f"{unstructured_count} blocks recorded as unstructured",
                                       toc_found=seg.toc_found,
                                       detail={"blocks_total": len(blocks),
                                               "blocks_unstructured": unstructured_count},
                                       duration_ms=int((time.time() - t0) * 1000))
                failed += 1
                continue
            instrument_id = legal_write.save(inst, writer)
            sections = sum(1 for r in inst.provisions if r["kind"] == "section")
            depth = max((r["path"].count(".") for r in inst.provisions), default=0)
            legal_write.record_run(
                doc_id, observation_id, instrument_id, writer, "segmented",
                provisions=len(inst.provisions), sections=sections, max_depth=depth,
                body_starts_page=seg.body_starts_page, toc_found=seg.toc_found,
                toc_entries=len(seg.toc_entries) or None,
                toc_matched=seg.matched if seg.toc else None,
                toc_missing=len(seg.missing) if seg.toc else None,
                toc_extra=len(seg.extra) if seg.toc else None,
                toc_agreement=round(seg.agreement, 4) if seg.toc else None,
                detail={"missing": seg.missing[:60], "extra": seg.extra[:60],
                        "blocks_total": len(blocks),
                        # This field is the expected itemized population used
                        # by the S7 audit, so it must equal the candidate rows
                        # written below. Keep the raw diagnostic separately.
                        "repeated_labels_demoted": new_candidates,
                        "repeated_labels_demoted_raw": seg.repeated_labels_demoted,
                        "schedule_sections_retyped": seg.schedule_sections_retyped,
                        "detached_heading_bodies_merged": seg.detached_heading_bodies_merged,
                        "marginal_notes_split": seg.marginal_notes_split,
                        "toc_dispositions_materialised": sum(
                            1 for row in inst.provisions
                            if row["toc_disposition_assertion_id"] is not None),
                        "curation_patches_applied": seg.curation_patches_applied,
                        "blocks_unassigned": sum(1 for r in inst.block_roles
                                                 if r[1] == "unassigned"),
                        # Profile evidence (docs/SEGMENTATION-PROFILES.md):
                        # present only for a pinned parse that used a rule.
                        **({"segmentation_profile": seg.profile}
                           if seg.profile != "default" else {}),
                        **({"contents_alignment": seg.contents_alignment}
                           if seg.contents_alignment else {})},
                duration_ms=int((time.time() - t0) * 1000))
            done += 1
            if seg.toc_found:
                agreements.append(seg.agreement)
            if not a.quiet:
                if seg.toc_found:
                    mark = "ok    " if seg.agreement >= 0.95 else "REVIEW"
                    toc = f"toc={seg.agreement:.3f}"
                else:
                    mark, toc = "ok    ", "no contents"
                print(f"  {n:>5}/{len(targets)} {mark} #{doc_id:<5} "
                      f"{len(inst.provisions):>5} prov {sections:>4} sec  {toc:<14} "
                      f"{(title or '')[:38]}", flush=True)
        except Exception as exc:
            if not a.dry_run:
                legal_write.record_run(doc_id, observation_id, None, writer, "error",
                                       reason=f"{type(exc).__name__}: {exc}"[:400],
                                       duration_ms=int((time.time() - t0) * 1000))
            failed += 1
            print(f"  ERROR #{doc_id}: {type(exc).__name__}: {exc}", file=sys.stderr)
        if n % 250 == 0:
            print(f"  ... {n}/{len(targets)}", flush=True)

    el = time.time() - started
    verb = "analysed" if a.dry_run else "segmented"
    print(f"\n{verb} {done}, failed {failed}, in {el/60:.1f} min")
    if a.dry_run:
        print(f"prospective S7: {candidate_units} candidates in "
              f"{candidate_observations} observations")
        print("TOC-improving replays:")
        if a.toc_improvements_summary:
            print("document\tobservation\told_pending\tnew_pending\tdelta\t"
                  "dispositions\t"
                  "tree_identical\tsections\tcandidates\tadded\tremoved\t"
                  "changed\tchanged_fields\tadded_nodes\tremoved_nodes")
            for item in sorted(
                    toc_improving_replays,
                    key=lambda value: (
                        value["old_pending_entries"] - value["new_pending_entries"],
                        value["old_pending_entries"]),
                    reverse=True):
                delta = item["old_pending_entries"] - item["new_pending_entries"]
                print(
                    f'{item["document_id"]}\t{item["source_observation_id"]}\t'
                    f'{item["old_pending_entries"]}\t{item["new_pending_entries"]}\t'
                    f'{delta}\t{item["materialised_dispositions"]}/'
                    f'{item["expected_dispositions"]}\t'
                    f'{str(item["tree_identical"]).lower()}\t'
                    f'{item["old_sections"]}->{item["new_sections"]}\t'
                    f'{item["old_candidates"]}->{item["new_candidates"]}\t'
                    f'{len(item["added_nodes"])}\t{len(item["removed_nodes"])}'
                    f'\t{sum(item["changed_field_counts"].values())}\t'
                    + ",".join(
                        f"{field}:{count}" for field, count in sorted(
                            item["changed_field_counts"].items()
                        )
                    )
                    + "\t" + ",".join(
                        f"{node['kind']}:{node['label']}@p{node['page']}#b{node['block']}"
                        for node in item["added_nodes"]
                    )
                    + "\t" + ",".join(
                        f"{node['kind']}:{node['label']}@p{node['page']}#b{node['block']}"
                        for node in item["removed_nodes"]
                    )
                )
        else:
            print(json.dumps(toc_improving_replays, ensure_ascii=False, indent=2))
        if not (a.toc_improvements_only or a.toc_improvements_summary):
            print("zero-candidate non-degrading replays:")
            print(json.dumps(zero_candidate_replays, ensure_ascii=False, indent=2))
            print("exact heading-only replays (all non-heading fields byte-identical):")
            print(json.dumps(heading_only_replays, ensure_ascii=False, indent=2))
            print("new explicit-contents/layout-proven body boundaries:")
            print(json.dumps(newly_proved_toc_replays, ensure_ascii=False, indent=2))
    if agreements:
        import statistics
        print(f"table-of-contents agreement over {len(agreements)} documents that print one:")
        print(f"  mean   {statistics.mean(agreements):.4f}")
        print(f"  median {statistics.median(agreements):.4f}")
        for t in (0.99, 0.95, 0.90):
            k = sum(1 for x in agreements if x >= t)
            print(f"  >= {t:.2f} {k:>5}/{len(agreements)}  ({k/len(agreements)*100:.1f}%)")
    return 0 if done else 1


if __name__ == "__main__":
    with only_one_run():
        raise SystemExit(main())
