"""sidestrip.py TRANSCRIPTION.txt CONTENTS_PAGES : remove side notes the OCR ran into the text, using the document's
own contents as the list of side notes (edits the transcription in place; prints every removal).

A margin note in these Acts repeats its section's contents heading ('1. This Act may be called the Pilgrim Ships
Title. Act, 1895.', doc 9842). For every body paragraph that opens 'N.', the heading of N (and of N+1, for a note set
beside the next section's first lines) is removed where it occurs whole, followed by a space, inside the paragraph's
first 400 characters. Only whole headings of 2+ words are removed; a split note is left for the reader, who checks
every page against its render anyway. CONTENTS_PAGES: e.g. '1-2'."""
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
n = 0
for k in range(1, len(parts), 2):
    p = int(re.search(r"\d+", parts[k]).group())
    if lo <= p <= hi:
        continue
    paras = parts[k + 1].split("\n\n")
    for i, para in enumerate(paras):
        body = re.sub(r"^@\d+ ", "", para)
        for m in re.finditer(r"(?m)^(\d+)\. ", body):
            sec = m.group(1)
            for lab in (sec, str(int(sec) + 1)):
                h = heads.get(lab)
                if not h or len(h.split()) < 2:
                    continue
                at = para.find(h + " ", 0, para.find(m.group(0)) + 400 + len(h))
                if at > 0 and at >= para.find(m.group(0)):
                    print(f"p{p} s.{sec}: removed {h!r}   ...{para[max(0, at - 40):at].replace(chr(10), ' ')}|{para[at + len(h) + 1:at + len(h) + 40]}...".replace("\n", " "))
                    para = para[:at] + para[at + len(h) + 1:]
                    n += 1
        paras[i] = para
    parts[k + 1] = "\n\n".join(paras)
open(path, "w", encoding="utf-8").write("".join(parts))
print(f"{n} side notes removed; {len(heads)} contents headings")
