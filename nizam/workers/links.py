"""Build and keep the derived link tables (D-108, migration 0114): what each released provision version defines, and
the units and schedules it names, with the phrase as the docs/03b edge kind.

    python -m nizam.workers.links                 # dry run: what would be rebuilt
    python -m nizam.workers.links --apply         # write (laws whose versions changed, or whose links went stale)
    python -m nizam.workers.links --apply --rebuild   # TRUNCATE and build from nothing (a linker change)
    python -m nizam.workers.links --instruments ID,ID --apply

The unit of work is a LAW: a reference is resolved against its law's labels, a definition's scope against its
law's tree, so a law with any new, retired or stale version is relinked whole. A law is stale when one of its rows
points at a provision or law that has left the release (a replay of the target law mints new ids). The boundary is
the release (v_release_provision, v_release_provision_version, v_release_instrument), as for chunks (0108).
Operative status is NOT decided here; readers ask operative_provision at their own as_of (INV-5).

Rules (nizam.storage.linking, pure and tested):
  * a reference resolves to the unit of the same law with that printed label (sections, articles and orders; the
    first in printed order when a label repeats), never to the unit it is in; a schedule by its printed number, or
    the law's only schedule for "the Schedule";
  * a reference to another law resolves when the words name one law: "the Act" / "said Act" in a subordinate
    instrument is the law its enacting formula names (empowers, 0089); a title ('Contract Act, 1872') matches by
    instrument_title_key and year among released laws -- a title naming its province in that province, otherwise the
    federal law first, then the source's own jurisdiction -- and exactly one must match; every section number of an
    amending law names the law it amends, and is resolved only when that law is named in the same words;
  * an amending law (title: Amendment, Finance Act) contributes no definitions: its quoted words are new text for
    another law;
  * a definition's scope is read from its own opening words, then the words of the nodes above it up to its unit:
    "In this Act" -> the law; "In this Chapter/Part" -> that division, for the units printed after the definition
    (a Chapter the tree lacks: the definition's own unit); "In this section" -> its unit;
  * a definition that stops mid-sentence with no children takes the siblings printed after it that carry its
    sub-items (until the next definition).
"""
from __future__ import annotations

import argparse
import collections
import re
import time

from nizam.storage import linking as L
from nizam.storage.db import connect
from nizam.storage.unit_search import OUTER_KINDS, UNIT_KINDS

LINKER = "nizam.links/7"     # /7: a phrase stops at a new clause; the dashes statutes print continue a definition     # /5: hyphenated labels ('4-A'), a run of references shares its trailing law; /6: headings
                             # and marginal notes are read too ('[See section 5]', 0115)     # /2: the word printed (section | rule | regulation), a subordinate instrument's implicit
BATCH = 150                  # parent, a title straight after the number; /3: 'Article' asks for articles only, the
                             # phrase governs only what it names, past-a-division titles, AJK/GB own copies; /4:
                             # decimal rule numbers, footnote markers before a title, never 'sub-section N', the
                             # parent named by its kind (D-108)
SUBORDINATE_KINDS = ("rules", "regulation", "notification")
_PROVINCE = re.compile(r"\b(punjab|sindh|sind|khyber|pakhtunkhwa|n\.?w\.?f\.?p|balochistan|baluchistan|islamabad|"
                       r"azad|kashmir|gilgit)\b", re.I)


def _fold(label: str) -> str:
    return "".join((label or "").split()).lower()


def word_class(unit_kind: str, law_kind: str | None) -> str:
    """which printed word names a unit: 'article' for an article, or for a section of a constitution or an Order
    (they number Articles, D-070); 'section' otherwise (a Rules instrument's rules are stored as sections)"""
    if unit_kind == "article" or (unit_kind == "section" and (law_kind or "") in ("constitution", "order")):
        return "article"
    return "section"


def asked_class(word: str) -> str:
    """the class a printed word asks for: 'Article 23' only an article (never a Stamp Act schedule's section 23)"""
    return "article" if word == "article" else "section"


