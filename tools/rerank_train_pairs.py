"""rerank_train_pairs.py --out DIR [--queries N] [--val N] [--seed S] : training groups for fine-tuning the CPU reranker
(D-171, item 3 of the 26 Nov queue; ADR-2's fine-tuned reranker), from the courts' own citations of the statutes.

A query is a sentence of a released judgment that cites a provision the linker resolved (judgment_statute_reference,
resolution 'resolved'), with EVERY statute and case citation in it cut out, so the model learns what the words are
about, not the identifier. Its slate is the SERVED CPU path -- nizam.retrieval.candidates.candidates, the hybrid, the
bge-m3 space, in the court's territory, as at the BUILD date (AS_OF: at the decision date most cited units are not
operative in the corpus, which serves most laws only from capture). A group is kept only when a provision the sentence
cites is in that slate:
  positives  the slate's units holding (or held by) a provision the sentence cites
  negatives  up to NEG of the slate's first DEPTH other units, none overlapping a unit the PARAGRAPH cites (a
             paragraph citing s.302 and s.34 makes neither a negative of the other)
Passages are cut at the CPU profile's 800 characters (rerank.RERANK_INPUT["cpu"]), as served.

What is never read (each counted in the manifest):
  * the Supreme Court (court SC): its site signals ai-train=no, so its text never enters a training set (D-144);
  * the Balochistan High Court: its files sit under a path its robots.txt disallows (D-139); fetched by owner ruling,
    not trained on;
  * judgments with any judgment_sensitivity row (D-131: names withheld);
  * the precedent golden set's judgments and every judgment of their cases (evals/golden, D-133), so the precedent
    stratum stays unseen; the statute golden questions are not judgment text, so they cannot leak in this way;
  * a sentence written as a reporter's headnote ("---" catchwords) that a judgment quotes: third-party text (D-120).
Groups are split by JUDGMENT into train and val (val is for early stopping only; the decision is on golden dev).

Writes DIR/groups.jsonl  {"g", "split", "court", "q", "pos": [text], "neg": [text]}  -- leaves the machine as a
                         private Kaggle dataset (public court text and statute text; no gold of any golden set)
       (each worker writes groups.I.jsonl and manifest.I.json; --merge joins them)
       DIR/manifest.json the rule, the seed, every exclusion count, per-court and per-role counts
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import random
import re
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nizam.retrieval.candidates import candidates  # noqa: E402
from nizam.storage import unit_search  # noqa: E402
from nizam.storage.db import connect  # noqa: E402
from nizam.storage.lexical import Filters  # noqa: E402
from nizam.storage.treatment import sentence_bounds  # noqa: E402

EXCLUDED_COURTS = {"SC": "D-144: scp.gov.pk robots.txt ai-train=no",
                   "BHC": "D-139: files under a robots.txt-disallowed path"}
ROLES = ("interpreted", "quoted", "challenged", "charge", "cited")
K, DEPTH, NEG, CHARS = 50, 20, 7, 800
# the slate is read at the BUILD date, not the decision date: most laws are served only from their capture date
# (text_known_from, 0096-0099), so at the decision date the cited unit was not operative for 21 of 25 sampled sentences
# (27 Nov 2026). The model learns relevance, and it serves today's law to a question asked today.
AS_OF = date.today()
MIN_WORDS, MAX_CHARS = 10, 700
PER_UNIT, PER_JUDGMENT = 4, 3


def gold_exclusions() -> tuple[set[str], set[str]]:
    ids, keys = set(), set()
    for line in open(ROOT / "evals/golden/golden-pk-v1-precedent1.draft.jsonl", encoding="utf-8"):
        d = json.loads(line)
        for j in (d.get("precedentGold") or {}).get("necessaryJudgments", []) + \
                 (d.get("precedentGold") or {}).get("relevantJudgments", []):
            ids.add(j["judgmentId"])
            keys.update(j.get("caseKeys") or [])
    return ids, keys


def jurisdiction(territory: str) -> tuple[str | None, tuple[str, ...] | None]:
    if territory == "fed":
        return None, ("fed",)
    if territory == "ict":
        return "ict", ("fed",)
    return territory, (territory, "fed")


_WS = re.compile(r"\s+")
_HEADNOTE = re.compile(r"-{3,}|—{2,}")
_DANGLING = re.compile(r"\s+([,.;:)])")


def masked(text: str, spans: list[tuple[int, int]], a: int, b: int) -> str:
    """text[a:b] with every span inside it cut out"""
    out, at = [], a
    for s, e in sorted(spans):
        if e <= a or s >= b:
            continue
        out.append(text[at:max(s, at)])
        at = max(at, min(e, b))
    out.append(text[at:b])
    q = _DANGLING.sub(r"\1", _WS.sub(" ", "".join(out))).strip(" ,;:")
    return q


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--queries", type=int, default=8000, help="sampled sentences to try (train + val)")
    ap.add_argument("--val", type=float, default=0.08, help="share of judgments held out for early stopping")
    ap.add_argument("--seed", type=int, default=20261127)
    ap.add_argument("--shard", default="0/1", help="i/n: this worker reads every n-th sampled sentence from i")
    ap.add_argument("--merge", action="store_true", help="join the shards' files into groups.jsonl + manifest.json")
    a = ap.parse_args()
    if a.merge:
        return merge(a.out)
    shard, shards = (int(x) for x in a.shard.split("/"))
    os.environ["NIZAM_DENSE_PROFILE"] = "cpu"
    rng = random.Random(a.seed)
    a.out.mkdir(parents=True, exist_ok=True)
    gold_ids, gold_keys = gold_exclusions()
    counts = collections.Counter()

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT code, territory FROM court WHERE withdrawn_at IS NULL")
        territory = dict(cur.fetchall())
        cur.execute("""
            SELECT r.judgment_id::text, r.decided_on, r.paragraph_id::text, r.char_start, r.char_end, r.role,
                   r.dst_provision_id::text, j.court_code
              FROM judgment_statute_reference r
              JOIN judgment j ON j.id = r.judgment_id AND j.decided_on = r.decided_on
             WHERE r.resolution = 'resolved' AND r.dst_provision_id IS NOT NULL
               AND j.retired_at IS NULL AND j.is_active
               AND j.court_code <> ALL(%s)
               AND NOT EXISTS (SELECT 1 FROM judgment_sensitivity s WHERE s.judgment_id = j.id)
               AND NOT EXISTS (SELECT 1 FROM judgment_case c WHERE c.judgment_id = j.id AND c.case_key = ANY(%s))
               AND NOT (j.id::text = ANY(%s))
             ORDER BY r.id""", (list(EXCLUDED_COURTS), list(gold_keys), list(gold_ids)))
        refs = cur.fetchall()
        cur.execute("""SELECT j.court_code, count(*) FROM judgment_statute_reference r
                         JOIN judgment j ON j.id = r.judgment_id AND j.decided_on = r.decided_on
                        WHERE r.resolution = 'resolved' AND j.court_code = ANY(%s) GROUP BY 1""",
                    (list(EXCLUDED_COURTS),))
        for court, n in cur.fetchall():
            counts[f"excluded_court_{court}_refs"] = n
    counts["eligible_refs"] = len(refs)
    print(f"{len(refs)} eligible resolved references", flush=True)

    # sample sentences: every role but 'cited' first (richer prose), then 'cited'; at most PER_UNIT sentences per cited
    # provision and PER_JUDGMENT per judgment, so s.302 PPC and one long judgment do not make the set
    by_sentence: dict[tuple, dict] = {}
    rng.shuffle(refs)
    refs.sort(key=lambda r: ROLES.index(r[5]) if r[5] in ROLES else len(ROLES))
    per_unit, per_judgment = collections.Counter(), collections.Counter()
    for jid, dec, par, s, e, role, prov, court in refs:
        if len(by_sentence) >= a.queries:
            break
        if per_unit[prov] >= PER_UNIT or per_judgment[jid] >= PER_JUDGMENT:
            continue
        key = (par, s)
        per_unit[prov] += 1
        per_judgment[jid] += 1
        by_sentence[key] = {"judgment": jid, "decided_on": dec, "paragraph": par, "start": s, "end": e,
                            "role": role, "court": court}
    print(f"{len(by_sentence)} sentences sampled", flush=True)

    judgments = sorted({v["judgment"] for v in by_sentence.values()})
    rng.shuffle(judgments)
    val = set(judgments[:int(len(judgments) * a.val)])

    groups, t0 = [], time.time()
    out = open(a.out / f"groups.{shard}.jsonl", "w", encoding="utf-8")
    mine = [v for i, v in enumerate(by_sentence.values()) if i % shards == shard]
    for i, v in enumerate(mine, 1):
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT text FROM judgment_paragraph WHERE id = %s AND decided_on = %s",
                        (v["paragraph"], v["decided_on"]))
            text = cur.fetchone()[0]
            cur.execute("""SELECT char_start, char_end, dst_provision_id::text, resolution FROM judgment_statute_reference
                            WHERE paragraph_id = %s AND decided_on = %s""", (v["paragraph"], v["decided_on"]))
            srefs = cur.fetchall()
            cur.execute("""SELECT char_start, char_end FROM judgment_case_reference
                            WHERE paragraph_id = %s AND decided_on = %s""", (v["paragraph"], v["decided_on"]))
            crefs = cur.fetchall()
        a_, b_ = sentence_bounds(text, v["start"], v["end"])
        if b_ - a_ > MAX_CHARS:                       # a run-on "sentence": the window around the citation
            a_, b_ = max(a_, v["start"] - MAX_CHARS // 2), min(b_, v["end"] + MAX_CHARS // 2)
        spans = [(s, e) for s, e, _, _ in srefs] + [(s, e) for s, e in crefs]
        q = masked(text, spans, a_, b_)
        if len(q.split()) < MIN_WORDS:
            counts["dropped_short_query"] += 1
            continue
        if _HEADNOTE.search(q):                       # a reporter's headnote quoted in the judgment: third-party text
            counts["dropped_headnote_style"] += 1     # (D-120), never trained on
            continue
        cited_here = {p for s, e, p, res in srefs if p and res == "resolved" and s < b_ and e > a_}
        cited_paragraph = {p for _, _, p, res in srefs if p and res == "resolved"}
        terr, juris = jurisdiction(territory[v["court"]])
        f = Filters(as_of=AS_OF, territory=terr, jurisdictions=juris)
        try:
            r = candidates(q, f, K)
        except Exception as exc:                       # noqa: BLE001 -- one bad sentence never stops the build
            counts[f"dropped_error_{type(exc).__name__}"] += 1
            continue
        if r.degraded:
            sys.exit(f"slate degraded to {r.degraded}: the CPU encoder is not loaded -- refusing to build")
        slate = r.candidates
        with unit_search.session(r.filters) as s:
            units_here = s.units_of(sorted(cited_here))
            units_par = s.units_of(sorted(cited_paragraph))
            s.cur.execute("SELECT id::text, path::text FROM provision WHERE id = ANY(%s::uuid[])",
                          ([c.unit_id for c in slate],))
            path_of = dict(s.cur.fetchall())

            def overlaps(c, units) -> bool:
                p = path_of.get(c.unit_id, "")
                return any(c.instrument_id == u.instrument_id and
                           (p == u.path or p.startswith(u.path + ".") or u.path.startswith(p + "."))
                           for u in units.values())
            pos = [c for c in slate if overlaps(c, units_here)]
            if not pos:
                counts["dropped_positive_not_in_slate"] += 1
                continue
            neg = [c for c in slate[:DEPTH] if not overlaps(c, units_par)][:NEG]
            if not neg:
                counts["dropped_no_negative"] += 1
                continue
            texts = s.unit_passages([(c.unit_id, c.version_id) for c in pos[:2] + neg], max_chars=CHARS)
        g = {"g": len(groups), "split": "val" if v["judgment"] in val else "train", "court": v["court"],
             "role": v["role"], "pos_rank": next(i for i, c in enumerate(slate, 1) if c in pos), "q": q,
             "pos": [texts[c.unit_id] for c in pos[:2]], "neg": [texts[c.unit_id] for c in neg]}
        groups.append({k: g[k] for k in ("g", "split", "court", "role", "pos_rank")})
        out.write(json.dumps(g, ensure_ascii=False) + "\n")
        out.flush()
        if i % 100 == 0:
            print(f"  {i}/{len(mine)} tried, {len(groups)} groups ({time.time() - t0:.0f}s)", flush=True)
    out.close()

    split = collections.Counter(g["split"] for g in groups)
    manifest = {"built": date.today().isoformat(), "seed": a.seed, "rule": {
        "excluded_courts": EXCLUDED_COURTS, "excluded": ["judgment_sensitivity (D-131)", "precedent golden judgments "
        "and their cases (D-133)"], "roles": ROLES, "k": K, "negatives_from_first": DEPTH,
        "negatives": NEG, "passage_chars": CHARS, "min_words": MIN_WORDS, "per_unit": PER_UNIT,
        "per_judgment": PER_JUDGMENT, "slate": f"candidates() hybrid, cpu (bge-m3), as_of {AS_OF} (build date), court territory"},
        "groups": len(groups), "split": dict(split), "counts": dict(counts),
        "by_court": dict(collections.Counter(g["court"] for g in groups)),
        "by_role": dict(collections.Counter(g["role"] for g in groups)),
        "positive_rank_le10": sum(g["pos_rank"] <= 10 for g in groups)}
    manifest["shard"] = a.shard
    (a.out / f"manifest.{shard}.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps(manifest, indent=1))
    return 0


def merge(out: Path) -> int:
    parts = sorted(out.glob("manifest.*.json"))
    if not parts:
        sys.exit(f"no shard manifests in {out}")
    ms = [json.loads(p.read_text(encoding="utf-8")) for p in parts]
    n, by = 0, {k: collections.Counter() for k in ("split", "counts", "by_court", "by_role")}
    with open(out / "groups.jsonl", "w", encoding="utf-8") as fh:
        for p in parts:
            for line in open(out / f"groups.{p.name.split('.')[1]}.jsonl", encoding="utf-8"):
                g = json.loads(line)
                g["g"] = n
                n += 1
                fh.write(json.dumps(g, ensure_ascii=False) + "\n")
    for m in ms:
        for k in by:
            by[k].update(m[k])
    manifest = {**{k: ms[0][k] for k in ("built", "seed", "rule")}, "shards": [m["shard"] for m in ms],
                "groups": n, **{k: dict(v) for k, v in by.items()},
                "positive_rank_le10": sum(m["positive_rank_le10"] for m in ms)}
    manifest["counts"]["eligible_refs"] = ms[0]["counts"]["eligible_refs"]
    for c in ("excluded_court_SC_refs", "excluded_court_BHC_refs"):
        manifest["counts"][c] = ms[0]["counts"].get(c, 0)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps(manifest, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
