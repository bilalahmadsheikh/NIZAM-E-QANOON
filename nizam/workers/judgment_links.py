"""Link released judgments to the law they cite and the cases they cite (docs/PRECEDENT-MODEL.md §4, D-119).

    uv run python -m nizam.workers.judgment_links [--rebuild] [--apply]

`judgment_statute_reference` and `judgment_case_reference` are derived tables, rebuilt from the released judgments
by one named linker (LINKER), as provision_reference is from the release (D-108). An ordinary run links the
judgments not yet linked by this linker; --rebuild relinks all. Without --apply nothing is written.

For each body or footnote paragraph:
1. **The provisions it names.** The citation grammar is nizam.storage.citations, the same one retrieval uses
   (D-097). A named law is resolved by its recorded title or alias, and the unit by its printed label, descending
   into the sub-section the citation names.
   - The version linked is the one in force on the decision date: the text the court read. When the corpus does
     not hold the text on that date (the law is served only from its capture, `text_known_from`), the unit is
     linked with version_basis 'not_dated' and no version.
   - Role: charge, challenged or interpreted from the words around the citation; 'quoted' when a quotation printed
     after it is found in the unit's own words.
2. **The cases it cites.** Reporter references are kept as identifiers ('not_held': no reporter index is held). A
   case number resolves to the case (judicial_case, D-125) when this court's case of that type, number and year is
   held, however many judgments it has; dst_judgment_id is set too when the case holds one decision (a second copy
   aside). A judgment citing a case it decides itself is 'own_case'. /1 matched judgment rows by the header parser's
   number and year, and called a case with several orders 'ambiguous'.

Run after nizam.workers.judgment_cases, whose cases this reads.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import sys
import time

from nizam.corpus.judgment import fold
from nizam.storage.case_key import case_key
from nizam.storage import citations as C
from nizam.storage import judgment_linking as JL
from nizam.storage import unit_search
from nizam.storage.db import connect
from nizam.storage.lexical import Filters

# /2 case citations to cases (D-125); /3 the deciding court's territory (D-128); /4 a title stops at its sentence's end
# or the next citation, trailing parentheses dropped, reviewed law aliases (law_alias); /5 a law is inherited only by a
# bare citation or one naming the same kind of law (D-134); /6 'of the Act.' refers back too, by kind and year, and
# is never remembered as a law (D-135); /7 a High Court's citation of a federal law is linked to the territory's copy
# too, and every copy only where its unit is the same provision (D-136)
LINKER = "nizam.judgment_links/7"


def _todo(cur, rebuild: bool) -> list[tuple]:
    cur.execute("""SELECT j.id, j.decided_on, j.court_code, j.decided_on_basis = 'undated' FROM v_release_judgment j
                    WHERE %s OR NOT EXISTS (SELECT 1 FROM judgment_link_state s
                                            WHERE s.judgment_id = j.id AND s.decided_on = j.decided_on
                                              AND s.linker = %s)
                    ORDER BY j.decided_on, j.id""", (rebuild, LINKER))
    return cur.fetchall()


def _case_types(cur) -> dict[str, list[tuple[str, str]]]:
    cur.execute("SELECT court_code, code, printed_forms FROM case_type")
    out = collections.defaultdict(list)
    for court, code, forms in cur.fetchall():
        for f in forms:
            out[court].append((f, code))
    for v in out.values():
        v.sort(key=lambda x: -len(x[0]))
    return out


class CaseIndex:
    """The held cases (D-125): case key -> the decisions shown in it; judgment -> the cases it decides."""

    def __init__(self, cur):
        cur.execute("SELECT case_key FROM judicial_case")
        self.decisions: dict[str, list] = {k: [] for (k,) in cur.fetchall()}
        cur.execute("""SELECT c.case_key, c.judgment_id FROM judgment_case c
                         JOIN v_shown_judgment j ON j.id = c.judgment_id AND j.decided_on = c.decided_on""")
        self.own: dict = collections.defaultdict(set)
        for key, jid in cur.fetchall():
            self.decisions[key].append(jid)
        cur.execute("SELECT case_key, judgment_id FROM judgment_case")
        for key, jid in cur.fetchall():
            self.own[jid].add(key)                      # a second copy still decides its case

    def resolve(self, jid, court: str, code: str, number: str, year: int) -> tuple[str | None, object, str]:
        """(case key, the case's one decision or None, resolution)."""
        key = case_key(court, code, number, year)
        if key in self.own.get(jid, ()):
            return key, None, "own_case"
        if key not in self.decisions:
            return None, None, "not_held"
        one = self.decisions[key]
        return key, (one[0] if len(one) == 1 else None), "resolved"


class Resolver:
    """Citation -> (unit, law title, alternates), cached per (law, label, subs); versions cached per (unit, day).

    One per deciding court's territory (D-128): a bare title in a Lahore High Court judgment ('the Rented Premises
    Act') resolves to Punjab's law first, then federal law, and the version linked is the one in force in Punjab on
    the decision date. A Supreme Court judgment reads federal law first and no territory."""

    def __init__(self, cur, territory: str | None = None):
        self.cur = cur
        self.territory = territory
        self.session = unit_search.Session(cur, Filters(as_of=dt.date.today()),
                                           prefer=(territory, "fed") if territory else ("fed",))
        self.units: dict[tuple, C.Citation] = {}
        self.versions: dict[tuple, str | None] = {}
        self.texts: dict[str, str] = {}
        self.pairs: dict[tuple, bool] = {}

    def resolve(self, c: JL.StatuteCitation) -> C.Citation:
        key = (c.law, c.label, tuple(c.subs))
        if key not in self.units:
            r = C.resolve(self.session, C.Citation(c.raw, c.label, list(c.subs), c.law),
                          copies_in=(self.territory,) if self.territory else None)
            if r.resolved_unit and r.alternates:
                # a copy is linked only in federal law and the court's own territory (a Lahore judgment is not
                # filed under AJK's Contract Act), and only where its unit is the same provision as the one
                # resolved: Punjab's copy of the PPC prints a prize-bond offence as s.489-F, not cheque dishonour
                # (D-136)
                allowed = {"fed", self.territory} if self.territory else {"fed"}
                self.cur.execute("""SELECT p.id::text, i.jurisdiction::text FROM provision p
                                      JOIN instrument i ON i.id = p.instrument_id WHERE p.id = ANY(%s::uuid[])""",
                                 ([u.unit_id for u in r.alternates],))
                where = dict(self.cur.fetchall())
                keep = [(t, u) for t, u in zip(r.alternate_laws, r.alternates)
                        if where.get(u.unit_id) in allowed
                        and self.same_provision(r.resolved_unit.unit_id, u.unit_id)]
                r.alternate_laws, r.alternates = [t for t, _u in keep], [u for _t, u in keep]
            self.units[key] = r
        return self.units[key]

    def same_provision(self, a: str, b: str) -> bool:
        """Two copies' units are one provision when their headings agree, or (no heading on either) their words do:
        JL.same_provision over the headings and the folded text of each unit and its sub-units."""
        if (a, b) not in self.pairs:
            self.cur.execute("""SELECT id::text, coalesce(heading, ''), lower(replace(coalesce(label, ''), '-', ''))
                                  FROM provision WHERE id = ANY(%s::uuid[])""", ([a, b],))
            info = {r[0]: r[1:] for r in self.cur.fetchall()}
            (ha, la), (hb, lb) = info.get(a, ("", "?")), info.get(b, ("", "!"))
            # the same label, at the same depth ('295A' and '295-A' alike), then the same provision by its words
            self.pairs[(a, b)] = la.replace(" ", "") == lb.replace(" ", "") and JL.same_provision(
                ha, hb, self.unit_text(a), self.unit_text(b))
        return self.pairs[(a, b)]

    def version_on(self, unit: "unit_search.Unit", day: dt.date) -> tuple[str | None, bool]:
        """(the unit's own served version on `day`, whether the unit or a unit inside it is served on `day`).

        Read through operative_provision as at the decision date (INV-5), never the base table: a law's held text
        is served before its capture date where its text_known_from allows (0096-0099). The version rows alone
        would call every such citation undated. A heading-only unit (Art. 189: its words are in its clauses) has no
        version of its own, and is dated through its clauses."""
        key = (unit.unit_id, day)
        if key not in self.versions:
            self.cur.execute("SELECT set_config('nzq.as_of', %s, true), set_config('nzq.territory', %s, true)",
                             (day.isoformat(), self.territory or ""))
            self.cur.execute("""SELECT op.version_id::text, op.provision_id = %s::uuid FROM operative_provision op
                                 WHERE op.instrument_id = %s::uuid AND op.path <@ %s::ltree
                                 ORDER BY op.provision_id = %s::uuid DESC, op.path LIMIT 1""",
                             (unit.unit_id, unit.instrument_id, unit.path, unit.unit_id))
            r = self.cur.fetchone()
            self.versions[key] = ((r[0] if r[1] else None), True) if r else (None, False)
        return self.versions[key]

    def unit_text(self, unit_id: str) -> str:
        if unit_id not in self.texts:
            self.cur.execute("""SELECT string_agg(v.text_normalised, ' ' ORDER BY c.ordinal)
                                  FROM provision p JOIN provision c ON c.instrument_id = p.instrument_id
                                                                  AND c.path <@ p.path AND c.is_active
                                  JOIN provision_version v ON v.provision_id = c.id
                                 WHERE p.id = %s""", (unit_id,))
            self.texts[unit_id] = fold(self.cur.fetchone()[0] or "")
        return self.texts[unit_id]


def link_one(cur, res: Resolver, types, jid, day, court, undated: bool = False,
             cases: CaseIndex | None = None) -> tuple[list, list]:
    """`undated` (D-124): `day` is only the latest possible decision day, so no version is claimed as the text the
    court read; the unit is linked 'not_dated'."""
    cur.execute("""SELECT id, text FROM judgment_paragraph WHERE judgment_id = %s AND decided_on = %s
                     AND kind IN ('body', 'footnote') ORDER BY ordinal""", (jid, day))
    statute_rows, case_rows = [], []
    last_law: dict[str, tuple[str, str]] = {}       # unit word -> (law, the citation that named it)
    for pid, text in cur.fetchall():
        for c in JL.statute_citations(text):
            word = "article" if c.raw.lower().startswith("art") else "section"
            law_basis, inherited_from = "named", None
            back = JL.back_reference(c.law)
            if c.law and not back:
                last_law[word] = (c.law, c.raw)
            elif word in last_law and JL.may_inherit(back[0] if back else c.named, last_law[word][0],
                                                     back[1] if back else None):
                # 'of the Act.' refers back to a law named earlier: it is not a name to remember, and it takes the
                # last-named law only when that law is of its kind and year (D-135)
                # a bare citation takes the law this judgment last named for this kind of unit (0121); one that names
                # a kind of law ('of the Ordinance') takes it only when that law is of the kind, and one that names
                # something that is not a law ('of the Hisba Bill') takes none (D-134)
                c = JL.StatuteCitation(c.start, c.end, c.raw, c.label, c.subs, last_law[word][0], c.role)
                law_basis, inherited_from = "inherited", last_law[word][1][:300]
            r = res.resolve(c)
            role = c.role
            dst_unit = r.resolved_unit.unit_id if r.resolved_unit else None
            dst_inst = r.resolved_unit.instrument_id if r.resolved_unit else None
            version = basis = None
            if dst_unit:
                if undated:
                    version, basis = None, "not_dated"
                else:
                    version, served = res.version_on(r.resolved_unit, day)
                    basis = "dated" if served else "not_dated"
                q = JL.quotation_after(text, c.end)
                if q and fold(q)[:120] and fold(q)[:120] in res.unit_text(dst_unit):
                    role = "quoted"
                resolution = "resolved"
            elif not c.law or (r.unresolved or "").startswith("no law named"):
                resolution = "no_law_named"                 # none printed, or only a kind of law (D-127)
            elif r.unresolved and r.unresolved.startswith("no served law"):
                resolution = "law_not_held"
            else:
                resolution = "unit_not_found"
            alternates = [u.unit_id for u in (r.alternates or [])]
            statute_rows.append((pid, day, jid, c.start, c.end, c.raw[:500], c.label, c.subs,
                                 (c.law if c.law not in C.ALIASES else None),
                                 (c.law if c.law in C.ALIASES else r.via_alias),     # a code or a reviewed alias
                                 dst_inst, dst_unit, version, basis, resolution, alternates, role, LINKER,
                                 law_basis, inherited_from))
        for k in JL.case_citations(text):
            dst, dst_case, resolution = None, None, "not_held"
            if k.case_type and cases is not None:
                code = next((cd for f, cd in types.get(court, []) if fold(k.case_type).startswith(f)), None)
                if code and k.case_number and k.case_year:
                    dst_case, dst, resolution = cases.resolve(jid, court, code, k.case_number, k.case_year)
            case_rows.append((pid, day, jid, k.start, k.end, k.raw[:300], k.series, k.year, k.court, k.page,
                              (f"{k.case_type} {k.case_number}/{k.case_year}" if k.case_type else None), dst,
                              resolution, LINKER, dst_case))
    return statute_rows, case_rows


def main() -> int:
    ap = argparse.ArgumentParser(description="link judgments to statutes and cases (D-119)")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    t0 = time.time()
    totals = collections.Counter()
    with connect() as conn, conn.cursor() as cur:
        todo = _todo(cur, a.rebuild)[: a.limit or None]
        types = _case_types(cur)
        cur.execute("SELECT code, territory::text FROM court")
        territory = {code: (None if j in (None, "fed") else j) for code, j in cur.fetchall()}
        resolvers: dict = {}
        cases = CaseIndex(cur)
        print(f"judgments to link: {len(todo)} ({LINKER}; {len(cases.decisions):,} cases held)")
        for n, (jid, day, court, undated) in enumerate(todo, 1):
            t = territory.get(court)
            res = resolvers.get(t) or resolvers.setdefault(t, Resolver(cur, t))
            srows, crows = link_one(cur, res, types, jid, day, court, undated, cases)
            for r in srows:
                totals[f"statute:{r[14]}"] += 1
                totals[f"role:{r[16]}"] += 1
                if r[13] == "not_dated":
                    totals["version:not_dated"] += 1
            for r in crows:
                totals[f"case:{r[12]}"] += 1
            if a.apply:
                cur.execute("DELETE FROM judgment_statute_reference WHERE judgment_id = %s", (jid,))
                cur.execute("DELETE FROM judgment_case_reference WHERE judgment_id = %s", (jid,))
                if srows:
                    with cur.copy("COPY judgment_statute_reference (paragraph_id, decided_on, judgment_id, "
                                  "char_start, char_end, raw, label, subs, law_printed, alias, dst_instrument_id, "
                                  "dst_provision_id, dst_version_id, version_basis, resolution, alternates, role, "
                                  "linker, law_basis, inherited_from) FROM STDIN") as cp:
                        for r in srows:
                            cp.write_row(r)
                if crows:
                    with cur.copy("COPY judgment_case_reference (paragraph_id, decided_on, judgment_id, char_start, "
                                  "char_end, raw, reporter_series, reporter_year, reporter_court, reporter_page, "
                                  "case_printed, dst_judgment_id, resolution, linker, dst_case_key) "
                                  "FROM STDIN") as cp:
                        for r in crows:
                            cp.write_row(r)
                cur.execute("""INSERT INTO judgment_link_state (judgment_id, decided_on, linker) VALUES (%s,%s,%s)
                               ON CONFLICT (judgment_id, decided_on) DO UPDATE SET linker = EXCLUDED.linker,
                                                                                   linked_at = now()""",
                            (jid, day, LINKER))
                if n % 100 == 0:
                    conn.commit()
            if n % 250 == 0:
                print(f"  {n}/{len(todo)} {time.time() - t0:.0f}s", flush=True)
        if not a.apply:
            conn.rollback()
    for k in sorted(totals):
        print(f"  {k:28} {totals[k]:>8,}")
    print(f"done in {time.time() - t0:.0f}s" + ("" if a.apply else " (dry run: nothing written; add --apply)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
