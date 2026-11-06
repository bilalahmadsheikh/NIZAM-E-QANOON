"""segtry.py DOC LABEL... -- 'BLOCK|OLD|NEW' ... : segment the document in memory as the worker would (active patches,
reviewed overrides, pinned profile), optionally after replacing OLD with NEW in a block's patched text, and print the
kind and path of every provision with one of the LABELs (read-only; nothing is written)."""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage import legal_write
from nizam.corpus import segment as S
from nizam.workers.segment import reviewed_structural_overrides
from nizam.storage.db import connect
args = sys.argv[1:]
cut = args.index("--") if "--" in args else len(args)
doc, labels, edits = int(args[0]), set(args[1:cut]), args[cut + 1:]
with connect() as c, c.cursor() as cur:
    cur.execute("SELECT source_observation_id FROM instrument WHERE document_id=%s AND is_active LIMIT 1", (doc,))
    obs = cur.fetchone()[0]
blocks = legal_write.blocks_for(doc)
patches = legal_write.segmentation_patches_for(obs)
import os
if os.environ.get("SKIP"):   # SKIP=match-text-prefix,... : leave those active records out, to test retiring them
    patches = [x for x in patches if not any(x["match_text"].startswith(k) for k in os.environ["SKIP"].split(","))]
res = legal_write.structural_resolutions_for(doc)
ov = reviewed_structural_overrides(res, patches) or {}
if os.environ.get("OVER"):   # OVER='{"key": [...]}' : reviewed overrides to try, merged in
    import json as _j
    for _k, _v in _j.loads(os.environ["OVER"]).items():
        ov.setdefault(_k, []).extend(_v) if isinstance(_v, list) else ov.__setitem__(_k, _v)
patched, _n = S._apply_curation_patches(blocks, patches)
for e in edits:
    bid, old, new = e.split("|", 2)
    for b in patched:
        if b.get("id") == int(bid):
            assert old in b["text"], (bid, old)
            b["text"] = b["text"].replace(old, new, 1)
seg = S.segment(patched, curation_patches=None, toc_dispositions=legal_write.toc_dispositions_for(obs),
                structural_resolutions=res, structural_overrides=ov or None,
                profile=os.environ.get("PROFILE") or legal_write.segmentation_profile_for(obs))
def walk(nodes, path=""):
    for n in nodes:
        p = f"{path}/{n.kind}:{n.label}"
        if n.label in labels:
            print(p, "|", (n.text or "")[:80].replace("\n", " "))
        walk(n.children, p)
walk(seg.root.children if hasattr(seg.root, "children") else seg.root)
print("missing", seg.missing[:20], "toc rows", len(seg.toc), "body page", seg.body_starts_page)
for n in seg.root.children if hasattr(seg.root, "children") else seg.root:
    if n.kind in ("schedule", "preamble", "part", "chapter"):
        print(" top", n.kind, n.label, (n.text or "")[:60].replace(chr(10), " "))
for d in getattr(seg, "repeated_label_decisions", []) or []:
    if not d.get("settled_by_review"):
        c, k = d["candidate"], d["canonical"]
        print(" S7", d["printed_label"], "kept", k.kind, k.first_page, (k.text or "")[:60].replace(chr(10), " "),
              "| demoted", c.kind, c.first_page, (c.text or "")[:60].replace(chr(10), " "))
