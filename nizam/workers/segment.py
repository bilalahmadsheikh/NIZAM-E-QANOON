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

from nizam.corpus.segment import _owner_cited_label_shape_ok, assign_paths, segment, reviewed_unit_move_shape_ok, reviewed_grid_row_shape_ok
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


def segmenter_fingerprint() -> str:
    """sha256 of the segment.py that builds this process's trees (owner decision 11 Oct, stage 0).

    SEGMENTER is a hand-bumped tag and was not bumped for the ungated fixes of late September, so a tree
    built by a different segmenter was indistinguishable in segmentation_run. Every run the worker records
    now carries this digest and the profile in its detail (docs/SEGMENTATION-PROFILES.md)."""
    import hashlib
    import nizam.corpus.segment as module
    return hashlib.sha256(pathlib.Path(module.__file__).read_bytes()).hexdigest()


def run_identity(profile: str) -> dict:
    return {"segmenter_sha256": segmenter_fingerprint(), "profile": profile}

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


def _patch_identity(patch: dict) -> str:
    evidence = patch.get("evidence") or {}
    return json.dumps([patch["page_no"], patch["match_text"], patch["before_text"], patch["after_text"],
                       evidence.get("structural_overrides") or {}], sort_keys=True, ensure_ascii=False)


def same_blob_problem(observations: dict[int, dict]) -> str | None:
    """Why observations of one blob would build different trees, or None (lead decision 12 Oct, doc 4419).

    observations: {source_observation_id: {"sha256", "profile", "patches": set of patch identities,
    "dispositions": set of active TOC disposition identities (optional)}}. Observations of the SAME blob carry the
    same pages, so their effective patch sets, disposition sets and profiles must be equal; otherwise a
    replay rebuilds one without the other's readings, it stops being an exact duplicate and enters the release
    (4419 obs 132, 12 Oct). Names each observation and what it lacks."""
    by_blob: dict = {}
    for obs, info in observations.items():
        by_blob.setdefault(info["sha256"], []).append(obs)
    problems = []
    for sha, members in sorted(by_blob.items(), key=lambda kv: min(kv[1])):
        if len(members) < 2:
            continue
        members = sorted(members)
        union = set().union(*(observations[o]["patches"] for o in members))
        for obs in members:
            lacking = union - observations[obs]["patches"]
            if lacking:
                pages = sorted({json.loads(item)[0] for item in lacking})
                problems.append(f"observation {obs} lacks {len(lacking)} curation patch(es) on page(s) {pages} "
                                f"that its same-blob observation(s) carry")
        # Active (non-withdrawn) TOC disposition assertions are parser input too (docs 4501, 2605: one observation
        # carried an omitted/repealed section the other did not, so both stayed released and different).
        dunion = set().union(*(observations[o].get("dispositions", set()) for o in members))
        for obs in members:
            dlacking = dunion - observations[obs].get("dispositions", set())
            if dlacking:
                labels = sorted({json.loads(item)[1] for item in dlacking})
                problems.append(f"observation {obs} lacks {len(dlacking)} TOC disposition(s) (labels {labels}) "
                                f"that its same-blob observation(s) carry")
        profiles = {o: observations[o]["profile"] for o in members}
        if len(set(profiles.values())) > 1:
            problems.append("same-blob observations are pinned to different profiles: "
                            + ", ".join(f"{o}={p}" for o, p in sorted(profiles.items())))
    return "; ".join(problems) or None


def same_blob_observation_problem(document_id: int) -> str | None:
    """same_blob_problem() over every observation behind an active instrument of the document (duplicates
    included). Checked BEFORE building by the worker and the multi-expression materializer (fail closed)."""
    from nizam.storage.db import connect
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT DISTINCT i.source_observation_id, o.sha256 FROM instrument i
                         JOIN source_observation o ON o.id=i.source_observation_id
                        WHERE i.document_id=%s AND i.is_active""", (document_id,))
        rows = cur.fetchall()
    if len(rows) < 2:
        return None
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""SELECT source_observation_id, expression_ordinal, printed_label, disposition::text,
                              source_block_id, source_page
                         FROM v_toc_disposition_assertion_latest WHERE source_observation_id = ANY(%s)""",
                    ([obs for obs, _sha in rows],))
        dispositions: dict[int, set] = {}
        for obs, expr, label, disposition, block, page in cur.fetchall():
            dispositions.setdefault(obs, set()).add(json.dumps([expr, label, disposition, block, page]))
    observations = {obs: {"sha256": sha, "profile": legal_write.segmentation_profile_for(obs),
                          "patches": {_patch_identity(p) for p in legal_write.segmentation_patches_for(obs)},
                          "dispositions": dispositions.get(obs, set())}
                    for obs, sha in rows}
    problem = same_blob_problem(observations)
    return f"document {document_id}: {problem} -- record them on each observation (tools/record_curation_patch.py, tools/review_toc_dispositions.py)"         if problem else None


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
    legal_write.validate_owner_cited_source_gaps(document_id, source_observation_id, structural_overrides)
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
    # A reviewed multi-expression plan may state an expression's own jurisdiction (doc 4347 E3, a Punjab
    # notification printed inside a Sindh booklet; lead decision 12 Oct 2026). Absent, nothing changes.
    if reviewed_identity and reviewed_identity.get("jurisdiction"):
        jur = reviewed_identity["jurisdiction"]
    if reviewed_identity is not None:
        # A reviewed identity is taken whole and nothing is inferred beside it
        # (inference had no side effect, so a dated identity builds exactly as
        # before).  Its year may be None only for an expression the owner
        # declared undated (migration 0063; the materializer's validate_plan
        # checks the owner's 'undated'): no year is ever inferred for it, since
        # one read from its title or text ('... Opium Act, 1878 ...') would be
        # rendered as the instrument's year (INV-1).
        kind = reviewed_identity["kind"]
        year = (None if reviewed_identity["year"] is None
                else int(reviewed_identity["year"]))
        number = reviewed_identity["number"]
    else:
        kind = infer_kind(title or "")
        year = infer_year(title or "", meta_year, head)
        number = infer_number(head, year)
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
    # An owner-declared undated expression carries 'yundated' (migration 0063).
    prefix = f"{jur}.{kind}.y{year if year is not None else 'undated'}_{ident}"
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


_CITATION_KEYS = frozenset({"export", "document_id", "question_id"})


def _owner_citation_shape_ok(value) -> bool:
    return (isinstance(value, dict) and set(value) == _CITATION_KEYS
            and isinstance(value["export"], str) and value["export"].strip()
            and type(value["document_id"]) is int and value["document_id"] > 0
            and isinstance(value["question_id"], str) and value["question_id"].strip())


def unlabelled_schedule_opener_shape_ok(item) -> bool:
    """The shape of one reviewed `source_unlabelled_schedule_openers` entry.

    Profile rule `unlabelled_schedule_opener` (doc 691 p9): {source_block_id,
    label, source_text, owner_decision}.  The segmenter checks the block's
    text, the label ("SCHEDULE") and where the block falls; the recorder checks
    that the export holds the cited answer."""
    return (isinstance(item, dict)
            and set(item) == {"source_block_id", "label", "source_text", "owner_decision"}
            and type(item["source_block_id"]) is int and item["source_block_id"] > 0
            and isinstance(item["label"], str) and bool(item["label"].strip())
            and isinstance(item["source_text"], str) and bool(item["source_text"].strip())
            and _owner_citation_shape_ok(item["owner_decision"]))


def printed_heading_shape_ok(item) -> bool:
    """The shape of one reviewed `source_printed_headings` entry.

    Profile rule `printed_heading_override` (docs 1003, 999): {label,
    source_block_id, heading, use: heading|marginal_note, owner_decision}.
    The segmenter checks that the words are printed in that block and that
    exactly one top-level section carries the label."""
    return (isinstance(item, dict)
            and set(item) == {"label", "source_block_id", "heading", "use", "owner_decision"}
            and isinstance(item["label"], str) and bool(item["label"].strip())
            and type(item["source_block_id"]) is int and item["source_block_id"] > 0
            and isinstance(item["heading"], str) and bool(item["heading"].strip())
            and item["use"] in ("heading", "marginal_note")
            and _owner_citation_shape_ok(item["owner_decision"]))


