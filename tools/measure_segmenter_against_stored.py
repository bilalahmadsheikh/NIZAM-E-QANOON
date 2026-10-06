"""Build instruments with ANY copy of the segmenter and diff them against the
trees the corpus actually STORES. Read-only; nothing is written to PostgreSQL.

Why this and not a segmenter-vs-segmenter diff: on 23 Sep a full replay
withdrew 24 released instruments although the parser fix it shipped measured
"0 S7 added" against the then-current segmenter. The harm was the distance
between the current segmenter and the one that built the stored trees
(docs/RELEASE-ALL-HANDOFF-2026-09-23.md, "a count-only gate passed a release
SWAP"). Only a build compared with what is stored predicts what a replay does.

Each instrument is built exactly as its writer builds it -- the segment
worker's `build()` with the same curation patches, TOC dispositions,
structural resolutions and overrides; multi-expression documents through
tools/materialize_multi_instrument.py's `prepare()` -- and compared on:

  tree  (path, parent path, kind, label, ordinal, first_page, last_page,
         first_block, text, heading) -- the worker's own dry-run identity
  s7    the candidate rows the writer would materialise
  toc   the contents entries and the provision each one links to

RESUMABLE. One JSON line per observation is appended and fsynced to
<out>.jsonl BEFORE the observation id is appended to <out>.done; on restart,
lines whose id is not in the ledger are purged and redone. Rerun the same
command to resume after a rate limit or a crash.

    # every canonical instrument (released and blocked), 3 shards in parallel
    python tools/measure_segmenter_against_stored.py SEGMENTER.py \\
        --shard 0/3 --out .scratch/stored-s0
    # a bounded list, and/or a named reference tree per document
    python tools/measure_segmenter_against_stored.py SEGMENTER.py \\
        --documents 1119,4347 --out .scratch/lost
    python tools/measure_segmenter_against_stored.py SEGMENTER.py \\
        --reference-json .scratch/lost_ids.json --out .scratch/lost-pre

``--reference-json`` maps "document:observation:expression" to
{"pre": <instrument uuid>} and compares against THAT tree (retired or not)
instead of the active one -- how the 24 withdrawn instruments are measured
against their pre-replay release.

    python tools/measure_segmenter_against_stored.py --summarise .scratch/stored-s*.jsonl
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import importlib.util
import json
import os
import pathlib
import sys
import time

MULTI_DOCS = {977, 1106, 3389, 3553, 3696, 3912, 4434, 4452, 3423, 3949, 4440, 4497, 268}
FIELDS = ("path", "parent", "kind", "label", "ordinal", "first_page",
          "last_page", "first_block", "text", "heading")

TREE_SQL = """
SELECT p.path::text, coalesce(parent.path::text,''), p.kind::text, p.label,
       p.ordinal, p.first_page, p.last_page, p.first_block,
       coalesce(v.text_en,v.text_ur,''), coalesce(p.heading,'')
  FROM provision p
  LEFT JOIN provision parent ON parent.id=p.parent_id
  LEFT JOIN LATERAL (
        SELECT text_en,text_ur FROM provision_version pv
         WHERE pv.provision_id=p.id
         ORDER BY lower(pv.validity) DESC,pv.created_at DESC LIMIT 1) v ON true
 WHERE p.instrument_id=%s
 ORDER BY p.ordinal"""

S7_SQL = """
SELECT c.printed_label, c.source_block_id, c.canonical_source_block_id,
       c.original_kind::text, cp.path::text, kp.path::text
  FROM segmentation_structural_candidate c
  JOIN provision cp ON cp.id=c.candidate_provision_id
  JOIN provision kp ON kp.id=c.canonical_provision_id
 WHERE c.instrument_id=%s"""

TOC_SQL = """
SELECT t.ordinal, t.printed_label, coalesce(t.printed_heading,''), t.entry_kind,
       p.path::text, t.match_method
  FROM instrument_toc_entry t LEFT JOIN provision p ON p.id=t.provision_id
 WHERE t.instrument_id=%s ORDER BY t.ordinal"""

TARGETS_SQL = """
SELECT i.document_id, i.source_observation_id, i.expression_ordinal, i.id::text,
       EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id),
       d.sha256, o.source_id, o.source_metadata->>'title',
       coalesce(o.source_metadata->>'year',o.source_metadata->>'year_or_dept'),
       o.canonical_url
  FROM instrument i
  JOIN document d ON d.id=i.document_id AND d.is_active
  JOIN source_observation o ON o.id=i.source_observation_id
 WHERE i.is_active AND i.duplicate_of IS NULL
 ORDER BY i.document_id, i.source_observation_id, i.expression_ordinal"""


def load(name: str, path) -> object:
    spec = importlib.util.spec_from_file_location(name, str(pathlib.Path(path).resolve()))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def squash(value, n=160) -> str:
    return " ".join(str(value or "").split())[:n]


def stored(cur, instrument_id: str) -> dict:
    cur.execute(TREE_SQL, (instrument_id,))
    rows = [tuple(r) for r in cur.fetchall()]
    cur.execute(S7_SQL, (instrument_id,))
    s7 = sorted(tuple(r) for r in cur.fetchall())
    cur.execute(TOC_SQL, (instrument_id,))
    toc = [tuple(r) for r in cur.fetchall()]
    return {"rows": rows, "s7": s7, "toc": toc}


def built(inst) -> dict:
    by_key = {r["key"]: r for r in inst.provisions}
    path = {r["key"]: r["path"] for r in inst.provisions}
    rows = []
    for r in inst.provisions:
        parent = by_key.get(r["parent_key"])
        rows.append((r["path"], parent["path"] if parent else "", r["kind"],
                     r["label"], r["ordinal"], r["first_page"], r["last_page"],
                     r["first_block"], r["text"] or "", r["heading"] or ""))
    s7 = sorted((d["printed_label"], d["source_block_id"], d["canonical_source_block_id"],
                 d["original_kind"], path[d["candidate_key"]], path[d["canonical_key"]])
                for d in inst.structural_decisions)
    toc = [(t["ordinal"], t["label"], t["heading"] or "", t["kind"],
            path.get(t["provision_key"]) if t["provision_key"] is not None else None,
            t["method"]) for t in inst.toc_entries]
    return {"rows": rows, "s7": s7, "toc": toc}


def compare(old: dict, new: dict) -> dict:
    """Name every node, candidate and contents link that differs."""
    out: dict = {}
    if old["rows"] == new["rows"]:
        out["tree"] = {"identical": True}
    else:
        ident = lambda r: (r[2], r[3], r[7])  # noqa: E731  kind, label, first block
        o: dict = {}
        n: dict = {}
        for r in old["rows"]:
            o.setdefault(ident(r), r)
        for r in new["rows"]:
            n.setdefault(ident(r), r)
        changed = []
        for key in sorted(o.keys() & n.keys(), key=str):
            a, b = o[key], n[key]
            if a == b:
                continue
            fields = [f for f, x, y in zip(FIELDS, a, b) if x != y]
            # path/ordinal alone follow from an add/remove elsewhere
            if not set(fields) - {"path", "ordinal"}:
                continue
            item = {"kind": key[0], "label": key[1], "block": key[2], "fields": fields}
            if "text" in fields:
                item["text"] = [squash(a[8], 240), squash(b[8], 240)]
            if "heading" in fields:
                item["heading"] = [a[9], b[9]]
            if "parent" in fields:
                item["parent"] = [a[1], b[1]]
            if "kind" in fields or "label" in fields:
                item["was"] = [a[2], a[3]]
            if "last_page" in fields:
                item["last_page"] = [a[6], b[6]]
            changed.append(item)
        out["tree"] = {
            "identical": False,
            "nodes": [len(old["rows"]), len(new["rows"])],
            "sections": [sum(1 for r in t if r[2] in ("section", "article"))
                         for t in (old["rows"], new["rows"])],
            "removed": [{"kind": k[0], "label": k[1], "block": k[2], "page": r[5],
                         "text": squash(r[8])} for k, r in o.items() if k not in n],
            "added": [{"kind": k[0], "label": k[1], "block": k[2], "page": r[5],
                       "text": squash(r[8])} for k, r in n.items() if k not in o],
            "changed": changed,
        }
    out["s7"] = {"stored": len(old["s7"]), "built": len(new["s7"]),
                 "identical": old["s7"] == new["s7"]}
    if old["s7"] != new["s7"]:
        out["s7"]["removed"] = [list(x[:4]) for x in old["s7"] if x not in new["s7"]]
        out["s7"]["added"] = [list(x[:4]) for x in new["s7"] if x not in old["s7"]]
    out["toc"] = {"stored": len(old["toc"]), "built": len(new["toc"]),
                  "identical": old["toc"] == new["toc"],
                  "unlinked": [sum(1 for t in old["toc"] if t[4] is None),
                               sum(1 for t in new["toc"] if t[4] is None)]}
    if old["toc"] != new["toc"]:
        so, sn = set(old["toc"]), set(new["toc"])
        out["toc"]["removed"] = [list(x) for x in old["toc"] if x not in sn][:40]
        out["toc"]["added"] = [list(x) for x in new["toc"] if x not in so][:40]
    out["same"] = (out["tree"]["identical"] and out["s7"]["identical"]
                   and out["toc"]["identical"])
    return out


def summarise(paths: list[str]) -> int:
    records = []
    for pattern in paths:
        for path in sorted(glob.glob(pattern)):
            with open(path, encoding="utf-8") as fh:
                records.extend(json.loads(line) for line in fh if line.strip())
    expressions = [(r, e) for r in records for e in r.get("expressions", [])]
    errors = [r for r in records if r.get("error")]
    released = [(r, e) for r, e in expressions if e.get("released")]
    moved = [(r, e) for r, e in expressions if not e["compare"]["same"]]
    moved_released = [(r, e) for r, e in moved if e.get("released")]
    tree_moved_released = [(r, e) for r, e in moved_released
                           if not e["compare"]["tree"]["identical"]]
    s7_up = [(r, e) for r, e in moved_released
             if e["compare"]["s7"]["built"] > e["compare"]["s7"]["stored"]]
    toc_up = [(r, e) for r, e in moved_released
              if e["compare"]["toc"]["unlinked"][1] > e["compare"]["toc"]["unlinked"][0]]
    print(f"observations recorded : {len(records)}  (errors {len(errors)})")
    print(f"expressions measured  : {len(expressions)}  released {len(released)}")
    print(f"differ from stored    : {len(moved)}  of which released {len(moved_released)}")
    print(f"  released, tree differs              : {len(tree_moved_released)}")
    print(f"  released, more S7 candidates        : {len(s7_up)}")
    print(f"  released, more unlinked TOC entries : {len(toc_up)}")
    for r, e in sorted(moved, key=lambda x: (x[0]["document"], x[1]["expression"])):
        c = e["compare"]
        t = c["tree"]
        tag = ("tree=" if t["identical"] else
               f"tree nodes {t['nodes'][0]}->{t['nodes'][1]} sec {t['sections'][0]}->{t['sections'][1]}"
               f" -{len(t['removed'])} +{len(t['added'])} ~{len(t['changed'])}")
        print(f"    {'RELEASED' if e.get('released') else 'blocked '} doc {r['document']:>5} "
              f"e{e['expression']:<2} {tag}  "
              f"s7 {c['s7']['stored']}->{c['s7']['built']}  "
              f"toc-unlinked {c['toc']['unlinked'][0]}->{c['toc']['unlinked'][1]}")
    for r in errors:
        print(f"    ERROR doc {r['document']} obs {r['observation']}: {r['error']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("segmenter", nargs="?", help="the segment.py copy to build with")
    ap.add_argument("--out", type=pathlib.Path)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--documents", help="restrict to these document ids")
    ap.add_argument("--released-only", action="store_true")
    ap.add_argument("--reference-json", type=pathlib.Path,
                    help='{"doc:obs:expr": {"pre": uuid}} -- compare against these trees')
    ap.add_argument("--summarise", nargs="+", metavar="JSONL")
    ap.add_argument("--progress-every", type=int, default=100)
    a = ap.parse_args()
    if a.summarise:
        return summarise(a.summarise)
    if not a.segmenter or not a.out:
        ap.error("segmenter and --out are required unless --summarise")

    from nizam.storage import legal_write
    from nizam.storage.db import connect
    import nizam.workers.segment as worker

    seg_path = pathlib.Path(a.segmenter)
    digest = hashlib.sha256(seg_path.read_bytes()).hexdigest()[:8]
    module = load(f"segmenter_{digest}", seg_path)
    worker.segment = module.segment          # build() calls the module global
    materializer = load("materialize_multi_instrument_m",
                        pathlib.Path(__file__).parent / "materialize_multi_instrument.py")
    shard, shards = (int(v) for v in a.shard.split("/"))

    references = (json.loads(a.reference_json.read_text(encoding="utf-8"))
                  if a.reference_json else None)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(TARGETS_SQL)
        rows = cur.fetchall()
    groups: dict = {}
    for (doc, obs, expr, iid, released, sha, source_id, title, year, url) in rows:
        groups.setdefault((doc, obs), {"meta": (sha, source_id, title, year, url),
                                       "expressions": []})
        groups[(doc, obs)]["expressions"].append((expr, iid, released))
    if references is not None:
        keep = {}
        for key, value in references.items():
            doc, obs, expr = (int(v) for v in key.split(":"))
            group = groups.get((doc, obs))
            if group is None:
                continue
            live = {e: (i, r) for e, i, r in group["expressions"]}
            keep.setdefault((doc, obs), {"meta": group["meta"], "expressions": []})
            keep[(doc, obs)]["expressions"].append(
                (expr, value["pre"], live.get(expr, (None, False))[1]))
        groups = keep
    if a.documents:
        wanted = {int(v) for v in a.documents.replace(",", " ").split()}
        groups = {k: v for k, v in groups.items() if k[0] in wanted}
    if a.released_only:
        groups = {k: v for k, v in groups.items()
                  if any(r for _, _, r in v["expressions"])}
    ordered = sorted(groups)
    ordered = [k for i, k in enumerate(ordered) if i % shards == shard]

    out_path = a.out.with_suffix(".jsonl")
    done_path = a.out.with_suffix(".done")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done: set[int] = set()
    if done_path.exists():
        done = {int(v) for v in done_path.read_text().split() if v.strip()}
    if out_path.exists():
        lines = out_path.read_text(encoding="utf-8").splitlines()
        kept = [ln for ln in lines if ln.strip() and json.loads(ln)["observation"] in done]
        out_path.write_text("".join(ln + "\n" for ln in kept), encoding="utf-8")
    print(f"shard {a.shard}: {len(ordered)} observations, segmenter {seg_path} "
          f"sha {digest}; resuming past {len(done)}", file=sys.stderr, flush=True)

    def append(record: dict) -> None:
        with open(out_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        with open(done_path, "a", encoding="utf-8") as fh:
            fh.write(f"{record['observation']}\n")
            fh.flush()
            os.fsync(fh.fileno())

    started = time.time()
    processed = 0
    with connect() as conn, conn.cursor() as cur:
        for doc, obs in ordered:
            if obs in done:
                continue
            group = groups[(doc, obs)]
            record: dict = {"document": doc, "observation": obs, "segmenter": digest,
                            "expressions": []}
            try:
                if doc in MULTI_DOCS:
                    insts = {inst.expression_ordinal: inst for inst, _ in
                             zip(*materializer.prepare(doc, obs)[:2])}
                else:
                    sha, source_id, title, year, url = group["meta"]
                    blocks = legal_write.blocks_for(doc)
                    res = legal_write.structural_resolutions_for(doc)
                    patches = legal_write.segmentation_patches_for(obs)
                    inst, _seg = worker.build(
                        doc, sha, obs, source_id, title, year, url, blocks,
                        legal_write.observed_on(obs),
                        patches,
                        toc_dispositions=legal_write.toc_dispositions_for(obs),
                        structural_resolutions=res,
                        structural_overrides=worker.reviewed_structural_overrides(
                            res, patches) or None)
                    insts = {0: inst}
                for expr, iid, released in group["expressions"]:
                    item = {"expression": expr, "instrument": iid, "released": released}
                    if expr not in insts:
                        item["compare"] = {"same": False, "missing_expression": True,
                                           "tree": {"identical": False, "nodes": [0, 0],
                                                    "sections": [0, 0], "removed": [],
                                                    "added": [], "changed": []},
                                           "s7": {"stored": 0, "built": 0, "identical": True},
                                           "toc": {"identical": True, "unlinked": [0, 0]}}
                    else:
                        item["compare"] = compare(stored(cur, iid), built(insts[expr]))
                    record["expressions"].append(item)
            except Exception as exc:  # noqa: BLE001 -- recorded, never swallowed
                conn.rollback()
                record["error"] = f"{type(exc).__name__}: {exc}"[:400]
                print(f"  {doc}/{obs}: {record['error']}", file=sys.stderr, flush=True)
            append(record)
            done.add(obs)
            processed += 1
            if processed % a.progress_every == 0:
                print(f"  {len(done)}/{len(ordered)} recorded, "
                      f"{processed / max(time.time() - started, 1e-9):.2f} obs/s",
                      file=sys.stderr, flush=True)
    remaining = [k for k in ordered if k[1] not in done]
    summary = {"shard": a.shard, "segmenter": str(seg_path), "sha": digest,
               "observations": len(ordered), "recorded": len(done & {k[1] for k in ordered}),
               "remaining": len(remaining),
               "elapsed_s_this_session": round(time.time() - started)}
    a.out.with_suffix(".json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary), file=sys.stderr, flush=True)
    return 0 if not remaining else 3


if __name__ == "__main__":
    sys.exit(main())
