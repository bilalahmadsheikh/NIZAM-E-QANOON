"""preflight_segment.py STAGED.csv FILES_DIR OUT.csv [--workers N] : predict, before landing, whether a staged law PDF
would release with no further processing (read-only: no database, nothing landed).

Why (14 Nov 2026): three ICT files landed because their text layer graded 'text', then proved to need days of
structural reading (contents read as Parts, notifications compiled into one file) and sat held. A text layer is
necessary, not sufficient. Each staged file graded 'text' is taken through the same pure steps the workers run --
nizam.corpus.extract.extract_pdf, nizam.corpus.segment.segment (default profile, no patches), and
nizam.workers.verify_text_quality.score -- and is reported with what would block or soil its release:

  s7           repeated-label units the segmenter could not settle (each blocks release)
  toc_pending  contents entries with no body provision, plus labels promised and missing (each blocks release)
  quality      verify_text_quality's outcome ('review' blocks release)
  leak_head    body blocks that repeat, digits aside, at the top of 3+ pages (running heads read as law)
  leak_note    body blocks opening like a page footnote ('1 This Act was passed ...', '2 Subs. by ...')
               (margin side notes are NOT predicted: tools/recrawl/leakscan.py finds them after landing)
  sections     top-level numbered units the tree holds (0 = no structure found)
  evidence     verify_extraction's character recall/precision and page count, and verify_order's ordered-trigram
               precision, against Poppler, with no reviewed credit ('passed', else what fails -- a failure blocks)
  verdict      clean      no blocker, no leak, at least one section -- land it
               leaky      no blocker but leak signals -- land it and run the leak repairs
               blocked    a blocker or no structure -- do NOT land (it would sit held)
               rejected   extraction refused the file
The prediction is not a release decision: landed files still pass every gate in the ordinary lane.

--ocr docai --second-read DIR (D-114): preflight the SCANS instead (grades scan, partial, urdu). Each is read by Google
Document AI (nizam.corpus.ocr_docai; responses are kept, so landing reads them again for nothing), and 'evidence' is
the cross-read against tools/acquire/second_read.py's Tesseract reading in DIR (nizam.corpus.crossread), in place of
Poppler, which a scan has nothing for. 'quality' then also needs verify_ocr's thresholds (confidence, legal-token
rate for English, words per page).
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

FOOTNOTE = re.compile(r"^\s*\d{1,2}\s*(?:This\s+(?:Act|Ordinance|Ordnance|Regulation)|These\s+rules|Subs?\.|Ins\.|"
                      r"Added|Omitted|Inserted|Substituted|Renumbered|Rep\.|The\s+words|Vide)", re.I)
FIELDS = ["sha256", "title", "pages", "verdict", "s7", "toc_found", "toc_pending", "quality", "legal_rate",
          "leak_head", "leak_note", "sections", "evidence", "char_recall", "char_precision", "order", "lane", "error"]


def _signature(text: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", text).strip().casefold())


OCR_MODE: dict = {}      # set in each worker by _init: {"engine": "docai", "second_read": DIR} for scans
_CLIENT = None


PROFILE = ["default"]     # --profile: the segmentation profile the landed observation will be pinned to (D-115)


def _init(mode: dict, profile: str = "default") -> None:
    OCR_MODE.update(mode)
    PROFILE[0] = profile


def _read(path: str, sha: str):
    global _CLIENT
    if not OCR_MODE:
        from nizam.corpus.extract import extract_pdf
        return extract_pdf(Path(path).read_bytes(), sha)
    from nizam.corpus.ocr_docai import DocAIClient
    if _CLIENT is None:
        _CLIENT = DocAIClient()
    return _CLIENT.ocr_pdf(Path(path).read_bytes(), sha)


def ocr_evidence(doc, second_read: Path) -> dict:
    """D-114: the release reading against the independent Tesseract reading, page by page; and verify_ocr's floor."""
    import gzip
    import json
    from nizam.corpus.crossread import compare_pages, release_pages
    from nizam.workers import verify_ocr as vo
    f = second_read / f"{doc.sha256}.json.gz"
    if not f.exists():
        return {"evidence": "no second reading", "order": None}
    rec = json.loads(gzip.decompress(f.read_bytes()))
    if "pages" not in rec:
        return {"evidence": f"second reader rejected the scan: {rec.get('rejected', '')[:80]}", "order": None}
    r = compare_pages(release_pages(doc.blocks, doc.page_count), rec["pages"])
    problems = [] if r["verdict"] == "agree" else [r["verdict"]]
    conf = float(doc.printable_ratio)
    if conf < vo.MIN_CONFIDENCE:
        problems.append(f"confidence {conf:.3f}")
    words = int(doc.pdf_metadata.get("ocr_words") or 0)
    if doc.page_count and words / doc.page_count < vo.MIN_WORDS_PER_PAGE:
        problems.append(f"{words / doc.page_count:.0f} words/page")
    if doc.pdf_metadata.get("ocr_language") == "eng":
        toks = vo.WORD.findall(" ".join(b.text for b in doc.blocks).lower())
        rate = sum(t in vo.LEGAL for t in toks) / len(toks) if toks else 0.0
        if rate < vo.MIN_LEGAL_RATE:
            problems.append(f"legal-token rate {rate:.3f}")
    rec_pages = [p for p in r["pages"] if p.get("compared")]
    return {"evidence": "passed" if not problems else "; ".join(problems),
            "char_recall": min((p["recall"] for p in rec_pages), default=None),
            "char_precision": min((p["precision"] for p in rec_pages), default=None),
            "order": r.get("bigram_precision")}


