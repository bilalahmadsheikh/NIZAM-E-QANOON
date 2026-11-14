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
               (margin side notes are NOT predicted: tools/recrawl/leakscan.py finds them after landing)
  sections     top-level numbered units the tree holds (0 = no structure found)
  verdict      clean      no blocker, no leak, at least one section -- land it
               leaky      no blocker but leak signals -- land it and run the leak repairs
               blocked    a blocker or no structure -- do NOT land (it would sit held)
               rejected   extraction refused the file
The prediction is not a release decision: landed files still pass every gate in the ordinary lane.
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
          "leak_head", "leak_note", "sections", "lane", "error"]


def _signature(text: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", text).strip().casefold())


def preflight(args: tuple[str, str, str]) -> dict:
    sha, title, path = args
    from nizam.corpus.extract import extract_pdf
    from nizam.corpus.segment import segment
    from nizam.shared.corpus_types import ExtractionRejected
    from nizam.workers.verify_text_quality import score
    out = {"sha256": sha, "title": title}
    try:
        doc = extract_pdf(Path(path).read_bytes(), sha)
    except ExtractionRejected as e:
        return {**out, "verdict": "rejected", "error": str(e)[:200]}
    except Exception as e:  # noqa: BLE001 -- one bad file never stops the run
        return {**out, "verdict": "rejected", "error": f"{type(e).__name__}: {str(e)[:180]}"}
    heights = {p.page_no: p.height for p in doc.pages} if doc.pages and hasattr(doc.pages[0], "height") else {}
    blocks = [{"id": n + 1, "text": b.text, "page_no": b.page_no, "y0": float(b.y0),
               "page_height": float(heights.get(b.page_no, 792)), "x0": float(b.x0), "x1": float(b.x1)}
              for n, b in enumerate(sorted(doc.blocks, key=lambda b: b.reading_order))]
    try:
        seg = segment(blocks)
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
                   for x in [n, *getattr(n, "children", [])] if getattr(x, "kind", None) in ("section", "article", "rule", "regulation"))
    blocker = s7 > 0 or toc_pending > 0 or q.get("outcome") == "review" or sections == 0
    verdict = "blocked" if blocker else ("leaky" if leak_head or leak_note else "clean")
    return {**out, "pages": doc.page_count, "lane": doc.lane, "verdict": verdict, "s7": s7,
            "toc_found": seg.toc_found, "toc_pending": toc_pending, "quality": q.get("outcome"),
            "legal_rate": q.get("legal_rate"), "leak_head": leak_head, "leak_note": leak_note, "sections": sections}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("staged"); ap.add_argument("files"); ap.add_argument("out")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    done = set()
    if Path(a.out).exists():                     # resumable: a file already preflighted is not run again
        done = {r["sha256"] for r in csv.DictReader(open(a.out, encoding="utf-8"))}
    jobs = []
    for r in csv.DictReader(open(a.staged, encoding="utf-8")):
        if r.get("grade") != "text" or not r.get("sha256") or r["sha256"] in done:
            continue
        f = Path(a.files) / f"{r['sha256']}.pdf"
        if f.exists():
            jobs.append((r["sha256"], r["title"], str(f)))
            done.add(r["sha256"])
    new = not Path(a.out).exists()
    with open(a.out, "a", encoding="utf-8", newline="") as fh, ProcessPoolExecutor(a.workers) as ex:
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
