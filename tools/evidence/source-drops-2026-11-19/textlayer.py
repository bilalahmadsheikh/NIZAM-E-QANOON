"""Text-layer check for PDFs inside a zip: characters on the first 3 pages, read in memory (nothing extracted to disk)."""
import hashlib
import sys
import zipfile

import fitz  # PyMuPDF

z = zipfile.ZipFile(sys.argv[1])
prefix = sys.argv[2] if len(sys.argv) > 2 else ""
seen = set()
for n in z.namelist():
    if not n.lower().endswith(".pdf") or not n.startswith(prefix):
        continue
    b = z.read(n)
    h = hashlib.sha256(b).hexdigest()
    if h in seen:
        continue
    seen.add(h)
    try:
        doc = fitz.open(stream=b, filetype="pdf")
        chars = sum(len(doc[i].get_text()) for i in range(min(3, doc.page_count)))
        print(f"{doc.page_count:4d} pages  {chars:6d} chars/3pp  {'TEXT' if chars > 300 else 'SCAN'}  {n[-90:]}")
    except Exception as e:
        print(f"ERROR {e} {n}")
