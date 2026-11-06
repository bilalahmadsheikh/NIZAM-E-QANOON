"""schedfind.py OUT.json [DOC ...] : unopened schedule headings in held documents with pending S7 units (read-only).

A heading is a whole printed line: 'THE FIRST SCHEDULE' / 'FIRST SCHEDULE' (ordinal, anywhere in a block -- the
segmenter cuts there) or a block's FIRST line starting 'SCHEDULE' (<= 50 chars). Lines on contents pages (pages holding
toc entries) are skipped, as are headings at or before the first pending unit's kept page when that unit is section 1-3
(a heading before the body is a contents/arrangement line). Proposes one source_division_unit_openers entry per
heading whose document has a pending S7 unit on or after the heading's page and no schedule node there yet."""
import json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
ORD = r"(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|ELEVENTH|TWELFTH)"
ORDRX = re.compile(r"(?im)^[^\w\n]{0,3}((?:THE\s+)?" + ORD + r"\s*/?\s*SCHEDULE)\b[^\n]{0,60}$")
KWRX = re.compile(r"(?i)^[^\w\n]{0,3}(SCHEDULE\b[^\n]{0,44})$")
docs = set(map(int, sys.argv[2:]))
out = []
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT DISTINCT c.document_id FROM v_structural_adjudication_pending p JOIN segmentation_structural_candidate c ON c.id=p.id
                    WHERE NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=c.instrument_id)""")
    held = [r[0] for r in cur.fetchall() if not docs or r[0] in docs]
    for d in held:
        cur.execute("""SELECT min(least(c.source_page, c.canonical_source_page)), max(greatest(c.source_page, c.canonical_source_page))
                         FROM v_structural_adjudication_pending p JOIN segmentation_structural_candidate c ON c.id=p.id WHERE c.document_id=%s""", (d,))
        pmin, pmax = cur.fetchone()
        cur.execute("""SELECT DISTINCT e.source_page FROM instrument_toc_entry e JOIN instrument i ON i.id=e.instrument_id
                        WHERE i.document_id=%s AND i.is_active""", (d,))
        tocp = {r[0] for r in cur.fetchall()}
        cur.execute("""SELECT count(*) FROM provision pr JOIN instrument i ON i.id=pr.instrument_id
                        WHERE i.document_id=%s AND i.is_active AND pr.is_active AND pr.kind::text='schedule'""", (d,))
        has_sched = cur.fetchone()[0]
        cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s ORDER BY page_no, reading_order", (d,))
        for bid, page, text in cur.fetchall():
            if page in tocp or page is None or page > (pmax or 0) or page < 2:
                continue
            hits = []
            for m in ORDRX.finditer(text):
                hits.append((m.group(1), f"{m.group(2).upper()} SCHEDULE"))
            first = text.strip().split("\n", 1)[0].strip()
            mk = KWRX.match(first)
            if mk and not hits and len(mk.group(1).strip()) >= 8:
                hits.append((mk.group(1).strip(), re.sub(r"\s+", " ", mk.group(1).strip())))
            for pref, lab in hits:
                if text.count(pref) != 1:
                    continue
                out.append({"doc": d, "page": page, "block": bid, "prefix": pref, "label": lab, "has_schedule_nodes": has_sched,
                            "pending_pages": [pmin, pmax]})
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(out), "headings in", len({x["doc"] for x in out}), "documents")
for x in out[:80]:
    print(x["doc"], f"p{x['page']}", x["block"], repr(x["prefix"]), "->", repr(x["label"]), "sched_nodes", x["has_schedule_nodes"], "pend", x["pending_pages"])