def order_suffix_label_shape_ok(item) -> bool:
    """The shape of one reviewed `source_order_suffix_labels` entry.

    Profile rule `order_suffix_label` (doc 999; sub-sections doc 1034, owner
    decision 2026-10-07 q2; clauses doc 1457 s.20, owner decision 8 Oct q4):
    {kind section|article|subsection|clause, label,
    source_block_ids (two or more distinct prints, in print order),
    owner_decision}.  The segmenter checks that the blocks are exactly one
    group of sibling prints of that label."""
    return (isinstance(item, dict)
            and set(item) == {"kind", "label", "source_block_ids", "owner_decision"}
            # agJF rule I `reviewed_order_suffix_form` (doc 4184): sibling FORMS printed under one label
            and item["kind"] in ("section", "article", "subsection", "clause", "form")
            and isinstance(item["label"], str) and bool(item["label"].strip())
            and isinstance(item["source_block_ids"], list) and len(item["source_block_ids"]) >= 2
            and all(type(value) is int and value > 0 for value in item["source_block_ids"])
            and (len(set(item["source_block_ids"])) == len(item["source_block_ids"])
                 # profile rule `order_suffix_one_block` (doc 1626 r.4): every print of a clause group in
                 # ONE block, named by repeating that block's id once per print
                 or (item["kind"] == "clause" and len(set(item["source_block_ids"])) == 1)
                 # agent K4 rule `order_suffix_one_block_section` (doc 3696 E4: regulation 17 printed twice in block
                 # 448263): a SECTION or ARTICLE group may name one block once per print too
                 or (item["kind"] in ("section", "article") and len(set(item["source_block_ids"])) == 1))
            and _owner_citation_shape_ok(item["owner_decision"]))


def named_schedule_row_shape_ok(item) -> bool:
    """The shape of one reviewed `source_named_schedule_rows` entry.

    Profile rule `named_schedule_row` (docs 1078, 1121; owner decisions
    2026-10-07): {source_block_id, schedule_block_id, label, source_text,
    owner_decision}.  The segmenter checks that the block's text is
    `source_text`, that the label (the printed post name) is printed in it
    exactly once and that the open top-level schedule starts at
    `schedule_block_id`; the recorder checks that the export holds the cited
    answer and that its choice asks for rows by post name."""
    return (isinstance(item, dict)
            and set(item) == {"source_block_id", "schedule_block_id", "label",
                              "source_text", "owner_decision"}
            and type(item["source_block_id"]) is int and item["source_block_id"] > 0
            and type(item["schedule_block_id"]) is int and item["schedule_block_id"] > 0
            and item["source_block_id"] != item["schedule_block_id"]
            and isinstance(item["label"], str) and bool(item["label"].strip())
            and isinstance(item["source_text"], str) and bool(item["source_text"].strip())
            and _owner_citation_shape_ok(item["owner_decision"]))


def contents_row_link_shape_ok(item) -> bool:
    """The shape of one reviewed `source_contents_row_links` entry.

    Profile rule `reviewed_contents_alignment` (doc 1368; owner decision
    2026-10-07 q1 'body'): {ordinal (the printed contents row's position,
    from 0), printed_label, unit_label (the top-level section or article
    label it names, or None when the row names no numbered unit),
    owner_decision}.  The segmenter checks the row's printed label and that
    the row ends linked to that unit; the recorder checks the export holds
    the cited answer."""
    # Profile rule `reviewed_contents_alignment`, index rows (docs 1889, 1635): an entry may carry
    # `index_row: true` -- the row links its unit but its words never become the unit's heading.
    # agent JD rule `reviewed_link_unit_kind` (group 5; lead 14 Oct): an entry may name the kind of the unit it links,
    # only a kind instrument_toc_entry.entry_kind already stores (part, schedule); the label is that division's.
    if isinstance(item, dict) and "unit_kind" in item:
        if item["unit_kind"] not in ("part", "schedule") or not isinstance(item.get("unit_label"), str):
            return False
        item = {k: v for k, v in item.items() if k != "unit_kind"}
    return (isinstance(item, dict)
            and set(item) in ({"ordinal", "printed_label", "unit_label", "owner_decision"},
                              {"ordinal", "printed_label", "unit_label", "owner_decision", "index_row"})
            and item.get("index_row", True) is True
            and type(item["ordinal"]) is int and item["ordinal"] >= 0
            and isinstance(item["printed_label"], str) and bool(item["printed_label"].strip())
            and (item["unit_label"] is None
                 or (isinstance(item["unit_label"], str) and bool(item["unit_label"].strip())))
            and _owner_citation_shape_ok(item["owner_decision"]))


def contents_row_links_ok(value) -> bool:
    """A whole `source_contents_row_links` list: well-shaped entries, one per
    contents row, no unit named twice."""
    if not (isinstance(value, list) and value and all(contents_row_link_shape_ok(v) for v in value)):
        return False
    units = [v["unit_label"] for v in value if v["unit_label"] is not None]
    return (len({v["ordinal"] for v in value}) == len(value)
            and len(set(units)) == len(units))


def owner_cited_label_shape_ok(item) -> bool:
    """The shape of one reviewed `source_owner_cited_labels` entry.

    Profile rule `owner_cited_label` (doc 1225; owner decision 2026-10-08
    export -f q1 'contents'): {kind section|article, printed_label (or null
    with source_prefix), cited_label, source_block_id, owner_decision}.  The
    one shape check is the segmenter's; the segmenter checks the rest against
    the source, the recorder that the export holds the answer."""
    return _owner_cited_label_shape_ok(item)


def substituted_schedule_items_shape_ok(item) -> bool:
    """The shape of one reviewed `source_substituted_schedule_items` entry.

    Profile rule `substituted_schedule_items` (doc 1431; owner decision
    2026-10-08 export -f q2 's2-text'): {owner_block_id, schedule_block_id,
    source_text, resume_block_id, owner_decision}.  The segmenter checks the
    owner section, the schedule block's text and where the span resumes."""
    return (isinstance(item, dict)
            and set(item) == {"owner_block_id", "schedule_block_id", "source_text",
                              "resume_block_id", "owner_decision"}
            and all(type(item[name]) is int and item[name] > 0
                    for name in ("owner_block_id", "schedule_block_id", "resume_block_id"))
            and len({item["owner_block_id"], item["schedule_block_id"], item["resume_block_id"]}) == 3
            and isinstance(item["source_text"], str) and bool(item["source_text"].strip())
            and _owner_citation_shape_ok(item["owner_decision"]))


# Stage 3 data-gated rules of agent DF (docs 4347, 4451): reviewed block lists, united across readings.
DF_BLOCK_KEYS = ('source_decimal_cut_blocks', 'source_table_row_blocks', 'source_division_continues_blocks', 'source_marked_label_cut_blocks',
                 # rule `reviewed_marker_run_cut` (agent DF, doc 4451 pp38, 40; lead 12 Oct)
                 'source_marker_run_cut_blocks',
                 # rule `reviewed_half_paren_items` (agent DF, doc 4347 E6 pp64-75; lead 12 Oct)
                 'source_half_paren_item_blocks',
                 # rule `leading_margin_heading_unit` for reviewed blocks (agent DB, doc 252; owner 12 Oct)
                 'source_leading_margin_heading_blocks',
                 # rules `reviewed_inline_table_blocks`, `reviewed_group_heading_blocks` (agent DF, 4347 split)
                 'source_inline_table_blocks', 'source_group_heading_blocks',
                 # rule `reviewed_decimal_item_cut` (agent JE, docs 4409/4416)
                 'source_decimal_item_cut_blocks',
                 # rule `reviewed_quoted_definition_cut` (agent JE, doc 4426)
                 'source_quoted_definition_cut_blocks',
                 # rule `reviewed_chapter_resumes_body` (agent JE, doc 4400)
                 'source_chapter_resumes_body_blocks',
                 # rule `reviewed_marked_rule_label` (agent K1, doc 4474)
                 'source_marked_rule_blocks',
                 # agent JF rule A `reviewed_long_romanette_cut` (group 26, doc 3533 p31)
                 'source_long_romanette_cut_blocks',
                 # agent JF rule E `reviewed_decoded_quote_cut` (group 29, doc 4497 E4 p86)
                 'source_decoded_quote_cut_blocks')


def long_suffix_openers_ok(value) -> bool:
    """Shape of a reviewed `source_long_suffix_section_openers` (the segmenter's own check)."""
    from nizam.corpus.segment import _long_suffix_openers_ok
    return _long_suffix_openers_ok(value)


def decoded_underscore_dash_ok(value) -> bool:
    """Shape of the reviewed glyph declaration of rule `decoded_underscore_dash` (the segmenter's own check)."""
    from nizam.corpus.segment import _agde_declaration_ok
    return _agde_declaration_ok(value)


def block_id_list_ok(value) -> bool:
    """A non-empty list of distinct positive block ids (profile rule
    `not_running_header_blocks`, doc 1431)."""
    return (isinstance(value, list) and bool(value)
            and all(type(item) is int and item > 0 for item in value)
            and len(set(value)) == len(value))


