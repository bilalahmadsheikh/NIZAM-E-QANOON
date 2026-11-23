"""Shared builder for the precedent stratum of golden-pk-v1 (D-133; docs/10 §5 LegalEvalCase; docs/PRECEDENT-MODEL §6).

A precedent case names judgment paragraphs, not provisions. Each gold unit is a released judgment found by its
source document id (stable across replays; judgment ids are not) and, inside it, one paragraph by its printed number
("6") or, where none is printed, its ordinal ("#12"). A unit of None names the judgment as a whole (a case lookup:
any of its paragraphs answers). Court, case as printed, decision date, case keys and the paragraph text are read
from the database, never typed (INV-1). Labels end at judgment paragraphs, never chunks (INV-4, docs/10).

Each case is checked:
  * every necessary and relevant judgment resolves to exactly one released judgment and paragraph;
  * every necessary judgment existed at the case's as_of: decided on or before it, or, if undated (D-124), its latest
    possible day of decision is on or before it (INV-5: the research date, PRECEDENT-MODEL §3);
  * every judgment in must_not_serve did NOT exist at as_of (a later decision is a trap, never gold);
  * every regex in `check` matches the necessary paragraphs' text, so what the propositions say is what the court
    said;
  * the author's expected binding status for the forum (Arts. 189 and 201, read by the author) is compared with the
    recorded authority rules (nizam.storage.authority, D-116). A difference is reported, not failed: the gold is the
    author's reading until the legal review (A1/A2);
  * an abstain case's code is checked against the release: `court_not_held` needs no released judgment of that
    court, `before_coverage` none in existence at as_of;
  * family ids are unique to this file among the golden sets (families are the split unit, docs/10 §4).

Stage A0 + A3 only. The gold was found by reading judgments selected by plain SQL text match
(evals/golden/peek_judgment.py), never by the precedent search it measures. It is incomplete by nature: many
judgments state a settled principle, and the gold names some of them. The harness (evals/precedent_eval.py)
therefore reports whether a gold judgment is found, not precision.
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
GOLDEN = ROOT / "evals/golden"
DEFAULT_AS_OF = "2026-11-24"
SUPREME = {"SC"}
HIGH_COURT_TERRITORY = {"LHC": "punjab", "PHC": "kp", "SHC": "sindh", "BHC": "balochistan", "IHC": "ict"}


def expected_status(court: str, forum_territory: str | None) -> str | None:
    """The author's reading, for a court subordinate to a High Court in `forum_territory`: Art. 189 binds every court
    to the Supreme Court; Art. 201 binds a High Court's subordinate courts to it, and no other court."""
    if forum_territory is None:
        return None
    if court in SUPREME:
        return "binding"
    return "binding" if HIGH_COURT_TERRITORY.get(court) == forum_territory else "not_binding"


class PrecedentSet:
    def __init__(self, name: str):
        self.name = name
        self.cases: list[dict] = []

    def case(self, cid, stratum, family, risk, lang, script, text, meaning, forum_territory, outcome, props,
             necessary=(), relevant=(), must_not_serve=(), abstention=None, check=(), as_of=DEFAULT_AS_OF,
             task="precedent"):
        """necessary/relevant: (document_id, paragraph-or-None, grade). must_not_serve: document ids of judgments
        that did not exist at as_of. forum_territory: the question is asked for a court subordinate to that
        territory's High Court (docs/10 scope.authorityPerspective); None asks no authority question."""
        if any(c["cid"] == cid for c in self.cases):
            raise ValueError(f"duplicate case id {cid}")
        self.cases.append(dict(cid=cid, stratum=stratum, family=family, risk=risk, lang=lang, script=script,
                               text=text, meaning=meaning, forum=forum_territory, outcome=outcome, props=list(props),
                               necessary=list(necessary), relevant=list(relevant),
                               must_not_serve=list(must_not_serve), abstention=abstention, check=list(check),
                               as_of=as_of, task=task))


def _judgment(cur, doc: int):
    cur.execute("""SELECT j.id, j.decided_on, j.court_code, j.case_no_printed, j.decision_date, j.decided_on_basis,
                          j.reported_flag,
                          coalesce((SELECT array_agg(c.case_key ORDER BY c.case_key) FROM judgment_case c
                                     WHERE c.judgment_id = j.id AND c.decided_on = j.decided_on), '{}')
                     FROM v_release_judgment j WHERE j.document_id = %s""", (doc,))
    rows = cur.fetchall()
    return rows[0] if len(rows) == 1 else None


