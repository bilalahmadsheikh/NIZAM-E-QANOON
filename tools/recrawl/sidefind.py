"""sidefind.py TRANSCRIPTION.txt CONTENTS_PAGES : side notes a split OCR reading left inside the text (read-only).

sidestrip.py removes a contents heading only where it occurs whole; a note the OCR interleaved line by line with the
text ('Tenants may apply for lease, who is in occupation abatement of rent on of any land', doc 9819) stays. For each
body paragraph, each contents heading of 2+ words whose words occur in order within the paragraph's first 500
characters, with at least two runs of 2+ consecutive heading words, is printed with the paragraph's head, for a reader
to mend against the page. Headings are those of the section the paragraph opens and the next one."""
import re, sys
path, (lo, hi) = sys.argv[1], map(int, sys.argv[2].split("-"))
src = open(path, encoding="utf-8").read()
parts = re.split(r"(?m)^(=== p\d+[ \t]*\n)", src)
heads = {}
for k in range(1, len(parts), 2):
    p = int(re.search(r"\d+", parts[k]).group())
    if lo <= p <= hi:
        for m in re.finditer(r"(?m)^(?:@\d+ )?(\d+[A-Z]?)\. (.+)$", parts[k + 1]):
            heads.setdefault(m.group(1), m.group(2).strip())
W = re.compile(r"[A-Za-z0-9\"']+")
for k in range(1, len(parts), 2):
    p = int(re.search(r"\d+", parts[k]).group())
    if lo <= p <= hi:
        continue
    for para in parts[k + 1].split("\n\n"):
        m = re.match(r"(?:@(\d+) )?(\d+)\. ", para)
        if not m:
            continue
        sec = m.group(2)
        body = para[m.end(0) if not m.group(1) else 0:][:500]
        toks = [t.casefold() for t in W.findall(body)]
        for lab in (sec, str(int(sec) + 1)):
            h = heads.get(lab)
            if not h:
                continue
            hw = [t.casefold() for t in W.findall(h)]
            if len(hw) < 2:
                continue
            # greedy in-order match; count adjacent pairs of heading words found adjacent in the paragraph
            at, pos = 0, []
            for i, t in enumerate(toks):
                if at < len(hw) and t == hw[at]:
                    pos.append(i); at += 1
            if at < len(hw):
                continue
            runs = sum(1 for a, b in zip(pos, pos[1:]) if b == a + 1)
            if runs >= 2 or len(hw) == 2 and runs == 1:
                print(f"p{p} s.{sec} [{lab}: {h}]\n    {para[:330]!r}")
                break
