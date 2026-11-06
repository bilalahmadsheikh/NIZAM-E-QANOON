"""sweep.py DOC SPEC.json : a blockfix spec setting aside the blocks of DOC that are unmistakably page apparatus
(read-only on the DB) -- for released OCR revisions whose provisions carry them (leakscan.py 'head'/'note'):

  head  a block of 120 characters or less holding a running head: 'THE GAZETTE OF PAKISTAN, EXTRA., MAY 2, 2017 [PART',
        'KHYBER PAKHTUNKHWA GOVERNMENT GAZETTE ...', '16 | Page', '1972 : Act XXIX] Peoples' Finance Corporation 81'
  note  a block opening as an amendment note: a note number (or OCR'd mark) then Subs./Ins./Inserted/Added/Omitted/
        Re-numbered/Replaced/Relettered/Substituted/Rep./Proviso added/For Statement of Objects ...

A block already set aside by an active patch is left out. Prints what it takes, page by page, for the record."""
import json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect

HEAD = re.compile(r"[GC]AZETTE|^\s*\d{1,4}\s*\|\s*[Pp]age\b|\b1[6-9]\d\d\s*[:;]\s*(?:Act|Ord|Sind|P\.\s*O|Reg)\.?\s*[IVXLC\d]+\s*\]"
                  r"|\[\s*1[6-9]\d\d\s*[:;]\s*(?:Act|Ord|Sind|P\.\s*O|Reg)\.?\s*[IVXLC\d]+")
# no bracket after the number: '30. [Omitted]' is a section stub, not a note -- and a note names its authority
NOTE = re.compile(r"^\s*(?:\d{1,2}|[*†‡§¶'‘’°®?>])\s*\.?\s*(?:Subs?\.|Sub\.\s*by|Ins\.|Inserted|Added|Omitted|"
                  r"Re-?numbered|Replaced|Relettered|Substituted|Rep\.|Repealed\s+by|Proviso\s+added|"
                  r"For\s+Statement\s+of\s+Objects|Came\s+into\s+force|Since\s+repealed)\b"
                  r"(?=.{0,160}\b(?:by|vide|ibid|for\s+the|see)\b)", re.I | re.S)
doc, out = int(sys.argv[1]), sys.argv[2]
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT id, page_no, text FROM text_block WHERE document_id=%s ORDER BY page_no, block_no", (doc,))
    rows = cur.fetchall()
    cur.execute("""SELECT DISTINCT jsonb_array_elements_text(evidence->'structural_overrides'->'source_apparatus_blocks')::bigint
                     FROM segmentation_curation_patch WHERE retired_at IS NULL
                      AND evidence->'structural_overrides' ? 'source_apparatus_blocks'
                      AND source_observation_id IN (SELECT source_observation_id FROM instrument
                                                     WHERE document_id=%s AND is_active AND duplicate_of IS NULL)""", (doc,))
    done = {r[0] for r in cur.fetchall()}
    # only a block whose words are inside a provision's text has leaked; a note the segmenter already took as a
    # footnote is left alone
    cur.execute("""SELECT string_agg(v.text_en, ' ') FROM instrument i JOIN provision p ON p.instrument_id=i.id AND p.is_active
                     JOIN provision_version v ON v.provision_id=p.id
                    WHERE i.document_id=%s AND i.is_active AND i.duplicate_of IS NULL""", (doc,))
    body = re.sub(r"\s+", " ", cur.fetchone()[0] or "")
pages = {}
for i, p, t in rows:
    flat = re.sub(r"\s+", " ", t or "").strip()
    if i in done or not flat:
        continue
    # a head block is the head and nothing else: three or more lower-case words mean law text shares the block
    # ('THE GAZETTE OF PAKISTAN ... 1297 / 7. Notwithstanding anything contained in' -- doc 9749 p3, 29 Oct)
    lower = len(re.findall(r"(?<![A-Za-z])[a-z][a-z'’-]+", flat))
    kind = ("head" if len(flat) <= 120 and HEAD.search(flat) and lower <= 2
            else "note" if NOTE.match(flat) else None)
    if kind and flat[:40] in body:
        pg = pages.setdefault(str(p), {"set_aside": [], "seen": []})
        pg["set_aside"].append(i)
        pg["seen"].append(f"{kind}: '{flat[:110]}'")
for p, pg in pages.items():
    pg["observed"] = "outside the text column: " + "; ".join(pg.pop("seen"))
    pg["defect"] = "the page's running head or amendment notes were read into the provisions' text"
json.dump({"document_id": doc, "pages": pages}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"doc {doc}: {sum(len(v['set_aside']) for v in pages.values())} blocks on {len(pages)} pages; {len(done)} set aside before")
