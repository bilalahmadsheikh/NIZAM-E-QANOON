"""Citation resolution on the golden units (D-097; docs/04 R0: "100% golden citation resolution or typed ambiguity").

    python evals/citation_resolution.py [--out evals/results/citations-<date>.json]

For every distinct necessary unit of golden sets 1-4 that is a section, article or order, the unit is cited in the
forms people write, built from the database's own records (its recorded label and title), and resolved by
nizam.retrieval.citations through the storage session:
  full     "section <label> of the <recorded title>"       ("article" for an article)
  alias    "s. <label> <ALIAS>"   when the unit's law is one an alias names (PPC, CrPC, CPC, QSO, MFLO, ...)
  bare     "<label> <ALIAS>"      likewise
Outcomes per query: CORRECT (the resolved unit is the golden unit), UNRESOLVED (a typed ambiguity, returned with its
reason: acceptable, never silent), WRONG (resolved to another unit: must be zero -- a wrong citation is the worst
failure). This measures the grammar and the resolver, not relevance.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nizam.retrieval import citations as C  # noqa: E402
from nizam.storage import unit_search  # noqa: E402
from nizam.storage.lexical import Filters  # noqa: E402


TERRITORIES = {"punjab", "sindh", "kp", "balochistan", "ict", "ajk", "gb"}


def golden_units():
    """(unit, territory of the first case citing it) -- a citation is read where its question is asked"""
    seen = set()
    for f in sorted(glob.glob(str(ROOT / "evals/golden/golden-pk-v1-set*.draft.jsonl"))):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            terr = (d.get("scope") or {}).get("territory")
            for u in d["retrievalGold"].get("necessaryUnits") or []:
                if u["provisionId"] not in seen:
                    seen.add(u["provisionId"])
                    yield u, (terr if terr in TERRITORIES else None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / f"evals/results/citations-{date.today().isoformat()}.json"))
    a = ap.parse_args()
    rows, tally = [], collections.Counter()
    with unit_search.session(Filters(as_of=date.today())) as s0:
        alias_law = {}
        for key, (words, juris) in C.ALIASES.items():
            laws = [x for x in s0.instruments_titled(words, 10, juris) if "amend" not in x[1].lower()]
            if laws:
                alias_law.setdefault(laws[0][0], key)
    for u, terr in golden_units():
        with unit_search.session(Filters(as_of=date.today(), territory=terr)) as s:
            s.cur.execute("""SELECT p.kind::text, p.label, coalesce(nullif(i.display_title, ''), i.short_title),
                                    i.id::text, p.path::text
                               FROM provision p JOIN instrument i ON i.id = p.instrument_id WHERE p.id = %s""",
                          (u["provisionId"],))
            row = s.cur.fetchone()
            if row is None or row[0] not in ("section", "article", "order"):
                continue
            kind, label, title, iid, path = row
            word = {"section": "section", "article": "article", "order": "order"}[kind]
            queries = [("full", f"{word} {label} of the {title}")]
            if iid in alias_law:
                alias = {"ppc": "PPC", "crpc": "CrPC", "cr.p.c": "Cr.P.C", "cpc": "CPC", "c.p.c": "C.P.C",
                         "qso": "QSO", "constitution": "Constitution", "mflo": "MFLO", "ata": "ATA",
                         "cnsa": "CNSA", "nao": "NAO"}[alias_law[iid]]
                if alias == "Constitution":
                    queries.append(("alias", f"Article {label} of the Constitution"))
                else:
                    queries += [("alias", f"s. {label} {alias}"), ("bare", f"{label} {alias}")]
            for form, q in queries:
                found = C.find(q)
                if not found:
                    outcome, why, got = "UNRESOLVED", "grammar found no citation", None
                else:
                    c = C.resolve(s, found[0])
                    if c.resolved_unit is None:
                        outcome, why, got = "UNRESOLVED", c.unresolved, None
                    elif c.resolved_unit.path == path:
                        outcome, why, got = "CORRECT", None, c.resolved_unit.path
                    elif any(a.path == path for a in c.alternates):
                        outcome, why, got = "CORRECT_ALT", c.alternate_laws, path
                    else:
                        outcome, why, got = "WRONG", c.resolved_law, c.resolved_unit.path
                tally[(form, outcome)] += 1
                rows.append({"form": form, "query": q, "expected": path, "outcome": outcome, "why": why, "got": got})
    summary = {}
    for form in ("full", "alias", "bare"):
        n = sum(v for (f, _o), v in tally.items() if f == form)
        if n:
            summary[form] = {o: tally[(form, o)] for o in ("CORRECT", "CORRECT_ALT", "UNRESOLVED", "WRONG")} | {"queries": n}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, ensure_ascii=False),
                           encoding="utf-8")
    print(json.dumps(summary, indent=1))
    for r in [r for r in rows if r["outcome"] not in ("CORRECT", "CORRECT_ALT")][:25]:
        print(f"  {r['outcome']:10} {r['form']:5} {r['query'][:70]!r} -> {r['why']} got {r['got'] or '-'} want {r['expected']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
