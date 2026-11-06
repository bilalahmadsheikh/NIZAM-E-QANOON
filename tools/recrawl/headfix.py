"""headfix.py DOC OUT_PATCH.json OUT_TRIAL_PREFIX : Gazette running heads ('PART II] THE GAZETTE OF PAKISTAN, EXTRA.,
<date> 425 (n)') read as Part headings (doc 6358 pattern). Writes, read-only on the database:
  * per page, a source_apparatus_blocks record for blocks that are ONLY the running head (and its page number), plus
    the masthead's bare 'PART II' block on page 1 if present;
  * for a block that prints the running head and then law text, a parser-input text patch that drops the head line
    (and a page-number line right after it) and keeps the rest (after_text = the first words kept).
Also writes OUT_TRIAL_PREFIX.over.json / .patches.json for tools/recrawl/trialseg.py (EXTRA_PATCHES)."""
import json, re, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
HEAD = re.compile(r"^PART\s+[IVX]+\]\s*THE GAZETTE[^\n]*\n?(?:[ \t]*[0-9][0-9()A-Za-z \t]{0,20}\n)?")
# doc 8539: the head of an even page prints its page number first ('894 / THE GAZETTE OF PAKISTAN, EXTRA, ... [Part II]'),
# an odd page's last ('Part Il] THE GAZETTE ... / 895'); the OCR reads II as 'Il', 'll', 'il', its bracket as '}' and
# 'Part' as 'Parr', and the page number as 'all', 'gio', 'g22'. A short line before or after the head is its page number.
# doc 8463 (S.R.O. Gazette 2017): 'Part II]' on its own line above the head, a trailing '[Part II' line, the page number
# '1705(12)', and up to two lines of bleed-through specks ('om', 'ed', '_ Z', '.') above. A page-number line never starts
# with '(' -- so a law line '(a)' after the head is never taken.
_PNO = r"(?:[0-9A-Za-z]{1,6}|\d{1,4}\(\S{1,5}\)|[_ Z.]{1,6})"
HEAD2 = re.compile(r"^(?:[ \t]*" + _PNO + r"[ \t]*\n){0,2}"
                   r"(?:[ \t]*\S{0,4}[ \t]*Par[tr]?\s*\[?\s*[IVXLliTUH1]{1,4}\s*[\]})]?\s*)?"
                   r"THE GAZETTE OF PAKISTAN[^\n]*\n?"
                   r"(?:[ \t]*(?:\[\s*Par[tr]\s*[IVXLliTU1]{1,4}\]?|[0-9A-Za-z]{1,4}|\d{1,4}\(\S{1,5}\))[ \t]*(?:\n|$)){0,2}")
doc, out, pre = int(sys.argv[1]), sys.argv[2], sys.argv[3]
rec, ap_by_page, patches = [], {}, []
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT t.id, t.page_no, t.text FROM text_block t JOIN document d ON d.id=t.document_id AND d.is_active
                    WHERE t.document_id=%s ORDER BY t.page_no, t.reading_order""", (doc,))
    rows = cur.fetchall()
for bid, p, text in rows:
    if p == 1 and re.fullmatch(r"\s*PART\s+[IVX]+\s*", text or ""):
        ap_by_page.setdefault(p, []).append(bid); continue
    m = HEAD.match(text or "") or HEAD2.match(text or "")
    if not m:
        continue
    rest = text[m.end():]
    if not rest.strip():
        ap_by_page.setdefault(p, []).append(bid); continue
    lead = rest.lstrip()
    keep = lead[:40]
    before = text[:m.end()] + rest[:len(rest) - len(lead)] + keep
    match = keep if len(keep.strip()) >= 12 else (text[:m.end()] + rest)[:60]
    patches.append({"document_id": doc, "page_no": p, "match_text": match, "before_text": before, "after_text": keep,
                    "defect": "the Gazette running head printed in the same text block as the law text was read as a "
                              "heading opening a phantom Part",
                    "fixes": "parser-input correction: the running head and its page number are page furniture and are "
                             "dropped from the text the parser reads; the law text after them is kept",
                    "observed": f"Page {p} prints the Gazette running head {text[:m.end()].strip()!r} and then "
                                f"{lead[:90]!r}"})
for p, bs in sorted(ap_by_page.items()):
    rec.append({"document_id": doc, "page_no": p, "source_apparatus_blocks": bs,
                "defect": "the Gazette part heading / running head 'PART ... ] THE GAZETTE ...' was read as a Part "
                          "heading, placing the instrument under a phantom Part",
                "fixes": "rule reviewed_apparatus_block: the Gazette part heading and running heads are page furniture, "
                         "not divisions of the instrument",
                "observed": f"Page {p} prints at its top only the Gazette running head (or, on page 1, the Gazette's "
                            f"own part heading)"})
json.dump(patches + rec, open(out, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
json.dump({"source_apparatus_blocks": [b for bs in ap_by_page.values() for b in bs]},
          open(pre + ".over.json", "w"), indent=1)
json.dump([{"id": f"h{i}", "page_no": x["page_no"], "match_text": x["match_text"], "before_text": x["before_text"],
            "after_text": x["after_text"], "evidence": {}} for i, x in enumerate(patches)], open(pre + ".patches.json", "w"))
print(f"doc {doc}: {sum(len(v) for v in ap_by_page.values())} apparatus block(s) on {len(ap_by_page)} page(s), "
      f"{len(patches)} text patch(es)")
