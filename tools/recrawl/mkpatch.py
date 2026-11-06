"""Build curation-patch files from compact lines (read-only on the database).

    python tools/recrawl/mkpatch.py LINES SUFFIX
Lines ('|'-separated):
  NC|doc|page|block[,block]|defect|observed                 reviewed_no_cut_block
  AP|doc|page|block[,block]|defect|observed                 source_apparatus_blocks
  TR|doc|page|block[,block]|defect|observed                 table rows (+ no_cut)
  MR|doc|page|block|before|after|defect|observed            misread number: before -> after in the block
Writes .artifacts/recrawl-queue/patches/patch-DOC<SUFFIX>.json (one per doc) and prints the docs."""
import json, sys, collections
from pathlib import Path
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.storage import legal_write
out = collections.defaultdict(list); cache = {}
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if not line.strip() or line.startswith("#"):
        continue
    f = line.split("|")
    kind, doc, page = f[0], int(f[1]), int(f[2])
    if kind == "KB":   # KB|doc|page|kind|label|block,block|page2|defect|observed  (owner q2 keep-both)
        k, lab, ids, p2, defect, obs = f[3], f[4], [int(x) for x in f[5].split(",")], int(f[6]), f[7], f[8]
        r = {"document_id": doc, "page_no": page, "source_order_suffix_labels": [{"kind": k, "label": lab, "source_block_ids": ids,
             "owner_decision": {"export": ".artifacts/decision-review/exports/policy-application-2026-10-22.json",
                                "document_id": doc, "question_id": "q2"}}],
             "defect": defect, "observed": obs,
             "fixes": f"rule order_suffix_label (owner policy q2 keep-both): both keep the printed number {lab}; the second is cited '{lab} (second)'"}
        if p2 != page:
            r["additional_render"] = f".artifacts/release-work-2026-09-24/claude/renders/doc{doc}-p{p2}.png"
        out[doc].append(r)
        continue
    if kind == "TU":   # TU|doc|page|block|kind|label|as_kind or ''|defect|observed  (reviewed_text_unit)
        e = {"source_block_id": int(f[3]), "kind": f[4], "label": f[5]}
        if f[6]:
            e["as_kind"] = f[6]
        r = {"document_id": doc, "page_no": page, "source_text_units": [e], "defect": f[7], "observed": f[8],
             "fixes": "rule reviewed_text_unit: the printed figure is " + (f"a {f[6]} of the open unit" if f[6] else "text of the open unit") + ", not a " + f[4]}
        out[doc].append(r)
        continue
    if kind == "IN":   # IN|doc|page|block|before|after|printed|defect|observed : the printed number lost by the OCR is restored
        bid, before, after, pn, defect, obs = int(f[3]), f[4], f[5], f[6], f[7], f[8]
        if doc not in cache:
            cache[doc] = legal_write.blocks_for(doc)
        blk = next(b for b in cache[doc] if b["id"] == bid)
        assert blk["text"].count(before) == 1, (doc, bid, before)
        ln = next(l for l in blk["text"].split("\n") if before in l)
        out[doc].append({"document_id": doc, "page_no": page, "match_text": ln, "before_text": before, "after_text": after,
                         "extracted_number": "", "printed_number": pn, "defect": defect,
                         "fixes": f"misread-number reading: the printed number '{pn}' lost from the text layer is restored", "observed": obs})
        continue
    if kind == "MR":
        bid, before, after, defect, obs = int(f[3]), f[4], f[5], f[6], f[7]
        if doc not in cache:
            cache[doc] = legal_write.blocks_for(doc)
        blk = next(b for b in cache[doc] if b["id"] == bid)
        assert blk["text"].count(before) == 1, (doc, bid, before)
        ln = next(l for l in blk["text"].split("\n") if before in l)
        pg = [b for b in cache[doc] if b["page_no"] == page]
        assert sum(ln in b["text"] for b in pg) == 1 and blk["text"].count(ln) == 1, (doc, bid, ln)
        en = before.split()[0]; pn = after.split()[0]
        r = {"document_id": doc, "page_no": page, "match_text": ln, "before_text": before, "after_text": after,
             "extracted_number": en, "printed_number": pn, "defect": defect,
             "fixes": f"misread-number reading: '{before}' -> '{after}'", "observed": obs}
    else:
        ids = [int(x) for x in f[3].split(",")]
        key = {"NC": ["source_no_cut_blocks"], "AP": ["source_apparatus_blocks"],
               "TR": ["source_table_row_blocks", "source_no_cut_blocks"]}[kind]
        fixes = {"NC": "rule reviewed_no_cut_block: the block never opens a unit",
                 "AP": "rule reviewed_apparatus_block: the block is page apparatus, not enacted text",
                 "TR": "rule reviewed_table_row_block: the block is a table row and never opens a unit"}[kind]
        r = {"document_id": doc, "page_no": page, **{k: ids for k in key}, "defect": f[4], "fixes": fixes, "observed": f[5]}
    out[doc].append(r)
for doc, lst in out.items():
    Path(f"/mnt/e/Nizam_e_Qanoon/.artifacts/recrawl-queue/patches/patch-{doc}{sys.argv[2]}.json").write_text(
        json.dumps(lst, ensure_ascii=False, indent=1), encoding="utf-8")
print(" ".join(map(str, out)))
