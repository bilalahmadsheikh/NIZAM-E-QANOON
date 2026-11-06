"""subfix.py DOC OUT.json < LINES : substring text corrections from a page read, one per line (read-only on the DB).
Line: PAGE@@MATCH@@REPLACEMENT@@WHAT THE PAGE PRINTS   ('\\n' in MATCH or REPLACEMENT is a line break)
The match must be 12+ characters, occur once in the document and never have been used as a locator before (the
recorder treats a reused locator as an identical patch). Every record carries the page's render."""
import hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
doc, out = int(sys.argv[1]), sys.argv[2]
sys.stdin.reconfigure(encoding="utf-8")   # a Windows interpreter reads a pipe as cp1252 otherwise
recs = []
for line in sys.stdin.read().splitlines():
    if not line.strip() or line.startswith("#"):
        continue
    page, match, new, obs = line.split("@@", 3)
    match, new = match.replace("\\n", "\n"), new.replace("\\n", "\n")
    assert len(match) >= 12, match
    render = f".artifacts/release-work-2026-09-24/claude/renders/doc{doc}-p{page}.png"
    recs.append({"document_id": doc, "page_no": int(page), "match_text": match, "before_text": match, "after_text": new,
                 "defect": f"OCR misread the line: '{match}'".replace("\n", " "),
                 "fixes": "text correction to the printed characters (amendment-note markers, ordinals, stray marks)",
                 "observed": f"Page {page} prints {obs}", "render": render,
                 "render_sha256": hashlib.sha256((ROOT / render).read_bytes()).hexdigest()})
json.dump(recs, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(recs), "records")