def preflight(args: tuple[str, str, str]) -> dict:
    sha, title, path = args
    from nizam.corpus.segment import segment
    from nizam.shared.corpus_types import ExtractionRejected
    from nizam.workers.verify_text_quality import score
    out = {"sha256": sha, "title": title}
    try:
        doc = _read(path, sha)
    except ExtractionRejected as e:
        return {**out, "verdict": "rejected", "error": str(e)[:200]}
    except Exception as e:  # noqa: BLE001 -- one bad file never stops the run
        return {**out, "verdict": "rejected", "error": f"{type(e).__name__}: {str(e)[:180]}"}
    heights = {p.page_no: p.height for p in doc.pages} if doc.pages and hasattr(doc.pages[0], "height") else {}
    blocks = [{"id": n + 1, "text": b.text, "page_no": b.page_no, "y0": float(b.y0),
               "page_height": float(heights.get(b.page_no, 792)), "x0": float(b.x0), "x1": float(b.x1)}
              for n, b in enumerate(sorted(doc.blocks, key=lambda b: b.reading_order))]
    try:
        seg = segment(blocks, **({} if PROFILE[0] == "default" else {"profile": PROFILE[0]}))
    except Exception as e:  # noqa: BLE001
        return {**out, "pages": doc.page_count, "lane": doc.lane, "verdict": "blocked",
                "error": f"segment: {type(e).__name__}: {str(e)[:160]}"}
    s7 = sum(1 for d in seg.repeated_label_decisions if not d.get("settled_by_review"))
    unmatched = [e for e in seg.toc_entries if e.get("node") is None]
    unmatched_labels = {e["label"] for e in unmatched if e.get("kind") != "schedule"}
    toc_pending = len(unmatched) + len(set(seg.missing) - unmatched_labels) if seg.toc_found else 0
    page_texts: dict[int, list[str]] = {}
    for b in blocks:
        page_texts.setdefault(b["page_no"], []).append(b["text"])
    q = score("\n".join(b["text"] for b in blocks), ["\n".join(v) for v in page_texts.values()])
    q["outcome"] = "review" if q["problems"] else "passed"     # verify_text_quality's rule: any problem -> review
    body = {bid for bid, (role, _node) in seg.block_roles.items() if role == "body"}
    tops: Counter = Counter()
    first_on_page: dict[int, list[dict]] = {}
    for b in blocks:
        first_on_page.setdefault(b["page_no"], [])
        if len(first_on_page[b["page_no"]]) < 3:
            first_on_page[b["page_no"]].append(b)
    for page_blocks in first_on_page.values():
        for b in page_blocks:
            if 4 <= len(b["text"].strip()) <= 160:
                tops[_signature(b["text"])] += 1
    heads = {s for s, n in tops.items() if n >= 3}
    leak_head = sum(1 for b in blocks if b["id"] in body and _signature(b["text"]) in heads)
    leak_note = sum(1 for b in blocks if b["id"] in body and FOOTNOTE.match(b["text"]))
    sections = sum(1 for n in getattr(seg.root, "children", []) or []
                   for x in [n, *getattr(n, "children", [])] if getattr(x, "kind", None) in ("section", "article", "rule", "regulation", "notification"))
    evidence = (ocr_evidence(doc, Path(OCR_MODE["second_read"])) if OCR_MODE
                else independent_evidence(Path(path), doc))
    blocker = (s7 > 0 or toc_pending > 0 or q.get("outcome") == "review" or sections == 0
               or evidence["evidence"] != "passed")
    verdict = "blocked" if blocker else ("leaky" if leak_head or leak_note else "clean")
    return {**out, "pages": doc.page_count, "lane": doc.lane, "verdict": verdict, "s7": s7,
            "toc_found": seg.toc_found, "toc_pending": toc_pending, "quality": q.get("outcome"),
            "legal_rate": q.get("legal_rate"), "leak_head": leak_head, "leak_note": leak_note, "sections": sections,
            **evidence}


