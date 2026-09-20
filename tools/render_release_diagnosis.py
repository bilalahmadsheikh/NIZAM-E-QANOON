"""Render selected snapshot source pages using the project's evidence renderer."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ap = argparse.ArgumentParser()
ap.add_argument("snapshot", type=Path)
ap.add_argument("pages", nargs="+", help="document:page,page")
args = ap.parse_args()
instruments = json.loads((args.snapshot / "instruments.json").read_text())
lookup = {i["document_id"]: i for i in instruments}
out = args.snapshot / "renders"
out.mkdir(exist_ok=True)
manifest_path = out / "manifest.json"
manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
for request in args.pages:
    doc, pages = request.split(":")
    inst = lookup[int(doc)]
    pdf = Path("/mnt/e/nizam-data") / inst["object_key"]
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != inst["sha256"].strip():
        raise ValueError(f"Source hash mismatch: {doc}")
    for page in pages.split(","):
        target = out / f"doc-{doc}-page-{page}.png"
        subprocess.run([sys.executable, "tools/render_pdf_page.py", str(pdf), page,
                        str(target), "--dpi", "135"], check=True)
        manifest[f"{doc}:{page}"] = dict(document_id=int(doc), page=int(page),
            pdf_sha256=inst["sha256"], artifact=str(target),
            render_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
manifest_path.write_text(json.dumps(manifest, indent=2))