class Law:
    """one released law's tree and text, enough to resolve its own words"""

    def __init__(self, iid, title, kind, juris, year):
        self.id, self.title, self.kind, self.juris, self.year = iid, title or "", kind, juris, year
        self.nodes: dict = {}                 # id -> (parent, path, kind, label, heading, ordinal)
        self.children: dict = collections.defaultdict(list)
        self.versions: dict = collections.defaultdict(list)     # provision id -> [(version id, text)]
        self.notes: dict = {}                 # provision id -> marginal note
        self.labels: dict = {}                # folded label -> unit id (first in printed order)
        self.schedules: list = []             # (unit id, number)
        self.amending = bool(L.AMENDING_TITLE.search(self.title))
        # a subordinate instrument numbers its own units as rules or regulations; 'section N' is its parent Act's
        self.subordinate = kind in SUBORDINATE_KINDS

    def finish(self):
        for pid, (parent, _path, _k, _l, _h, ordinal) in self.nodes.items():
            if parent in self.nodes:
                self.children[parent].append((ordinal, pid))
        for v in self.children.values():
            v.sort()
        for pid, (parent, path, kind, label, heading, ordinal) in sorted(self.nodes.items(), key=lambda x: x[1][5]):
            if kind in UNIT_KINDS:
                self.labels.setdefault((word_class(kind, self.kind), _fold(label)), pid)
            if kind == "schedule" and not any(self.nodes.get(a, (None, None, ""))[2] in OUTER_KINDS
                                              for a in self.chain(pid)[:-1]):
                self.schedules.append((pid, L.schedule_number(label, heading)))

    def chain(self, pid) -> list:
        """ancestors of pid, outermost first, pid last"""
        out, cur = [], pid
        while cur in self.nodes:
            out.append(cur)
            cur = self.nodes[cur][0]
        return out[::-1]

    def unit_of(self, pid):
        ch = self.chain(pid)
        inner = [a for a in ch if self.nodes[a][2] in UNIT_KINDS]
        if inner:
            return inner[-1]
        outer = [a for a in ch if self.nodes[a][2] in OUTER_KINDS]
        return outer[0] if outer else pid

    def text_of(self, pid) -> str:
        vs = self.versions.get(pid)
        return vs[0][1] if vs else ""

    def schedule(self, number):
        if number:
            hits = [u for u, n in self.schedules if n == number]
        else:
            hits = [u for u, _n in self.schedules] if len(self.schedules) == 1 else []
        return hits[0] if hits else None


def _laws(cur, ids) -> dict:
    cur.execute("""SELECT id, coalesce(nullif(display_title, ''), short_title), kind::text, jurisdiction::text, year
                     FROM v_release_instrument WHERE id = ANY(%s::uuid[])""", ([str(i) for i in ids],))
    laws = {r[0]: Law(*r) for r in cur.fetchall()}
    keys = [str(i) for i in laws]
    cur.execute("""SELECT id, instrument_id, parent_id, path::text, kind::text, label, heading, ordinal, marginal_note
                     FROM v_release_provision WHERE instrument_id = ANY(%s::uuid[])""", (keys,))
    for pid, iid, parent, path, kind, label, heading, ordinal, note in cur.fetchall():
        laws[iid].nodes[pid] = (parent, path, kind, label, heading, ordinal)
        if note:
            laws[iid].notes[pid] = note
    cur.execute("""SELECT v.id, v.provision_id, p.instrument_id, coalesce(v.text_normalised, '')
                     FROM v_release_provision_version v JOIN provision p ON p.id = v.provision_id
                    WHERE p.instrument_id = ANY(%s::uuid[])
                    ORDER BY v.provision_id, lower(v.validity) DESC NULLS LAST, v.id""", (keys,))
    for vid, pid, iid, text in cur.fetchall():
        laws[iid].versions[pid].append((vid, text))
    for law in laws.values():
        law.finish()
    return laws


def _parents(cur, ids) -> dict:
    """{subordinate instrument: (the one law its enacting formula names, that law's kind)} (empowers, 0089); none
    when it names two"""
    cur.execute("""SELECT d.delegated_instrument_id, array_agg(DISTINCT d.enabling_instrument_id),
                          array_agg(DISTINCT i.kind::text)
                     FROM v_delegation_current d JOIN instrument i ON i.id = d.enabling_instrument_id
                    WHERE d.delegated_instrument_id = ANY(%s::uuid[]) GROUP BY 1""", ([str(i) for i in ids],))
    return {d: (e[0], k[0]) for d, e, k in cur.fetchall() if len(e) == 1}


