"""Run the independent Surya layout parser only over the live release backlog.

This is a shadow lane, not another publisher.  ``prepare`` takes a repeatable-
read snapshot of instruments absent from ``v_release_instrument`` and stages
only documents whose Surya coverage is incomplete.  ``verify`` proves that the
snapshot is still current and that no instrument released at snapshot time has
changed.  ``propose`` maps Surya's labelled page regions back to immutable
``text_block`` rows and writes evidence proposals; it never adjudicates or
writes a legal tree.

Typical use (inside WSL)::

    uv run python tools/second_parser_release.py prepare \
        --out .artifacts/second-parser/current --stage
    tools/run_surya_ocr.sh \
        .artifacts/second-parser/current/input \
        .artifacts/second-parser/current/output
    uv run python tools/second_parser_release.py import-results \
        --run .artifacts/second-parser/current
    uv run python tools/second_parser_release.py verify \
        --run .artifacts/second-parser/current
    uv run python tools/second_parser_release.py propose \
        --run .artifacts/second-parser/current

The manifest is deliberately self-invalidating.  A replay, adjudication or
source replacement after ``prepare`` makes that target stale; re-run prepare
instead of applying yesterday's answer to today's tree.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable

from nizam.storage.db import connect


SURYA_ENGINE_PREFIX = "surya-"
TOOL_VERSION = "nizam.second_parser_release/1"
DEFAULT_CORPUS_ROOT = Path("/mnt/e/nizam-data")

TARGET_SQL = """
SELECT i.id::text AS instrument_id,
       i.document_id,
       i.source_observation_id,
       i.expression_ordinal,
       i.source_sha256,
       i.short_title,
       d.page_count,
       b.object_key,
       (SELECT count(*) FROM v_toc_gap_pending g
         WHERE g.instrument_id=i.id) AS toc_count,
       (SELECT count(*) FROM v_structural_adjudication_pending s
         WHERE s.instrument_id=i.id) AS s7_count,
       (SELECT count(*) FROM v_boundary_adjudication_pending x
         WHERE x.document_id=i.document_id) AS boundary_count
  FROM instrument i
  JOIN document d ON d.id=i.document_id AND d.is_active
  JOIN blob b ON b.sha256=d.sha256
 WHERE i.is_active
   AND i.duplicate_of IS NULL
   AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)
 ORDER BY i.document_id,i.expression_ordinal,i.id
"""

RELEASE_FINGERPRINT_SQL = """
SELECT i.id::text,
       md5(jsonb_build_object(
           'instrument', to_jsonb(i),
           'provisions', coalesce((
               SELECT jsonb_agg(
                   jsonb_build_object(
                       'id',p.id,'parent',p.parent_id,'path',p.path::text,
                       'kind',p.kind::text,'label',p.label,'heading',p.heading,
                       'ordinal',p.ordinal,'first_page',p.first_page,
                       'last_page',p.last_page,'first_block',p.first_block,
                       'versions',coalesce((
                           SELECT jsonb_agg(to_jsonb(v) ORDER BY v.created_at,v.id)
                             FROM provision_version v WHERE v.provision_id=p.id
                       ),'[]'::jsonb)
                   ) ORDER BY p.ordinal,p.id
               ) FROM provision p WHERE p.instrument_id=i.id
           ),'[]'::jsonb)
       )::text) AS fingerprint
  FROM v_release_instrument i
 ORDER BY i.id
"""

RELEASE_IDENTITY_SQL = """
SELECT id::text AS instrument_id,
       document_id,
       source_observation_id,
       expression_ordinal,
       source_sha256
  FROM v_release_instrument
 ORDER BY id
