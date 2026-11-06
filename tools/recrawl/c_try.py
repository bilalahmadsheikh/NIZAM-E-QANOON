"""c_try.py DOC [PATCH.json ...] [--all] : build DOC in memory with its recorded patches plus the readings of the given
patch files (not recorded), and print the section-level tree and the S7 collisions the build would write. Read-only.
--all prints every node (clauses too)."""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
import json
from nizam.storage import legal_write
from nizam.workers import segment as W

args = [a for a in sys.argv[1:] if not a.startswith("--")]
show_all = "--all" in sys.argv
doc = int(args[0])
targets = [t for t in legal_write.documents_needing_segmentation(redo=True, include_review=True) if t[0] == doc]
if not targets:
    sys.exit("no target")
doc_id, sha, obs, source_id, title, year, doc_type, url = targets[0]
blocks = legal_write.blocks_for(doc_id)
as_at = legal_write.observed_on(obs)
patches = legal_write.segmentation_patches_for(obs)
for n, f in enumerate(args[1:]):
    for i, r in enumerate(json.loads(open(f, encoding="utf-8-sig").read())):
        so = {k: v for k, v in r.items() if k.startswith("source_") and k != "source_block_id"}
        ev = {"structural_overrides": so} if so else {}
        ev.update({k: r[k] for k in ("extracted_number", "printed_number") if k in r})
        ev["source_block_id"] = r.get("source_block_id")
        if r.get("exact_block_locator"):
            ev["exact_block_locator"] = True
        if not r.get("match_text"):
            pb = [b for b in blocks if b["page_no"] == r["page_no"]]
            ids = [x for k, v in r.items() if k.startswith("source_") and isinstance(v, list) for x in v if isinstance(x, int)]
            ids += [x.get("source_block_id") for k, v in r.items() if k.startswith("source_") and isinstance(v, list) for x in v if isinstance(x, dict)]
            named = [b for b in pb if b["id"] in ids] or pb
            for first in named + [b for b in pb if b not in named]:
                cands = sorted({ln.strip() for ln in first["text"].split(chr(10)) if len(ln.strip()) >= 12}, key=len, reverse=True)
                m = next((c for c in cands if sum(c.casefold() in b["text"].casefold() for b in pb) == 1 and first["text"].count(c) == 1), None)
                if m:
                    r["match_text"] = r["before_text"] = r["after_text"] = m
                    break
        patches.append({"id": f"try-{n}-{i}", "page_no": r["page_no"], "match_text": r.get("match_text"),
                        "before_text": r.get("before_text"), "after_text": r.get("after_text"), "evidence": ev})
patches.sort(key=lambda p: p["page_no"])
tocd = legal_write.toc_dispositions_for(obs)
res = legal_write.structural_resolutions_for(doc_id)
ov = W.reviewed_structural_overrides(res, patches)
inst, seg = W.build(doc_id, sha, obs, source_id, title, year, url, blocks, as_at, patches,
                    toc_dispositions=tocd, structural_resolutions=res, structural_overrides=ov or None)
keep = ("section", "article", "part", "chapter", "schedule", "rule", "regulation", "order", "paragraph")
for r in inst.provisions:
    p = r["path"].split(".", 3)[-1] if r["path"].count(".") >= 3 else r["path"]
    if show_all or r["kind"] in keep or r["kind"] not in ("clause", "subsection", "item", "subclause"):
        t = " ".join((r["text"] or "").split())
        print(f"p{r['first_page']} {r['kind']:9} {p:30} [{len(r['text'] or '')}c] {(r['heading'] or '')[:30]!r} :: {t[:90]}")
print("--- S7 collisions this build writes:", len(inst.structural_decisions))
by_key = {r["key"]: r for r in inst.provisions}
from nizam.storage.db import connect
with connect() as conn, conn.cursor() as cur:
    cur.execute("""SELECT c.source_block_id, c.canonical_source_block_id, c.printed_label, a.resolution
                     FROM v_active_structural_candidate c JOIN v_structural_adjudication_latest a ON a.candidate_id=c.id
                    WHERE c.document_id=%s""", (doc,))
    prior = {(r[0], r[1], r[2]): r[3] for r in cur.fetchall()}
for d in inst.structural_decisions:
    c, k = by_key[d["candidate_key"]], by_key[d["canonical_key"]]
    pr = prior.get((d["source_block_id"], d["canonical_source_block_id"], d["printed_label"]))
    print(f"  {'[prior '+pr+']' if pr else '[NEW]'} label {d['printed_label']!r}: kept p{k['first_page']} {k['path'].split('.',3)[-1]} | demoted p{c['first_page']} {c['path'].split('.',3)[-1]} :: {' '.join((c['text'] or '').split())[:80]}")
for a in sys.argv[1:]:
    if a.startswith("--role="):
        for bid in a[7:].split(","):
            role, node = seg.block_roles.get(int(bid), (None, None))
            print("role", bid, role, getattr(node, "kind", None), getattr(node, "label", None))
if seg.toc_found:
    un = [e for e in seg.toc_entries if e.get("node") is None]
    print("--- toc entries:", len(seg.toc_entries), "unmatched:", len(un), [(e["label"], (e["heading"] or "")[:30]) for e in un][:30])
