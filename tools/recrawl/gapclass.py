"""Classify pending contents gaps of held documents (read-only). gapclass.py OUT.jsonl

Per gap: doc, label, heading, source block/page, block text, the doc's contents-page range (pages holding linked
toc entries), whether the gap's source page is a body page (holds a provision first block), and a class:
  year        label is a 4-digit year 1800-2099 (running head '1898 ] Act ...')
  pageno      heading ends in a bare number and the label <= 3 digits and the block also holds 'Gazette'/']'/'['
  body_page   the row's source page is outside the contents pages and holds provisions (a body line read as a row)
  real        anything else (a genuine promised unit not linked)"""
import json, re, sys, collections
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
with connect() as conn, conn.cursor() as cur:
    cur.execute(r"""
      SELECT g.document_id, g.toc_entry_id, g.printed_label, coalesce(g.printed_heading,''), g.source_block_id, g.source_page,
             coalesce(left(regexp_replace(t.text,'\s+',' ','g'),160),''),
             (SELECT array_agg(DISTINCT e.source_page) FROM instrument_toc_entry e WHERE e.instrument_id=g.instrument_id),
             EXISTS (SELECT 1 FROM provision p JOIN text_block b ON b.id=p.first_block
                      WHERE p.instrument_id=g.instrument_id AND p.is_active AND b.page_no=g.source_page
                        AND p.kind::text IN ('section','article','rule','regulation'))
        FROM v_toc_gap_pending g LEFT JOIN text_block t ON t.id=g.source_block_id
       WHERE NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=g.instrument_id)""")
    rows = cur.fetchall()
cnt, out = collections.Counter(), []
for doc, eid, lab, head, bid, page, text, tpages, bodyp in rows:
    lab = lab or ""
    if re.fullmatch(r"(18|19|20)\d\d", lab.strip()):
        c = "year"
    elif eid is None:
        c = "run_only"
    elif re.search(r"\d+\s*$", head) and re.search(r"gazette|\]|\[", text, re.I) and len(lab) <= 3:
        c = "pageno"
    elif bodyp and tpages and page is not None and page > max(p for p in tpages if p is not None) - 0:
        c = "body_page"
    else:
        c = "real"
    cnt[c] += 1
    out.append({"doc": doc, "entry": eid, "label": lab, "heading": head[:90], "block": bid, "page": page, "text": text,
                "toc_pages": sorted(p for p in (tpages or []) if p is not None), "cls": c})
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    for x in out:
        fh.write(json.dumps(x, ensure_ascii=False) + "\n")
print(len(out), "gaps", dict(cnt), len({x['doc'] for x in out}), "docs")
by = collections.Counter(x["doc"] for x in out)
print("docs by gap count:", sorted(by.values())[:40])
