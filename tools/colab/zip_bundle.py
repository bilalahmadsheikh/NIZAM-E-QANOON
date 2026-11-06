"""zip_bundle.py ROOT : one stored (uncompressed -- PDFs are already compressed) zip per priority folder of
ROOT/in, written as ROOT/in-<folder>.zip"""
import sys, zipfile
from pathlib import Path
root = Path(sys.argv[1])
for k in ("1-pages", "2-small", "3-holes", "4-large"):
    z = root / f"in-{k}.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as zf:
        for f in sorted((root / "in" / k).glob("*.pdf")):
            zf.write(f, f.name)
    print(z.name, round(z.stat().st_size / 2**20), "MB")
