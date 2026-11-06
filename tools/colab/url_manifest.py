"""url_manifest.py OUT.json : for every item of the Colab input bundle, the official URL its PDF was landed from and
its SHA-256 (so the Colab runtime can fetch it itself and verify it), plus the pages to read. Read-only.
Items: whole documents ({doc, sha256, urls, pages: null}) and page reads ({doc, sha256, urls, pages: [n], rotate})."""
import json, re, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage.db import connect
B = Path("/mnt/e/nizam-data/ocr/colab/in")
man = json.loads((B / "manifest.json").read_text())
items = []
for stem in man["1-pages"]:
    m = re.fullmatch(r"(\d+)-page(\d+)", stem); items.append(("1-pages", int(m.group(1)), int(m.group(2)), stem))
for k in ("2-small", "3-holes", "4-large"):
    for d in man[k]: items.append((k, int(d), None, d))
for d in (9551, 9495): items.append(("5-extra", d, None, str(d)))
out, miss = [], []
with connect() as conn, conn.cursor() as cur:
    for k, d, p, stem in items:
        cur.execute("""SELECT d.sha256, array_agg(DISTINCT o.canonical_url) FILTER (WHERE o.canonical_url IS NOT NULL)
                         FROM document d LEFT JOIN source_observation o ON o.sha256=d.sha256 AND o.outcome='landed'
                        WHERE d.id=%s GROUP BY d.sha256""", (d,))
        sha, urls = cur.fetchone()
        rec = {"group": k, "stem": stem, "doc": d, "sha256": sha, "urls": urls or [], "page": p, "rotate": stem == "9665-page3"}
        (out if urls else miss).append(rec)
Path(sys.argv[1]).write_text(json.dumps(out, indent=0))
from collections import Counter
print("with url:", Counter(r["group"] for r in out), "| without:", Counter(r["group"] for r in miss))
print("hosts:", Counter(re.sub(r"^https?://([^/]+).*", r"\1", r["urls"][0]) for r in out).most_common(8))