def level_cell_block_shape_ok(item) -> bool:
    """One reviewed `source_level_cell_blocks` pair {cell_block_id,
    row_block_id} (profile rule `level_cell_blocks`, doc 1431).  The segmenter
    checks the geometry (same page, tops within 2.5 pt, cell right of the
    row's start)."""
    return (isinstance(item, dict) and set(item) == {"cell_block_id", "row_block_id"}
            and type(item["cell_block_id"]) is int and item["cell_block_id"] > 0
            and type(item["row_block_id"]) is int and item["row_block_id"] > 0
            and item["cell_block_id"] != item["row_block_id"])


# The decision-review choices that ask for an unheaded table to be held as the
# instrument's APPENDIX with its rows (doc 1491 q1 'appendix-rows-by-serial');
# a `source_unlabelled_schedule_openers` entry labelled 'APPENDIX' (profile
# rule `unlabelled_appendix_opener`) must cite one.  The label 'SCHEDULE' keeps
# its existing check (the export holds the answer).
APPENDIX_OPENER_CHOICES = frozenset({"appendix-rows-by-serial",
                                     # doc 2658 q1 'appendix-rows' (owner export j; lead 13 Oct): the same effect
                                     "appendix-rows"})
UNLABELLED_OPENER_LABELS = frozenset({"SCHEDULE", "APPENDIX"})


# The decision-review choice that asks for an unquoted substituted Schedule to
# be held as items of the substituting section (doc 1431 q2 's2-text').
SUBSTITUTED_SCHEDULE_CHOICES = frozenset({"s2-text"})


# The decision-review choices an owner-cited label carries out: the CONTENTS
# numbering (doc 1225 q1 'contents') and opening a section whose number the
# copy prints only later at its first printed words, numbered from its
# contents row (doc 1457 q3 'open-at-p3', owner decision 8 Oct), and releasing
# a copy as printed with a section opened from its contents and margin where
# the printed number is not legible (doc 1463 q1 'release-as-is', export -g).
# Opening a unit at its bracketed print '(3)' (doc 1666 q1 'rule-3', export -h).
# Choice ids are per question in the decision pack, as for
# NAMED_SCHEDULE_ROW_CHOICES; the set is closed, so any other answer is refused.
# Assigning a number to a byelaw the copy prints without one, or with another
# (doc 1946 q3, q4 'assign', export -h).
# Rules 19-35 printed '(19)'-'(35)' held as rules, each with its printed heading (doc 2191 q1 'rules', export -i).
# doc 1973 q4 'number-1' (export -i): each unnumbered West Pakistan notification holds one provision '1'.
OWNER_CITED_LABEL_CHOICES = frozenset({"contents", "open-at-p3", "release-as-is", "rule-3", "assign", "rules",
                                       "number-1",
                                       # doc 2756 q1 'cite-47A' (owner 12 Oct): the second '47.' on p25 is s.47A.
                                       "cite-47A",
                                       # doc 4222 q1 'repealed-stubs' (export j, 12 Oct): the repealed sections
                                       # are held as stubs under their cited numbers (lead 13 Oct: admit the
                                       # choice; 4222 itself stays blocked).
                                       "repealed-stubs",
                                       # doc 4154 q2 'printed-6' (export j, 12 Oct): the section printed '7. 6.'
                                       # is cited as s.6, opening at its second number (lead 13 Oct).
                                       "printed-6",
                                       # doc 3700 q1 'regulations' (export j; lead 13 Oct): the bracketed '(N)' prints
                                       # are the regulations, cited by their printed numbers.
                                       "regulations",
                                       # doc 2985 q2 'other-copy' (export j; lead 13 Oct): the definitions rule takes
                                       # its number from doc 3389's copy already held.
                                       "other-copy",
                                       # doc 4149 q2 'cite-115A' (export l; lead 15 Oct): the second '115' is s.115A,
                                       # as 'cite-47A'.
                                       "cite-115A",
                                       # doc 4426 q1 'printed-42A' (export j) and q2 'same-as-42A' (delegated export,
                                       # 15 Oct; agent JE): the lettered rules 42A, 55A, 58A are cited as printed.
                                       "printed-42A", "same-as-42A",
                                       # doc 4498 q4/q6 'sequence' (export l; agent JE, 16 Oct): the body's own
                                       # numbering stands and a contents row with another number links to the rule.
                                       "sequence",
                                       # doc 4588 q1 'owner-numbered' (owner 18 Oct, decision-review-2026-10-18-
                                       # 4588.json; agent K6; group 36): rules 29 and 46, whose headings stand under
                                       # pasted slips, open at their first visible words under the owner's numbers.
                                       "owner-numbered"})
# The decision-review choice an order suffix carries out: keep both prints of
# one label, cited by order (docs 999, 1034, 1368, 1415, 1457: 'keep-both').
ORDER_SUFFIX_CHOICES = frozenset({"keep-both"})


# The decision-review choices that ask for a Schedule's rows to be held and
# cited by their printed post name with no number supplied (export -e,
# 2026-10-07: doc 1078 q1 'schedule-rows-by-post', doc 1121 q2
# 'rows-by-post'; doc 1106 q3 'rows-by-group', where a row with no printed
# serial is identified by its group caption and post name).  A
# `source_named_schedule_rows` entry citing any other answer is refused where
# the reading enters the system.
NAMED_SCHEDULE_ROW_CHOICES = frozenset({"schedule-rows-by-post", "rows-by-post", "rows-by-group"})
# The choices that ask for a Schedule's rows to be held under their printed
# group captions (doc 1106 q3 'rows-by-group'); a
# `source_schedule_group_captions` entry must cite one.
# doc 1839 q2 'rows-by-serial' (its 'II MINISTERIAL GROUP' caption over rows 55-72; lead decision 9 Oct).
# doc 2211 q1 'release-as-is' (the 'IV. SYLLABUS FOR MEDICAL/HEALTH BRANCH.' caption; export -i).
SCHEDULE_GROUP_CAPTION_CHOICES = frozenset({"rows-by-group", "rows-by-serial", "release-as-is",
                                            # doc 2611 q1 'body' (owner export j; lead 13 Oct): the Papers I-IV
                                            # captions are read as group captions
                                            "body",
                                            # doc 4264 q2 'one-schedule-rows-by-group' (delegated export, 15 Oct;
                                            # agent K4): one unlabelled SCHEDULE, its posts as rows by group caption
                                            "one-schedule-rows-by-group",
                                            # doc 4053 q3 'table-under-caption' (delegated answers, 16 Oct; agent
                                            # K4): the caption's table rows are the caption's rows
                                            "table-under-caption"})
# The choice that asks for a section's own printed caption divisions (agent K6 `section_group_caption`, group 33; doc
# 4640 q5 'section-group-captions'); a `source_section_group_captions` entry must cite one.
SECTION_GROUP_CAPTION_CHOICES = frozenset({"section-group-captions"})


def schedule_group_caption_shape_ok(item) -> bool:
    """The shape of one reviewed `source_schedule_group_captions` entry.

    Profile rule `schedule_group_caption` (doc 1106; owner decision
    2026-10-07 q3 'rows-by-group'): {source_block_id, caption, level 1|2,
    owner_decision}.  The segmenter checks that the unit's text is the
    caption and where it opens; the recorder checks the cited answer."""
    return (isinstance(item, dict)
            and set(item) == {"source_block_id", "caption", "level", "owner_decision"}
            and type(item["source_block_id"]) is int and item["source_block_id"] > 0
            and isinstance(item["caption"], str) and bool(item["caption"].strip())
            and type(item["level"]) is int and item["level"] in (1, 2)
            and _owner_citation_shape_ok(item["owner_decision"]))


def quoted_table_row_blocks_shape_ok(value) -> bool:
    """`source_quoted_table_row_blocks` (profile rule `quoted_table_row_text`,
    doc 691): a non-empty list of distinct source block ids."""
    return (isinstance(value, list) and bool(value)
            and all(type(item) is int and item > 0 for item in value)
            and len(set(value)) == len(value))


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