class TitleIndex:
    """released laws by title key, to resolve 'of the Contract Act, 1872' (D-097's preference order)"""

    def __init__(self, cur):
        cur.execute("""SELECT id, instrument_title_key(coalesce(nullif(display_title, ''), short_title)),
                              instrument_title_key(short_title), year, jurisdiction::text
                         FROM v_release_instrument WHERE duplicate_of IS NULL""")
        self.by_key: dict = collections.defaultdict(list)
        for iid, k1, k2, year, juris in cur.fetchall():
            for k in {k1, k2} - {None, ""}:
                self.by_key[k].append((iid, year, juris))
        self.cur = cur
        self._key_memo: dict = {}

    def key(self, title: str) -> str:
        if title not in self._key_memo:
            self.cur.execute("SELECT instrument_title_key(%s)", (title,))
            self._key_memo[title] = self.cur.fetchone()[0] or ""
        return self._key_memo[title]

    def resolve(self, title: str, year: int | None, src_juris: str):
        cands = [c for c in self.by_key.get(self.key(title), []) if year is None or c[1] == year]
        cands = list({c[0]: c for c in cands}.values())
        if not cands:
            return None
        if _PROVINCE.search(title):
            tiers = [[c for c in cands if c[2] == src_juris], cands]       # a title naming its province
        elif src_juris in ("ajk", "gb"):
            # AJK and GB law names its own adapted copy first (federal law does not reach them, 0086)
            tiers = [[c for c in cands if c[2] == src_juris], [c for c in cands if c[2] == "fed"]]
        else:
            tiers = [[c for c in cands if c[2] == "fed"], [c for c in cands if c[2] == src_juris]]
        for tier in tiers:
            if tier:
                return tier[0][0] if len(tier) == 1 else None
        return None


def link_law(law: Law, parent, titles: TitleIndex, stats) -> tuple[list, list, list]:
    parent_id, parent_kind = parent if parent else (None, None)
    return _link_law(law, parent_id, parent_kind, titles, stats)


def _link_law(law: Law, parent_id, parent_kind, titles: TitleIndex, stats) -> tuple[list, list, list]:
    """(reference rows, definition rows, pending other-law references) for one law"""
    refs, defs, pending = [], [], []
    for pid, (parent, path, kind, label, heading, ordinal) in law.nodes.items():
        unit = law.unit_of(pid)
        vers = law.versions.get(pid, [])
        # what the provision prints: its version's text, and (once, against its first version) its heading and
        # marginal note -- a schedule's '[See section 5]' lives there (0115)
        reads = [(vid, text, False) for vid, text in vers]
        head = " ".join(x for x in (heading, law.notes.get(pid)) if x)
        if head and vers:
            reads.append((vers[0][0], head, True))
        for vid, text, in_heading in reads:
            if not text:
                continue
            for r in L.references(text):
                labels = r.labels if r.kind == "unit" else (r.labels or ("",))
                for lab in labels:
                    row = {"src_version_id": vid, "src_provision_id": pid, "src_instrument_id": law.id,
                           "kind": r.edge, "target": r.kind, "label": str(lab), "other_law": None,
                           "dst_unit_id": None, "dst_instrument_id": None, "char_start": r.start,
                           "char_end": r.end, "in_heading": in_heading, "_class": asked_class(r.word)}
                    if r.kind == "unit" and r.word in ("rule", "regulation") and not law.subordinate:
                        stats["rule numbers named in a law (not followed)"] += 1
                        continue           # rules made under the law, or a CPC Order's rule: not this law's unit
                    implicit = (r.kind == "unit" and law.subordinate and r.word == "section"
                                and not r.of_these and not r.external)
                    if r.external or implicit or (law.amending and r.kind == "unit"):
                        # a subordinate instrument's bare 'section 25' is its parent Act's (empowers, 0089)
                        # the implicit parent is named by its own kind ('Act' for an Act, 'Ordinance' for one)
                        row["other_law"] = ((parent_kind or "act").capitalize() if implicit
                                            else (r.other_law or ""))
                        pending.append(row)
                        stats["references to another law" + (" (implicit parent)" if implicit else "")] += 1
                        continue
                    if r.kind == "unit":
                        dst = law.labels.get((asked_class(r.word), _fold(str(lab))))
                    else:
                        dst = law.schedule(lab or None)
                    if dst is not None and dst == unit:
                        stats["references to the unit itself (skipped)"] += 1
                        continue
                    if dst is not None:
                        row["dst_unit_id"], row["dst_instrument_id"] = dst, law.id
                        stats["references resolved in the same law"] += 1
                    else:
                        stats["references unresolved in the same law"] += 1
                    refs.append(row)
            if law.amending or in_heading:
                continue
            found = L.definitions_in(text)
            if not found:
                continue
            chain = law.chain(pid)
            unit_depth = chain.index(unit) if unit in chain else 0
            above = [law.text_of(a) for a in reversed(chain[unit_depth:-1])]
            word = L.scope_word([L.opening(text)] + above)
            scope, scope_pid = L.definition_scope(word, [(a, law.nodes[a][2]) for a in chain], unit, law.kind)
            after = ordinal if scope == "division" else None
            if word in ("part", "chapter") and scope == "unit":
                stats["definitions naming a division the tree lacks (kept to their unit)"] += 1
            cont: list = []
            if not law.children.get(pid) and L.continues(text) and parent is not None:
                sibs = [s for o, s in law.children.get(parent, []) if o > ordinal]
                n = L.continuation([law.text_of(s) for s in sibs])
                cont = sibs[:n]
                stats["definitions continued into their siblings"] += bool(cont)
            for term, empty in found:
                defs.append({"version_id": vid, "provision_id": pid, "instrument_id": law.id, "unit_id": unit,
                             "term": term, "term_key": L.term_key(term), "scope": scope,
                             "scope_provision_id": scope_pid, "after_ordinal": after,
                             "empty": bool(empty and not cont), "continuation": cont})
                stats[f"definitions, scope {scope}"] += 1
    # the other law: the parent ('the Act'), or a named title
    for row in pending:
        dst_law = None
        asked = L.parent_word(row["other_law"])
        if asked and parent_id and (parent_kind or "") == asked:
            dst_law = parent_id                    # 'the Ordinance' only when the parent is an Ordinance
        elif asked:
            stats["parent named by another kind (unresolved)"] += 1
        else:
            named = L.law_named(row["other_law"])
            if named:
                dst_law = titles.resolve(named[0], named[1], law.juris)
        row["dst_instrument_id"] = dst_law
        refs.append(row)
    return refs, defs, pending


