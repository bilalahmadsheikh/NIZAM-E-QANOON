"""ajk_folio_patch.py OUT_DIR [DOC,DOC,...] -- readings that set aside page numbers (folios) read into released AJK provisions.

The AJK Code prints each page's number at its foot (doc 10935: '202' on p4, '205' on p7, numbered by the volume, not
the file). Where the text layer gave the number a block of its own inside the law, it ran into the sentence that
crosses the page ('any 202 movable antiquity', s.6(1)). A block is set aside only when ALL hold:
  * its whole text is a number of 1-4 digits, and it starts in the top 12% or the bottom 20% of its page;
  * it is body text of an active provision of a released AJK instrument;
  * number minus page is the document's folio offset -- the same offset holds for at least three such blocks of the
    document (so the number is the page's own, never a table cell or a figure).
One reading per page (rule reviewed_apparatus_block). Read-only; writes OUT_DIR/patch-<doc>f.json; prints totals."""
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect  # noqa: E402

ROOT = Path("/mnt/e/Nizam_e_Qanoon")
REL = ".artifacts/release-work-2026-09-24/claude/renders/ajk-folio"
IN_LAW = """
SELECT pb.block_id FROM provision_block pb
  JOIN block_assignment_set s ON s.id=pb.assignment_set_id AND s.is_active
  JOIN provision p ON p.id=pb.provision_id AND p.is_active
  JOIN (SELECT id FROM v_release_instrument WHERE jurisdiction='ajk') r ON r.id=p.instrument_id
 WHERE pb.role='body'"""
FOLIOS = """
SELECT t.document_id, t.page_no, t.id, btrim(t.text), t.y0, pg.height
  FROM text_block t JOIN page pg ON pg.document_id=t.document_id AND pg.page_no=t.page_no
  JOIN (SELECT DISTINCT document_id FROM v_release_instrument WHERE jurisdiction='ajk') r ON r.document_id=t.document_id
 WHERE t.text ~ '^\\s*[0-9]{1,4}\\s*$'"""


def main() -> int:
    out_dir = Path(sys.argv[1])
    only = {int(x) for x in sys.argv[2].split(",")} if len(sys.argv) > 2 else None   # optional DOC,DOC,...
    out_dir.mkdir(parents=True, exist_ok=True)
    (ROOT / REL).mkdir(parents=True, exist_ok=True)
    totals = collections.Counter()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET max_parallel_workers_per_gather = 0")
        cur.execute(IN_LAW)
        in_law = {r[0] for r in cur.fetchall()}
        cur.execute(FOLIOS)
        by_doc = collections.defaultdict(list)
        for d, p, bid, num, y0, h in cur.fetchall():
            y, hh = float(y0 or 0), float(h or 1)
            if y < .12 * hh or y > .8 * hh:
                by_doc[d].append((p, bid, int(num), bid in in_law))
        for d, rows in sorted(by_doc.items()):
            if only is not None and d not in only:
                continue
            offsets = collections.Counter(n - p for p, _b, n, _l in rows)
            off, count = offsets.most_common(1)[0]
            if count < 3:
                continue
            hits = [(p, b, n) for p, b, n, il in rows if il and n - p == off]
            if not hits:
                continue
            cur.execute("SELECT page_no, id, coalesce(text,'') FROM text_block WHERE document_id=%s", (d,))
            by_page = collections.defaultdict(list)
            for p, b, t in cur.fetchall():
                by_page[p].append((b, t))
            # locators any reading of the document ever used, page by page, retired or not (the recorder refuses an
            # identical patch even when the earlier one was withdrawn; the evidence is append-only)
            cur.execute("""SELECT DISTINCT c.page_no, c.match_text FROM segmentation_curation_patch c
                             JOIN source_observation o ON o.id=c.source_observation_id
                             JOIN document x ON x.sha256=o.sha256 WHERE x.id=%s""", (d,))
            used = {(p, m) for p, m in cur.fetchall()}
            cur.execute("SELECT b.object_key FROM document x JOIN blob b ON b.sha256=x.sha256 WHERE x.id=%s", (d,))
            pdf = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
            out = []
            for p, bid, n in sorted(hits):
                # The locator comes from law body text only. A footnote or other apparatus line can be located at
                # record time and then match nothing at replay, because the segmenter has moved it out of the
                # provision text first (18 Nov 2026: 6 AJK laws, "curation patch ... matched 0 blocks").
                cands = sorted({ln.strip() for b, t in by_page[p] if b != bid and b in in_law
                                for ln in t.split("\n") if len(ln.strip()) >= 12}, key=len, reverse=True)
                loc = next((ln for ln in cands if sum(t.count(ln) for _b, t in by_page[p]) == 1
                            and sum(ln.casefold() in t.casefold() for _b, t in by_page[p]) == 1
                            and (p, ln) not in used), None)
                if loc is None:
                    totals["skipped: no locator"] += 1
                    continue
                render = f"{REL}/doc{d}-p{p}.png"
                if not (ROOT / render).exists():
                    pdf[p - 1].get_pixmap(dpi=60).save(ROOT / render)
                out.append({"document_id": d, "page_no": p, "source_apparatus_blocks": [bid],
                            "match_text": loc, "before_text": loc, "after_text": loc,
                            "defect": "the page's printed number (folio) was read into a provision's text",
                            "fixes": "rule reviewed_apparatus_block: the folio block is set aside; no law text changes",
                            "observed": f"Page {p} prints its folio '{n}' alone at its head or foot (block {bid}); the "
                                        f"document's folios run at page + {off} on {count} pages",
                            "render": render,
                            "render_sha256": hashlib.sha256((ROOT / render).read_bytes()).hexdigest()})
                totals["folios set aside"] += 1
            if out:
                (out_dir / f"patch-{d}f.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                          encoding="utf-8")
                totals["documents"] += 1
    print(json.dumps(dict(totals)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
