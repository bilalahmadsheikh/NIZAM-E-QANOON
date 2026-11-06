"""sidenote_strip.py DOC CONTENTS_BLOCK_ID... OUT.json : side notes (margin headings) an OCR read into the law text.

A code reprint prints each section's side notes in the margin and lists them again in its contents. The OCR runs the
margin words into the neighbouring line ('... or to appear before Refusal to go before Police Magistrate or Justice of
the Peace ...'). The note texts are taken from the contents blocks named (one per line, the row number dropped), and
every body block is checked:
  * a block that is only a note (with or without its stop) is set aside -- one source_apparatus_blocks record per page;
  * a note printed INSIDE a block (not at its start, where the segmenter already reads it as the heading) becomes a
    parser-input text patch removing it, with up to 25 characters of the law words around it as the locator.
Matching is case-sensitive and only for notes of two or more words, so a law word such as 'discipline' is never
taken. Writes OUT.json for tools/recrawl/patch.sh and prints every change for review; read-only on the database."""
import json, re, sys
from collections import defaultdict
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage import legal_write

# --strict : cut only a note that ends in its own stop or comma with the sentence going on in lower case after it
# ('... within Accidents to be reported, forty-eight hours', '... of such Fares to be prepaid. officer as ...') and
# with a lower-case word or comma before it. Every wrong cut reviewed on 29 Oct lacked that shape ('procure
# Certificates of Competency hereinafter', '16. Notes where legal tender ...'), so strict cuts run unreviewed.
strict = "--strict" in sys.argv
sys.argv = [a for a in sys.argv if a != "--strict"]
doc, contents, out = int(sys.argv[1]), {int(v) for v in sys.argv[2:-1]}, sys.argv[-1]
blocks = legal_write.blocks_for(doc)
notes = set()
for b in blocks:
    if b["id"] in contents:
        for line in (b["text"] or "").split("\n"):
            n = re.sub(r"^\s*\d{1,3}[A-Z]?\.\s*", "", line).strip().rstrip(".").strip()
            if len(n.split()) >= 2 and len(n) >= 8:
                notes.add(n)
# A note the law itself uses as a term is not a note when it appears in the text: s.7's side note 'Financial
# Commissioner' (doc 9695) is printed in the body dozens of times. A margin note is read into the text once or twice;
# a note found in more than two places of the body is skipped and reported, never cut.
body = "\n".join(b["text"] or "" for b in blocks if b["id"] not in contents)
terms = {n for n in notes if len(re.findall(re.escape(n), body)) > 2}
for n in sorted(terms):
    print(f"  TERM (skipped, {len(re.findall(re.escape(n), body))} places): {n!r}")
notes = sorted(set(notes) - terms, key=len, reverse=True)   # longest first: a note may contain a shorter one
apparatus, patches = defaultdict(list), []
REND = ".artifacts/release-work-2026-09-24/claude/renders/doc{}-p{}.png"
for b in blocks:
    if b["id"] in contents:
        continue
    t = b["text"] or ""
    # a block that is itself a contents list (3+ lines 'N. Heading') is no body block (doc 9831 p4: the contents
    # continued in a block no toc entry named; every row would have been cut)
    if len(re.findall(r"(?m)^\s*(?:\d{1,3}[A-Z]?\.|\(\d{1,2}\))\s+[A-Z]", t)) >= 3 and len(t) / max(1, t.count("\n") + 1) < 90:
        continue
    flat = re.sub(r"\s+", " ", t).strip().rstrip(".").strip()
    if flat in notes:
        # a division heading printed as its own block ('II.—The Department of Paper Currency') is listed in the
        # contents too, and is no side note: strict mode never sets one aside
        if not (strict and re.match(r"(?:[IVXLC]{1,6}|PART|CHAPTER|Part|Chapter)\b", flat)):
            apparatus[b["page_no"]].append((b["id"], flat))
        continue
    for n in notes:
        # the note's own stop or comma goes with it ('... and, Local extent, so far as ...' -> '... and, so far as')
        for m in re.finditer(re.escape(n) + r"[.,]?", t):
            i, j = m.start(), m.end()
            if t[:i].strip() == "":
                continue           # leads the block: the segmenter reads it as the section's heading
            if strict and not (t[j - 1] in ".," and re.match(r"\s*[a-z]", t[j:j + 3])
                               and re.search(r"(?:[a-z]|,)\s*$", t[max(0, i - 3):i])):
                continue
            left, right = t[max(0, i - 25):i], t[j:j + 25]
            before = left + t[i:j] + right
            after = left.rstrip() + " " + right.lstrip() if right.strip() else left.rstrip()
            if t.count(before) != 1 or len(before) < 12:
                print(f"  SKIP b{b['id']} p{b['page_no']}: {n!r} (no unique locator)")
                continue
            patches.append({"document_id": doc, "page_no": b["page_no"], "match_text": before.split("\n")[0]
                            if len(before.split("\n")[0]) >= 12 else before,
                            "before_text": before, "after_text": after,
                            "defect": f"the margin side note {n!r} was read into the law text",
                            "fixes": "parser-input correction: the side note (listed in the contents and printed in the "
                                     "margin) is taken out of the sentence it was read into",
                            "observed": f"Page {b['page_no']} prints {n!r} in the margin beside the law words "
                                        f"{left.strip()[-20:]!r} ... {right.strip()[:20]!r}",
                            "render": REND.format(doc, b["page_no"])})
            print(f"  PATCH p{b['page_no']} b{b['id']}: {before!r} -> {after!r}")
recs = patches + [{"document_id": doc, "page_no": p, "source_apparatus_blocks": [i for i, _ in items],
                   "defect": "a margin side note printed as a block of its own was read into the provision before it",
                   "fixes": "rule reviewed_apparatus_block: the side-note block is set aside (the contents give the "
                            "section its heading)",
                   "observed": f"Page {p} prints the side notes " + "; ".join(repr(n) for _, n in items) + " in the margin",
                   "render": REND.format(doc, p)} for p, items in sorted(apparatus.items())]
for p, items in sorted(apparatus.items()):
    print(f"  APPARATUS p{p}: " + "; ".join(f"b{i} {n!r}" for i, n in items))
json.dump(recs, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(patches), "text patches;", sum(len(v) for v in apparatus.values()), "note blocks set aside;", len(notes), "notes")