def independent_evidence(path: Path, doc) -> dict:
    """The two Poppler gates the extraction lane runs after landing (nizam.workers.verify_extraction, verify_order),
    with their own functions and thresholds and WITHOUT any reviewed credit (no source_content_confirmed, decode-damage
    or repaired-reference assertion exists for a file not yet landed) -- so a pass here cannot fail there, while a
    file the gates would pass only with a reviewed credit is predicted blocked."""
    import subprocess
    from nizam.workers import verify_extraction as ve
    from nizam.workers import verify_order as vo
    text_blocks = [b for b in sorted(doc.blocks, key=lambda b: b.reading_order) if b.confidence is None]
    mine = "\n".join(b.text for b in text_blocks)
    outside = "\n".join(b.text for b in text_blocks if not b.inside_cropbox)
    raw = ve.pdftotext(path)
    ours, theirs = ve._chars(mine), ve._chars(raw)
    problems = []
    recall = precision = order = None
    if not theirs:
        problems.append("pdftotext found no text")
    else:
        shared = ve._multiset_overlap(ours, theirs)
        recall = shared / sum(theirs.values())
        extra = ve._unexplained_extra(mine, raw, outside, "")
        precision = (sum(ours.values()) - sum(extra.values())) / sum(ours.values()) if ours else 0.0
        if recall < ve.MIN_CHAR_RECALL:
            problems.append(f"char recall {recall:.5f}")
        if precision < ve.MIN_CHAR_PRECISION:
            problems.append(f"char precision {precision:.5f}")
    info = subprocess.run(["pdfinfo", str(path)], capture_output=True, timeout=60)
    m = re.search(rb"Pages:\s+(\d+)", info.stdout)
    if m and int(m.group(1)) != doc.page_count:
        problems.append(f"page count {m.group(1).decode()} != {doc.page_count}")
    by_page: dict[int, list[str]] = {}
    for b in text_blocks:
        by_page.setdefault(b.page_no, []).append(b.text)
    refs = []
    for layout in (False, True):
        pages = vo.pdftotext(path, layout=layout).split("\f")
        if pages and not pages[-1].strip():
            pages.pop()
        refs.append(pages)
    if max(len(vo.lexical_words(" ".join(p))) for p in refs) < vo.MIN_REFERENCE_LEXICAL_WORDS:
        stored = [vo.lexical_words(" ".join(by_page.get(n, []))) for n in range(1, max(by_page, default=0) + 1)]
        if not any(stored == [vo.lexical_words(p) for p in pages] and any(stored) for pages in refs):
            problems.append("order unverifiable: too few reference words")
    else:
        order = max(vo._score_reference(by_page, pages)["ordered_trigram_precision"] for pages in refs)
        if order < vo.MIN_ORDERED_TRIGRAM_PRECISION:
            problems.append(f"ordered-trigram precision {order:.3f}")
    return {"evidence": "passed" if not problems else "; ".join(problems),
            "char_recall": None if recall is None else round(recall, 5),
            "char_precision": None if precision is None else round(precision, 5),
            "order": None if order is None else round(order, 4)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("staged"); ap.add_argument("files"); ap.add_argument("out")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--ocr", choices=("docai",), help="preflight the scans, read by this engine (D-114)")
    ap.add_argument("--profile", help="segment under this profile, the one the observation will be pinned to (D-115)")
    ap.add_argument("--second-read", type=Path, help="with --ocr: tools/acquire/second_read.py's output directory")
    a = ap.parse_args()
    if bool(a.ocr) != bool(a.second_read):
        ap.error("--ocr and --second-read go together")
    grades = {"scan", "partial", "urdu"} if a.ocr else {"text"}
    mode = {"engine": a.ocr, "second_read": str(a.second_read)} if a.ocr else {}
    if a.profile:
        from nizam.corpus.segment import SEGMENTATION_PROFILES
        if a.profile not in SEGMENTATION_PROFILES:
            ap.error(f"unknown profile {a.profile!r}")
    done = set()
    if Path(a.out).exists():                     # resumable: a file already preflighted is not run again
        done = {r["sha256"] for r in csv.DictReader(open(a.out, encoding="utf-8"))}
    jobs = []
    for r in csv.DictReader(open(a.staged, encoding="utf-8")):
        if r.get("grade") not in grades or not r.get("sha256") or r["sha256"] in done:
            continue
        f = Path(a.files) / f"{r['sha256']}.pdf"
        if f.exists():
            jobs.append((r["sha256"], r["title"], str(f)))
            done.add(r["sha256"])
    new = not Path(a.out).exists()
    with open(a.out, "a", encoding="utf-8", newline="") as fh, ProcessPoolExecutor(a.workers, initializer=_init, initargs=(mode, a.profile or "default")) as ex:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        for n, row in enumerate(ex.map(preflight, jobs, chunksize=4), 1):
            w.writerow(row); fh.flush()
            if n % 50 == 0:
                print(f"{n}/{len(jobs)}", flush=True)
    rows = list(csv.DictReader(open(a.out, encoding="utf-8")))
    print(Counter(r["verdict"] for r in rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