# Export j ports (13 Oct 2026, builder BZ): reviewed keys of agents JB and JA merged by shape (docs/SEGMENTATION-PROFILES.md).
_BZ_FLAG_KEYS = frozenset({"source_statute_row_headings", "source_explanation_of_heading", "source_chapter_over_part"})
_BZ_BLOCK_LIST_KEYS = frozenset({"source_no_cut_blocks", "source_form_text_blocks", "source_lettered_part_blocks",
                                 "source_unheaded_section_blocks",
                                 # agent JD (group 5): rules roman_chapter_line, marked_dash_section_cut, subsection_line_cut
                                 "source_chapter_line_blocks", "source_marked_dash_section_blocks",
                                 "source_subsection_line_cut_blocks",
                                 # agent JD (group 6): rule reviewed_division_line
                                 "source_division_line_blocks",
                                 # agent JD (group 7): rule reviewed_dotted_letter_item
                                 "source_dotted_letter_item_blocks",
                                 # agent K4 (group 19): rules Q, U
                                 "source_part_line_blocks",
                                 "source_dotted_serial_row_blocks",
                                 # agent K6 (group 20): rule C, doc 4643
                                 "source_division_note_blocks",
                                 # agent K6 (group 24): rule F, doc 4450
                                 "source_hyphen_first_subsection_blocks",
                                 # agent K6 (group 32): reviewed_division_series, doc 4626
                                 "source_division_series_blocks",
                                 # agent K4 (group 17): rules H, J, L, M
                                 "source_half_paren_roman_blocks",
                                 "source_bare_half_paren_subrule_blocks",
                                 "source_inserted_row_blocks",
                                 "source_bare_serial_row_blocks",
                                 # agent JD (group 14): rule reviewed_clause_repeal_stub
                                 "source_clause_repeal_stub_blocks",
                                 # group 10 (16 Oct): agents K4 (B, C, F), K5 (MS, CO), K3 (A, D)
                                 "source_heading_line_stub_blocks",
                                 "source_quote_span_end_blocks",
                                 "source_percent_clause_blocks",
                                 "source_marked_subsection_cut_blocks",
                                 "source_chapter_opener_blocks",
                                 "source_section_word_part_blocks",
                                 "source_dash_label_section_blocks"})


def _bz_margin_heading_owner_ok(v) -> bool:
    return (isinstance(v, dict) and set(v) == {"heading_block_id", "owner_block_id", "owner_label", "owner_kind"}
            and type(v["heading_block_id"]) is int and v["heading_block_id"] > 0
            and type(v["owner_block_id"]) is int and v["owner_block_id"] > 0
            and isinstance(v["owner_label"], str) and bool(v["owner_label"])
            and v["owner_kind"] in ("section", "article", "clause", "subsection"))


def _bz_root_reparent_ok(v) -> bool:
    return (isinstance(v, dict) and set(v) == {"source_block_id", "source_label", "source_kind"}
            and type(v["source_block_id"]) is int and v["source_block_id"] > 0
            and isinstance(v["source_label"], str) and bool(v["source_label"])
            and v["source_kind"] in ("section", "article"))


def _bz_contents_named_division_ok(v) -> bool:
    # agent JD rule `contents_named_division` (group 5): the segmenter checks the print and the owner answer
    return (isinstance(v, dict)
            and set(v) == {"first_block_id", "kind", "label", "heading", "contents_block_ids", "owner_decision"}
            and type(v["first_block_id"]) is int and v["first_block_id"] > 0 and v["kind"] in ("part", "chapter")
            and isinstance(v["label"], str) and bool(v["label"]) and (v["heading"] is None or isinstance(v["heading"], str))
            and isinstance(v["contents_block_ids"], list) and bool(v["contents_block_ids"])
            and all(type(x) is int and x > 0 for x in v["contents_block_ids"]))


def _bz_schedule_paragraph_heading_ok(v) -> bool:
    # agent JD rule `schedule_paragraph_printed_heading` (group 7): the segmenter checks the print, the one target clause
    # and the citation's form; the recorder checks that the export holds the cited answer
    return (isinstance(v, dict) and set(v) == {"label", "source_block_id", "heading", "owner_decision"}
            and isinstance(v["label"], str) and bool(v["label"].strip())
            and type(v["source_block_id"]) is int and v["source_block_id"] > 0
            and isinstance(v["heading"], str) and bool(v["heading"].strip())
            and isinstance(v["owner_decision"], dict))


def _bz_owner_schedule_part_ok(v) -> bool:
    # agent JD rule `owner_supplied_schedule_part` (group 8): the segmenter checks the schedule, the print of the evidence
    # block and the citation's form; the recorder checks that the export holds the cited answer
    return (isinstance(v, dict) and set(v) == {"first_block_id", "label", "evidence_block_id", "owner_decision"}
            and type(v["first_block_id"]) is int and v["first_block_id"] > 0
            and type(v["evidence_block_id"]) is int and v["evidence_block_id"] > 0
            and isinstance(v["label"], str) and bool(v["label"].strip())
            and isinstance(v["owner_decision"], dict))


def _bz_paired_repeal_stub_ok(v) -> bool:
    # agent K4 rule `paired_repeal_stub` (group 10): the segmenter checks the row, the stub and the citation's use
    return (isinstance(v, dict) and set(v) == {"body_block_id", "contents_block_id", "labels", "owner_decision"}
            and type(v["body_block_id"]) is int and v["body_block_id"] > 0
            and type(v["contents_block_id"]) is int and v["contents_block_id"] > 0
            and isinstance(v["labels"], list) and len(v["labels"]) == 2
            and all(isinstance(x, str) and x.strip() for x in v["labels"]) and isinstance(v["owner_decision"], dict))


def _bz_quoted_appendix_label_ok(v) -> bool:
    # agent K4 rule `reviewed_quoted_appendix_label` (group 10); owner_decision optional
    return (isinstance(v, dict) and {"block_id", "printed", "label"} <= set(v)
            and set(v) <= {"block_id", "printed", "label", "owner_decision"}
            and type(v["block_id"]) is int and v["block_id"] > 0
            and isinstance(v["printed"], str) and bool(v["printed"].strip())
            and isinstance(v["label"], str) and bool(v["label"].strip())
            and isinstance(v.get("owner_decision", {}), dict))


def _bz_note_owner_ok(v) -> bool:
    # agent K3 rule `reviewed_note_owner` (group 10)
    return (isinstance(v, dict) and set(v) == {"block_id", "owner_block_id", "owner_label", "owner_kind"}
            and type(v["block_id"]) is int and v["block_id"] > 0
            and type(v["owner_block_id"]) is int and v["owner_block_id"] > 0
            and isinstance(v["owner_label"], str) and bool(v["owner_label"])
            and v["owner_kind"] in ("section", "article", "clause", "subsection", "part", "chapter"))


def _bz_heading_line_ok(v) -> bool:
    # agent K3 rule `reviewed_heading_line` (group 10)
    return (isinstance(v, dict) and set(v) == {"label", "source_block_id", "heading", "owner_decision"}
            and isinstance(v["label"], str) and bool(v["label"]) and type(v["source_block_id"]) is int
            and v["source_block_id"] > 0 and isinstance(v["heading"], str) and bool(v["heading"].strip())
            and isinstance(v["owner_decision"], dict))


def _bz_form_code_opener_ok(v) -> bool:
    # agent K4 rule `reviewed_form_code_opener` (group 17); the segmenter checks the print and the label block
    return (isinstance(v, dict) and set(v) - {"printed"} == {"source_block_id", "label", "label_block_id"}
            and type(v["source_block_id"]) is int and v["source_block_id"] > 0
            and type(v["label_block_id"]) is int and v["label_block_id"] > 0
            and isinstance(v["label"], str) and bool(v["label"].strip()))


def _bz_schedule_row_cells_ok(item) -> bool:
    """Agent JF's rule D (group 27, doc 3949): {row_block_id, row_prefix, label, cell_block_ids} -- a reviewed schedule
    row (its block, the printed start of the row unit, its serial) and the cell blocks that gather after it. The
    segmenter checks the rest against the source. Rule G (group 29, doc 4497 E9): an optional "kind" ('section' or
    'clause': a table row inside a rule), and a row block printing only its serial may name '<label>.' as prefix."""
    import re as _re
    return (isinstance(item, dict)
            and set(item) - {"kind"} == {"row_block_id", "row_prefix", "label", "cell_block_ids"}
            and item.get("kind", "section") in ("section", "clause")
            and type(item["row_block_id"]) is int and item["row_block_id"] > 0
            and isinstance(item["label"], str) and _re.fullmatch(r"\d{1,3}", item["label"]) is not None
            and isinstance(item["row_prefix"], str)
            and (len(item["row_prefix"].strip()) >= 6 or item["row_prefix"].strip() == item["label"] + ".")
            and isinstance(item["cell_block_ids"], list)
            and all(type(v) is int and v > 0 for v in item["cell_block_ids"]))


def _bz_inline_margin_note_ok(item) -> bool:
    """Agent K6's rule H (group 28; docs 4529, 4558): a margin note the OCR wrote into a law block -- {block_id, anchor
    (>= 8 chars), note (>= 4 chars)} located by the law words it stands beside (marginal note), or {block_id, label
    (\\d{1,3}[A-Z]?), note} printed before that section's number (its heading)."""
    import re as _re
    if not (isinstance(item, dict) and type(item.get("block_id")) is int and item["block_id"] > 0
            and isinstance(item.get("note"), str) and len(item["note"].strip()) >= 4):
        return False
    if set(item) == {"block_id", "anchor", "note"}:
        return isinstance(item["anchor"], str) and len(item["anchor"].strip()) >= 8
    return (set(item) == {"block_id", "label", "note"} and isinstance(item["label"], str)
            and _re.fullmatch(r"\d{1,3}[A-Z]?", item["label"]) is not None)


