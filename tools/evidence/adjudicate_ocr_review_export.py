"""Record a validated owner OCR-review export as page_ocr_adjudication rows.

The export (tools/build_ocr_review_pack.py -> the reviewer's browser -> JSON,
checked by tools/validate_ocr_review_export.py) is the person's decision; this
script only writes it down. Each decision is tied to exactly one imported Surya
candidate whose text hashes to the export's candidate_text_sha256, or nothing
is written.

Where the reviewer accepted a page only with a correction, or rejected it while
supplying the missing text and saying the page may then be accepted, the
correction is recorded as a new candidate (engine suffixed
"+owner-correction/1") built from the Surya blocks plus the reviewer's words,
and that candidate carries the acceptance. The Surya candidate keeps the
reviewer's own decision (or none, for an accept-with-correction, so that a page
never has two accepted readings).

    ./.venv/bin/python tools/evidence/adjudicate_ocr_review_export.py EXPORT.json \
        [--corrections CORRECTIONS.json] [--apply]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from nizam.storage.db import connect
from nizam.workers.import_surya_candidates import ENGINE

DECIDED_BY = "bilalahmadsheikh"
CORRECTION_ENGINE = ENGINE + "+owner-correction/1"
_WORD = re.compile(r"\w+", re.UNICODE)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def corrected_blocks(blocks: list[dict], spec: dict, page_height: float) -> list[dict]:
    """Surya blocks plus the reviewer's lines (above or below), or a replacement."""
    out = [dict(b) for b in blocks]
    for old, new in spec.get("replace", []):
        hits = [b for b in out if old in b["text"]]
        if len(hits) != 1:
            raise ValueError(f"replacement {old!r} matches {len(hits)} blocks")
        hits[0]["text"] = hits[0]["text"].replace(old, new, 1)
        hits[0]["html"] = hits[0].get("html", "").replace(old, new, 1)
        hits[0]["owner_corrected"] = True
    lines = [line for line in spec.get("lines", []) if line.strip()]
    if lines:
        x0 = min(b["bbox"][0] for b in blocks)
        x1 = max(b["bbox"][2] for b in blocks)
        if spec["position"] == "below":
            top = max(b["bbox"][3] for b in blocks) + 2.0
            bottom = page_height - 2.0
        else:
            top, bottom = 0.0, max(min(b["bbox"][1] for b in blocks) - 0.5, 1.0)
        step = (bottom - top) / len(lines)
        added = [{
            "bbox": [x0, top + i * step, x1, top + (i + 1) * step],
            "html": "", "text": line, "error": False, "label": "Text",
            "script": "latin", "skipped": False, "raw_label": "OwnerCorrection",
            "confidence": 1.0, "owner_supplied": True,
            "geometry": "approximate: spaced evenly over the region the reviewer placed it in",
        } for i, line in enumerate(lines)]
        out = out + added if spec["position"] == "below" else added + out
    for number, block in enumerate(out):
        block["block_no"] = number
        block["reading_order"] = number
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("export", type=Path)
    ap.add_argument("--corrections", type=Path)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    raw = args.export.read_bytes()
    export = json.loads(raw)
    corrections = (json.loads(args.corrections.read_text(encoding="utf-8"))
                   if args.corrections else {})
    doc = int(export["document_id"])
    base_evidence = {
        "review": "owner-ocr-review-pack", "review_export": str(args.export),
        "review_export_sha256": hashlib.sha256(raw).hexdigest(),
        "reviewer_name": export["reviewer_name"], "exported_at": export["exported_at"],
        "source_sha256": export["source_sha256"], "result_sha256": export["result_sha256"],
        "validated_by": "tools/validate_ocr_review_export.py",
    }
    plan = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT sha256 FROM document WHERE id=%s AND is_active", (doc,))
        row = cur.fetchone()
        if not row or row[0] != export["source_sha256"]:
            raise SystemExit(f"document {doc} is not the active source the export reviewed")
        for d in export["decisions"]:
            page = int(d["page_no"])
            cur.execute("""SELECT id, text, blocks, mean_confidence FROM page_ocr_candidate
                            WHERE document_id=%s AND page_no=%s AND engine=%s""", (doc, page, ENGINE))
            hits = [r for r in cur.fetchall() if sha(r[1]) == d["candidate_text_sha256"]]
            if len(hits) != 1:
                raise SystemExit(f"page {page}: {len(hits)} candidates match the reviewed text hash")
            cand_id, _text, blocks, _conf = hits[0]
            evidence = dict(base_evidence, page_no=page, document_id=doc,
                            candidate_text_sha256=d["candidate_text_sha256"],
                            source_image=d.get("source_image"),
                            reviewed_source_image=d.get("reviewed_source_image"))
            fix = corrections.get(str(page))
            if d["decision"] == "rejected":
                plan.append(("adjudicate", cand_id, "rejected", d["reason"], evidence))
            elif d["decision"] == "accepted" and not fix:
                reason = d["reason"] or ("Owner checked the source image and accepted this "
                                         "Surya reading (OCR review pack r5).")
                plan.append(("adjudicate", cand_id, "accepted", reason, evidence))
            elif d["decision"] != "accepted":
                raise SystemExit(f"page {page}: unsupported decision {d['decision']!r}")
            if fix:
                cur.execute("SELECT height FROM page WHERE document_id=%s AND page_no=%s", (doc, page))
                height = float(cur.fetchone()[0])
                new_blocks = corrected_blocks(blocks, fix, height)
                text = "\n\n".join(b["text"] for b in new_blocks)
                words = len(_WORD.findall(text))
                weighted = sum(float(b["confidence"]) * max(len(_WORD.findall(b["text"])), 1)
                               for b in new_blocks)
                weight = sum(max(len(_WORD.findall(b["text"])), 1) for b in new_blocks)
                reason = ("Owner's correction applied as the reviewer instructed: "
                          + fix["summary"])
                plan.append(("correct", page, cand_id, text, new_blocks, round(weighted / weight, 4),
                             words, reason, dict(evidence, reviewer_decision=d["decision"],
                                                 reviewer_reason=d["reason"],
                                                 corrects_candidate_id=cand_id,
                                                 correction=fix)))
        for item in plan:
            if item[0] == "adjudicate":
                print(f"  candidate {item[1]}: {item[2]} -- {item[3][:90]!r}")
            else:
                print(f"  page {item[1]}: new corrected candidate from {item[2]} "
                      f"({len(item[4])} blocks, {item[6]} words) -> accepted")
        if not args.apply:
            print("dry run -- pass --apply to record")
            return 0
        for item in plan:
            if item[0] == "adjudicate":
                _, cand_id, decision, reason, evidence = item
                cur.execute("""INSERT INTO page_ocr_adjudication
                               (candidate_id, decision, reason, evidence, decided_by)
                               VALUES (%s,%s,%s,%s,%s)""",
                            (cand_id, decision, reason, json.dumps(evidence, ensure_ascii=False),
                             DECIDED_BY))
            else:
                _, page, old_id, text, new_blocks, conf, words, reason, evidence = item
                cur.execute("""SELECT languages, dpi FROM page_ocr_candidate WHERE id=%s""", (old_id,))
                languages, dpi = cur.fetchone()
                cur.execute("""INSERT INTO page_ocr_candidate
                               (document_id, page_no, engine, languages, dpi, text,
                                mean_confidence, word_count, blocks)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                            (doc, page, CORRECTION_ENGINE, languages, dpi, text, conf, words,
                             json.dumps(new_blocks, ensure_ascii=False)))
                new_id = cur.fetchone()[0]
                cur.execute("""INSERT INTO page_ocr_adjudication
                               (candidate_id, decision, reason, evidence, decided_by)
                               VALUES (%s,'accepted',%s,%s,%s)""",
                            (new_id, reason, json.dumps(evidence, ensure_ascii=False), DECIDED_BY))
                print(f"  page {page}: corrected candidate {new_id} accepted")
        conn.commit()
        print(f"recorded {len(plan)} item(s) for document {doc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
