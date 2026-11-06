"""trialseg.py DOC [EXTRA.json] [KINDS] : segment a document in memory with its recorded inputs plus extra reviewed
overrides (a JSON object of override lists), and print the tree (read-only; nothing is written)."""
import json, sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.corpus import segment as S
from nizam.storage import legal_write
from nizam.storage.db import connect
from nizam.workers.segment import reviewed_structural_overrides
doc = int(sys.argv[1]); extra = json.load(open(sys.argv[2])) if len(sys.argv) > 2 and sys.argv[2] != "-" else {}
kinds = set((sys.argv[3] if len(sys.argv) > 3 else "part,chapter,section,schedule,appendix").split(","))
with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT source_observation_id FROM instrument WHERE document_id=%s AND is_active LIMIT 1", (doc,))
    obs = cur.fetchone()[0]
import os
prof = os.environ.get("PROFILE") or legal_write.segmentation_profile_for(obs)
blocks = legal_write.blocks_for(doc)
patches = legal_write.segmentation_patches_for(obs)
if os.environ.get("EXTRA_PATCHES"):
    patches = patches + json.load(open(os.environ["EXTRA_PATCHES"]))
tocd = legal_write.toc_dispositions_for(obs)
res = legal_write.structural_resolutions_for(doc)
over = reviewed_structural_overrides(res, patches) or {}
for k, v in extra.items():
    over[k] = v if (os.environ.get("REPLACE") or not isinstance(v, list)) else list(over.get(k) or []) + v
seg = S.segment(blocks, curation_patches=patches, toc_dispositions=tocd, structural_resolutions=res,
                structural_overrides=over or None, **({} if prof == "default" else {"profile": prof}))
def walk(n, path):
    for c in n.children:
        p = f"{path}.{c.kind[:2]}{c.label}" if path else f"{c.kind[:2]}{c.label}"
        if c.kind in kinds:
            print(f"p{c.first_page} {p} b{c.first_block} [{len(c.text or '')}c] {(c.heading or '')[:30]!r} :: {(c.text or '')[:50]!r}")
        walk(c, p)
print("profile", prof, "| toc_found", seg.toc_found, "matched", seg.matched, "missing", seg.missing[:12], "demoted", seg.repeated_labels_demoted)
walk(seg.root, "")
