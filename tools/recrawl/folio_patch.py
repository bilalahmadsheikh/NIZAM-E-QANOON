"""folio_patch.py OUT_DIR [DOC ...] -- page-read patches setting aside printed page numbers read into released provisions.

A block is a page number only when ALL hold (measured 15 Nov 2026: 10,443 such blocks in 1,037 released documents,
10,038 of them in sequence):
  * it is its page's LAST block in reading order and its whole text is 1-4 digits;
  * it starts in the bottom 12% of the page;
  * the number continues the document's page sequence: the page before prints n-1 or the page after prints n+1 the
    same way (a table cell at the foot of a page does neither);
  * it is assigned to an active provision of a released instrument.
One entry per page (rule reviewed_apparatus_block), with a 60-dpi render and an identity locator: the longest line
(>= 12 chars) of the page that occurs in exactly one block and was never recorded as a locator for the document.
A page with no such line is skipped and counted. Read-only on the database; writes OUT_DIR/patch-<doc>p.json."""
import collections, hashlib, json, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect

ROOT = Path("/mnt/e/Nizam_e_Qanoon"); REL = ".artifacts/release-work-2026-09-24/claude/renders/folio"
FIND = """
WITH last AS (
  SELECT DISTINCT ON (t.document_id, t.page_no) t.id, t.document_id, t.page_no, t.text, t.y0, pg.height
    FROM text_block t JOIN page pg ON pg.document_id=t.document_id AND pg.page_no=t.page_no
   WHERE t.document_id IN (SELECT DISTINCT document_id FROM v_release_instrument)
     AND (%(docs)s::int[] IS NULL OR t.document_id = ANY(%(docs)s::int[]))
   ORDER BY t.document_id, t.page_no, t.reading_order DESC),
fol AS (SELECT id, document_id, page_no, btrim(text)::int n FROM last
         WHERE text ~ '^\\s*[0-9]{1,4}\\s*$' AND y0 >= 0.88*height)
SELECT f.document_id, f.page_no, f.id, f.n FROM fol f
 WHERE (EXISTS (SELECT 1 FROM fol g WHERE g.document_id=f.document_id AND g.page_no=f.page_no-1 AND g.n=f.n-1)
        OR EXISTS (SELECT 1 FROM fol g WHERE g.document_id=f.document_id AND g.page_no=f.page_no+1 AND g.n=f.n+1))
   AND EXISTS (SELECT 1 FROM provision_block pb JOIN block_assignment_set s ON s.id=pb.assignment_set_id AND s.is_active
                 JOIN provision p ON p.id=pb.provision_id AND p.is_active
                 JOIN v_release_instrument r ON r.id=p.instrument_id WHERE pb.block_id=f.id)
 ORDER BY 1, 2"""


def main() -> int:
    out_dir = Path(sys.argv[1]); out_dir.mkdir(parents=True, exist_ok=True)
    docs = [int(d) for d in sys.argv[2:]] or None
    (ROOT / REL).mkdir(parents=True, exist_ok=True)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET max_parallel_workers_per_gather = 0")
        cur.execute(FIND, {"docs": docs})
        hits = collections.defaultdict(list)
        for d, p, bid, n in cur.fetchall():
            hits[d].append((p, bid, n))
        totals = collections.Counter()
        for d, rows in hits.items():
            cur.execute("SELECT page_no, id, text FROM text_block WHERE document_id=%s ORDER BY reading_order", (d,))
            by_page = collections.defaultdict(list)
            for p, bid, text in cur.fetchall():
                by_page[p].append((bid, text or ""))
            cur.execute("""SELECT DISTINCT c.match_text FROM segmentation_curation_patch c JOIN source_observation o
                             ON o.id=c.source_observation_id JOIN document x ON x.sha256=o.sha256 WHERE x.id=%s""", (d,))
            used = {r[0] for r in cur.fetchall()}
            cur.execute("SELECT b.object_key FROM document x JOIN blob b ON b.sha256=x.sha256 WHERE x.id=%s", (d,))
            pdf = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
            out = []
            for p, bid, n in rows:
                blocks = by_page[p]
                lines = sorted({ln.strip() for _, t in blocks for ln in t.split("\n") if len(ln.strip()) >= 12},
                               key=len, reverse=True)
                loc = next((ln for ln in lines if sum(ln.casefold() in t.casefold() for _, t in blocks) == 1
                            and sum(t.count(ln) for _, t in blocks) == 1 and ln not in used), None)
                if loc is None:
                    totals["skipped: no locator"] += 1
                    continue
                used.add(loc)
                render = f"{REL}/doc{d}-p{p}.png"
                if not (ROOT / render).exists():
                    pdf[p - 1].get_pixmap(dpi=60).save(ROOT / render)
                out.append({"document_id": d, "page_no": p, "source_apparatus_blocks": [bid],
                            "defect": "the page's printed page number was read into a provision's text",
                            "fixes": "rule reviewed_apparatus_block: the page-number block is set aside; no law text changes",
                            "observed": (f"Page {p} prints its page number '{n}' alone at its foot (block {bid}, the "
                                         f"page's last block), continuing the document's page sequence"),
                            "render": render,
                            "render_sha256": hashlib.sha256((ROOT / render).read_bytes()).hexdigest(),
                            "match_text": loc, "before_text": loc, "after_text": loc})
            if out:
                (out_dir / f"patch-{d}p.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
                totals["documents"] += 1
                totals["pages"] += len(out)
    print(json.dumps(dict(totals)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
