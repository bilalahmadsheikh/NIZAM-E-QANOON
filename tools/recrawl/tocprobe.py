"""tocprobe.py DOC : how the segmenter reads a document's contents (read-only): every section-shaped piece of the
patched, override-applied blocks with page and number, then the contents list it kept and where the body starts."""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage import legal_write
from nizam.corpus import segment as S
from nizam.workers.segment import reviewed_structural_overrides
from nizam.storage.db import connect
doc = int(sys.argv[1])
with connect() as c, c.cursor() as cur:
    cur.execute("SELECT source_observation_id FROM instrument WHERE document_id=%s AND is_active LIMIT 1", (doc,))
    obs = cur.fetchone()[0]
blocks = legal_write.blocks_for(doc)
patches = legal_write.segmentation_patches_for(obs)
res = legal_write.structural_resolutions_for(doc)
ov = reviewed_structural_overrides(res, patches) or {}
aside = set()
for k, v in ov.items():
    if "apparatus" in k and isinstance(v, (list, set, tuple)):
        aside |= {x if isinstance(x, int) else x.get("source_block_id") for x in v}
print("override keys:", sorted(ov), "set aside:", len(aside))
patched, _n = S._apply_curation_patches(blocks, patches)
kept = [b for b in patched if b.get("id") not in aside]
for i, num, lbl, h in S._section_numbers(kept)[:int(sys.argv[2]) if len(sys.argv) > 2 else 80]:
    print(i, kept[i].get("page_no"), lbl, (h or "")[:50])
toc, boundary, ok = S.parse_contents(kept)
print("contents rows", len(toc), "boundary block", boundary, "page", kept[boundary].get("page_no") if boundary < len(kept) else None, ok)

# the full segmenter, as the worker calls it, and (argv[3:]) in-memory variants: 'drop:<page>:<text>' removes a line
# from that page's replacement text before segmenting
def run(bl):
    seg = S.segment(bl, curation_patches=None, toc_dispositions=legal_write.toc_dispositions_for(obs),
                    structural_resolutions=res, structural_overrides=ov or None,
                    profile=legal_write.segmentation_profile_for(obs))
    return seg
import copy
seg = run(patched)
print("segment(): contents rows", len(seg.toc), "body page", seg.body_starts_page, "missing", seg.missing[:12])
for v in sys.argv[3:]:
    _k, page, text = v.split(":", 2)
    bl = copy.deepcopy(patched)
    for b in bl:
        if b.get("page_no") == int(page) and b.get("id") not in aside and text in b["text"]:
            b["text"] = b["text"].replace(text + "\n", "", 1)
    seg = run(bl)
    print(v, "-> contents rows", len(seg.toc), "body page", seg.body_starts_page, "missing", seg.missing[:12])
if "--trace" in sys.argv[2:3] or True:
    _orig = S.parse_contents
    def traced(bl):
        r = _orig(bl)
        b = r[1]
        print("  parse_contents over", len(bl), "blocks ->", len(r[0]), "rows, boundary", b,
              "page", bl[b].get("page_no") if b < len(bl) else None, repr((bl[b]["text"] if b < len(bl) else "")[:60]), r[2])
        return r
    S.parse_contents = traced
    seg = run(patched)
