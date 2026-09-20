"""Compare selected single-expression sources without persisting any trees."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from nizam.storage import legal_write
from nizam.corpus.segment import _is_footnote_run
from nizam.workers.segment import build

ap = argparse.ArgumentParser()
ap.add_argument("snapshot", type=Path)
ap.add_argument("documents", type=int, nargs="+")
args = ap.parse_args()
instruments = json.loads((args.snapshot / "instruments.json").read_text())
stored = json.loads((args.snapshot / "provisions.json").read_text())
out = args.snapshot / "dry-runs"
out.mkdir(exist_ok=True)
source_hash = hashlib.sha256(Path("nizam/corpus/segment.py").read_bytes()).hexdigest()
for doc in args.documents:
    rows = [i for i in instruments if i["document_id"] == doc]
    if len(rows) != 1 or rows[0]["active_expressions_in_document"] != 1:
        print(doc, "HELD: multi-expression source")
        continue
    i = rows[0]
    obs = i["source_observation_id"]
    blocks = legal_write.blocks_for(doc)
    patches = legal_write.segmentation_patches_for(obs)
    inst, seg = build(doc, i["sha256"], obs, i["object_key"].split("/")[1],
        i["short_title"], None, i["source_url"], blocks, legal_write.observed_on(obs),
        patches,
        toc_dispositions=legal_write.toc_dispositions_for(obs))
    unlinked = [e for e in inst.toc_entries if e.get("provision_key") is None]
    # Mirror both branches of the pending view BEFORE source adjudications:
    # exact unresolved entry rows plus run-only labels not among those rows.
    run_only = set(seg.missing) - {e["label"] for e in unlinked}
    result = dict(document_id=doc, segment_source_sha256=source_hash,
        stored_pending_toc=i["toc_count"], stored_pending_s7=i["s7_count"],
        stored_sections=sum(p["kind"] in ("section","article") for p in stored if p["instrument_id"] == i["id"]),
        new_sections=sum(p["kind"] in ("section","article") for p in inst.provisions),
        new_unresolved_before_adjudications=len(unlinked)+len(run_only),
        new_collisions_before_adjudications=seg.repeated_labels_demoted,
        missing=seg.missing, toc_entries=inst.toc_entries, provisions=inst.provisions,
        curation_patches=patches,
        split_number_notes=[dict(block_id=b['id'],text=b['text'],
            role=seg.block_roles.get(b['id'], ('missing',None))[0])
            for b in blocks if _is_footnote_run(b['text'],split_numbers_only=True)],
        decisions=inst.structural_decisions)
    (out / f"{doc}.json").write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2))
    print({k:v for k,v in result.items() if k not in ("provisions","decisions","toc_entries","segment_source_sha256","curation_patches","split_number_notes")}, flush=True)
