"""The law-alias review sheet (D-134; PRECEDENT-MODEL §4.1: aliases grow only from evidence a person reads).

    python tools/alias_review.py build [--min-judgments 3 --min-citations 10]
        reads every judgment citation whose law is not held, re-reads it under today's grammar, and writes
        docs/alias-review/law-aliases-<date>.csv (one row per printed name still unmatched, with counts, printed forms,
        three passages to read and up to three candidate laws) and a summary .md beside it. Nothing is written to the
        database.
    python tools/alias_review.py load docs/alias-review/law-aliases-<date>.csv --reviewer NAME [--apply]
        writes the rows decided 'alias' into law_alias, after checking each against the corpus: the target document
        holds exactly one active law; its title, searched as the resolver searches, finds that law first in its
        jurisdiction; a year printed in the name is the year in its title; every evidence passage is a released
        paragraph that prints one of the forms. A row already loaded is left alone; a changed decision withdraws the
        old row with a reason and adds the new one.

A reviewer fills four columns for each row: `decision` (alias, not_held, foreign, historical, ambiguous,
not_a_law), `target_document_id` (for alias), `basis` (abbreviation, spelling, former_name, short_name) and
`reviewer_note` (what was read). Only 'alias' rows reach the database; the others are kept on the sheet as the reason
the citation stays unresolved.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nizam.storage import citations as C            # noqa: E402
from nizam.storage import unit_search               # noqa: E402
from nizam.storage.db import connect                # noqa: E402
from nizam.storage.lexical import Filters           # noqa: E402

OUT_DIR = ROOT / "docs/alias-review"
COLUMNS = ["alias_key", "citations", "judgments", "courts", "printed_forms", "evidence", "passages",
           "candidates", "decision", "target_document_id", "basis", "reviewer_note"]
DECISIONS = {"alias", "not_held", "foreign", "historical", "ambiguous", "not_a_law"}
BASES = {"abbreviation", "spelling", "former_name", "short_name"}
_ACRONYM = re.compile(r"^[A-Z][A-Z.\-]{1,8}$")


def _initials(title: str) -> str:
    words = re.findall(r"[A-Za-z]+", re.sub(r"\([^)]*\)", " ", title))
    return "".join(w[0] for w in words if w.lower() not in ("of", "the", "and", "for", "in", "on", "to")).upper()


def _candidates(cur, key: str, printed: str, titles) -> list[dict]:
    """Up to three laws the printed name may mean: by initials (an acronym such as ITO or PEEDA), then by trigram
    similarity of the folded name to the folded title. A suggestion for the reader, never a decision."""
    year = (C._YEAR.findall(printed) or [None])[-1]
    head = printed.split()[0].strip(",") if printed.split() else ""
    out = []
    if _ACRONYM.match(head):
        letters = re.sub(r"[^A-Z]", "", head)
        for doc, title, jur, served in titles:
            ini = _initials(title)
            if ini.startswith(letters) and (year is None or year in title) and len(letters) >= 2:
                out.append(dict(document_id=doc, title=title, jurisdiction=jur, served=served, by="initials"))
    cur.execute("""SELECT i.document_id, coalesce(nullif(i.display_title, ''), i.short_title), i.jurisdiction::text,
                          EXISTS (SELECT 1 FROM mv_instrument_serving m WHERE m.instrument_id = i.id),
                          similarity(lower(coalesce(nullif(i.display_title, ''), i.short_title)), %s) AS s
                     FROM instrument i WHERE i.is_active AND i.duplicate_of IS NULL
                      AND lower(coalesce(nullif(i.display_title, ''), i.short_title)) %% %s
                    ORDER BY s DESC LIMIT 5""", (key, key))
    for doc, title, jur, served, s in cur.fetchall():
        if year and not (year in title or not C._YEAR.findall(title)):
            continue
        out.append(dict(document_id=doc, title=title, jurisdiction=jur, served=served, by=f"trigram {s:.2f}"))
    seen, best = set(), []
    for c in sorted(out, key=lambda c: (not c["served"], c["by"] != "initials")):
        if c["document_id"] not in seen:
            seen.add(c["document_id"]); best.append(c)
    return best[:3]


def _decided_keys() -> set[str]:
    """Names already decided on an earlier sheet: never put on a new one."""
    keys = set()
    for p in sorted(OUT_DIR.glob("law-aliases-*.csv")):
        keys |= {r["alias_key"] for r in csv.DictReader(p.open(encoding="utf-8")) if r.get("decision", "").strip()}
    return keys


def build(min_judgments: int, min_citations: int, name: str | None = None) -> int:
    today = dt.date.today().isoformat()
    decided = _decided_keys()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET statement_timeout = 0")
        cur.execute("""SELECT r.raw, r.paragraph_id::text, r.decided_on, r.char_start, r.char_end, r.judgment_id::text,
                              j.court_code, c.territory::text
                         FROM judgment_statute_reference r
                         JOIN v_release_judgment j ON j.id = r.judgment_id AND j.decided_on = r.decided_on
                         JOIN court c ON c.code = j.court_code
                        WHERE r.resolution = 'law_not_held'""")
        rows = cur.fetchall()
        sessions = {}
        outcome = collections.Counter()
        groups: dict[str, dict] = {}
        resolved_cache: dict = {}
        for raw, pid, day, s, e, jid, court, terr in rows:
            found = C.find(raw)
            law = found[0].law if found else None
            if not law or C._KIND_ONLY.match(law):
                outcome["names only a kind of law under today's grammar (no_law_named)"] += 1; continue
            if law in C.ALIASES:
                outcome["a code alias matches under today's grammar"] += 1; continue
            t = None if terr in (None, "fed") else terr
            ses = sessions.get(t) or sessions.setdefault(t, unit_search.Session(
                cur, Filters(as_of=dt.date.today()), prefer=(t, "fed") if t else ("fed",)))
            ck = (law, t)
            if ck not in resolved_cache:
                r = C.resolve(ses, C.Citation(raw, found[0].label, [], law))
                resolved_cache[ck] = not (r.unresolved or "").startswith("no served law")
            if resolved_cache[ck]:
                outcome["its title is found under today's grammar"] += 1; continue
            outcome["still unmatched"] += 1
            g = groups.setdefault(C.law_key(law), dict(citations=0, judgments=set(), courts=set(),
                                                       forms=collections.Counter(), evidence=[]))
            g["citations"] += 1
            g["judgments"].add(jid)
            g["courts"].add(court)
            g["forms"][law] += 1
            if len(g["evidence"]) < 3 and jid not in {x[4] for x in g["evidence"]}:
                g["evidence"].append((pid, day, s, e, jid, raw))
        cur.execute("""SELECT i.document_id, coalesce(nullif(i.display_title, ''), i.short_title), i.jurisdiction::text,
                              EXISTS (SELECT 1 FROM mv_instrument_serving m WHERE m.instrument_id = i.id)
                         FROM instrument i WHERE i.is_active AND i.duplicate_of IS NULL""")
        titles = cur.fetchall()
        sheet, tail = [], collections.Counter()
        for key, g in sorted(groups.items(), key=lambda kv: (-len(kv[1]["judgments"]), -kv[1]["citations"])):
            if key in decided:
                tail["already decided on an earlier sheet"] += 1; continue
            if len(g["judgments"]) < min_judgments and g["citations"] < min_citations:
                tail["names"] += 1; tail["citations"] += g["citations"]; continue
            passages = []
            for pid, day, s, e, jid, raw in g["evidence"]:
                cur.execute("SELECT text FROM judgment_paragraph WHERE id = %s AND decided_on = %s", (pid, day))
                text = cur.fetchone()[0]
                passages.append(" ".join(text[max(0, s - 160):e + 160].split()))
            printed = g["forms"].most_common(1)[0][0]
            sheet.append(dict(
                alias_key=key, citations=g["citations"], judgments=len(g["judgments"]),
                courts=",".join(sorted(g["courts"])),
                printed_forms=" | ".join(f for f, _n in g["forms"].most_common(5)),
                evidence=json.dumps([dict(paragraph_id=p, decided_on=d.isoformat(), raw=r)
                                     for p, d, _s, _e, _j, r in g["evidence"]], ensure_ascii=False),
                passages=" ||| ".join(passages),
                candidates=" | ".join(f"{c['document_id']}: {c['title']} [{c['jurisdiction']}"
                                      f"{'' if c['served'] else ', not served'}; {c['by']}]"
                                      for c in _candidates(cur, key, printed, titles)),
                decision="", target_document_id="", basis="", reviewer_note=""))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"law-aliases-{today}{'-' + name if name else ''}.csv"
    if out.exists():
        print(f"{out} exists; a filled sheet is never overwritten"); return 1
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(sheet)
    summary = out.with_suffix(".md")
    lines = [f"# Law-alias review sheet, {today} (D-134)\n",
             f"Judgment citations recorded `law_not_held`, re-read under today's grammar: {len(rows):,}.\n",
             "| Outcome | Citations |", "|---|---:|"]
    lines += [f"| {k} | {v:,} |" for k, v in outcome.most_common()]
    lines += ["", f"Rows on the sheet (≥ {min_judgments} judgments or ≥ {min_citations} citations): {len(sheet)}. "
              f"Below that: {tail['names']:,} printed names, {tail['citations']:,} citations, not reviewed. "
              f"Already decided on an earlier sheet: {tail['already decided on an earlier sheet']:,}.", ""]
    summary.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"-> {out}")
    return 0


def load(sheet: Path, reviewer: str, apply: bool) -> int:
    rows = list(csv.DictReader(sheet.open(encoding="utf-8")))
    problems, added, kept, withdrawn = [], 0, 0, 0
    with connect() as conn, conn.cursor() as cur:
        ses = unit_search.Session(cur, Filters(as_of=dt.date.today()))
        cur.execute("SELECT alias_key, document_id, id FROM law_alias WHERE withdrawn_at IS NULL")
        active = {k: (d, i) for k, d, i in cur.fetchall()}
        for r in rows:
            key, decision = r["alias_key"], r["decision"].strip()
            if decision not in DECISIONS:
                problems.append(f"{key}: decision {decision!r} is not one of {sorted(DECISIONS)}"); continue
            if decision != "alias":
                if key in active:
                    problems.append(f"{key}: decided {decision} but an alias is active; withdraw it by hand")
                continue
            if r["basis"] not in BASES:
                problems.append(f"{key}: basis {r['basis']!r} is not one of {sorted(BASES)}"); continue
            if not r["reviewer_note"].strip():
                problems.append(f"{key}: an alias needs a note of what was read"); continue
            doc = int(r["target_document_id"])
            cur.execute("""SELECT id::text, coalesce(nullif(display_title, ''), short_title), jurisdiction::text
                             FROM instrument WHERE document_id = %s AND is_active AND duplicate_of IS NULL""", (doc,))
            inst = cur.fetchall()
            if len(inst) != 1:
                problems.append(f"{key}: document {doc} holds {len(inst)} active laws"); continue
            iid, title, jur = inst[0]
            # the title, searched as the resolver searches it, must find this law first, or a same-titled copy of it
            # (the resolver treats copies as one law, the others its alternates; a compilation document can hold a
            # copy, D-134)
            first = ses.instruments_titled(title, 3, (jur,))
            if not first or C._norm_title(first[0][1]) != C._norm_title(title):
                problems.append(f"{key}: the title {title!r} does not find document {doc}'s law first in {jur}")
                continue
            if C.law_key(title) == key:
                # the name IS the title: an alias would override the title search (and its territory preference)
                # for every correct citation of the law (D-135)
                problems.append(f"{key}: the key is the law's own title folded; not an alias"); continue
            forms = [f.strip() for f in r["printed_forms"].split("|") if f.strip()]
            years = {y for f in forms for y in C._YEAR.findall(f)}
            if years and C._YEAR.findall(title) and not years <= set(C._YEAR.findall(title)):
                problems.append(f"{key}: printed year {sorted(years)} is not the title's ({title!r})"); continue
            evidence = json.loads(r["evidence"])
            for ev in evidence:
                cur.execute("""SELECT text FROM v_release_judgment_paragraph WHERE id = %s AND decided_on = %s""",
                            (ev["paragraph_id"], ev["decided_on"]))
                p = cur.fetchone()
                if not p or ev["raw"] not in p[0]:
                    problems.append(f"{key}: evidence {ev['paragraph_id']} is not a released paragraph printing "
                                    f"{ev['raw']!r}")
            if key in active and active[key][0] == doc:
                kept += 1; continue
            if key in active:
                cur.execute("UPDATE law_alias SET withdrawn_at = now(), withdrawn_reason = %s WHERE id = %s",
                            (f"re-reviewed in {sheet.name}: now document {doc}", active[key][1]))
                withdrawn += 1
            cur.execute("""INSERT INTO law_alias (alias_key, printed_forms, document_id, title_words, jurisdiction, basis,
                                                  evidence, citations_seen, judgments_seen, review_sheet, reviewed_by,
                                                  reviewed_on, note)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (key, forms, doc, title, jur, r["basis"], json.dumps(evidence), int(r["citations"]),
                         int(r["judgments"]), str(sheet.relative_to(ROOT)).replace("\\", "/"), reviewer,
                         dt.date.today(), r["reviewer_note"].strip()))
            added += 1
        if problems or not apply:
            conn.rollback()
        else:
            conn.commit()
    decided = collections.Counter(r["decision"].strip() or "(blank)" for r in rows)
    print(f"rows {len(rows)}: " + ", ".join(f"{k} {v}" for k, v in decided.most_common()))
    print(f"aliases: {added} new, {kept} already loaded, {withdrawn} withdrawn and replaced")
    for p in problems:
        print("  PROBLEM", p)
    print("written" if (apply and not problems) else "nothing written" + ("" if apply else " (dry run; add --apply)"))
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--min-judgments", type=int, default=3)
    b.add_argument("--min-citations", type=int, default=10)
    b.add_argument("--name", help="a suffix for a further sheet of the same day ('tail')")
    lo = sub.add_parser("load")
    lo.add_argument("sheet", type=Path)
    lo.add_argument("--reviewer", required=True)
    lo.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.cmd == "build":
        return build(a.min_judgments, a.min_citations, a.name)
    return load(a.sheet.resolve(), a.reviewer, a.apply)


if __name__ == "__main__":
    sys.exit(main())