def _resolve_other_units(cur, pending, stats) -> None:
    """the unit labels of other laws named by references, by one query per batch"""
    want = collections.defaultdict(set)
    for row in pending:
        if row["dst_instrument_id"] and row["target"] == "unit":
            want[row["dst_instrument_id"]].add(_fold(row["label"]))
    labels: dict = {}
    if want:
        cur.execute("""SELECT p.instrument_id, lower(replace(p.label, ' ', '')), p.id, p.kind::text, i.kind::text
                         FROM v_release_provision p JOIN instrument i ON i.id = p.instrument_id
                        WHERE p.instrument_id = ANY(%s::uuid[]) AND p.kind::text = ANY(%s) ORDER BY p.ordinal""",
                    ([str(w) for w in want], list(UNIT_KINDS)))
        for iid, lab, pid, kind, law_kind in cur.fetchall():
            labels.setdefault((iid, word_class(kind, law_kind), lab), pid)
    for row in pending:
        dst = None
        if row["dst_instrument_id"] and row["target"] == "unit":
            dst = labels.get((row["dst_instrument_id"], row["_class"], _fold(row["label"])))
        row["dst_unit_id"] = dst
        if dst is None:
            row["dst_instrument_id"] = None        # an edge needs its unit; the law named alone is not resolved
            stats["references to another law unresolved"] += 1
        else:
            stats["references to another law resolved"] += 1


_REF_COLS = ("src_version_id", "src_provision_id", "src_instrument_id", "kind", "target", "label", "other_law",
             "dst_unit_id", "dst_instrument_id", "char_start", "char_end", "in_heading")
_DEF_COLS = ("version_id", "provision_id", "instrument_id", "unit_id", "term", "term_key", "scope",
             "scope_provision_id", "after_ordinal", "empty", "continuation")


