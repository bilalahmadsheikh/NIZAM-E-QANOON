"""Fill render, sha256 and a safe identity locator into structural readings, in place (read-only on the database).

    python tools/recrawl/fill_patch.py PATCH.json
For each reading whose before_text == after_text (or which has none): the locator is the longest single line
(>= 12 chars) of the first named block on its page that occurs in exactly one block of that page."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage import legal_write
ROOT = Path("/mnt/e/Nizam_e_Qanoon"); REL = ".artifacts/release-work-2026-09-24/claude/renders"
p = Path(sys.argv[1]); lst = json.loads(p.read_text(encoding="utf-8"))
cache = {}; used = {}
for r in lst:
    doc, page = r["document_id"], r["page_no"]
    r["render"] = r.get("render") or f"{REL}/doc{doc}-p{page}.png"
    r["render_sha256"] = hashlib.sha256((ROOT / r["render"]).read_bytes()).hexdigest()
    if isinstance(r.get("additional_render"), str):
        r["additional_render_sha256"] = hashlib.sha256((ROOT / r["additional_render"]).read_bytes()).hexdigest()
    if r.get("match_text") or (r.get("before_text") and r["before_text"] != r.get("after_text")):
        continue
    if doc not in cache:
        cache[doc] = legal_write.blocks_for(doc)
        from nizam.storage.db import connect
        with connect() as conn, conn.cursor() as cur:   # locators already recorded (retired too) are refused as identical
            cur.execute("SELECT DISTINCT p.match_text FROM segmentation_curation_patch p JOIN source_observation o "
                        "ON o.id=p.source_observation_id JOIN document d ON d.sha256=o.sha256 WHERE d.id=%s", (doc,))
            used[doc] = {r[0] for r in cur.fetchall()}
    blocks = [b for b in cache[doc] if b["page_no"] == page]
    ids = [i for k, v in r.items() if k.startswith("source_") and isinstance(v, list) for i in v if isinstance(i, int)]
    ids += [e["source_block_id"] for k, v in r.items() if k.startswith("source_") and isinstance(v, list)
            for e in v if isinstance(e, dict) and isinstance(e.get("source_block_id"), int)]
    ids += [b for k, v in r.items() if k.startswith("source_") and isinstance(v, list)
            for e in v if isinstance(e, dict) for b in (e.get("source_block_ids") or []) if isinstance(b, int)]
    named = [b for b in blocks if b["id"] in ids] or blocks
    match = None
    pos = [i for i, b in enumerate(blocks) if b in named] or [0]
    rest = sorted((b for b in blocks if b not in named), key=lambda b: min(abs(blocks.index(b) - i) for i in pos))
    for first in named + rest:
        cands = sorted({ln.strip() for ln in first["text"].split("\n") if len(ln.strip()) >= 12}, key=len, reverse=True)
        match = next((c for c in cands if sum(c.casefold() in b["text"].casefold() for b in blocks) == 1
                      and first["text"].count(c) == 1 and c not in used.get(doc, ())), None)
        if match:
            break
    if not match:
        sys.exit(f"doc {doc} p{page}: no unique locator line")
    r["match_text"] = r["before_text"] = r["after_text"] = match
    print(f"doc {doc} p{page}: locator {match!r}")
p.write_text(json.dumps(lst, ensure_ascii=False, indent=1), encoding="utf-8")
