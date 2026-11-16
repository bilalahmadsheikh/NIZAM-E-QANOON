"""Shared builder for golden-pk-v1 draft sets (docs/10 §5 LegalEvalCase records), used by build_set2/3/4.py.

Every gold unit is a released provision resolved by its document and section label (or ltree path) to its
provision id; its text, instrument, currency and official source URL are read from the database (INV-1). Each case
is checked:

  * every necessary unit of an 'answer'/'conditional' case must be served by operative_provision at the case's own
    as_of and territory (INV-5);
  * every regex in the case's `check` list must match the full text of its necessary units, so the facts the
    propositions state (periods, amounts, forums) are verified against the law as held, not recalled;
  * a hard negative marked `must_not_serve` (another territory's law, a law not yet made or already ended at
    as_of) must NOT be served there;
  * a family id must not appear in another set's file (families are the split unit, docs/10 §4).

Stage A0 + A3 only: drafted by the lead (claude); A1 (two legal annotators), A2 (senior-advocate adjudication) and
A4 (split freeze) are still to happen, so every record says status 'draft'.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DEFAULT_AS_OF = "2026-11-16"
GOLDEN = ROOT / "evals/golden"

# A province's own official text of a federal-era code (Punjab Code / KP Code / Balochistan Code copies), found
# 16 Nov 2026 by title. In that province the provincial text carries the provincial amendments, so a federal unit in
# a case scoped to it is compared with the provincial unit: near-identical -> recorded as an equivalent text;
# different -> the build stops until the author decides which text answers (Punjab's Family Courts Act s.17-A, for
# one, differs materially from the federal s.17A).
PROVINCIAL_COPY = {
    4441: {"punjab": 4458},                    # Pakistan Penal Code
    4463: {"punjab": 4490},                    # Code of Civil Procedure
    4337: {"punjab": 4351},                    # Contract Act
    4237: {"punjab": 4006},                    # Limitation Act
    3283: {"punjab": 3910},                    # Muslim Family Laws Ordinance
    4075: {"punjab": 3275},                    # Partnership Act
    4166: {"punjab": 4215},                    # Qanun-e-Shahadat
    3617: {"punjab": 3712},                    # Sale of Goods Act
    3944: {"punjab": 4052, "kp": 3883},        # Specific Relief Act
    3991: {"punjab": 4290},                    # Transfer of Property Act
    2944: {"punjab": 4081, "balochistan": 1170},  # Family Courts Act
    3132: {"punjab": 3187},                    # Arbitration Act
    4099: {"punjab": 3474, "kp": 4403},        # Land Acquisition Act
    3876: {"punjab": 4261, "kp": 4349},        # Registration Act
    3550: {"punjab": 2265},                    # Payment of Wages Act
}
SIMILAR = 0.90


def _words(t: str) -> list[str]:
    return re.findall(r"[a-z]+", t.lower())


def similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, _words(a), _words(b), autojunk=False).ratio()


def label_variants(ref: str) -> list[str]:
    if "." in ref:
        return []
    m = re.fullmatch(r"(\d+)-?([A-Z]+)", ref)
    return [ref] if not m else list(dict.fromkeys([ref, f"{m[1]}{m[2]}", f"{m[1]}-{m[2]}"]))


class CaseSet:
    def __init__(self, name: str, require_checks: bool = True):
        self.name = name
        self.cases: list[dict] = []
        self.require_checks = require_checks

    def case(self, cid, stratum, family, risk, lang, script, text, meaning, jurisdiction, territory, outcome, props,
             necessary=(), relevant=(), negatives=(), abstention=None, facts=(), omitted=(), check=(),
             as_of=DEFAULT_AS_OF, must_not_serve=(), equivalent=(), provincial_decided=()):
        """necessary/relevant/negatives: (document_id, label-or-path, grade). check: regexes the necessary text must
        contain. must_not_serve: (document_id, label) hard negatives that must not be operative at as_of/territory.
        equivalent: (document_id, label) the same provision in a province's own official text of the same law (e.g.
        the Punjab Code copy of the Contract Act); recorded as a grade-3 relevant unit so a system citing either text
        is not marked wrong."""
        relevant = list(relevant) + [(d, r, 3, "equivalent") for d, r in equivalent]
        if any(c["cid"] == cid for c in self.cases):
            raise ValueError(f"duplicate case id {cid}")
        self.cases.append(dict(cid=cid, stratum=stratum, family=family, risk=risk, lang=lang, script=script,
                               text=text, meaning=meaning, jurisdiction=jurisdiction, territory=territory,
                               outcome=outcome, props=props, necessary=list(necessary), relevant=list(relevant),
                               negatives=list(negatives), abstention=abstention, facts=list(facts),
                               omitted=list(omitted), check=list(check), as_of=as_of,
                               must_not_serve=list(must_not_serve),
                               # federal units whose provincial text the author has compared and decided on
                               provincial_decided=set(provincial_decided)))


def resolve(cur, doc: int, ref: str, chars: int = 400) -> dict | None:
    cur.execute("SELECT id, coalesce(display_title, short_title), status::text, source_url, jurisdiction::text, year "
                "FROM v_release_instrument WHERE document_id = %s", (doc,))
    found = cur.fetchall()
    if len(found) != 1:      # none, or a document holding several laws: never guess which one is meant
        return None
    iid, title, status, url, jur, year = found[0]
    if "." in ref:
        cur.execute("""SELECT p.id::text, p.path::text, p.label, p.heading FROM provision p
                        WHERE p.instrument_id = %s AND p.is_active AND p.path::text = %s""", (iid, ref))
    else:
        cur.execute("""SELECT p.id::text, p.path::text, p.label, p.heading FROM provision p
                        WHERE p.instrument_id = %s AND p.is_active AND p.label = %s
                          AND p.kind::text IN ('section', 'article', 'order', 'schedule', 'rule')
                        ORDER BY nlevel(p.path), p.ordinal LIMIT 1""", (iid, ref))
    p = cur.fetchone()
    if not p:
        return None
    pid, path, label, heading = p
    cur.execute("""SELECT string_agg(concat_ws(' ', d.heading, v.text_en), ' ' ORDER BY d.ord) FROM (
                     SELECT p2.id, p2.ordinal AS ord, p2.heading FROM provision p2
                      WHERE p2.instrument_id = %s AND p2.is_active AND (p2.path <@ %s::ltree)) d
                     LEFT JOIN provision_version v ON v.provision_id = d.id AND upper_inf(v.validity)""", (iid, path))
    text = " ".join((cur.fetchone()[0] or "").split())
    cur.execute("SELECT currency, currency_reason, not_current_from::text FROM mv_instrument_serving "
                "WHERE instrument_id = %s", (iid,))
    currency, reason, ncf = cur.fetchone() or (None, None, None)
    return dict(provisionId=pid, path=path, label=label, heading=heading, instrumentId=str(iid), documentId=doc,
                instrument=title, jurisdiction=jur, year=year, status=status, currency=currency,
                currencyReason=reason, notCurrentFrom=ncf, officialUrl=url,
                textSha256=hashlib.sha256(text.encode()).hexdigest(), excerpt=text[:chars], _full=text)


def operative(cur, unit: dict, territory: str | None, as_of: str) -> bool:
    cur.execute("SELECT set_config('nzq.as_of', %s, false)", (as_of,))
    cur.execute("SELECT set_config('nzq.territory', %s, false)", (territory or "",))
    # a section whose words sit in its subsections is served through its descendants (ltree subtree)
    cur.execute("SELECT EXISTS (SELECT 1 FROM operative_provision WHERE instrument_id = %s AND path <@ %s::ltree)",
                (unit["instrumentId"], unit["path"]))
    ok = cur.fetchone()[0]
    cur.execute("RESET nzq.territory")
    return ok


def other_set_families(name: str) -> dict[str, str]:
    seen = {}
    for p in sorted(GOLDEN.glob("golden-pk-v1-set*.draft.jsonl")):
        if f"-{name}." in p.name:
            continue
        for line in p.open(encoding="utf-8"):
            if line.strip():
                seen[json.loads(line)["familyId"]] = p.name
    return seen


def build(cs: CaseSet, title_note: str) -> int:
    from nizam.storage.db import connect
    out = GOLDEN / f"golden-pk-v1-{cs.name}.draft.jsonl"
    report = GOLDEN / f"golden-pk-v1-{cs.name}.draft.md"
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    problems, observations, rows = [], [], []
    foreign = other_set_families(cs.name)
    for c in cs.cases:
        if c["family"] in foreign:
            problems.append(f"{c['cid']}: family {c['family']} already used in {foreign[c['family']]}")
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET statement_timeout = 0")
        for c in cs.cases:
            units = {}
            full = []
            for kind in ("necessary", "relevant", "negatives"):
                units[kind] = []
                for doc, ref, grade, *tag in c[kind]:
                    u = resolve(cur, doc, ref)
                    if u is None:
                        problems.append(f"{c['cid']}: {kind} unit {doc}/{ref} does not resolve"); continue
                    u["grade"] = grade
                    if tag:
                        u["equivalentText"] = True
                    u["operativeAtAsOfInTerritory"] = (operative(cur, u, c["territory"], c["as_of"])
                                                       if c["territory"] else None)
                    if kind == "necessary":
                        full.append(u["_full"])
                        if c["outcome"] != "abstain" and not u["operativeAtAsOfInTerritory"]:
                            cur.execute("""SELECT min(lower(v.validity))::text,
                                                  min(k.text_known_from)::text, string_agg(DISTINCT k.basis, ',')
                                             FROM provision p
                                             JOIN provision_version v ON v.provision_id = p.id
                                             LEFT JOIN mv_provision_text_known_from k ON k.provision_id = p.id
                                            WHERE p.instrument_id = %s AND p.is_active AND p.path <@ %s::ltree""",
                                        (u["instrumentId"], u["path"]))
                            held_from, known_from, basis = cur.fetchone()
                            if c["as_of"] != DEFAULT_AS_OF and held_from and held_from > c["as_of"]:
                                # a past-dated (temporal) case: the gold is the law in force then; the system cannot
                                # yet show the held text was the law that early (mv_provision_text_known_from, 0098)
                                observations.append(f"{c['cid']}: necessary {doc}/{ref} ({u['instrument']}) is not "
                                                    f"servable at {c['as_of']}: held text captured {held_from}, "
                                                    f"known from {known_from or 'unknown'} ({basis})")
                            else:
                                problems.append(f"{c['cid']}: necessary {doc}/{ref} NOT served at {c['as_of']} in "
                                                f"{c['territory']}")
                    if (doc, ref) in c["must_not_serve"] and u["operativeAtAsOfInTerritory"]:
                        # the gold is right either way; a served trap is a finding about the SYSTEM, kept for L3
                        observations.append(f"{c['cid']}: hard negative {doc}/{ref} ({u['instrument']}) IS served "
                                            f"at {c['as_of']} in {c['territory']}; the gold says it must not be")
                    units[kind].append({k: v for k, v in u.items() if k != "_full"})
            # a federal unit in a province that publishes its own text of the same law: compare the two texts
            in_case = {u["documentId"] for k in units for u in units[k]}
            for u in list(units["necessary"]):
                prov = PROVINCIAL_COPY.get(u["documentId"], {}).get(c["territory"] or "")
                if not prov or prov in in_case or (u["documentId"], u["label"]) in c["provincial_decided"]:
                    continue
                p = next((x for x in (resolve(cur, prov, v) for v in label_variants(u["label"])) if x), None)
                if p is None:
                    problems.append(f"{c['cid']}: {c['territory']} text (doc {prov}) of {u['instrument']} has no "
                                    f"s.{u['label']}; decide which text answers"); continue
                full_u = resolve(cur, u["documentId"], u["path"])["_full"]
                sim = similarity(full_u, p["_full"])
                if sim >= SIMILAR:
                    p.update(grade=3, equivalentText=True, similarityToNecessary=round(sim, 3),
                             operativeAtAsOfInTerritory=operative(cur, p, c["territory"], c["as_of"]))
                    units["relevant"].append({k: v for k, v in p.items() if k != "_full"})
                else:
                    problems.append(f"{c['cid']}: the {c['territory']} text (doc {prov}) of {u['instrument']} "
                                    f"s.{u['label']} differs from the federal text (similarity {sim:.2f}); the "
                                    f"provincial text may be the one that answers — decide")
            blob = " ".join(full)
            for rx in c["check"]:
                if not re.search(rx, blob, re.I):
                    problems.append(f"{c['cid']}: check /{rx}/ not found in the necessary text")
            if c["outcome"] != "abstain" and not units["necessary"]:
                problems.append(f"{c['cid']}: an answer case with no necessary unit")
            if cs.require_checks and c["outcome"] != "abstain" and not c["check"]:
                problems.append(f"{c['cid']}: an answer case with no text check")
            rows.append({
                "caseId": c["cid"], "datasetVersion": f"golden-pk-v1-draft/{cs.name}", "familyId": c["family"],
                "riskClass": c["risk"], "languages": c["lang"], "stratum": c["stratum"],
                "question": {"text": c["text"], "script": c["script"], "intendedMeaning": c["meaning"],
                             "suppliedFacts": c["facts"], "omittedFacts": c["omitted"]},
                "scope": {"jurisdiction": c["jurisdiction"], "territory": c["territory"], "asOf": c["as_of"]},
                "expectedOutcome": c["outcome"],
                "propositions": [{"id": f"{c['cid']}-p{i + 1}", "text": t, "materiality": "material",
                                  "necessaryEvidence": [u["provisionId"] for u in units["necessary"]]}
                                 for i, t in enumerate(c["props"])],
                "retrievalGold": {"necessaryUnits": units["necessary"], "relevantUnits": units["relevant"],
                                  "hardNegatives": units["negatives"]},
                "abstention": c["abstention"],
                "textChecks": c["check"],
                "provenance": {"officialUrls": sorted({u["officialUrl"] for k in units for u in units[k]
                                                       if u.get("officialUrl")}),
                               "corpusRevision": rev, "labelledAt": date.today().isoformat()},
                "review": {"annotatorA": "claude (draft: A0 authoring + A3 identity resolution)", "annotatorB": None,
                           "agreement": None, "adjudicator": None, "reasons": [],
                           "status": "draft — not gold until A1/A2 (two legal annotators, senior advocate)"},
            })
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    strata = Counter(r["stratum"] for r in rows)
    lines = [f"# golden-pk-v1 — draft {cs.name} ({len(rows)} cases)\n", title_note + "\n",
             f"Corpus revision {rev}. Strata: " + ", ".join(f"{k} {v}" for k, v in strata.items()) + ".",
             "Status: **draft** — A0 authoring and A3 identity resolution only. Not gold until two legal annotators "
             "(A1) and a senior advocate (A2) have reviewed it; do not tune or report on it before then.\n"]
    for r in rows:
        q = r["question"]
        lines.append(f"## {r['caseId']} · {r['stratum']} · {r['scope']['jurisdiction']}/{r['scope']['territory']} · "
                     f"as of {r['scope']['asOf']} · expect **{r['expectedOutcome']}**\n")
        lines.append(f"**Q:** {q['text']}\n")
        for p in r["propositions"]:
            lines.append(f"- *Proposition:* {p['text']}")
        for kind, label in (("necessaryUnits", "Necessary"), ("relevantUnits", "Relevant"),
                            ("hardNegatives", "Hard negative")):
            for u in r["retrievalGold"][kind]:
                served = {True: "served", False: "not served", None: "-"}[u["operativeAtAsOfInTerritory"]]
                lines.append(f"- **{label} (grade {u['grade']})** — {u['instrument']}, s./art. {u['label']} "
                             f"({u['currency']}: {u['currencyReason']}; {served} in {r['scope']['territory']}) · "
                             f"`{u['provisionId']}` · [source]({u['officialUrl']})\n  > {u['excerpt'][:260]}")
        if r["abstention"]:
            lines.append(f"- *Abstain:* {r['abstention']['code']} — {r['abstention']['why']}")
        lines.append("")
    if observations:
        lines.append("## What the system currently gets wrong (traps it serves)\n\n"
                     "The gold is unchanged by these; they are what an L3 run is expected to fail until fixed.\n\n"
                     + "\n".join(f"- {o}" for o in observations) + "\n")
    if problems:
        lines.append("## Problems found while building\n" + "\n".join(f"- {p}" for p in problems))
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(rows)} cases -> {out}")
    print(dict(strata))
    print("observations (system serves a trap):", len(observations))
    for o in observations:
        print("  ", o)
    print("problems:", len(problems))
    for p in problems:
        print("  ", p)
    return 0 if not problems else 1