def _stale_laws(cur, released_laws) -> set:
    """laws to relink: a released version not read by today's linker, a link row whose version left the release, or
    a row pointing at a provision or law that has left it"""
    cur.execute("""
        SELECT DISTINCT p.instrument_id FROM v_release_provision_version v JOIN provision p ON p.id = v.provision_id
         WHERE NOT EXISTS (SELECT 1 FROM provision_link_state s WHERE s.version_id = v.id AND s.linker = %s)""",
                (LINKER,))
    stale = {r[0] for r in cur.fetchall()}
    cur.execute("""
        SELECT DISTINCT r.src_instrument_id FROM provision_reference r
         WHERE NOT EXISTS (SELECT 1 FROM v_release_provision_version v WHERE v.id = r.src_version_id)
            OR (r.dst_unit_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM v_release_provision p WHERE p.id = r.dst_unit_id))
        UNION
        SELECT DISTINCT d.instrument_id FROM provision_definition d
         WHERE NOT EXISTS (SELECT 1 FROM v_release_provision_version v WHERE v.id = d.version_id)
            OR EXISTS (SELECT 1 FROM unnest(d.continuation || d.unit_id || d.scope_provision_id) x(pid)
                        WHERE x.pid IS NOT NULL AND NOT EXISTS (SELECT 1 FROM v_release_provision p WHERE p.id = x.pid))
    """)
    stale |= {r[0] for r in cur.fetchall()}
    return stale                    # a law that left the release is in it too: its rows are deleted, none written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--rebuild", action="store_true", help="TRUNCATE the link tables first (with --apply)")
    ap.add_argument("--instruments", default="", help="comma-separated instrument ids (a trial; implies relink)")
    a = ap.parse_args()
    t0 = time.time()
    stats = collections.Counter()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM v_release_instrument")
        released = [r[0] for r in cur.fetchall()]
        if a.instruments:
            todo = [i.strip() for i in a.instruments.split(",") if i.strip()]
        elif a.rebuild:
            todo = list(released)
            if a.apply:
                cur.execute("TRUNCATE provision_reference, provision_definition, provision_link_state")
        else:
            todo = sorted(_stale_laws(cur, released), key=str)
        stats["laws to link"] = len(todo)
        titles = TitleIndex(cur)
        released_set = set(map(str, released))
        for i in range(0, len(todo), BATCH):
            batch = todo[i:i + BATCH]
            # what this batch replaces: every row of these laws, and the read-state of their versions
            keys = [str(b) for b in batch]
            if a.apply and not (a.rebuild and not a.instruments):
                cur.execute("DELETE FROM provision_reference WHERE src_instrument_id = ANY(%s::uuid[])", (keys,))
                cur.execute("DELETE FROM provision_definition WHERE instrument_id = ANY(%s::uuid[])", (keys,))
                cur.execute("""DELETE FROM provision_link_state s USING provision_version v, provision p
                                WHERE s.version_id = v.id AND p.id = v.provision_id
                                  AND p.instrument_id = ANY(%s::uuid[])""", (keys,))
            live = [b for b in batch if str(b) in released_set]
            laws = _laws(cur, live) if live else {}
            parents = _parents(cur, list(laws)) if laws else {}
            refs, defs, pending, versions = [], [], [], []
            for law in laws.values():
                r, d, p = link_law(law, parents.get(law.id), titles, stats)
                refs += r
                defs += d
                pending += p
                versions += [vid for vs in law.versions.values() for vid, _t in vs]
            _resolve_other_units(cur, pending, stats)
            stats["reference rows"] += len(refs)
            stats["definition rows"] += len(defs)
            stats["versions read"] += len(versions)
            if a.apply:
                with cur.copy(f"COPY provision_reference ({', '.join(_REF_COLS)}, linker) FROM STDIN") as cp:
                    for row in refs:
                        cp.write_row([row[c] for c in _REF_COLS] + [LINKER])
                with cur.copy(f"COPY provision_definition ({', '.join(_DEF_COLS)}, linker) FROM STDIN") as cp:
                    for row in defs:
                        cp.write_row([row[c] for c in _DEF_COLS] + [LINKER])
                with cur.copy("COPY provision_link_state (version_id, linker) FROM STDIN") as cp:
                    for vid in versions:
                        cp.write_row([vid, LINKER])
            if (i // BATCH) % 10 == 0:
                print(f"  {min(i + BATCH, len(todo))}/{len(todo)} laws, {time.time() - t0:.0f}s", flush=True)
        if not a.apply:
            conn.rollback()
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    print(f"{'applied' if a.apply else 'dry run (nothing written); pass --apply'} in {time.time() - t0:.0f}s ({LINKER})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