def _bz_digit_led_clause_ok(item) -> bool:
    """Agent K6's rule E (group 23, doc 4649): {block_id, label} -- a lettered or roman clause label whose printed
    text opens with a digit ('(h) 3 Notables ...')."""
    import re as _re
    return (isinstance(item, dict) and set(item) == {"block_id", "label"} and type(item["block_id"]) is int
            and item["block_id"] > 0 and isinstance(item["label"], str)
            and _re.fullmatch(r"[a-z]{1,2}|[ivxlc]{1,6}", item["label"]) is not None)


def _bz_fused_margin_tail_ok(item) -> bool:
    """Agent K6's rule D (group 22, doc 4645): {block_id, tail} -- the exact margin words fused onto the end of a law
    line of that block (>= 4 characters)."""
    return (isinstance(item, dict) and set(item) == {"block_id", "tail"} and type(item["block_id"]) is int
            and item["block_id"] > 0 and isinstance(item["tail"], str) and len(item["tail"].strip()) >= 4)


def _bz_block_order_move_ok(item) -> bool:
    """Agent K6's `reviewed_block_order` (group 33, doc 4640 q4): {first_block_id, last_block_id, after_block_id} -- a
    run of whole pages (input order) moved to just after a page's last block; the segmenter checks the rest."""
    return (isinstance(item, dict) and set(item) == {"first_block_id", "last_block_id", "after_block_id"}
            and all(type(item[k]) is int and item[k] > 0 for k in item))


def _bz_section_group_caption_ok(item) -> bool:
    """Agent K6's `section_group_caption` (group 33, doc 4640 q5): {source_block_id, caption, label, heading, level 1|2,
    owner_decision}; the segmenter checks the caption against the unit, the recorder the cited answer."""
    return (isinstance(item, dict)
            and set(item) == {"source_block_id", "caption", "label", "heading", "level", "owner_decision"}
            and type(item["source_block_id"]) is int and item["source_block_id"] > 0
            and all(isinstance(item[k], str) and bool(item[k].strip()) for k in ("caption", "label", "heading"))
            and type(item["level"]) is int and item["level"] in (1, 2)
            and _owner_citation_shape_ok(item["owner_decision"]))


def _bz_lettered_head_ok(item) -> bool:
    """Agent K6's `reviewed_lettered_head` (group 37, doc 4591 q3): {source_block_id, label (one capital),
    source_prefix (>= 8 characters)}; the segmenter checks the printed '(<label>) CAPS' and that every entry opens."""
    return (isinstance(item, dict) and set(item) == {"source_block_id", "label", "source_prefix"}
            and type(item["source_block_id"]) is int and item["source_block_id"] > 0
            and isinstance(item["label"], str) and len(item["label"]) == 1 and item["label"].isupper()
            and isinstance(item["source_prefix"], str) and len(item["source_prefix"].strip()) >= 8)


def _bz_bracketed_rule_ok(item) -> bool:
    """Agent K6's `reviewed_bracketed_rule` (group 38, doc 4479): {source_block_id, label (1-3 digits), heading (the
    printed margin words, >= 3 characters) or null}; the segmenter checks the rest."""
    return (isinstance(item, dict) and set(item) == {"source_block_id", "label", "heading"}
            and type(item["source_block_id"]) is int and item["source_block_id"] > 0
            and isinstance(item["label"], str) and item["label"].isdigit() and 1 <= len(item["label"]) <= 3
            and (item["heading"] is None or (isinstance(item["heading"], str) and len(item["heading"].strip()) >= 3)))


