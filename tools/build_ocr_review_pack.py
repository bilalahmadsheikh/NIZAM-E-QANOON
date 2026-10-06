"""Build a local, read-only source-image/OCR comparison pack.

Run under the repository's WSL environment, for example::

    ./.venv/bin/python tools/build_ocr_review_pack.py --document 3800

The HTML exports proposed human decisions as JSON. It never adjudicates,
promotes OCR, changes a source revision, or releases an instrument.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from nizam.storage.db import connect
from nizam.workers.import_surya_candidates import ENGINE, html_to_text

DEFAULT_INPUT = Path("/mnt/e/nizam-data/ocr/r5-input")
DEFAULT_RESULTS = Path("/mnt/e/nizam-data/ocr/r5-output")
DEFAULT_OUTPUT = Path(".artifacts/ocr-review-pack-r5")
TEMPLATE = Path(__file__).with_name("ocr_review_template.html")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def result_pages(path: Path, document_id: int) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    pages = payload.get(str(document_id))
    if not isinstance(pages, list) or not pages:
        raise ValueError(f"{path}: no pages for document {document_id}")
    by_number = {}
    for item in pages:
        number = int(item["page"])
        if number < 1 or number in by_number or not isinstance(item.get("blocks"), list):
            raise ValueError(f"{path}: invalid or repeated page {number}")
        by_number[number] = item
    return [by_number[number] for number in sorted(by_number)]


def stored_evidence(document_id: int) -> tuple[dict, dict[int, str], dict[tuple[int, str], dict]]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cur.execute("""SELECT sha256,page_count,is_active,lane FROM document
                       WHERE id=%s""", (document_id,))
        row = cur.fetchone()
        if row is None or not row[2]:
            raise ValueError(f"document {document_id} is not an active source revision")
        source = dict(zip(("sha256", "page_count", "is_active", "lane"), row))
        cur.execute("""SELECT page_no,text FROM text_block WHERE document_id=%s
                       ORDER BY page_no,reading_order,id""", (document_id,))
        stored: dict[int, list[str]] = {}
        for page_no, text in cur.fetchall():
            stored.setdefault(page_no, []).append(text or "")
        cur.execute("""SELECT c.id,c.page_no,c.text,c.engine,
                              (SELECT a.decision FROM page_ocr_adjudication a
                               WHERE a.candidate_id=c.id
                               ORDER BY a.decided_at DESC,a.id DESC LIMIT 1)
                       FROM page_ocr_candidate c WHERE c.document_id=%s
                         AND c.engine=%s ORDER BY c.id DESC""",
                    (document_id, ENGINE))
        candidates = {}
        for candidate_id, page_no, text, engine, decision in cur.fetchall():
            candidates.setdefault((page_no, text), {
                "candidate_id": candidate_id, "engine": engine,
                "database_decision": decision or "review",
            })
    return source, {k: "\n\n".join(v) for k, v in stored.items()}, candidates


def prepare_page(result: dict, stored: str, candidate: dict | None) -> dict:
    blocks = []
    for raw in sorted(result["blocks"], key=lambda b: b.get("reading_order", 10**9)):
        text = html_to_text(raw.get("html", ""))
        if not text:
            continue
        blocks.append({
            "text": text, "label": raw.get("label"),
            "confidence": raw.get("confidence"),
            "bbox": raw.get("bbox"),
            "reading_order": raw.get("reading_order"),
        })
    candidate_text = "\n\n".join(block["text"] for block in blocks)
    return {
        "page_no": int(result["page"]), "stored_text": stored,
        "candidate_text": candidate_text,
        "candidate_text_sha256": hashlib.sha256(candidate_text.encode("utf-8")).hexdigest(),
        "candidate_id": candidate["candidate_id"] if candidate else None,
        "database_decision": candidate["database_decision"] if candidate else "not_imported",
        "blocks": blocks,
        "image": f"images/page-{int(result['page']):03d}.png",
    }


def render_page(pdf: Path, page_no: int, output: Path, dpi: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_file() and output.stat().st_size:
        return
    command = ["pdftoppm", "-f", str(page_no), "-l", str(page_no),
               "-r", str(dpi), "-png", "-singlefile", str(pdf),
               str(output.with_suffix(""))]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE)
    if not output.is_file() or not output.stat().st_size:
        raise RuntimeError(f"source image not rendered: {output}")


def build_one(document_id: int, input_dir: Path, result_dir: Path,
              output_dir: Path, dpi: int) -> dict:
    pdf = input_dir / f"{document_id}.pdf"
    result_file = result_dir / str(document_id) / "results.json"
    if not pdf.is_file() or not result_file.is_file():
        raise FileNotFoundError(f"document {document_id}: PDF or completed results.json missing")
    source, stored, candidates = stored_evidence(document_id)
    pdf_sha = sha256_file(pdf)
    if pdf_sha != source["sha256"]:
        raise ValueError(f"document {document_id}: staged PDF differs from active source hash")
    pages = result_pages(result_file, document_id)
    if any(int(page["page"]) > source["page_count"] for page in pages):
        raise ValueError(f"document {document_id}: OCR page outside source PDF")
    doc_dir = output_dir / f"doc-{document_id}"
    doc_dir.mkdir(parents=True, exist_ok=True)
    prepared = []
    for result in pages:
        no = int(result["page"])
        page = prepare_page(result, stored.get(no, ""), None)
        match = candidates.get((no, page["candidate_text"]))
        if match:
            page["candidate_id"] = match["candidate_id"]
            page["database_decision"] = match["database_decision"]
        render_page(pdf, no, doc_dir / page["image"], dpi)
        prepared.append(page)
    review = {
        "schema": "nizam.ocr_page_review.v1",
        "document_id": document_id,
        "source_sha256": pdf_sha,
        "result_sha256": sha256_file(result_file),
        "candidate_engine": ENGINE,
        "source_page_count": source["page_count"],
        "candidate_page_count": len(prepared),
        "source_lane": source["lane"],
        "pages": prepared,
    }
    (doc_dir / "manifest.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    encoded = json.dumps(review, ensure_ascii=False).replace("<", "\\u003c")
    (doc_dir / "index.html").write_text(
        template.replace("/*__OCR_REVIEW_DATA__*/", encoded), encoding="utf-8")
    return {"document_id": document_id, "pages": len(prepared),
            "source_pages": source["page_count"],
            "imported_pages": sum(p["candidate_id"] is not None for p in prepared),
            "path": f"doc-{document_id}/index.html"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--document", type=int, action="append",
                        help="repeat to build only specified completed OCR documents")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dpi", type=int, default=120)
    args = parser.parse_args()
    if not 72 <= args.dpi <= 220:
        parser.error("--dpi must be 72..220")
    docs = args.document or sorted(int(path.parent.name) for path in
        args.results.glob("[0-9]*/results.json") if path.parent.name.isdigit())
    if not docs:
        parser.error("no completed OCR results found")
    built = [build_one(doc, args.input, args.results, args.out, args.dpi)
             for doc in sorted(set(docs))]
    links = "\n".join(
        f'<li><a href="{row["path"]}">Document {row["document_id"]}</a> '
        f'— OCR {row["pages"]}/{row["source_pages"]} pages, '
        f'DB candidates {row["imported_pages"]}</li>' for row in built)
    (args.out / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>OCR review</title>'
        '<style>body{font:16px system-ui;max-width:750px;margin:4rem auto;'
        'padding:1rem}li{margin:.8rem 0}</style><h1>OCR source review</h1>'
        '<p>Open a document. Decisions export to JSON; nothing is sent to the database.</p>'
        f'<ul>{links}</ul>', encoding="utf-8")
    print(json.dumps({"output": str(args.out / "index.html"), "documents": built}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
