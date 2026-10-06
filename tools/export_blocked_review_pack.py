"""Export one source-anchored question per live release blocker, without DB writes.

The signed run is an authorization *boundary*: released trees are excluded,
target signatures must still be fresh, and an exporter can never decide a
legal question. Page images are shared by cases on the same PDF page; exact
source-block crops are separate. An incomplete image set is reported plainly.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import subprocess

import pymupdf

from nizam.storage.db import connect
from tools.review_toc_gaps import SQL as TOC_BRACKET_SQL
from tools.second_parser_release import (
    DEFAULT_CORPUS_ROOT, _load_run, verify_state,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               default=str) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _toc_body_pages(row: dict, page_count: int,
                    max_pages: int) -> tuple[list[int], dict]:
    """Bracket a missing promise; never call a short search proof of absence."""
    before = row.get("page_before")
    after = row.get("page_after")
    lo = before or row.get("body_starts_page") or min(
        page_count, (row.get("contents_page") or 1) + 1)
    hi = after or min(page_count, lo + 1)
    inverted = hi < lo
    if inverted:
        hi = min(page_count, lo + max_pages - 1)
    pages = list(range(max(1, lo), min(page_count, hi, lo + max_pages - 1) + 1))
    return pages, {
        "linked_section_before_page": before,
        "linked_section_after_page": after,
        "body_starts_page": row.get("body_starts_page"),
        "inverted": inverted,
        "coverage_limited": inverted or (hi - lo + 1 > max_pages)
            or before is None or after is None,
    }


def _block(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {key: row[key] for key in (
        "id", "document_id", "page_no", "reading_order", "text",
        "x0", "y0", "x1", "y1")}


def _fetch_context(state: dict) -> tuple[dict, dict, dict]:
    toc_keys = {(r["instrument_id"], r["ordinal"], r["printed_label"])
                for r in state["toc"]}
    s7_ids = [r["id"] for r in state["s7"]]
    block_ids = sorted({int(value) for row in state["toc"] + state["s7"]
                        for value in (row.get("source_block_id"),
                                      row.get("canonical_source_block_id"))
                        if value is not None})
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        # The latest run can report a missing label without a TOC-entry row.
        # Include instrument+ordinal in the bracket query so those NULL entry
        # ids never collide or disappear from the review pack.
        query = TOC_BRACKET_SQL.replace(
            "SELECT gap.toc_entry_id, gap.document_id,",
            "SELECT gap.toc_entry_id, gap.instrument_id::text, gap.ordinal, "
            "gap.document_id,", 1)
        if query == TOC_BRACKET_SQL:
            raise ValueError("TOC bracket query shape changed")
        cur.execute(query, {"document": None})
        names = [c.name for c in cur.description]
        brackets = {(row["instrument_id"], row["ordinal"],
                     row["printed_label"]): row for row in
                    (dict(zip(names, values)) for values in cur.fetchall())
                    if (row["instrument_id"], row["ordinal"],
                        row["printed_label"]) in toc_keys}
        cur.execute("""
            SELECT c.id::text AS id,a.resolution,a.review_basis,a.rationale,
                   a.evidence AS reviewed_evidence,
                   candidate.kind::text AS candidate_kind,
                   candidate.label AS candidate_label,
                   candidate.heading AS candidate_heading,
                   candidate.path::text AS candidate_path,
                   canonical.kind::text AS canonical_kind,
                   canonical.label AS canonical_label,
                   canonical.heading AS canonical_heading,
                   canonical.path::text AS canonical_path,
                   c.evidence AS parser_evidence
              FROM segmentation_structural_candidate c
              JOIN provision candidate ON candidate.id=c.candidate_provision_id
              JOIN provision canonical ON canonical.id=c.canonical_provision_id
              LEFT JOIN v_structural_adjudication_latest a ON a.candidate_id=c.id
             WHERE c.id=ANY(%s::uuid[])
        """, (s7_ids,))
        names = [c.name for c in cur.description]
        s7_details = {row["id"]: row for row in
                      (dict(zip(names, values)) for values in cur.fetchall())}
        cur.execute("""
            SELECT id,document_id,page_no,reading_order,text,x0,y0,x1,y1
              FROM text_block WHERE id=ANY(%s::bigint[])
        """, (block_ids,))
        names = [c.name for c in cur.description]
        blocks = {row["id"]: row for row in
                  (dict(zip(names, values)) for values in cur.fetchall())}
    if len(brackets) != len(toc_keys) or len(s7_details) != len(s7_ids):
        raise ValueError("live issue rows changed during context read")
    return brackets, s7_details, blocks


def _question_toc(row: dict, bracket: dict, block: dict | None,
                  target: dict, max_pages: int) -> dict:
    body_pages, search = _toc_body_pages(bracket, target["page_count"],
                                          max_pages)
    pages = sorted({p for p in [row["source_page"], *body_pages] if p})
    case_id = (f"toc-{row['document_id']}-{row['toc_entry_id']}"
               if row["toc_entry_id"] is not None else
               f"toc-{row['document_id']}-run-{row['ordinal']}-"
               f"{row['instrument_id'][:8]}")
    has_source_entry = row["toc_entry_id"] is not None
    already_reviewed = row["resolution"] == "parser_defect"
    return {
        "case_id": case_id, "defect_type": "unresolved_contents_promise",
        "workflow_lane": ("repair_from_existing_source_review"
                          if already_reviewed else "needs_new_source_review"),
        "needs_new_source_classification": not already_reviewed,
        "blocked_instrument_id": row["instrument_id"],
        "document_id": row["document_id"],
        "source_observation_id": target["source_observation_id"],
        "expression_ordinal": target["expression_ordinal"],
        "source_sha256": target["source_sha256"],
        "title": target["short_title"],
        "blocker_signature": target["blocker_signature"],
        "other_blockers_on_instrument": {
            "toc": target["toc_count"], "s7": target["s7_count"],
            "boundary": target["boundary_count"]},
        "what_is_missing": (
            "The printed contents promises this numbered entry, but the "
            "active provision tree does not link it to an operative provision."
            if has_source_entry else
            "The latest segmentation run reports a missing label without "
            "an anchored contents-entry row. First verify the promise exists."),
        "how_found": {
            "database_view": "v_toc_gap_pending",
            "evidence_kind": ("anchored_toc_entry" if has_source_entry
                              else "run_only_missing_label"),
            "toc_entry_id": row["toc_entry_id"],
            "contents_ordinal": row["ordinal"],
            "printed_label": row["printed_label"],
            "printed_heading": row["printed_heading"],
            "entry_kind": row["entry_kind"],
            "contents_page": row["source_page"],
            "contents_source_block": _block(block),
            "existing_resolution": row["resolution"],
            "existing_adjudication_id": row["adjudication_id"],
            "body_search": search,
            "body_pages_supplied": body_pages,
        },
        "image_pages": sorted(set(pages) | ({1} if not has_source_entry
                                            else set())),
        "crop_blocks": [block["id"]] if block else [],
        "question": (
            f"In the official PDF, what happens to contents entry "
            f"{row['printed_label']!r} ({row['printed_heading'] or 'no heading'})? "
            "Is its operative text printed, omitted/repealed, part of another "
            "instrument, or not decidable from these pages? Identify the exact "
            "body page and quote its opening if present. A contents row alone "
            "is not operative law; request more pages before claiming absence."
            if has_source_entry else
            f"The latest run reports missing label {row['printed_label']!r} "
            "without an anchored contents entry. Does the official PDF even "
            "print this promise? If so, locate the contents and operative "
            "pages. If not, report a run-only parser signal, not absent law."),
        "prior_review_note": (
            "A source review already classified this as a parser defect. "
            "Do not repeat that classification; only supply a precise body "
            "location/correction or evidence disputing it."
            if already_reviewed else None),
        "allowed_verdicts": [
            "operative_text_present_parser_missed", "absent_in_official_source",
            "belongs_to_other_instrument", "contents_entry_not_a_provision",
            "source_pdf_incomplete", "run_signal_not_printed",
            "needs_more_pages_or_review"],
        "response_template": {
            "case_id": case_id, "verdict": None, "observed_on_page": None,
            "exact_printed_text": None, "body_page": None,
            "body_source_block_id_if_known": None, "evidence_image_paths": [],
            "reviewer_kind": None, "reviewer_id": None,
            "confidence": None, "requested_additional_pages": [],
        },
    }


def _question_s7(row: dict, detail: dict, blocks: dict,
                 target: dict) -> dict:
    candidate = blocks.get(row["source_block_id"])
    canonical = blocks.get(row["canonical_source_block_id"])
    pages = sorted({p for p in (row["source_page"],
                                row["canonical_source_page"]) if p})
    case_id = f"s7-{row['document_id']}-{row['id']}"
    already_reviewed = detail.get("review_basis") in (
        "source_verified", "human_verified")
    return {
        "case_id": case_id, "defect_type": "repeated_citation_label",
        "workflow_lane": ("repair_from_existing_source_review"
                          if already_reviewed else "needs_new_source_review"),
        "needs_new_source_classification": not already_reviewed,
        "blocked_instrument_id": row["instrument_id"],
        "document_id": row["document_id"],
        "source_observation_id": target["source_observation_id"],
        "expression_ordinal": target["expression_ordinal"],
        "source_sha256": target["source_sha256"],
        "title": target["short_title"],
        "blocker_signature": target["blocker_signature"],
        "other_blockers_on_instrument": {
            "toc": target["toc_count"], "s7": target["s7_count"],
            "boundary": target["boundary_count"]},
        "what_is_missing": (
            "The parser found two sibling candidates for one citation label "
            "and demoted one pending a source-backed classification."),
        "how_found": {
            "database_view": "v_structural_adjudication_pending",
            "candidate_id": row["id"],
            "printed_label": row["printed_label"],
            "parser_proposal": row["proposed_resolution"],
            "candidate_page": row["source_page"],
            "candidate_source_block": _block(candidate),
            "canonical_page": row["canonical_source_page"],
            "canonical_source_block": _block(canonical),
            "candidate_tree_node": {k: detail.get(k) for k in (
                "candidate_kind", "candidate_label", "candidate_heading",
                "candidate_path")},
            "canonical_tree_node": {k: detail.get(k) for k in (
                "canonical_kind", "canonical_label", "canonical_heading",
                "canonical_path")},
            "parser_evidence": detail.get("parser_evidence"),
            "existing_review": {k: detail.get(k) for k in (
                "resolution", "review_basis", "rationale",
                "reviewed_evidence")},
        },
        "image_pages": pages,
        "crop_blocks": [b["id"] for b in (candidate, canonical) if b],
        "question": (
            f"The tree has two candidates labelled {row['printed_label']!r}. "
            "On the official pages, what is each occurrence: separate "
            "operative law, a footnote/marginal note/table/contents entry, "
            "a child of another section, or the start of another instrument? "
            "Quote the candidate's opening and say where its text belongs. "
            "Do not approve demotion merely because the labels match."),
        "prior_review_note": (
            "A source review already records this candidate's role. Do not "
            "repeat it; only provide an implementable parser correction or "
            "evidence disputing the recorded review."
            if already_reviewed else None),
        "allowed_verdicts": [
            "candidate_noncitable", "candidate_is_operative_law",
            "candidate_belongs_under_other_parent", "different_instrument",
            "parser_candidate_false_alarm", "needs_more_pages_or_review"],
        "response_template": {
            "case_id": case_id, "verdict": None, "observed_on_page": None,
            "exact_printed_text": None, "candidate_role": None,
            "canonical_role": None, "correct_parent_label_if_any": None,
            "evidence_image_paths": [], "reviewer_kind": None,
            "reviewer_id": None, "confidence": None,
            "requested_additional_pages": [],
        },
    }


def _render_page(pdf, source: Path, page_no: int, dest: Path,
                 dpi: int) -> dict:
    if dest.is_file() and dest.stat().st_size:
        return {"path": dest, "sha256": _sha(dest), "dpi": dpi}
    dest.parent.mkdir(parents=True, exist_ok=True)
    error = None
    if pdf is not None:
        try:
            page = pdf[page_no - 1]
            # Oversized official pages can otherwise exhaust WSL alongside OCR.
            effective_dpi = min(dpi, int((40_000_000 /
                max(1, page.rect.width * page.rect.height)) ** 0.5 * 72))
            page.get_pixmap(dpi=max(72, effective_dpi), alpha=False).save(dest)
            return {"path": dest, "sha256": _sha(dest),
                    "dpi": max(72, effective_dpi)}
        except Exception as exc:
            error = f"PyMuPDF: {type(exc).__name__}: {exc}"[:300]
    try:
        done = subprocess.run([
            "pdftoppm", "-f", str(page_no), "-l", str(page_no),
            "-r", str(dpi), "-png", "-singlefile", str(source),
            str(dest.with_suffix(""))], capture_output=True, timeout=120)
        if done.returncode == 0 and dest.is_file() and dest.stat().st_size:
            return {"path": dest, "sha256": _sha(dest), "dpi": dpi,
                    "renderer": "poppler_fallback"}
        error = (error or "") + " Poppler: " + done.stderr.decode(
            "utf-8", "replace")[:200]
    except (OSError, subprocess.TimeoutExpired) as exc:
        error = (error or "") + f" Poppler: {type(exc).__name__}: {exc}"
    return {"error": (error or "render failed")[:500]}


def _render_crop(pdf, block: dict, dest: Path) -> dict:
    if dest.is_file() and dest.stat().st_size:
        return {"path": dest, "sha256": _sha(dest), "dpi": 180}
    if pdf is None:
        return {"error": "PDF unavailable for crop"}
    try:
        page = pdf[block["page_no"] - 1]
        box = pymupdf.Rect(*[float(block[key]) for key in (
            "x0", "y0", "x1", "y1")])
        box = (box + (-35, -28, 35, 48)) & page.rect
        if box.is_empty or box.is_infinite:
            raise ValueError("source block has invalid PDF coordinates")
        dest.parent.mkdir(parents=True, exist_ok=True)
        page.get_pixmap(dpi=180, alpha=False, clip=box).save(dest)
        return {"path": dest, "sha256": _sha(dest), "dpi": 180}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"[:300]}


def _image_record(out: Path, item: dict, role: str, page: int,
                  block_id: int | None = None) -> dict:
    record = {"role": role, "page": page}
    if block_id is not None:
        record["source_block_id"] = block_id
    if "path" in item:
        record.update(path=item["path"].relative_to(out).as_posix(),
                      sha256=item["sha256"], dpi=item["dpi"])
    else:
        record["render_error"] = item["error"]
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    ap.add_argument("--dpi", type=int, default=130)
    ap.add_argument("--max-body-pages", type=int, default=2)
    ap.add_argument("--plan", action="store_true", help="count only; no files")
    args = ap.parse_args()
    if args.dpi < 90 or args.max_body_pages < 1:
        ap.error("dpi must be >=90 and max-body-pages >=1")
    run = args.run.resolve()
    out = args.out.resolve()
    state = _load_run(run)
    freshness = verify_state(state)
    if not freshness["safe"]:
        raise SystemExit("signed target/release baseline is stale; refusing pack")
    fresh = set(freshness["fresh_target_ids"])
    targets = {r["instrument_id"]: r for r in state["targets"]
               if r["instrument_id"] in fresh}
    toc = [r for r in state["toc"] if r["instrument_id"] in fresh]
    s7 = [r for r in state["s7"] if r["instrument_id"] in fresh]
    if (len(targets), len(toc), len(s7)) != (
            state["manifest"]["blocked"], state["manifest"]["toc"],
            state["manifest"]["s7"]):
        raise SystemExit("fresh issue counts differ from signed snapshot")
    brackets, s7_details, blocks = _fetch_context(state)
    cases = []
    for row in toc:
        target = targets[row["instrument_id"]]
        key = (row["instrument_id"], row["ordinal"], row["printed_label"])
        cases.append(_question_toc(row, brackets[key],
                                   blocks.get(row["source_block_id"]),
                                   target, args.max_body_pages))
    for row in s7:
        cases.append(_question_s7(row, s7_details[row["id"]], blocks,
                                  targets[row["instrument_id"]]))
    cases.sort(key=lambda case: (case["document_id"], case["defect_type"],
                                 case["case_id"]))
    documents = {r["document_id"]: r for r in state["documents"]}
    needed = defaultdict(set)
    crops = defaultdict(set)
    for case in cases:
        needed[case["document_id"]].update(case["image_pages"])
        crops[case["document_id"]].update(case["crop_blocks"])
    plan = {
        "blocked_instruments": len(targets),
        "blocked_documents": len(documents),
        "questions": len(cases), "toc_questions": len(toc),
        "s7_questions": len(s7),
        "unique_full_pages": sum(map(len, needed.values())),
        "unique_block_crops": sum(map(len, crops.values())),
        "already_source_reviewed_needing_repair": sum(
            not case["needs_new_source_classification"] for case in cases),
        "needs_new_source_review": sum(
            case["needs_new_source_classification"] for case in cases),
    }
    print(json.dumps(plan, indent=2), flush=True)
    if args.plan:
        return 0

    out.mkdir(parents=True, exist_ok=True)
    page_images = {}
    block_crops = {}
    source_errors = {}
    for n, document_id in enumerate(sorted(documents), 1):
        doc = documents[document_id]
        source = args.corpus_root / doc["object_key"]
        if not source.is_file():
            source_errors[document_id] = "source PDF blob is absent"
            pdf = None
        elif _sha(source) != doc["source_sha256"]:
            source_errors[document_id] = "source PDF SHA-256 differs from signed snapshot"
            pdf = None
        else:
            try:
                pdf = pymupdf.open(source)
                if pdf.page_count != doc["page_count"]:
                    source_errors[document_id] = (
                        f"PDF has {pdf.page_count} pages, snapshot says "
                        f"{doc['page_count']}")
            except Exception as exc:
                pdf = None
                source_errors[document_id] = (
                    f"PyMuPDF open: {type(exc).__name__}: {exc}"[:300])
        for page_no in sorted(needed[document_id]):
            dest = out / "images" / f"doc-{document_id}" / f"page-{page_no}.png"
            if source.is_file() and document_id not in source_errors:
                page_images[document_id, page_no] = _render_page(
                    pdf, source, page_no, dest, args.dpi)
            else:
                page_images[document_id, page_no] = {
                    "error": source_errors.get(document_id, "source unavailable")}
        for block_id in sorted(crops[document_id]):
            block = blocks.get(block_id)
            if block is not None and document_id not in source_errors:
                dest = (out / "crops" / f"doc-{document_id}" /
                        f"block-{block_id}.png")
                block_crops[block_id] = _render_crop(pdf, block, dest)
            else:
                block_crops[block_id] = {
                    "error": source_errors.get(document_id, "source block absent")}
        if pdf is not None:
            pdf.close()
        if n % 20 == 0 or n == len(documents):
            print(f"rendered documents {n}/{len(documents)}", flush=True)

    render_failures = []
    for case in cases:
        document_id = case["document_id"]
        target = documents[document_id]
        case["source_pdf"] = {
            "object_key": target["object_key"],
            "local_path": str(args.corpus_root / target["object_key"]),
            "page_count": target["page_count"],
            "source_error": source_errors.get(document_id),
        }
        images = []
        for page in case.pop("image_pages"):
            item = page_images[document_id, page]
            images.append(_image_record(out, item, "full_page", page))
        for block_id in case.pop("crop_blocks"):
            block = blocks.get(block_id)
            if block:
                crop = block_crops[block_id]
                if "path" in crop:
                    images.append(_image_record(out, crop, "exact_block_crop",
                                                block["page_no"], block_id))
                elif "path" in page_images.get(
                        (document_id, block["page_no"]), {}):
                    # Some PDFs expose a usable page but corrupt/out-of-page
                    # text-block coordinates. Cite the full official page,
                    # never invent a crop or leave the case image-less.
                    images.append(_image_record(
                        out, page_images[document_id, block["page_no"]],
                        "source_block_page_fallback", block["page_no"],
                        block_id))
                    images[-1]["crop_error"] = crop["error"]
                else:
                    images.append(_image_record(out, crop,
                                                "exact_block_crop",
                                                block["page_no"], block_id))
        case["images"] = images
        case["image_status"] = (
            "ready" if images and all("sha256" in image for image in images)
            else "render_incomplete")
        if case["image_status"] != "ready":
            render_failures.append(case["case_id"])
        _write_json(out / "questions" / f"doc-{document_id}" /
                    (case["case_id"] + ".json"), case)

    # A second freshness check ensures no legal-tree writer overtook the pack.
    ending = verify_state(state)
    manifest = {
        "schema_version": "blocked-source-review-pack/1",
        "status": ("ready" if ending["safe"] and not render_failures
                   else "needs_attention"),
        "signed_run": str(run),
        "snapshot_manifest_sha256": _sha(run / "manifest.json"),
        "released_baseline": state["manifest"]["released"],
        "fresh_at_start": freshness["safe"],
        "fresh_at_end": ending["safe"],
        "counts": plan,
        "source_errors": source_errors,
        "render_incomplete_cases": render_failures,
        "instructions": (
            "Answer each questions/doc-*/<case_id>.json in a separate response "
            "JSON using its response_template. Never mark absent from a short "
            "page search; request more pages. Responses are proposals, not DB "
            "writes or release authorization."),
    }
    _write_json(out / "manifest.json", manifest)
    print(json.dumps({"status": manifest["status"], **plan,
                      "render_incomplete": len(render_failures),
                      "source_errors": len(source_errors),
                      "out": str(out)}, indent=2), flush=True)
    return 0 if manifest["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
