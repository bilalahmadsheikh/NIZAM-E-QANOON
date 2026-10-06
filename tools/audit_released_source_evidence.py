"""Export conservative, instrument-level evidence for the current release set.

The database transaction is read-only and repeatable-read. PDF hashing and
artifact joins are also read-only. No parser tree or release state is written.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import glob
import hashlib
import json
from pathlib import Path

from nizam.storage.db import connect


def read_jsonl(patterns: list[str]):
    for pattern in patterns:
        for filename in sorted(glob.glob(pattern)):
            with open(filename, encoding="utf-8") as stream:
                for line in stream:
                    if line.strip():
                        yield json.loads(line)


def source_integrity(root: Path, key: str | None, expected: str | None,
                     cache: dict) -> dict:
    if not key or not expected:
        return {"exists": False, "sha256_matches": False,
                "reason": "missing_source_key_or_hash"}
    if expected in cache:
        return cache[expected]
    target = (root / key).resolve()
    if not target.is_relative_to(root.resolve()):
        result = {"exists": False, "sha256_matches": False,
                  "reason": "object_key_outside_source_root"}
    elif not target.is_file():
        result = {"exists": False, "sha256_matches": False,
                  "reason": "source_file_not_found"}
    else:
        digest = hashlib.sha256()
        with target.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        result = {"exists": True, "sha256_matches": digest.hexdigest() == expected,
                  "actual_sha256": digest.hexdigest(), "byte_length": target.stat().st_size}
    cache[expected] = result
    return result


def add_review(bucket: dict, key, name: str, value: dict) -> None:
    bucket[key][name].append(value)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--screening", type=Path, required=True)
    ap.add_argument("--baseline", nargs="+", required=True)
    ap.add_argument("--patched", nargs="+", required=True)
    ap.add_argument("--control-comparison", type=Path, required=True)
    ap.add_argument("--source-reviewed", type=Path, required=True)
    ap.add_argument("--source-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--verify-pdf-hashes", action="store_true")
    ap.add_argument("--source-integrity-cache-from", type=Path,
                    help="Reuse PDF hashes from a completed prior read-only manifest")
    args = ap.parse_args()

    comparison = {row["instrument"]: row for row in
                  read_jsonl([str(args.control_comparison)])}
    baseline = {e["instrument"]: e for row in read_jsonl(args.baseline)
                for e in row.get("expressions", [])}
    patched = {e["instrument"]: e for row in read_jsonl(args.patched)
               for e in row.get("expressions", [])}
    build_errors = {(row["document"], row["observation"]): row["error"]
                    for row in read_jsonl(args.patched) if row.get("error")}
    source_reviews = {item["document_id"]: item for item in
                      json.loads(args.source_reviewed.read_text(encoding="utf-8"))["cases"]}

    screening = json.loads(args.screening.read_text(encoding="utf-8"))
    flag_counts: dict[str, Counter] = defaultdict(Counter)
    flag_keys: dict[str, set] = defaultdict(set)
    for flag in screening["findings"]:
        instrument = flag.get("instrument_id")
        if not instrument:
            continue
        category = flag["category"]
        flag_counts[instrument][category] += 1
        block = (flag.get("first_block") or flag.get("source_block_id")
                 or flag.get("block_id") or flag.get("id"))
        flag_keys[instrument].add((category, str(block)))

    reviews: dict[str, dict] = defaultdict(lambda: defaultdict(list))
    observation_reviews: dict[int, dict] = defaultdict(lambda: defaultdict(list))
    document_reviews: dict[int, dict] = defaultdict(lambda: defaultdict(list))
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute("SELECT now()")
        snapshot_at = cur.fetchone()[0].isoformat()
        cur.execute("""SELECT
                count(*) FILTER (WHERE is_active AND duplicate_of IS NULL),
                count(*) FILTER (WHERE is_active AND duplicate_of IS NOT NULL),
                count(*) FILTER (WHERE NOT is_active)
                FROM instrument""")
        active_canonical, active_copies, inactive_historical = cur.fetchone()
        cur.execute("""SELECT i.document_id,i.id::text,
                CASE WHEN r.id IS NULL THEN 'not_released' ELSE 'released' END
                FROM instrument i LEFT JOIN v_release_instrument r ON r.id=i.id
                WHERE i.is_active AND i.duplicate_of IS NULL
                  AND i.document_id IN (118,956)
                ORDER BY i.document_id,i.expression_ordinal""")
        known_defect_document_release_states = [
            {"document_id": doc, "instrument_id": iid, "release_status": state}
            for doc, iid, state in cur.fetchall()]
        cur.execute("""SELECT i.id::text,i.document_id,i.short_title,i.long_title,
                i.jurisdiction::text,i.kind::text,i.number,i.year,i.created_at,
                i.supersedes_instrument_id::text,i.source_observation_id,
                i.expression_ordinal,i.source_start_block_id,i.source_end_block_id,
                i.verification_state::text,d.sha256,o.sha256,
                coalesce(b.object_key,o.object_key),d.page_count
              FROM v_release_instrument r
              JOIN instrument i ON i.id=r.id
              JOIN document d ON d.id=i.document_id AND d.is_active
              JOIN source_observation o ON o.id=i.source_observation_id
              LEFT JOIN blob b ON b.sha256=d.sha256
             WHERE i.is_active AND i.duplicate_of IS NULL
             ORDER BY i.document_id,i.expression_ordinal,i.id""")
        base = cur.fetchall()
        ids = [row[0] for row in base]
        obs_ids = sorted({row[10] for row in base})
        doc_ids = sorted({row[1] for row in base})
        cur.execute("""SELECT instrument_id::text,count(*) FROM provision
                       WHERE instrument_id=ANY(%s::uuid[]) GROUP BY instrument_id""", (ids,))
        node_counts = dict(cur.fetchall())
        cur.execute("""SELECT instrument_id::text,id::text,segmenter,created_at
                       FROM block_assignment_set
                       WHERE is_active AND instrument_id=ANY(%s::uuid[])""", (ids,))
        assignments = defaultdict(list)
        for iid, aid, segmenter, created in cur.fetchall():
            assignments[iid].append({"id": aid, "segmenter": segmenter,
                                     "created_at": created.isoformat()})
        cur.execute("""SELECT s.instrument_id::text,
                              count(*),
                              count(*) FILTER (WHERE pb.role='unassigned'),
                              count(*) FILTER (WHERE pb.role='unstructured')
                       FROM block_assignment_set s
                       JOIN provision_block pb ON pb.assignment_set_id=s.id
                       WHERE s.is_active AND s.instrument_id=ANY(%s::uuid[])
                       GROUP BY s.instrument_id""", (ids,))
        assignment_coverage = {iid: {
            "assigned_block_rows": total, "unassigned_block_rows": unassigned,
            "unstructured_block_rows": unstructured}
            for iid, total, unassigned, unstructured in cur.fetchall()}
        cur.execute("""SELECT c.instrument_id::text,c.id::text,a.id::text,
                              a.resolution::text
                       FROM segmentation_structural_candidate c
                       LEFT JOIN segmentation_structural_adjudication a
                         ON a.candidate_id=c.id
                       WHERE c.instrument_id=ANY(%s::uuid[])""", (ids,))
        for iid, candidate, adjudication, resolution in cur.fetchall():
            add_review(reviews, iid, "structural", {
                "candidate_id": candidate, "adjudication_id": adjudication,
                "resolution": resolution})
        cur.execute("""SELECT instrument_id::text,id::text,resolution::text,
                              evidence->>'render_artifact'
                       FROM toc_gap_adjudication
                       WHERE instrument_id=ANY(%s::uuid[])""", (ids,))
        for iid, aid, resolution, render in cur.fetchall():
            add_review(reviews, iid, "toc_gap", {"id": aid,
                       "resolution": resolution, "render_artifact": render})
        cur.execute("""SELECT c.instrument_id::text,c.id::text,a.id::text,
                              a.resolution::text
                       FROM segmentation_boundary_candidate c
                       LEFT JOIN segmentation_boundary_adjudication a
                         ON a.candidate_id=c.id
                       WHERE c.instrument_id=ANY(%s::uuid[])""", (ids,))
        for iid, candidate, adjudication, resolution in cur.fetchall():
            add_review(reviews, iid, "boundary", {
                "candidate_id": candidate, "adjudication_id": adjudication,
                "resolution": resolution})
        cur.execute("""SELECT source_observation_id,expression_ordinal,id::text,
                              disposition::text,render_artifact
                       FROM toc_disposition_assertion
                       WHERE source_observation_id=ANY(%s::bigint[])""", (obs_ids,))
        dispositions = defaultdict(list)
        for obs, expr, aid, disposition, render in cur.fetchall():
            dispositions[(obs, expr)].append({"id": aid,
                "disposition": disposition, "render_artifact": render})
        cur.execute("""SELECT source_observation_id,id::text,operation::text,
                              review_state::text
                       FROM segmentation_curation_patch
                       WHERE source_observation_id=ANY(%s::bigint[])""", (obs_ids,))
        for obs, pid, operation, state in cur.fetchall():
            add_review(observation_reviews, obs, "curation_patch", {
                "id": pid, "operation": operation, "review_state": state})
        cur.execute("""SELECT source_observation_id,id::text,resolution::text
                       FROM source_incompleteness
                       WHERE source_observation_id=ANY(%s::bigint[])""", (obs_ids,))
        for obs, sid, resolution in cur.fetchall():
            add_review(observation_reviews, obs, "source_incompleteness", {
                "id": sid, "resolution": resolution})
        cur.execute("""SELECT c.document_id,a.id::text,a.decision::text
                       FROM page_ocr_adjudication a
                       JOIN page_ocr_candidate c ON c.id=a.candidate_id
                       WHERE c.document_id=ANY(%s::bigint[])""", (doc_ids,))
        for doc, aid, decision in cur.fetchall():
            add_review(document_reviews, doc, "ocr_page", {
                "id": aid, "decision": decision})
        cur.execute("""SELECT p.instrument_id::text,count(DISTINCT p.id)
                       FROM provision p JOIN provision_version v
                         ON v.provision_id=p.id
                       WHERE p.instrument_id=ANY(%s::uuid[])
                         AND v.verified_at IS NOT NULL
                       GROUP BY p.instrument_id""", (ids,))
        verified_node_counts = dict(cur.fetchall())

    args.out.parent.mkdir(parents=True, exist_ok=True)
    summary = Counter()
    pdf_cache = {}
    if args.source_integrity_cache_from:
        for prior in read_jsonl([str(args.source_integrity_cache_from)]):
            pdf = prior["source_pdf"]
            if pdf.get("sha256_matches") is not None:
                pdf_cache[pdf["document_sha256"]] = {
                    key: pdf[key] for key in
                    ("exists", "sha256_matches", "actual_sha256", "byte_length", "reason")
                    if key in pdf}
    with args.out.open("w", encoding="utf-8") as sink:
        for row in base:
            (iid, doc, short_title, long_title, jurisdiction, kind, number,
             year, created, supersedes, obs, expr, first_block, last_block,
             verification_state, doc_sha, obs_sha, object_key, page_count) = row
            tree = patched.get(iid)
            old_tree = baseline.get(iid)
            error = build_errors.get((doc, obs))
            source = (source_integrity(args.source_root, object_key, doc_sha,
                                       pdf_cache) if args.verify_pdf_hashes else
                      {"exists": None, "sha256_matches": None,
                       "reason": "not_hash_checked"})
            flags = dict(flag_counts.get(iid, {}))
            source_review = source_reviews.get(doc)
            patch_changed = iid in comparison
            tree_same = (tree["compare"]["same"] if tree else None)
            # Every screening flag is only a lead. Without full source review,
            # even an identical tree and intact PDF cannot justify status A.
            coverage = assignment_coverage.get(iid)
            automated_pass = bool(source["sha256_matches"] and tree_same
                                  and not flags and not error
                                  and assignments.get(iid) and coverage
                                  and coverage["unassigned_block_rows"] == 0)
            if source_review and not source["sha256_matches"]:
                status = "UNRESOLVED"
            elif source_review:
                status = source_review["evidence_status"]
            elif automated_pass:
                status = "AUTOMATED_CHECKS_PASSED"
            else:
                status = "UNRESOLVED"
            record = {
                "instrument_id": iid, "document_id": doc,
                "title": short_title or long_title,
                "jurisdiction": jurisdiction, "kind": kind,
                "number": number, "year": year,
                "current_revision": {"instrument_id": iid,
                    "created_at": created.isoformat(),
                    "supersedes_instrument_id": supersedes,
                    "source_observation_id": obs, "expression_ordinal": expr,
                    "source_start_block_id": first_block,
                    "source_end_block_id": last_block},
                "source_pdf": {"object_key": object_key,
                    "document_sha256": doc_sha, "observation_sha256": obs_sha,
                    "page_count": page_count, **source},
                "production_release_status": "released",
                "stored_tree_version": {
                    "provision_count": node_counts.get(iid, 0),
                    "active_block_assignment_sets": assignments.get(iid, []),
                    "assignment_coverage": coverage,
                    "verified_provision_node_count": verified_node_counts.get(iid, 0),
                    "instrument_verification_state": verification_state},
                "existing_review_records": {
                    **dict(reviews.get(iid, {})),
                    "toc_disposition": dispositions.get((obs, expr), []),
                    **dict(observation_reviews.get(obs, {})),
                    **dict(document_reviews.get(doc, {}))},
                "structural_screen": {"flag_counts": flags,
                    "flag_count": sum(flags.values()),
                    "deduplicated_category_block_leads": len(flag_keys.get(iid, set())),
                    "status": "heuristic_not_source_verified"},
                "read_only_reparse": {
                    "built": tree is not None,
                    "build_error": error,
                    "identical_to_stored": tree_same,
                    "tree_identical": tree["compare"]["tree"]["identical"] if tree else None,
                    "s7_identical": tree["compare"]["s7"]["identical"] if tree else None,
                    "toc_identical": tree["compare"]["toc"]["identical"] if tree else None,
                    "patch_attributable_change": patch_changed,
                    "preexisting_parser_drift": (
                        not old_tree["compare"]["same"] if old_tree else None)},
                "automated_bundle_passed": automated_pass,
                "automated_bundle_scope": [
                    "source_pdf_sha256_matches_document_record",
                    "current_parser_tree_s7_toc_equal_stored",
                    "active_block_assignment_set_present",
                    "no_unassigned_block_role_in_active_set",
                    "no_unreviewed_heuristic_screening_flag"],
                "evidence_status": status,
                "full_instrument_source_image_review_completed": bool(
                    source_review and source_review["full_pdf_pages_reviewed"]),
                "independent_source_review": source_review,
                "needs_release_status_decision": status == "CONFIRMED_DEFECT",
            }
            sink.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            summary["released_canonical_instruments"] += 1
            summary["status_" + status] += 1
            summary["automated_bundle_passed"] += automated_pass
            summary["pdf_exists"] += bool(source["exists"])
            summary["pdf_hash_matches"] += bool(source["sha256_matches"])
            summary["reparse_built"] += tree is not None
            summary["reparse_identical_to_stored"] += tree_same is True
            summary["patch_attributable_change"] += patch_changed
            summary["has_heuristic_flags"] += bool(flags)
            summary["independently_source_reviewed_instruments"] += bool(source_review)
            summary["full_instrument_source_image_reviews"] += bool(
                source_review and source_review["full_pdf_pages_reviewed"])
    summary = dict(summary)
    summary.update({"snapshot_at": snapshot_at,
                    "active_canonical_instruments": active_canonical,
                    "active_noncanonical_copies": active_copies,
                    "inactive_historical_revisions": inactive_historical,
                    "known_defect_document_release_states": known_defect_document_release_states,
                    "source_screen_generated_at": screening.get("generated_at"),
                    "source_review_sample_size": len(source_reviews)})
    args.out.with_suffix(".summary.json").write_text(
        json.dumps(dict(summary), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(summary), indent=2))


if __name__ == "__main__":
    main()