"""


def _rows(cur, sql: str, params=None) -> list[dict]:
    cur.execute(sql, params or ())
    names = [column.name for column in cur.description]
    return [dict(zip(names, values)) for values in cur.fetchall()]


def _json_hash(value) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str,
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, default=str, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True,
    ).strip()


def _source_hash() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _blocker_rows(cur, instrument_ids: list[str]) -> tuple[list[dict], list[dict]]:
    if not instrument_ids:
        return [], []
    toc = _rows(cur, """
        SELECT instrument_id::text,toc_entry_id,document_id,ordinal,
               printed_label,printed_heading,entry_kind,source_block_id,
               source_page,resolution,adjudication_id::text
          FROM v_toc_gap_pending
         WHERE instrument_id=ANY(%s::uuid[])
         ORDER BY instrument_id,ordinal,toc_entry_id
    """, (instrument_ids,))
    s7 = _rows(cur, """
        SELECT id::text,instrument_id::text,source_observation_id,document_id,
               printed_label,source_block_id,source_page,
               canonical_source_block_id,canonical_source_page,
               proposed_resolution,decision_kind,original_kind::text
          FROM v_structural_adjudication_pending
         WHERE instrument_id=ANY(%s::uuid[])
         ORDER BY instrument_id,source_page,id
    """, (instrument_ids,))
    return toc, s7


def _blocker_signatures(targets: list[dict], toc: list[dict],
                        s7: list[dict]) -> dict[str, str]:
    toc_by = defaultdict(list)
    s7_by = defaultdict(list)
    for row in toc:
        toc_by[row["instrument_id"]].append(row)
    for row in s7:
        s7_by[row["instrument_id"]].append(row)
    return {
        row["instrument_id"]: _json_hash({
            "toc": toc_by[row["instrument_id"]],
            "s7": s7_by[row["instrument_id"]],
            "boundary_count": row["boundary_count"],
        })
        for row in targets
    }


def snapshot() -> dict:
    """Read one internally consistent release/backlog snapshot."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        measured = _rows(cur, """
            SELECT now() AS measured_at,current_database() AS database,
                   (SELECT count(*) FROM instrument
                     WHERE is_active AND duplicate_of IS NULL) AS canonical,
                   (SELECT count(*) FROM v_release_instrument) AS released
        """)[0]
        targets = _rows(cur, TARGET_SQL)
        instrument_ids = [row["instrument_id"] for row in targets]
        toc, s7 = _blocker_rows(cur, instrument_ids)
        signatures = _blocker_signatures(targets, toc, s7)
        for row in targets:
            row["blocker_signature"] = signatures[row["instrument_id"]]
        released = dict(cur.execute(RELEASE_FINGERPRINT_SQL).fetchall())
        document_ids = sorted({row["document_id"] for row in targets})
        coverage = _rows(cur, """
            SELECT document_id,page_no
              FROM page_ocr_candidate
             WHERE document_id=ANY(%s) AND engine LIKE %s
             GROUP BY document_id,page_no ORDER BY document_id,page_no
        """, (document_ids, SURYA_ENGINE_PREFIX + "%"))
        # Cheap, deliberately broad candidates for a missing TOC row's body
        # occurrence.  Surya only needs the pages that could settle a blocker,
        # not all 20,000+ pages in the withheld corpus.
        opener_blocks = _rows(cur, r"""
            SELECT document_id,page_no,text
              FROM text_block
             WHERE document_id=ANY(%s)
               AND text ~ '(?m)^\s*(?:[0-9]{1,3}\[\s*)?[0-9]{1,4}[A-Za-z]?'
             ORDER BY document_id,page_no,reading_order
        """, (document_ids,))
    documents = {}
    for row in targets:
        documents.setdefault(row["document_id"], {
            "document_id": row["document_id"],
            "source_sha256": row["source_sha256"],
            "object_key": row["object_key"],
            "page_count": row["page_count"],
            "instrument_ids": [],
        })["instrument_ids"].append(row["instrument_id"])
    coverage_by_doc = defaultdict(set)
    for row in coverage:
        coverage_by_doc[row["document_id"]].add(row["page_no"])
    toc_by_doc = defaultdict(list)
    s7_by_doc = defaultdict(list)
    openers_by_doc = defaultdict(list)
    for row in toc:
        toc_by_doc[row["document_id"]].append(row)
    for row in s7:
        s7_by_doc[row["document_id"]].append(row)
    for row in opener_blocks:
        openers_by_doc[row["document_id"]].append(row)
    for document in documents.values():
        document_id = document["document_id"]
        covered = coverage_by_doc[document_id]
        wanted = {1}
        unresolved_toc = 0
        for blocker in toc_by_doc[document_id]:
            if blocker.get("source_page"):
                wanted.add(int(blocker["source_page"]))
            label = (blocker.get("printed_label") or "").strip().rstrip(".")
            heading = _normalise(blocker.get("printed_heading"))
            label_pattern = re.compile(
                r"(?m)^\s*(?:\d{1,3}\[\s*)?" + re.escape(label)
                + r"\s*(?:[.)\]:-]|\s)", re.I) if label else None
            hits = {
                int(block["page_no"])
                for block in openers_by_doc[document_id]
                if ((label_pattern and label_pattern.search(block["text"] or ""))
                    or (len(heading) >= 12
                        and heading in _normalise(block["text"])))
                and int(block["page_no"]) != blocker.get("source_page")
            }
            if hits:
                wanted.update(hits)
            else:
                unresolved_toc += 1
        for blocker in s7_by_doc[document_id]:
            wanted.update(int(page) for page in (
                blocker.get("source_page"), blocker.get("canonical_source_page"))
                          if page)
        # One page of context on either side lets the layout model distinguish
        # a footer/table continuation from a provision that crosses a page.
        wanted = {
            page for anchor in wanted
            for page in (anchor - 1, anchor, anchor + 1)
            if 1 <= page <= document["page_count"]
        }
        document["surya_page_numbers"] = sorted(covered)
        document["surya_pages"] = len(covered)
        document["target_pages"] = sorted(wanted)
        document["missing_target_pages"] = sorted(wanted - covered)
        document["unlocated_toc_gaps"] = unresolved_toc
        document["needs_second_parse"] = bool(wanted - covered)
    return {
        "manifest": {
            **measured,
            "blocked": len(targets),
            "blocked_documents": len(documents),
            "toc": len(toc),
            "s7": len(s7),
            "git_commit": _git_commit(),
            "tool": TOOL_VERSION,
            "tool_sha256": _source_hash(),
            "target_query_sha256": hashlib.sha256(
                TARGET_SQL.encode("utf-8")).hexdigest(),
        },
        "targets": targets,
        "documents": list(documents.values()),
        "toc": toc,
        "s7": s7,
        "released": released,
    }


def _stage_documents(run: Path, documents: list[dict], corpus_root: Path,
                     page_slices: bool = False) -> dict:
    input_dir = run / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    staged = complete = staged_pages = full_fallbacks = 0
    fallback_documents = []
    for document in documents:
        if not document["needs_second_parse"]:
            complete += 1
            continue
        source = corpus_root / document["object_key"]
        if not source.is_file():
            raise FileNotFoundError(f"missing corpus blob: {source}")
        if page_slices:
            import pymupdf
            try:
                with pymupdf.open(source) as pdf:
                    for page_no in document["missing_target_pages"]:
                        destination = input_dir / (
                            f"{document['document_id']}-page{page_no}.pdf")
                        if destination.is_file() and destination.stat().st_size:
                            continue
                        if destination.exists():
                            destination.unlink()
                        single = pymupdf.open()
                        try:
                            single.insert_pdf(pdf, from_page=page_no - 1,
                                              to_page=page_no - 1)
                            single.save(destination)
                        finally:
                            single.close()
                        staged_pages += 1
            except Exception as exc:                         # source PDF defect
                # Some official PDFs have a malformed page tree: PyMuPDF can
                # read the extracted pages but cannot graft one into a new PDF.
                # Keep that document in scope by handing Surya the immutable
                # original. Existing page slices are harmless and the importer
                # deduplicates identical readings.
                destination = input_dir / f"{document['document_id']}.pdf"
                if not destination.exists():
                    destination.symlink_to(source)
                full_fallbacks += 1
                fallback_documents.append({
                    "document_id": document["document_id"],
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                })
        else:
            destination = input_dir / f"{document['document_id']}.pdf"
            if destination.exists() or destination.is_symlink():
                if destination.resolve() != source.resolve():
                    raise ValueError(
                        f"staged path points at another blob: {destination}")
            else:
                destination.symlink_to(source)
        staged += 1
    total_page_slices = sum(1 for path in input_dir.glob("*-page*.pdf")
                            if path.is_file() and path.stat().st_size)
    return {"staged_documents": staged,
            "staged_pages": total_page_slices,
            "new_staged_pages": staged_pages,
            "full_document_fallbacks": full_fallbacks,
            "fallback_documents": fallback_documents,
            "already_complete": complete, "page_slices": page_slices}


def prepare(args) -> int:
    state = snapshot()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest = state.pop("manifest")
    if args.stage:
        manifest["stage"] = _stage_documents(
            out, state["documents"], args.corpus_root, args.page_slices)
    for name, value in state.items():
        _write_json(out / f"{name}.json", value)
    manifest["released_baseline_sha256"] = _json_hash(state["released"])
    manifest["targets_sha256"] = _json_hash(state["targets"])
    _write_json(out / "manifest.json", manifest)
    print(json.dumps(manifest, default=str, indent=2))
    return 0


def _load_run(run: Path) -> dict:
    required = ("manifest", "targets", "documents", "toc", "s7", "released")
    result = {}
    for name in required:
        path = run / f"{name}.json"
        if not path.is_file():
            raise FileNotFoundError(f"run is missing {path}")
        result[name] = json.loads(path.read_text(encoding="utf-8"))
    if result["manifest"]["targets_sha256"] != _json_hash(result["targets"]):
        raise ValueError("targets.json no longer matches the signed manifest")
    if result["manifest"]["released_baseline_sha256"] != _json_hash(
            result["released"]):
        raise ValueError("released-baseline.json no longer matches the manifest")
    return result


def _target_identity(row: dict) -> tuple[str, str, str, str]:
    """Stable expression identity across a normal segmentation UUID rewrite."""
    return (
        str(row["document_id"]),
        str(row["source_observation_id"]),
        str(row["expression_ordinal"]),
        str(row["source_sha256"]),
    )


def _released_target_replacements(expected: dict, live_by_id: dict,
                                  live_release: dict,
                                  live_release_rows: list[dict]):
    release_by_identity = defaultdict(list)
    for row in live_release_rows:
        release_by_identity[_target_identity(row)].append(row["instrument_id"])
    already_released = sorted(set(expected) & set(live_release))
    replacements = []
    accounted_target_ids = set(already_released)
    expected_release_ids = set(already_released)
    for old_id, old in expected.items():
        if old_id in live_by_id or old_id in accounted_target_ids:
            continue
        matches = release_by_identity.get(_target_identity(old), [])
        # Ambiguity is never guessed through: zero or multiple matches remain
        # stale and make verification fail closed.
        if len(matches) == 1:
            new_id = matches[0]
            replacements.append({
                "snapshot_instrument_id": old_id,
                "released_instrument_id": new_id,
                "document_id": old["document_id"],
                "source_observation_id": old["source_observation_id"],
                "expression_ordinal": old["expression_ordinal"],
            })
            accounted_target_ids.add(old_id)
            expected_release_ids.add(new_id)
    return (already_released, replacements, accounted_target_ids,
            expected_release_ids)


def verify_state(state: dict) -> dict:
    """Compare a saved manifest with live rows; never infer freshness by age."""
    expected = {row["instrument_id"]: row for row in state["targets"]}
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        now = _rows(cur, "SELECT now() measured_at,current_database() database")[0]
        live_targets = _rows(cur, TARGET_SQL)
        live_by_id = {row["instrument_id"]: row for row in live_targets}
        still_ids = sorted(set(expected) & set(live_by_id))
        toc, s7 = _blocker_rows(cur, still_ids)
        signatures = _blocker_signatures(
            [live_by_id[value] for value in still_ids], toc, s7)
        live_release = dict(cur.execute(RELEASE_FINGERPRINT_SQL).fetchall())
        live_release_rows = _rows(cur, RELEASE_IDENTITY_SQL)

    (already_released, released_replacements, accounted_target_ids,
     expected_release_ids) = _released_target_replacements(
         expected, live_by_id, live_release, live_release_rows)
    missing_or_replaced = sorted(
        set(expected) - set(live_by_id) - accounted_target_ids)
    changed = []
    fresh = []
    for instrument_id in still_ids:
        old, new = expected[instrument_id], live_by_id[instrument_id]
        reasons = []
        for field in ("document_id", "source_observation_id", "source_sha256"):
            if str(old[field]) != str(new[field]):
                reasons.append(field)
        if old["blocker_signature"] != signatures[instrument_id]:
            reasons.append("blockers")
        if reasons:
            changed.append({"instrument_id": instrument_id, "changed": reasons})
        else:
            fresh.append(instrument_id)

    baseline = state["released"]
    removed_released = sorted(set(baseline) - set(live_release))
    changed_released = sorted(
        instrument_id for instrument_id, fingerprint in baseline.items()
        if live_release.get(instrument_id) not in (None, fingerprint)
    )
    added_released = sorted(set(live_release) - set(baseline))
    unexpected_additions = sorted(set(added_released) - expected_release_ids)
    return {
        **now,
        "fresh_targets": len(fresh),
        "fresh_target_ids": fresh,
        "already_released_skip": already_released,
        "released_replacements": released_replacements,
        "changed_targets": changed,
        "missing_or_replaced_targets": missing_or_replaced,
        "released_baseline": len(baseline),
        "removed_released": removed_released,
        "changed_released": changed_released,
        "added_released": added_released,
        "unexpected_release_additions": unexpected_additions,
        "safe": not (changed or missing_or_replaced or removed_released
                     or changed_released or unexpected_additions),
    }


def verify(args) -> int:
    report = verify_state(_load_run(args.run.resolve()))
    _write_json(args.run / "freshness.json", report)
    print(json.dumps(report, default=str, indent=2))
    return 0 if report["safe"] else 1


def _normalise(text: str | None) -> str:
    return re.sub(r"[^\w]+", " ", text or "", flags=re.UNICODE).strip().casefold()


def _overlap(first: Iterable[float], second: Iterable[float]) -> float:
    ax0, ay0, ax1, ay1 = map(float, first)
    bx0, by0, bx1, by1 = map(float, second)
    area = max(0.0, min(ax1, bx1) - max(ax0, bx0)) * max(
        0.0, min(ay1, by1) - max(ay0, by0))
    base = max(1.0, min((ax1 - ax0) * (ay1 - ay0),
                        (bx1 - bx0) * (by1 - by0)))
    return area / base


def _match_secondary(source: dict, candidates: list[dict]) -> dict | None:
    source_box = [source["x0"], source["y0"], source["x1"], source["y1"]]
    source_text = _normalise(source["text"])
    best = None
    for candidate in candidates:
        box = candidate.get("bbox")
        if not box or len(box) != 4:
            continue
        geometry = _overlap(source_box, box)
        candidate_text = _normalise(candidate.get("text") or candidate.get("html"))
        similarity = SequenceMatcher(None, source_text[:800],
                                     candidate_text[:800]).ratio()
        score = 0.65 * geometry + 0.35 * similarity
        if best is None or score > best["score"]:
            best = {"block": candidate, "score": score,
                    "geometry": geometry, "text_similarity": similarity}
    return best if best and (best["geometry"] >= 0.20
                             or best["text_similarity"] >= 0.60) else None


APPARATUS_LABELS = {
    "footnote", "pagefooter", "page footer", "caption", "formula",
    "table", "picture", "figure",
}
BODY_LABELS = {
    "text", "paragraph", "sectionheader", "section header", "listitem",
    "list item", "title", "form",
}


def _role(label: str | None) -> str:
    value = re.sub(r"[_-]+", " ", (label or "").strip().casefold())
    if value in APPARATUS_LABELS:
        return "apparatus"
    if value in BODY_LABELS:
        return "body"
    return "unknown"


def _block_text(block: dict) -> str:
    return _normalise(block.get("text") or block.get("html"))


def _contents_marker_order(blocks: list[dict]) -> int | None:
    for fallback, block in enumerate(blocks):
        text = _block_text(block)
        if text in {"contents", "table of contents", "index"}:
            return int(block.get("reading_order", fallback))
    return None


def _matched_role(match: dict | None, page_blocks: list[dict]) -> str:
    if not match:
        return "unknown"
    block = match["block"]
    marker = _contents_marker_order(page_blocks)
    order = int(block.get("reading_order", 10**9))
    if marker is not None and order > marker:
        return "contents"
    return _role(block.get("label"))


def _s7_resolution(candidate_role: str, canonical_role: str) -> str:
    noncitable = {"apparatus", "contents"}
    if candidate_role in noncitable and canonical_role == "body":
        return "reject_candidate"
    if candidate_role == "body" and canonical_role in noncitable:
        return "restore_citable"
    return "review"


def _page_candidates(cur, document_ids: list[int]) -> dict[tuple[int, int], list[dict]]:
    rows = _rows(cur, """
        SELECT DISTINCT ON (document_id,page_no)
               document_id,page_no,id,engine,blocks
          FROM page_ocr_candidate
         WHERE document_id=ANY(%s) AND engine LIKE %s
         ORDER BY document_id,page_no,created_at DESC,id DESC
    """, (document_ids, SURYA_ENGINE_PREFIX + "%"))
    return {(row["document_id"], row["page_no"]): row["blocks"] or []
            for row in rows}


def _source_blocks(cur, block_ids: list[int]) -> dict[int, dict]:
    if not block_ids:
        return {}
    rows = _rows(cur, """
        SELECT id,document_id,page_no,text,x0,y0,x1,y1,reading_order
          FROM text_block WHERE id=ANY(%s) ORDER BY id
    """, (block_ids,))
    return {row["id"]: row for row in rows}


def propose(args) -> int:
    state = _load_run(args.run.resolve())
    freshness = verify_state(state)
    _write_json(args.run / "freshness.json", freshness)
    if not freshness["safe"]:
        print(json.dumps(freshness, default=str, indent=2), file=sys.stderr)
        print("manifest is stale; run prepare again", file=sys.stderr)
        return 1
    fresh = set(freshness["fresh_target_ids"])
    toc = [row for row in state["toc"] if row["instrument_id"] in fresh]
    s7 = [row for row in state["s7"] if row["instrument_id"] in fresh]
    document_ids = sorted({row["document_id"] for row in toc + s7})
    block_ids = sorted({int(value) for row in s7 for value in (
        row.get("source_block_id"), row.get("canonical_source_block_id")) if value})
    with connect() as conn, conn.cursor() as cur:
        pages = _page_candidates(cur, document_ids)
        blocks = _source_blocks(cur, block_ids)

    proposals = []
    for row in s7:
        candidate = blocks.get(row.get("source_block_id"))
        canonical = blocks.get(row.get("canonical_source_block_id"))
        if not candidate or not canonical:
            continue
        candidate_match = _match_secondary(
            candidate, pages.get((row["document_id"], candidate["page_no"]), []))
        canonical_match = _match_secondary(
            canonical, pages.get((row["document_id"], canonical["page_no"]), []))
        candidate_page = pages.get(
            (row["document_id"], candidate["page_no"]), [])
        canonical_page = pages.get(
            (row["document_id"], canonical["page_no"]), [])
        candidate_role = _matched_role(candidate_match, candidate_page)
        canonical_role = _matched_role(canonical_match, canonical_page)
        resolution = _s7_resolution(candidate_role, canonical_role)
        confidence = min(
            candidate_match["score"] if candidate_match else 0.0,
            canonical_match["score"] if canonical_match else 0.0,
        )
        proposals.append({
            "kind": "s7",
            "instrument_id": row["instrument_id"],
            "document_id": row["document_id"],
            "candidate_id": row["id"],
            "printed_label": row["printed_label"],
            "source_block_id": row["source_block_id"],
            "canonical_source_block_id": row["canonical_source_block_id"],
            "proposal": resolution,
            "candidate_role": candidate_role,
            "canonical_role": canonical_role,
            "confidence": round(confidence, 4),
            "candidate_match": candidate_match,
            "canonical_match": canonical_match,
            "review_state": "proposed",
            "method": TOOL_VERSION,
        })

    label_re = {}
    for row in toc:
        label = (row.get("printed_label") or "").strip().rstrip(".")
        if not label:
            continue
        pattern = label_re.setdefault(label, re.compile(
            r"^\s*" + re.escape(label) + r"\s*(?:[.)\]:-]|\s)", re.I))
        hits = []
        for (document_id, page_no), candidate_blocks in pages.items():
            if document_id != row["document_id"] or page_no == row.get("source_page"):
                continue
            contents_marker = _contents_marker_order(candidate_blocks)
            for block in candidate_blocks:
                text = re.sub(r"\s+", " ", block.get("text") or "").strip()
                order = int(block.get("reading_order", 10**9))
                role = ("contents" if contents_marker is not None
                        and order > contents_marker else _role(block.get("label")))
                if role == "body" and pattern.match(text):
                    hits.append({"page": page_no, "bbox": block.get("bbox"),
                                 "label": block.get("label"),
                                 "text": text[:500]})
        proposals.append({
            "kind": "toc",
            "instrument_id": row["instrument_id"],
            "document_id": row["document_id"],
            "toc_entry_id": row["toc_entry_id"],
            "printed_label": row["printed_label"],
            "printed_heading": row.get("printed_heading"),
            "proposal": ("unique_body_candidate" if len(hits) == 1
                         else "review"),
            "body_candidates": hits[:20],
            "confidence": 1.0 if len(hits) == 1 else 0.0,
            "review_state": "proposed",
            "method": TOOL_VERSION,
        })
    report = {
        "tool": TOOL_VERSION,
        "manifest_measured_at": state["manifest"]["measured_at"],
        "proposed_at_target_count": len(fresh),
        "proposals": len(proposals),
        "counts": dict(Counter(
            f"{row['kind']}:{row['proposal']}" for row in proposals)),
    }
    _write_json(args.run / "proposals.json", proposals)
    _write_json(args.run / "proposal-summary.json", report)
    print(json.dumps(report, indent=2))
    return 0


def import_results(args) -> int:
    state = _load_run(args.run.resolve())
    freshness = verify_state(state)
    if not freshness["safe"]:
        print("manifest is stale; refusing to import", file=sys.stderr)
        return 1
    output = args.run / "output"
    files = sorted(output.glob("*/results.json"))
    if not files:
        print(f"no Surya results under {output}", file=sys.stderr)
        return 1
    imported = failed = 0
    for path in files:
        command = [sys.executable, "-m", "nizam.workers.import_surya_candidates",
                   str(path)]
        completed = subprocess.run(command, check=False)
        if completed.returncode:
            failed += 1
        else:
            imported += 1
    print(json.dumps({"result_files": len(files), "imported": imported,
                      "failed": failed}, indent=2))
    return int(bool(failed))


def batch(args) -> int:
    """Make a small, deterministic input queue without changing the manifest."""
    state = _load_run(args.run.resolve())
    freshness = verify_state(state)
    if not freshness["safe"]:
        print("manifest is stale; refusing to build a batch", file=sys.stderr)
        return 1
    fresh_ids = set(freshness["fresh_target_ids"])
    targets_by_doc = defaultdict(list)
    for target in state["targets"]:
        if target["instrument_id"] in fresh_ids:
            targets_by_doc[target["document_id"]].append(target)
    documents = {row["document_id"]: row for row in state["documents"]}
    excluded_documents = set(args.exclude_document)
    ranked = []
    for document_id, targets in targets_by_doc.items():
        if document_id in excluded_documents:
            continue
        blocker_counts = [
            int(row["toc_count"]) + int(row["s7_count"])
            + int(row["boundary_count"])
            for row in targets
        ]
        if args.single_blocker and 1 not in blocker_counts:
            continue
        document = documents[document_id]
        ranked.append((min(blocker_counts), len(targets),
                       len(document["missing_target_pages"]), document_id))
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    selected_files = []
    selected_documents = []
    source_dir = args.run.resolve() / "input"
    result_dir = args.run.resolve() / "output"
    for _blockers, _expressions, _pages, document_id in sorted(ranked):
        candidates = sorted(source_dir.glob(f"{document_id}-page*.pdf"))
        candidates += sorted(source_dir.glob(f"{document_id}.pdf"))
        candidates = [
            source for source in candidates
            if not (result_dir / source.stem / "results.json").is_file()
        ]
        if not candidates:
            continue
        if selected_files and len(selected_files) + len(candidates) > args.max_files:
            continue
        for source in candidates:
            destination = output / source.name
            if not destination.exists():
                destination.symlink_to(source)
            selected_files.append(source.name)
        selected_documents.append(document_id)
        if len(selected_files) >= args.max_files:
            break
    report = {
        "source_manifest": str(args.run.resolve() / "manifest.json"),
        "single_blocker": args.single_blocker,
        "max_files": args.max_files,
        "excluded_documents": sorted(excluded_documents),
        "selected_documents": selected_documents,
        "selected_files": selected_files,
    }
    _write_json(output / "batch.json", report)
    print(json.dumps({"documents": len(selected_documents),
                      "files": len(selected_files),
                      "out": str(output)}, indent=2))
    return 0


def inspect_target(args) -> int:
    """Explain whether today's parser can enact reviewed readings; no writes."""
    from nizam.storage import legal_write
    from nizam.workers.segment import build, reviewed_structural_overrides

    targets = [row for row in legal_write.documents_needing_segmentation(
        redo=True, include_review=True) if row[0] == args.document]
    if len(targets) != 1:
        raise ValueError(
            f"document {args.document} has {len(targets)} observations; "
            "inspect one single-expression document at a time")
    (document_id, sha, observation_id, source_id, title, year, _kind,
     source_url) = targets[0]
    blocks = legal_write.blocks_for(document_id)
    reviewed = legal_write.structural_resolutions_for(document_id)
    patches = legal_write.segmentation_patches_for(observation_id)
    structural_overrides = reviewed_structural_overrides(reviewed, patches)
    if args.source_body_start_block:
        structural_overrides["source_body_start_block"] = (
            args.source_body_start_block)
    if args.source_apparatus_blocks:
        structural_overrides["source_apparatus_blocks"] = sorted({
            int(value) for value in re.split(
                r"[\s,]+", args.source_apparatus_blocks)
            if value.strip()
        })
    inst, seg = build(
        document_id, sha, observation_id, source_id, title, year, source_url,
        blocks, legal_write.observed_on(observation_id),
        patches,
        toc_dispositions=legal_write.toc_dispositions_for(observation_id),
        structural_resolutions=reviewed,
        force_opening_contents=args.force_opening_contents,
        structural_overrides=structural_overrides or None,
    )
    result = {
        "document_id": document_id,
        "source_observation_id": observation_id,
        "provisions": len(inst.provisions),
        "sections": sum(row["kind"] in ("section", "article")
                        for row in inst.provisions),
        "s7_candidates": seg.repeated_labels_demoted,
        "reviews_enacted": seg.structural_reviews_enacted,
        "reviews_refused": seg.structural_reviews_refused,
        "structural_decisions": inst.structural_decisions,
        "unlinked_toc": sum(entry.get("provision_key") is None
                            for entry in inst.toc_entries),
        "structural_overrides": structural_overrides,
        "provision_preview": [
            {key: row.get(key) for key in (
                "path", "kind", "label", "heading", "first_page",
                "first_block", "text")}
            for row in inst.provisions
        ],
        "block_roles": [
            {"block_id": row[0], "role": row[1], "node_key": row[2],
             "chars": row[3]}
            for row in inst.block_roles
        ],
    }
    print(json.dumps(result, default=str, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fresh, unreleased-only Surya shadow-parser lane")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--stage", action="store_true",
                   help="symlink incompletely covered PDFs into RUN/input")
    p.add_argument("--page-slices", action="store_true",
                   help="stage only blocker pages and their immediate context")
    p.add_argument("--corpus-root", type=Path,
                   default=Path(os.environ.get("CORPUS_ROOT", DEFAULT_CORPUS_ROOT)))
    p.set_defaults(func=prepare)
    for name, func in (("verify", verify), ("propose", propose),
                       ("import-results", import_results)):
        command = sub.add_parser(name)
        command.add_argument("--run", type=Path, required=True)
        command.set_defaults(func=func)
    command = sub.add_parser("batch")
    command.add_argument("--run", type=Path, required=True)
    command.add_argument("--out", type=Path, required=True)
    command.add_argument("--max-files", type=int, default=40)
    command.add_argument("--single-blocker", action="store_true")
    command.add_argument("--exclude-document", type=int, action="append",
                         default=[], help="explicitly quarantined source PDF")
    command.set_defaults(func=batch)
    command = sub.add_parser("inspect")
    command.add_argument("--document", type=int, required=True)
    command.add_argument("--force-opening-contents", action="store_true")
    command.add_argument("--source-body-start-block", type=int)
    command.add_argument("--source-apparatus-blocks",
                         help="comma-separated source-reviewed apparatus blocks")
    command.set_defaults(func=inspect_target)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
