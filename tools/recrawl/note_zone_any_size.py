"""note_zone_any_size.py OUT.json DOC... -- PROPOSALS (for page-read review, never applied unread) of AJK revised-volume
note zones that tools/recrawl/footnote_zone.py cannot take because the notes are not set smaller than the law (doc
10063 prints them at 9.0, 8.0, 6.9 and 11.0 against the law's 9.9) or sit under a rule near the top of a page that
continues the previous page's notes (doc 10685 p3).

Per page: the LOWEST horizontal stroke (<=2pt tall, 5-95% of the page width) with a non-page-number block below it;
the zone is every block whose top is at or below it, except the page number. The zone is proposed only when its first
block opens like a note -- a marker ('1', '2Sub-section', 'A.', '(a)', '*', '[2]'), note words (subs./ins./omitted/
added/Ibid/original), or an opening quote -- or when the previous page proposed a zone (a note runs on). Blocks already
outside every provision are listed but not proposed. Read-only."""
import json, re, sys
from pathlib import Path
import pymupdf
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect

OPENS_NOTE = re.compile(r"^\s*(?:\[?\d{1,2}\]?\s*(?:$|[A-Z]|\n)|[A-H]\s*[.\-]|\(\s*[a-z]{1,3}\s*\)|\(\s*[ivx]{1,5}\s*\)|\*|"
                        r"[\"“]|_{5,})", re.M)
NOTE_WORDS = re.compile(r"\b(?:subs|ins|add|omitted|added|inserted|substituted|ibid|original|amended|reproduced)\b", re.I)
FOLIO = re.compile(r"^\s*\d{1,4}\s*$")


def strokes(page):
    w = page.rect.width
    return sorted({round(d["rect"].y0) for d in page.get_drawings()
                   if d.get("rect") is not None and d["rect"].height <= 2 and 0.05 * w <= d["rect"].width <= 0.95 * w})


def main() -> int:
    out, docs = sys.argv[1], [int(d) for d in sys.argv[2:]]
    props = []
    with connect() as conn, conn.cursor() as cur:
        for doc in docs:
            cur.execute("SELECT b.object_key FROM document d JOIN blob b ON b.sha256=d.sha256 WHERE d.id=%s", (doc,))
            pdf = pymupdf.open(Path("/mnt/e/nizam-data") / cur.fetchone()[0])
            cur.execute("""SELECT t.id, t.page_no, t.y0, t.text,
                                  EXISTS (SELECT 1 FROM provision_block pb JOIN block_assignment_set s ON s.id=pb.assignment_set_id
                                            AND s.is_active JOIN provision p ON p.id=pb.provision_id AND p.is_active
                                           WHERE pb.block_id=t.id)
                             FROM text_block t WHERE t.document_id=%s ORDER BY t.reading_order""", (doc,))
            pages = {}
            for bid, p, y0, text, inside in cur.fetchall():
                pages.setdefault(p, []).append((bid, float(y0), text or "", inside))
            before = False
            for p in sorted(pages):
                blocks = pages[p]
                body = [b for b in blocks if not (b is blocks[-1] and FOLIO.match(b[2]))]
                ys = [y for y in strokes(pdf[p - 1]) if any(b[1] >= y - 2 for b in body)]
                if not ys:
                    before = False
                    continue
                rule = max(ys)
                zone = [b for b in body if b[1] >= rule - 2]
                first = zone[0][2] if zone else ""
                second = zone[1][2] if len(zone) > 1 else ""
                # (tightened after the first review, 15 Nov 2026: '(a)' after a heading underline or a table rule is
                # law) the zone opens with note WORDS, or a bare marker whose next block has them; a zone carried over
                # from the previous page needs its rule in the top third and a quote or lower-case run-on first
                opens = bool(NOTE_WORDS.search(first[:200])
                             or (re.fullmatch(r"\s*\[?\d{1,2}\]?\s*", first) and NOTE_WORDS.search(second[:200])))
                carried = bool(before and rule < pdf[p - 1].rect.height / 3
                               and re.match(r"\s*[\"“‘a-z(]", first))
                if not zone or not (opens or carried):
                    before = False
                    continue
                before = True
                take = [b for b in zone if b[3]]
                if take:
                    props.append({"document_id": doc, "page_no": p, "rule_y": rule, "blocks": [b[0] for b in take],
                                  "texts": [" / ".join(ln.strip() for ln in b[2].split("\n") if ln.strip())[:200]
                                            for b in take],
                                  "already_outside": len(zone) - len(take)})
    Path(out).write_text(json.dumps(props, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(props), "pages proposed,", sum(len(x["blocks"]) for x in props), "blocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