def resolve(cur, doc: int, ref: str | None, chars: int = 400) -> dict | None:
    j = _judgment(cur, doc)
    if j is None:
        return None
    jid, decided_on, court, case, day, basis, reported, keys = j
    unit = dict(judgmentDocumentId=doc, judgmentId=str(jid), court=court, caseNoPrinted=case,
                decisionDate=day.isoformat() if day else None, undated=basis == "undated",
                existsFrom=decided_on.isoformat(), reported=reported, caseKeys=list(keys), paragraph=ref)
    if ref is None:
        cur.execute("""SELECT string_agg(text, ' ' ORDER BY ordinal) FROM v_release_judgment_paragraph
                        WHERE judgment_id = %s AND decided_on = %s AND kind = 'body'""", (jid, decided_on))
        text = cur.fetchone()[0] or ""
        unit.update(paragraphId=None, printedNo=None, ordinal=None)
    else:
        col, val = ("ordinal", int(ref[1:])) if ref.startswith("#") else ("printed_no", ref)
        cur.execute(f"""SELECT id, printed_no, ordinal, text FROM v_release_judgment_paragraph
                         WHERE judgment_id = %s AND decided_on = %s AND kind = 'body' AND {col} = %s
                         ORDER BY ordinal""", (jid, decided_on, val))
        rows = cur.fetchall()
        if len(rows) != 1:     # none, or a printed number used twice: never guess which paragraph is meant
            return None
        pid, no, ordinal, text = rows[0]
        unit.update(paragraphId=str(pid), printedNo=no, ordinal=ordinal)
    text = " ".join(text.split())
    unit.update(textSha256=hashlib.sha256(text.encode()).hexdigest(), excerpt=text[:chars])
    unit["_full"] = text
    return unit


def system_status(cur, registry, court: str, forum_territory: str | None, as_of: str) -> str | None:
    if forum_territory is None:
        return None
    from nizam.storage import authority as A
    courts, rules, sup = registry
    r = A.authority(court, A.Subordinate(forum_territory), date.fromisoformat(as_of), courts=courts, rules=rules,
                    superintendence=sup)
    return {A.Binding: "binding", A.NotBinding: "not_binding"}.get(type(r), "not_recorded")


def other_set_families(name: str) -> dict[str, str]:
    seen = {}
    for p in sorted(GOLDEN.glob("golden-pk-v1-*.draft.jsonl")):
        if p.name == f"golden-pk-v1-{name}.draft.jsonl":
            continue
        for line in p.open(encoding="utf-8"):
            if line.strip():
                seen[json.loads(line)["familyId"]] = p.name
    return seen