_BZ_KEYED_LIST_KEYS = {"source_margin_heading_owners": (_bz_margin_heading_owner_ok, "heading_block_id"),
                       "source_contents_named_divisions": (_bz_contents_named_division_ok, "first_block_id"),
                       "source_root_reparent_blocks": (_bz_root_reparent_ok, "source_block_id"),
                       # agent JD (group 7): keyed by printed label; one reading per page, merged (doc 3901: 5 pages)
                       "source_schedule_paragraph_headings": (_bz_schedule_paragraph_heading_ok, "label"),
                       # agent JD (group 8): keyed by the block the Part opens at
                       "source_owner_schedule_parts": (_bz_owner_schedule_part_ok, "first_block_id"),
                       "source_form_code_openers": (_bz_form_code_opener_ok, "source_block_id"),   # K4 I (group 17)
                       # group 10 (16 Oct): agents K4 (A, D), K3 (B, C)
                       "source_paired_repeal_stubs": (_bz_paired_repeal_stub_ok, "body_block_id"),
                       "source_quoted_appendix_labels": (_bz_quoted_appendix_label_ok, "block_id"),
                       "source_note_owner_blocks": (_bz_note_owner_ok, "block_id"),
                       "source_heading_lines": (_bz_heading_line_ok, "label"),
                       # agent K6 rule D (group 22, doc 4645): keyed by block
                       "source_fused_margin_tails": (_bz_fused_margin_tail_ok, "block_id"),
                       # agent K6 rule E (group 23, doc 4649): keyed by block
                       "source_digit_led_clause_labels": (_bz_digit_led_clause_ok, "block_id"),
                       # agent JF rule D (group 27, doc 3949): keyed by the row's block
                       "source_schedule_row_cells": (_bz_schedule_row_cells_ok, "row_block_id"),
                       # agent K6 rule H (group 28, docs 4529/4558): keyed by note (several notes may share one block)
                       "source_inline_margin_notes": (_bz_inline_margin_note_ok, "note"),
                       # agent K6 (group 33, doc 4640): reviewed_block_order keyed by the run's first block,
                       # section_group_caption by the caption's block
                       "source_block_order_moves": (_bz_block_order_move_ok, "first_block_id"),
                       "source_section_group_captions": (_bz_section_group_caption_ok, "source_block_id"),
                       # agent K6 (group 37, doc 4591): reviewed_lettered_head, keyed by the head's block
                       "source_lettered_head_blocks": (_bz_lettered_head_ok, "source_block_id"),
                       # agent K6 (group 38, doc 4479): reviewed_bracketed_rule, keyed by label (one bracketed series)
                       "source_bracketed_rules": (_bz_bracketed_rule_ok, "label")}


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
    patch_schedule_heads: set[int] = set()
    patch_stub_cuts: set[int] = set()
    patch_reparents: list[dict] = []
    patch_continuations: list[dict] = []
    patch_unnumbered_openers: list[dict] = []
    patch_unnumbered_parts: list[dict] = []
    patch_schedule_rows: list[dict] = []
    # Profile rules `unlabelled_schedule_opener`, `quoted_table_row_text` (doc
    # 691) and `printed_heading_override` (docs 1003, 999); each patch names
    # its own page's blocks, so the lists are united like apparatus.
    patch_unlabelled_schedules: list[dict] = []
    patch_quoted_rows: set[int] = set()
    # Profile rule `half_paren_clause_label` (doc 1626): page-read block ids, united.
    patch_half_paren: set[int] = set()
    patch_printed_headings: list[dict] = []
    patch_order_suffixes: list[dict] = []
    # Profile rule `named_schedule_row` (docs 1078, 1121): each patch names
    # its own page's row blocks, so the lists are united like openers.
    patch_named_rows: list[dict] = []
    # Profile rule `schedule_group_caption` (doc 1106): page-scoped, united.
    patch_group_captions: list[dict] = []
    # Profile rule `owner_cited_label` (doc 1225): page-scoped, united.
    patch_owner_cited: list[dict] = []
    # Profile rules `substituted_schedule_items`, `not_running_header_blocks`,
    # `level_cell_blocks` (doc 1431): page-scoped lists, united.
    patch_substituted: list[dict] = []
    patch_not_running: set[int] = set()
    # Rules `contents_marker_block` (page-read block ids, united) and `heading_scan_section_only` (true;
    # must agree) -- stage 3, agent DB, owner 11 Oct.
    patch_contents_markers: set[int] = set()
    patch_section_only: bool | None = None
    # Rule `decoded_underscore_dash` (stage 3, agent DE, owner 12 Oct): one reviewed glyph declaration per
    # observation; a second patch must carry the identical value.
    patch_underscore_dash: dict | None = None
    # Rule `reviewed_long_suffix_section` (stage 3, agent DE, doc 4225; owner 12 Oct): one value per observation.
    patch_long_suffix: list | None = None
    # Rules `reviewed_decimal_cut`, `reviewed_table_row_blocks`, `reviewed_division_continues`,
    # `reviewed_marked_label_cut` (page-read block ids, united) -- stage 3, agent DF, owner 11-12 Oct.
    patch_df_blocks: dict[str, set[int]] = {key: set() for key in DF_BLOCK_KEYS}
    patch_level_cells: list[dict] = []
    for patch in patches or []:
        evidence = patch.get("evidence") or {}
        for key, value in (evidence.get("structural_overrides") or {}).items():
            if key == "source_schedule_heading_blocks":
                # Rule `reviewed_schedule_heading` (agent DC, doc 2703): page-read block ids, united.
                if not block_id_list_ok(value):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_schedule_heads.update(value)
                continue
            if key == "source_repeal_stub_cut_blocks":
                # Rule `reviewed_repeal_stub_cut` (agent DC, doc 2703): page-read block ids, united.
                if not block_id_list_ok(value):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_stub_cuts.update(value)
                continue
            if key == "source_apparatus_blocks":
                if not (isinstance(value, list) and value
                        and all(type(item) is int and item > 0 for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_apparatus.update(value)
                continue
            if key == "source_unlabelled_schedule_openers":
                if not (isinstance(value, list) and value
                        and all(unlabelled_schedule_opener_shape_ok(item) for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_unlabelled_schedules.extend(value)
                continue
            if key == "source_quoted_table_row_blocks":
                if not quoted_table_row_blocks_shape_ok(value):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_quoted_rows.update(value)
                continue
            if key == "source_half_paren_clause_blocks":
                # same shape as quoted row blocks: distinct positive block ids
                if not quoted_table_row_blocks_shape_ok(value):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_half_paren.update(value)
                continue
            if key == "source_margin_note_pieces":
                # Rule `reviewed_margin_note_pieces` (agent JE, doc 4426): page-scoped entry lists, united.
                if not (isinstance(value, list) and value and all(
                        isinstance(item, dict) and type(item.get("target_block_id")) is int
                        and isinstance(item.get("source_block_ids"), list) and item["source_block_ids"]
                        and isinstance(item.get("label"), str) and isinstance(item.get("heading"), str)
                        for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                merged[key] = list(merged.get(key) or []) + [v for v in value if v not in (merged.get(key) or [])]
                continue
            if key == "source_figure_subsections":
                # Rule `reviewed_figure_subsections` (agent JE, doc 4521): one reviewed entry list per observation.
                if not (isinstance(value, list) and value and all(
                        isinstance(item, dict) and type(item.get("section_block_id")) is int
                        and isinstance(item.get("subsections"), list) and item["subsections"]
                        for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                if key in merged and merged[key] != value:
                    raise ValueError(f"conflicting reviewed structural override {key}")
                merged[key] = value
                continue
            if key in ("source_division_openers", "source_division_captions"):
                # Rules `reviewed_division_opener`, `reviewed_division_caption` (agent JE, doc 4426): entry lists, united.
                if not (isinstance(value, list) and value and all(isinstance(item, dict) for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                merged[key] = list(merged.get(key) or []) + [v for v in value if v not in (merged.get(key) or [])]
                continue
            if key == "source_bound_notes":
                # Rule `reviewed_bound_note` (agent K2, doc 4397): page-scoped entry lists, united in print order.
                if not (isinstance(value, list) and value and all(
                        isinstance(item, dict) and set(item) - {"use"} == {"source_block_id", "source_prefix",
                                                                           "end_block_id", "end_prefix", "owner_kind",
                                                                           "owner_label"}
                        and type(item["source_block_id"]) is int and type(item["end_block_id"]) is int
                        for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                merged[key] = list(merged.get(key) or []) + [v for v in value if v not in (merged.get(key) or [])]
                continue
            if key == "source_table_close_blocks":
                # Rule `reviewed_table_close` (agent K2, doc 4489): page-scoped entry lists, united.
                if not (isinstance(value, list) and value and all(
                        isinstance(item, dict) and set(item) - {"source_prefix"} == {"source_block_id", "owner_block_id"}
                        and type(item["source_block_id"]) is int
                        and (item["owner_block_id"] is None or type(item["owner_block_id"]) is int)
                        for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                merged[key] = list(merged.get(key) or []) + [v for v in value if v not in (merged.get(key) or [])]
                continue
            if key == "source_unstopped_contents_rows":
                # Rule `reviewed_unstopped_contents_rows` (agent K2, doc 4369): page-scoped entry lists, united.
                if not (isinstance(value, list) and value and all(
                        isinstance(item, dict) and set(item) == {"source_block_id", "label"} for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                merged[key] = list(merged.get(key) or []) + [v for v in value if v not in (merged.get(key) or [])]
                continue
            if key == "source_contents_page_column":
                # Rule `reviewed_contents_page_column` (agent K2, doc 4489): an observation flag.
                if value is not True:
                    raise ValueError(f"unsupported curation structural override {key}")
                merged[key] = True
                continue
            if key == "source_half_paren_subrule_blocks":
                # Rule `reviewed_half_paren_subrules` (agent K2, doc 4431): page-read block ids, united.
                if not block_id_list_ok(value):
                    raise ValueError(f"unsupported curation structural override {key}")
                merged[key] = sorted(set(merged.get(key) or []) | set(value))
                continue
            if key == "source_label_moves":
                # Rule `reviewed_label_block_move` (agent K2, doc 4431): applied with the curation patches; the merged
                # override only records them (page-scoped lists, united).
                if not (isinstance(value, list) and value and all(
                        isinstance(item, dict)
                        and set(item) == {"label_block_id", "label", "target_block_id", "target_prefix"}
                        for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                merged[key] = list(merged.get(key) or []) + [v for v in value if v not in (merged.get(key) or [])]
                continue
            if key == "source_reviewed_grid_rows":
                if not (isinstance(value, list) and value and all(reviewed_grid_row_shape_ok(v) for v in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                prior = {v["source_block_id"]: v for v in merged.get(key, [])}
                for row_spec in value:
                    bid = row_spec["source_block_id"]
                    if bid in prior and prior[bid] != row_spec:
                        raise ValueError("conflicting reviewed grid row")
                    prior[bid] = row_spec
                merged[key] = list(prior.values())
                continue
            if key == "source_unit_moves":
                if not (isinstance(value, list) and value and all(reviewed_unit_move_shape_ok(v) for v in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                merged[key] = list(merged.get(key) or []) + [v for v in value if v not in (merged.get(key) or [])]
                continue
            if key == "source_quoted_insertion_spans":
                # Rule `reviewed_quoted_insertion_span` (agent K2, doc 4431): page-scoped span lists, united.
                if not (isinstance(value, list) and value and all(
                        isinstance(item, dict)
                        and set(item) == {"first_block_id", "first_prefix", "last_block_id", "last_prefix"}
                        for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                merged[key] = list(merged.get(key) or []) + [v for v in value if v not in (merged.get(key) or [])]
                continue
            if key == "source_division_unit_openers":
                # agent K4 rule `reviewed_division_unit_opener` (group 19, doc 3730): one entry per (block, prefix)
                if not (isinstance(value, list) and value and all(
                        isinstance(item, dict) and set(item) == {"source_block_id", "source_prefix", "kind", "label"}
                        and type(item["source_block_id"]) is int and isinstance(item["source_prefix"], str)
                        and len(item["source_prefix"].strip()) >= 8
                        and item["kind"] in ("form", "appendix", "annexure", "schedule")
                        and (item["label"] is None or isinstance(item["label"], str)) for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                _k4v = {(v["source_block_id"], v["source_prefix"]): v for v in (merged.get(key) or [])}
                for item in value:
                    k4 = (item["source_block_id"], item["source_prefix"])
                    if k4 in _k4v and _k4v[k4] != item:
                        raise ValueError(f"conflicting reviewed division unit opener {k4}")
                    _k4v[k4] = item
                merged[key] = list(_k4v.values())
                continue
            if key == "source_set_aside_units":
                # Rule `reviewed_set_aside_unit` (agent JE, doc 4431 q4): page-scoped entry lists, united.
                if not (isinstance(value, list) and value and all(
                        isinstance(item, dict) and set(item) == {"source_block_id", "source_prefix"}
                        and type(item["source_block_id"]) is int and isinstance(item["source_prefix"], str)
                        for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                merged[key] = list(merged.get(key) or []) + [v for v in value if v not in (merged.get(key) or [])]
                continue
            if key == "source_printed_rule_openers":
                # Rule `reviewed_printed_rule_opener` (agent JE, doc 4431): page-scoped entry lists, united.
                if not (isinstance(value, list) and value and all(
                        isinstance(item, dict) and set(item) - {"kind"} == {"source_block_id", "label", "source_prefix"}
                        and type(item["source_block_id"]) is int and isinstance(item["label"], str)
                        and isinstance(item["source_prefix"], str) for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                merged[key] = list(merged.get(key) or []) + [v for v in value if v not in (merged.get(key) or [])]
                continue
            if key == "source_hyphen_rule_numbers":
                # Rule `reviewed_hyphen_rule_numbers` (agent JE, doc 4498): one reviewed entry per observation.
                if not isinstance(value, dict):
                    raise ValueError(f"unsupported curation structural override {key}")
                if key in merged and merged[key] != value:
                    raise ValueError(f"conflicting reviewed structural override {key}")
                merged[key] = value
                continue
            if key == "source_list_text_sections":
                # Rule `reviewed_list_item_text` (agent JE, docs 4408/4409/4416): page-scoped entry lists, united.
                if not (isinstance(value, list) and value and all(
                        isinstance(item, dict)
                        and set(item) - {"item_kind", "owner_decision"} == {"section_block_id", "section_label", "items"}
                        and type(item["section_block_id"]) is int and type(item["items"]) is int
                        and isinstance(item["section_label"], str) for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                _lt_have = list(merged.get(key) or [])
                for item in value:
                    if any(h["section_block_id"] == item["section_block_id"] and h != item for h in _lt_have):
                        raise ValueError(f"conflicting reviewed structural override {key}")
                    if item not in _lt_have:
                        _lt_have.append(item)
                merged[key] = _lt_have
                continue
            if key == "source_text_units":
                # Rule `reviewed_text_unit` (agent JE, doc 4408): page-scoped entry lists, united.
                if not (isinstance(value, list) and value and all(
                        isinstance(item, dict) and set(item) - {"as_kind"} == {"source_block_id", "kind", "label"}
                        and type(item["source_block_id"]) is int and isinstance(item["kind"], str)
                        and isinstance(item["label"], str) for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                merged[key] = list(merged.get(key) or []) + [v for v in value if v not in (merged.get(key) or [])]
                continue
            # Export j ports (builder BZ): JB D/F and JA C flags, JB G and JA F/G/H block lists, JB H/I keyed lists,
            # JA E's one declaration per observation.
            if key in _BZ_FLAG_KEYS:
                if value is not True:
                    raise ValueError(f"unsupported curation structural override {key}")
                merged[key] = True
                continue
            if key in _BZ_BLOCK_LIST_KEYS:
                if not (isinstance(value, list) and value and all(type(x) is int and x > 0 for x in value)
                        and len(set(value)) == len(value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                merged[key] = list(merged.get(key) or []) + [x for x in value if x not in (merged.get(key) or [])]
                continue
            if key in _BZ_KEYED_LIST_KEYS:
                _bz_ok, _bz_id = _BZ_KEYED_LIST_KEYS[key]
                if not (isinstance(value, list) and value and all(_bz_ok(x) for x in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                _bz_have = {x[_bz_id]: x for x in (merged.get(key) or [])}
                for x in value:
                    if x[_bz_id] in _bz_have and _bz_have[x[_bz_id]] != x:
                        raise ValueError(f"conflicting reviewed {key} {x[_bz_id]}")
                    _bz_have[x[_bz_id]] = x
                merged[key] = [_bz_have[i] for i in sorted(_bz_have)]
                continue
            if key == "source_contents_schedule_rows":
                if not (isinstance(value, dict)
                        and set(value) in ({"schedule_block_id", "owner_decision"},
                                          {"schedule_block_id", "owner_decision", "row_labels", "row_kind"})
                        and type(value["schedule_block_id"]) is int and value["schedule_block_id"] > 0
                        and value.get("row_kind", "clause") in ("section", "clause")
                        and ("row_labels" not in value or (isinstance(value["row_labels"], dict)
                             and value["row_labels"] and all(isinstance(k, str) and k.isdigit()
                             and isinstance(v, str) and v.strip() for k,v in value["row_labels"].items())
                             and len(set(value["row_labels"].values())) == len(value["row_labels"])))):
                    raise ValueError(f"unsupported curation structural override {key}")
                if key in merged and merged[key] != value:
                    raise ValueError(f"conflicting reviewed structural override {key}")
                merged[key] = value
                continue
            if key == "source_contents_region":
                # Rule `reviewed_contents_region` (agent JE, docs 4400/4137): one reviewed region per observation.
                if not isinstance(value, dict):
                    raise ValueError(f"unsupported curation structural override {key}")
                if key in merged and merged[key] != value:
                    raise ValueError(f"conflicting reviewed structural override {key}")
                merged[key] = value
                continue
            if key == "source_printed_headings":
                if not (isinstance(value, list) and value
                        and all(printed_heading_shape_ok(item) for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_printed_headings.extend(value)
                continue
            if key == "source_order_suffix_labels":
                if not (isinstance(value, list) and value
                        and all(order_suffix_label_shape_ok(item) for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_order_suffixes.extend(value)
                continue
            if key == "source_contents_row_links":
                # Profile rule `reviewed_contents_alignment` (doc 1368): the
                # alignment is one page-read list, so patches must agree.
                if not contents_row_links_ok(value):
                    raise ValueError(f"unsupported curation structural override {key}")
                if key in merged and merged[key] != value:
                    raise ValueError(f"conflicting reviewed structural override {key}")
                merged[key] = value
                continue
            if key == "source_substituted_schedule_items":
                if not (isinstance(value, list) and value
                        and all(substituted_schedule_items_shape_ok(item) for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_substituted.extend(value)
                continue
            if key == "source_contents_marker_blocks":
                if not block_id_list_ok(value):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_contents_markers.update(value)
                continue
            if key in DF_BLOCK_KEYS:
                if not block_id_list_ok(value):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_df_blocks[key].update(value)
                continue
            if key == "source_long_suffix_section_openers":
                if not long_suffix_openers_ok(value):
                    raise ValueError(f"unsupported curation structural override {key}")
                if patch_long_suffix is not None and patch_long_suffix != value:
                    raise ValueError(f"conflicting reviewed structural override {key}")
                patch_long_suffix = value
                continue
            if key == "source_decoded_underscore_dash":
                if not decoded_underscore_dash_ok(value):
                    raise ValueError(f"unsupported curation structural override {key}")
                if patch_underscore_dash is not None and patch_underscore_dash != value:
                    raise ValueError(f"conflicting reviewed structural override {key}")
                patch_underscore_dash = value
                continue
            if key == "source_heading_scan_section_only":
                if value is not True or (patch_section_only is not None and patch_section_only != value):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_section_only = True
                continue
            if key == "source_not_running_header_blocks":
                if not block_id_list_ok(value):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_not_running.update(value)
                continue
            if key == "source_level_cell_blocks":
                if not (isinstance(value, list) and value
                        and all(level_cell_block_shape_ok(item) for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_level_cells.extend(value)
                continue
            if key == "source_owner_cited_labels":
                if not (isinstance(value, list) and value
                        and all(owner_cited_label_shape_ok(item) for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_owner_cited.extend(value)
                continue
            if key == "source_schedule_group_captions":
                if not (isinstance(value, list) and value
                        and all(schedule_group_caption_shape_ok(item) for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_group_captions.extend(value)
                continue
            if key == "source_named_schedule_rows":
                if not (isinstance(value, list) and value
                        and all(named_schedule_row_shape_ok(item) for item in value)):
                    raise ValueError(f"unsupported curation structural override {key}")
                patch_named_rows.extend(value)
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
                             and (item.get("kind") in (
                                 "clause", "subsection", "explanation", "proviso")
                                  # Rule `reviewed_schedule_chapter_reparent` (stage 3, agent DG, doc 4236): a
                                  # schedule's printed CHAPTER closed the schedule (chapter and schedule share
                                  # depth 2) and opened at the Act root; the reviewed spec moves it, with its
                                  # subtree, under the schedule that prints it. Only chapter -> schedule.
                                  or (item.get("kind") == "chapter"
                                      and item.get("source_kind") == "chapter"
                                      and item.get("parent_kind") == "schedule")
                                  # Rule `reviewed_clause_section_reparent` (agent JE, doc 4441 s.390): a numbered
                                  # section the walk demoted to a clause of the section before it returns, with its
                                  # subtree, to the chapter/part printing it. Only clause -> section, named label.
                                  or (item.get("kind") == "section"
                                      and item.get("source_kind") == "clause"
                                      and isinstance(item.get("source_label"), str)
                                      and item.get("parent_kind") in ("chapter", "part"))
                                  # Rule `reviewed_annexure_appendix_reparent` (agent JE, doc 4400 q5): an annexure
                                  # the walk opened at the root returns, with its subtree, under the appendix
                                  # printing it. Only annexure -> appendix.
                                  or (item.get("kind") == "annexure"
                                      and item.get("source_kind") == "annexure"
                                      and item.get("parent_kind") == "appendix"))
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
    if patch_stub_cuts:
        merged["source_repeal_stub_cut_blocks"] = sorted(
            patch_stub_cuts | set(merged.get("source_repeal_stub_cut_blocks") or []))
    if patch_schedule_heads:
        merged["source_schedule_heading_blocks"] = sorted(
            patch_schedule_heads | set(merged.get("source_schedule_heading_blocks") or []))
    if patch_apparatus:
        merged["source_apparatus_blocks"] = sorted(
            patch_apparatus | set(merged.get("source_apparatus_blocks") or []))
    if patch_reparents:
        combined = list(merged.get("source_reparent_blocks") or []) + patch_reparents
        unique: dict[tuple, dict] = {}
        for item in combined:
            # agent K6 (group 33, doc 4640 p25): source_ordinal is part of a reviewed reparent's identity -- one
            # block can print the same label twice (34(3)(c)'s (v)-(vii) and (d)'s (v)-(vii)) and the segmenter
            # resolves the ordinal (doc 4447), so two such specs are two specs, not one conflicting spec
            key = (item["source_block_id"], item.get("source_label"),
                   item.get("source_kind"), item.get("source_ordinal"))
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
    if patch_unlabelled_schedules:
        combined = (list(merged.get("source_unlabelled_schedule_openers") or [])
                    + patch_unlabelled_schedules)
        unique_schedules: dict[int, dict] = {}
        for item in combined:
            source_id = item["source_block_id"]
            if source_id in unique_schedules and unique_schedules[source_id] != item:
                raise ValueError(f"conflicting reviewed unlabelled schedule opener {source_id}")
            unique_schedules[source_id] = item
        merged["source_unlabelled_schedule_openers"] = list(unique_schedules.values())
    if patch_quoted_rows:
        merged["source_quoted_table_row_blocks"] = sorted(
            patch_quoted_rows | set(merged.get("source_quoted_table_row_blocks") or []))
    if patch_half_paren:
        merged["source_half_paren_clause_blocks"] = sorted(
            patch_half_paren | set(merged.get("source_half_paren_clause_blocks") or []))
    if patch_printed_headings:
        combined = list(merged.get("source_printed_headings") or []) + patch_printed_headings
        unique_headings: dict[str, dict] = {}
        for item in combined:
            label = item["label"]
            if label in unique_headings and unique_headings[label] != item:
                raise ValueError(f"conflicting reviewed printed heading {label!r}")
            unique_headings[label] = item
        merged["source_printed_headings"] = list(unique_headings.values())
    if patch_order_suffixes:
        combined = list(merged.get("source_order_suffix_labels") or []) + patch_order_suffixes
        unique_suffixes: dict[tuple, dict] = {}
        for item in combined:
            # Keyed on the first print as well: two sections may each print
            # a duplicate sub-section (2) (doc 1034); two entries naming the
            # same first print with different later prints still conflict.
            group = (item["kind"], item["label"], item["source_block_ids"][0])
            if group in unique_suffixes and unique_suffixes[group] != item:
                raise ValueError(f"conflicting reviewed order suffix {group!r}")
            unique_suffixes[group] = item
        merged["source_order_suffix_labels"] = list(unique_suffixes.values())
    if patch_named_rows:
        combined = list(merged.get("source_named_schedule_rows") or []) + patch_named_rows
        unique_named_rows: dict[int, dict] = {}
        for item in combined:
            source_id = item["source_block_id"]
            if source_id in unique_named_rows and unique_named_rows[source_id] != item:
                raise ValueError(f"conflicting reviewed named schedule row {source_id}")
            unique_named_rows[source_id] = item
        merged["source_named_schedule_rows"] = list(unique_named_rows.values())
    if patch_group_captions:
        combined = list(merged.get("source_schedule_group_captions") or []) + patch_group_captions
        unique_captions: dict[tuple, dict] = {}
        for item in combined:
            # agent K4 rule `group_caption_cut_from_block` (doc 3730 p21: four captions in one block): one entry per
            # (block, caption); the same entry twice is one, two different entries for one (block, caption) refuse
            source_id = (item["source_block_id"], " ".join((item.get("caption") or "").split()))
            if source_id in unique_captions and unique_captions[source_id] != item:
                raise ValueError(f"conflicting reviewed schedule group caption {source_id}")
            unique_captions[source_id] = item
        merged["source_schedule_group_captions"] = list(unique_captions.values())
    if patch_owner_cited:
        # Deduplicated by the print they name: block, printed label, kind (a
        # block may print two sections; one print takes one cited label).
        combined = list(merged.get("source_owner_cited_labels") or []) + patch_owner_cited
        unique_cited: dict[tuple, dict] = {}
        for item in combined:
            group = (item["source_block_id"], item["printed_label"], item["kind"],
                     # extension `owner_cited_cross_chapter_label` (agent JE, doc 4498): which print
                     item.get("source_occurrence", 1),
                     # extension `owner_cited_openers_per_prefix` (agent JE, doc 4498 q8): an opener's print
                     item.get("source_prefix"))
            if group in unique_cited and unique_cited[group] != item:
                raise ValueError(f"conflicting reviewed owner cited label {group!r}")
            unique_cited[group] = item
        merged["source_owner_cited_labels"] = list(unique_cited.values())
    if patch_substituted:
        combined = list(merged.get("source_substituted_schedule_items") or []) + patch_substituted
        unique_spans: dict[int, dict] = {}
        for item in combined:
            source_id = item["schedule_block_id"]
            if source_id in unique_spans and unique_spans[source_id] != item:
                raise ValueError(f"conflicting reviewed substituted schedule {source_id}")
            unique_spans[source_id] = item
        merged["source_substituted_schedule_items"] = list(unique_spans.values())
    if patch_contents_markers:
        merged["source_contents_marker_blocks"] = sorted(
            patch_contents_markers | set(merged.get("source_contents_marker_blocks") or []))
    if patch_section_only:
        merged["source_heading_scan_section_only"] = True
    if patch_long_suffix is not None:
        merged["source_long_suffix_section_openers"] = patch_long_suffix
    if patch_underscore_dash is not None:
        merged["source_decoded_underscore_dash"] = patch_underscore_dash
    for key, ids in patch_df_blocks.items():
        if ids:
            merged[key] = sorted(ids | set(merged.get(key) or []))
    if patch_not_running:
        merged["source_not_running_header_blocks"] = sorted(
            patch_not_running | set(merged.get("source_not_running_header_blocks") or []))
    if patch_level_cells:
        combined = list(merged.get("source_level_cell_blocks") or []) + patch_level_cells
        unique_cells: dict[int, dict] = {}
        for item in combined:
            source_id = item["cell_block_id"]
            if source_id in unique_cells and unique_cells[source_id] != item:
                raise ValueError(f"conflicting reviewed level cell {source_id}")
            unique_cells[source_id] = item
        merged["source_level_cell_blocks"] = list(unique_cells.values())
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
    ap.add_argument("--approve-release-change", metavar="REASON",
                    default=os.environ.get("NIZAM_APPROVE_RELEASE_CHANGE"),
                    help="replace a RELEASED tree although the rebuild differs from it: "
                         "'<reason; owner approval ref>', recorded in segmentation_run.detail "
                         "(without it such a replacement is refused; identical rebuilds pass)")
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
        profile = "unresolved"
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
                                       detail=run_identity(profile),
                                       duration_ms=int((time.time() - t0) * 1000))
                failed += 1
                continue
            # Fail closed BEFORE building: observations of one blob must carry the same readings and profile
            # (same_blob_problem; doc 4419, lead 12 Oct).
            same_blob = same_blob_observation_problem(doc_id)
            if same_blob:
                raise ValueError(same_blob)
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
                                               "blocks_unstructured": unstructured_count,
                                               **run_identity(profile)},
                                       duration_ms=int((time.time() - t0) * 1000))
                failed += 1
                continue
            save_report: dict = {}
            instrument_id = legal_write.save(
                inst, writer, approve_release_change=a.approve_release_change,
                report=save_report)
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
                           if seg.contents_alignment else {}),
                        **run_identity(profile),
                        # The run's approval reason is recorded whenever one was given -- also where no released tree
                        # changed (a blocked expression newly released), so tools/released_count_guard.py can read a
                        # declared rise (12 Oct 2026).
                        **({"release_change_approval": " ".join(a.approve_release_change.split())}
                           if a.approve_release_change else {}),
                        # A released tree replaced although it changed: the approval and what changed.
                        **save_report},
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
                                       detail=run_identity(profile),
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