def build(ps: PrecedentSet, title_note: str) -> int:
    from nizam.storage import authority as A
    from nizam.storage.db import connect
    out = GOLDEN / f"golden-pk-v1-{ps.name}.draft.jsonl"
    report = GOLDEN / f"golden-pk-v1-{ps.name}.draft.md"
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    problems, observations, rows = [], [], []
    foreign = other_set_families(ps.name)
    for c in ps.cases:
        if c["family"] in foreign:
            problems.append(f"{c['cid']}: family {c['family']} already used in {foreign[c['family']]}")
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET statement_timeout = 0")
        registry = A.load(cur)
        for c in ps.cases:
            units, full = {}, []
            for kind in ("necessary", "relevant"):
                units[kind] = []
                for doc, ref, grade in c[kind]:
                    u = resolve(cur, doc, ref)
                    if u is None:
                        problems.append(f"{c['cid']}: {kind} judgment {doc} para {ref} does not resolve"); continue
                    u["grade"] = grade
                    u["existsAtAsOf"] = u["existsFrom"] <= c["as_of"]
                    u["expectedAuthority"] = expected_status(u["court"], c["forum"])
                    sys_status = system_status(cur, registry, u["court"], c["forum"], c["as_of"])
                    if u["expectedAuthority"] and sys_status != u["expectedAuthority"]:
                        observations.append(f"{c['cid']}: {u['court']} judgment {doc} for a court subordinate in "
                                            f"{c['forum']}: the author reads {u['expectedAuthority']}, the recorded "
                                            f"rules give {sys_status}")
                    if kind == "necessary":
                        full.append(u.pop("_full"))
                        if c["outcome"] != "abstain" and not u["existsAtAsOf"]:
                            problems.append(f"{c['cid']}: necessary judgment {doc} did not exist at {c['as_of']} "
                                            f"(exists from {u['existsFrom']})")
                    u.pop("_full", None)
                    units[kind].append(u)
            negatives = []
            for doc in c["must_not_serve"]:
                u = resolve(cur, doc, None)
                if u is None:
                    problems.append(f"{c['cid']}: trap judgment {doc} does not resolve"); continue
                u.pop("_full")
                u.update(grade=0, existsAtAsOf=u["existsFrom"] <= c["as_of"], reason="decided after as_of")
                if u["existsAtAsOf"]:
                    problems.append(f"{c['cid']}: trap judgment {doc} existed at {c['as_of']}; it cannot be a trap")
                negatives.append(u)
            blob = " ".join(full)
            for rx in c["check"]:
                if not re.search(rx, blob, re.I):
                    problems.append(f"{c['cid']}: check /{rx}/ not found in the necessary paragraphs")
            if c["outcome"] != "abstain":
                if not units["necessary"]:
                    problems.append(f"{c['cid']}: an answer case with no necessary judgment")
                if not c["check"]:
                    problems.append(f"{c['cid']}: an answer case with no text check")
            else:
                code = (c["abstention"] or {}).get("code")
                if code == "court_not_held":
                    cur.execute("SELECT count(*) FROM v_release_judgment WHERE court_code = %s",
                                (c["abstention"]["court"],))
                    if cur.fetchone()[0]:
                        problems.append(f"{c['cid']}: {c['abstention']['court']} judgments ARE held")
                elif code == "before_coverage":
                    cur.execute("SELECT count(*) FROM v_release_judgment WHERE decided_on <= %s", (c["as_of"],))
                    if cur.fetchone()[0]:
                        problems.append(f"{c['cid']}: judgments exist at {c['as_of']}; not before coverage")
                else:
                    problems.append(f"{c['cid']}: unknown abstention code {code}")
            rows.append({
                "caseId": c["cid"], "datasetVersion": f"golden-pk-v1-draft/{ps.name}", "familyId": c["family"],
                "riskClass": c["risk"], "languages": c["lang"], "stratum": c["stratum"], "task": c["task"],
                "question": {"text": c["text"], "script": c["script"], "intendedMeaning": c["meaning"],
                             "suppliedFacts": [], "omittedFacts": []},
                "scope": {"jurisdiction": "fed", "territory": c["forum"], "asOf": c["as_of"],
                          "forum": f"subordinate:{c['forum']}" if c["forum"] else None,
                          "authorityPerspective": "court subordinate to the High Court" if c["forum"] else None},
                "expectedOutcome": c["outcome"],
                "propositions": [{"id": f"{c['cid']}-p{i + 1}", "text": t, "materiality": "material",
                                  "necessaryEvidence": [u["paragraphId"] or u["judgmentId"]
                                                        for u in units["necessary"]]}
                                 for i, t in enumerate(c["props"])],
                "precedentGold": {"necessaryJudgments": units["necessary"], "relevantJudgments": units["relevant"],
                                  "hardNegatives": negatives},
                "abstention": c["abstention"],
                "textChecks": c["check"],
                "provenance": {"corpusRevision": rev, "labelledAt": date.today().isoformat(),
                               "foundBy": "plain SQL text match and reading (peek_judgment.py), not L3"},
                "review": {"annotatorA": "claude (draft: A0 authoring + A3 identity resolution)", "annotatorB": None,
                           "agreement": None, "adjudicator": None, "reasons": [],
                           "status": "draft — not gold until A1/A2 (two legal annotators, senior advocate)"},
            })
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    strata = Counter(r["stratum"] for r in rows)
    lines = [f"# golden-pk-v1 — draft {ps.name} ({len(rows)} cases)\n", title_note + "\n",
             f"Corpus revision {rev}. Strata: " + ", ".join(f"{k} {v}" for k, v in strata.items()) + ".",
             "Status: **draft** — A0 authoring and A3 identity resolution only. Not gold until two legal annotators "
             "(A1) and a senior advocate (A2) have reviewed it; do not tune or report on it before then.\n"]
    for r in rows:
        q, s = r["question"], r["scope"]
        lines.append(f"## {r['caseId']} · {r['stratum']} · forum {s['forum'] or '-'} · as of {s['asOf']} · "
                     f"expect **{r['expectedOutcome']}**\n")
        lines.append(f"**Q:** {q['text']}\n")
        for p in r["propositions"]:
            lines.append(f"- *Proposition:* {p['text']}")
        for kind, label in (("necessaryJudgments", "Necessary"), ("relevantJudgments", "Relevant"),
                            ("hardNegatives", "Must not be served")):
            for u in r["precedentGold"][kind]:
                where = f"para {u['printedNo'] or '#' + str(u['ordinal'])}" if u["paragraph"] else "whole judgment"
                day = u["decisionDate"] or f"undated, exists from {u['existsFrom']}"
                auth = f" · expected {u['expectedAuthority']}" if u.get("expectedAuthority") else ""
                lines.append(f"- **{label} (grade {u['grade']})** — {u['court']} {u['caseNoPrinted']} ({day}), "
                             f"{where} · doc {u['judgmentDocumentId']}{auth}\n  > {u['excerpt'][:260]}")
        if r["abstention"]:
            lines.append(f"- *Abstain:* {r['abstention']['code']} — {r['abstention']['why']}")
        lines.append("")
    if observations:
        lines.append("## Where the author's authority reading and the recorded rules differ\n\n"
                     + "\n".join(f"- {o}" for o in observations) + "\n")
    if problems:
        lines.append("## Problems found while building\n" + "\n".join(f"- {p}" for p in problems))
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(rows)} cases -> {out}")
    print(dict(strata))
    print("authority differences:", len(observations))
    for o in observations:
        print("  ", o)
    print("problems:", len(problems))
    for p in problems:
        print("  ", p)
    return 0 if not problems else 1
