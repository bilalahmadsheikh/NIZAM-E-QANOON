"""L3 evidence assembly (docs/04 §7: "retrieve narrow; assemble complete"; D-107).

The gate passes a bundle of unit identities (GroundingContext.items). Assembly turns it into the evidence the
generator reads, deterministically, with a recorded reason for every addition:

  1. Each bundle unit is widened to the WHOLE unit: every operative sub-section, clause, proviso, explanation and
     illustration, printed order, as at the context's date and in its territory (INV-5). Never half a section.
  2. Definitions the unit depends on: clauses of the SAME law that define a word the unit uses ('"employer"
     means ...'), in scope -- "In this Act" (the whole law), "In this Chapter/Part" (units inside it), "In this
     section" (that section only, already whole). The narrowest definition in scope wins.
  3. Qualifications: units of the same law that the unit is "subject to", "notwithstanding", "save as / except
     as provided in", or "without prejudice to".
  4. References: other units and schedules of the same law the unit names ("under section 4", "the Second
     Schedule"). A reference to ANOTHER law ("section 5 of the Pakistan Penal Code", "of the Act") is not
     followed here; it is counted in the coverage record.
  5. Each item carries its law's facts (title, place, status, currency, dates, how far back the text is known),
     the Part and Chapter it sits in, the amendment footnotes printed on its nodes, the instruments made under it
     (`empowers`, 0089), its source (URL, file sha256, pages), and a citation RENDERED FROM RECORDS (INV-1).
  6. A budget selector admits items in priority order -- the governing rule first, then what it needs, then the
     next bundle unit -- skipping (never cutting) an item that does not fit, and recording why. The result is
     ordered as the law is printed: law by law (the best-ranked law first), then by printed order.

Assembly changes nothing the gate decided. If none of the bundle is law at the context's date (the corpus changed
between the two reads), retrieve() abstains; that is still one of the two values (INV-2).

Not built here (recorded in coverage['not_built']): sub-question coverage, conflict sets, definitions in General
Clauses Acts or a parent Act, references to other laws, the matched span's offsets, Urdu-script definitions.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field, replace
from datetime import date

from nizam.storage import evidence_read as ER
from nizam.storage.library_read import render_citation
from nizam.storage.unit_search import OUTER_KINDS, UNIT_KINDS

# --- the budget (docs/05 §5.2: "a compact evidence window capped by a configured input budget"; no figure is set
# there, so this one is D-107's, by evals/results/assembly-rule-2026-11-20.json: the smallest multiple of 5,000 at
# or above the dev p90 of the unconstrained GPU packet (48,593 characters, 20 Nov 2026), fixed before any gold
# metric was computed. About 12.5k tokens at ~4 characters a token) -----------------------------------------------
BUDGET_CHARS = int(os.environ.get("NIZAM_EVIDENCE_CHARS", "50000"))
MAX_UNITS = 20              # docs/04 §7: "admit at most about 20 legal units"
DEFS_PER_UNIT = 8           # definitions attached for one unit, by first use in its words
QUALS_PER_UNIT = 3
REFS_PER_UNIT = 3
PREVAILS_PER_UNIT = 3       # provisions that say 'notwithstanding' a unit (they prevail over it)
GENERAL_PER_UNIT = 3        # General Clauses Act definitions for words the law does not define (defaults_from)
NOTES_PER_ITEM = 12         # printed amendment footnotes carried per item
RANGE_MAX = 6               # "sections 4 to 9" is expanded when it names at most this many
DIVISION_SHARE = 0.25       # of the budget, for the sections standing for one bundle Part or Chapter
DIVISION_UNITS = 5          # sections standing for one Part or Chapter, at most (of MAX_UNITS)
DIVISION_READ = 60          # sections read from one Part or Chapter, at most
STUB_CHARS = 40             # a section this short ('3A. [Omitted]') does not stand for its Chapter

NOT_BUILT = ("sub-question coverage", "conflict sets", "matched-span offsets", "Urdu-script definitions",
             "General Clauses Acts of Sindh, Balochistan, AJK and GB (not held)")

ROLE_RANK = {"governing": 0, "qualification": 1, "definition": 2, "reference": 3, "schedule": 3}


# What a provision defines and names is read once, at build time, into the link tables (nizam.storage.linking via
# nizam.workers.links, D-108); assembly reads the tables and applies only the read-time rules: does a definition's
# scope reach this unit, and does this unit use the word.
from nizam.storage.linking import DRAFTING_WORDS, GENERAL_TOO_BROAD, term_use  # noqa: E402
from nizam.storage.linking import roman as _roman  # noqa: E402


# ====================================================================================================================
# pure rendering (INV-1: every part of a citation is a stored record; nothing is generated)
# ====================================================================================================================
def _tidy(label: str) -> str:
    lab = " ".join((label or "").split())
    if lab.isupper():
        lab = " ".join(w if _roman(w) else w.capitalize() for w in lab.split())
    return lab


def unit_head(kind: str, label: str, law_kind: str | None = None) -> str:
    """a unit as prose names it ('Section 4', 'Article 25' -- a constitution's sections are Articles, D-070)"""
    lab = " ".join((label or "").split())
    if kind == "section":
        return f"Article {lab}" if law_kind == "constitution" else f"Section {lab}"
    if kind == "article":
        return f"Article {lab}"
    if kind == "order":
        return _tidy(lab) if lab.lower().startswith("order") else f"Order {lab}"
    if kind in OUTER_KINDS:
        lab = re.sub(r"^\d+(?=[A-Za-z])", "", lab)        # a footnote marker glued to 'Schedule' ('19Schedule')
        return _tidy(lab) if re.search(r"[A-Za-z]{3}", lab) else f"{kind.capitalize()} {lab}".strip()
    return lab


def citation(unit_kind: str, unit_label: str, title: str, chain=(), year: int | None = None,
             law_kind: str | None = None) -> str | None:
    """the server's citation form (nizam.storage.library_read.render_citation, D-070), from records only (INV-1):
    'Punjab ... Act, 2021, s. 2(1)(e)'; 'Constitution of ..., Art. 25'; '..., Order XXI'; '..., Third Schedule'.
    The labels below the unit follow it: sub-sections and clauses in brackets, then ', proviso' or ', Explanation 1'.
    None without a title or label, never guessed."""
    brackets, tail = "", ""
    for kind, label in chain:
        lab = " ".join((label or "").split())
        if kind in ("subsection", "clause") and lab:
            brackets += f"({lab})"
        elif kind == "proviso":
            tail += ", proviso"
        elif kind in ("explanation", "illustration") and lab:
            tail += f", {lab}"
    lab = " ".join((unit_label or "").split())
    if unit_kind in ("section", "article", "preamble"):
        out = render_citation(title, year, unit_kind, (lab + brackets) if lab else lab, law_kind)
        return out + tail if out else None
    if not title or not lab:
        return None
    name = title.strip().rstrip(".")
    if year and str(year) not in name:
        name = f"{name}, {year}"
    return f"{name}, {unit_head(unit_kind, unit_label, law_kind)}{brackets}{tail}"


def node_line(n: ER.Node, base_depth: int) -> str:
    text = " ".join((n.text or "").split())
    lab = " ".join((n.label or "").split())
    indent = "  " * max(0, n.path.count(".") - base_depth)
    if n.kind in ("section", "article"):
        head = f"{lab}." + (f" {' '.join(n.heading.split())}" if n.heading else "")
        line = f"{head} {text}".strip()
    elif n.kind == "order":
        line = f"{_tidy(lab)}" + (f" {' '.join(n.heading.split())}" if n.heading else "") + (f" {text}" if text else "")
    elif n.kind in ("subsection", "clause"):
        line = f"({lab}) {text}".strip()
    elif n.kind in ("proviso", "explanation", "illustration"):
        line = text if (lab.isdigit() or text.lower().startswith(lab.lower())) else f"{lab} {text}".strip()
    else:
        head = " ".join(x for x in (_tidy(lab), " ".join((n.heading or "").split())) if x)
        line = f"{head} {text}".strip()
    return indent + line


def unit_line(u) -> str:
    """a unit's own label and heading, as printed ('5. Jurisdiction'): the first line of an item whose unit node
    has no words of its own (the section's words are all in its sub-sections)"""
    lab = " ".join((u.label or "").split())
    heading = " ".join((u.heading or "").split())
    if u.kind in ("section", "article"):
        return f"{lab}." + (f" {heading}" if heading else "")
    return " ".join(x for x in (_tidy(lab), heading) if x)


def render(nodes, base_path: str, head_line: str | None = None) -> str:
    depth = base_path.count(".")
    lines = [line for line in (node_line(n, depth) for n in nodes) if line.strip()]
    if head_line and (not nodes or nodes[0].path != base_path):
        lines.insert(0, head_line)
    return "\n".join(lines)


# ====================================================================================================================
# the output
# ====================================================================================================================
@dataclass(frozen=True)
class EvidenceItem:
    """docs/04 §7's EvidenceItem, as built. Identities are stored ids (INV-4: provisions, never chunks)."""
    unit_id: str                     # legalUnitId: the section, article, order or schedule
    provision_id: str                # the node the item IS: the unit, or a definition clause inside one
    instrument_id: str
    role: str                        # governing | qualification | definition | reference | schedule
    inclusion_reason: str
    citation: str                    # displayCitation, rendered from records (INV-1)
    heading: str | None
    text: str                        # the item's operative nodes, printed order, one per line
    nodes: tuple                     # ((provision id, version id, kind, label), ...), the lines' order
    divisions: tuple                 # ((kind, label, heading), ...): the Parts and Chapters it sits in
    law: dict                        # the law's facts from operative_provision at as_of in the territory
    amendments: tuple                # printed amendment footnotes on its nodes, verbatim
    delegated: tuple                 # ((instrument id, title, kind, year), ...) made under it (governing units)
    source: dict                     # url, sha256, document id, pages
    as_of: date
    territory: str | None
    rank: int | None = None          # the bundle rank of a governing unit
    rerank_score: float | None = None
    order: tuple = field(default=(), compare=False)

    @property
    def chars(self) -> int:
        return len(self.text) + sum(len(a) for a in self.amendments)


@dataclass
class _Cand:
    key: str                         # the provision the item is
    unit_id: str
    instrument_id: str
    role: str
    reason: str
    nodes: tuple
    base_path: str
    chain: tuple = ()
    rank: int | None = None
    rerank: float | None = None
    size: int = 0
    head_line: str | None = None     # the unit's label and heading, when its own node has no words


def select(cands: list[_Cand], budget: int, max_units: int):
    """admit in priority order: skip an item already inside an admitted one, an item that would pass the unit cap,
    or one that does not fit the budget (it is skipped, never cut). The first governing unit is always admitted
    (an answer never lacks its governing rule); if it alone passes the budget, that is recorded. A whole unit
    admitted after one of its own clauses replaces the clause."""
    admitted: list[_Cand] = []
    omitted: list[dict] = []
    used = 0
    units = 0

    def inside(path: str, other: _Cand) -> bool:
        return path == other.base_path or path.startswith(other.base_path + ".")

    for c in cands:
        holder = next((a for a in admitted if a.instrument_id == c.instrument_id and inside(c.base_path, a)), None)
        if holder is not None:
            omitted.append({"provision": c.key, "role": c.role, "reason": f"inside {holder.key}"})
            continue
        whole = c.role != "definition"
        first = not admitted and c.role == "governing"
        if whole and units >= max_units and not first:
            omitted.append({"provision": c.key, "role": c.role, "reason": "unit cap"})
            continue
        replaced = [a for a in admitted if a.instrument_id == c.instrument_id and inside(a.base_path, c)]
        size = c.size - sum(a.size for a in replaced)
        if used + size > budget and not first:
            omitted.append({"provision": c.key, "role": c.role, "reason": "budget", "chars": c.size})
            continue
        for a in replaced:
            admitted.remove(a)
            omitted.append({"provision": a.key, "role": a.role, "reason": f"inside {c.key}"})
            if a.role != "definition":
                units -= 1
        admitted.append(c)
        used += size
        units += int(whole)
    return admitted, omitted, used


# ====================================================================================================================
# assembly
# ====================================================================================================================
def _unit_text(u: ER.Unit) -> str:
    return " ".join(x for n in u.nodes for x in (n.heading or "", n.text or "") if x)


def _applies(scope: tuple, unit_path: str, unit_ordinal: int | None = None) -> bool:
    """does a definition's scope reach a unit? ('law', None) reaches the whole law; ('division', path[, ordinal])
    the units inside that Part or Chapter printed AFTER the definition -- a Chapter's definitions open it, so a unit
    printed before them is outside them, which also keeps a definition inside its true Chapter when the tree has
    folded two Chapters into one (Constitution Chapter 3A under Chapter 3, D-107); ('unit', path) its own unit"""
    kind, path = scope[0], scope[1]
    if kind == "law":
        return True
    if not (unit_path == path or unit_path.startswith(path + ".")):
        return False
    after = scope[2] if len(scope) > 2 else None
    return kind != "division" or after is None or unit_ordinal is None or unit_ordinal > after


@dataclass(frozen=True)
class _Gov:
    """a governing unit: a bundle unit, or a section standing for a bundle Part or Chapter"""
    unit_id: str
    rank: int
    rerank_score: float | None
    via_citation: bool
    note: str


def division_name(kind: str, label: str, heading: str | None) -> str:
    name = f"{'Chapter' if kind == 'chapter' else 'Part'} {' '.join((label or '').split())}"
    return name + (f" ({' '.join(heading.split())})" if heading else "")


def _governing(s, live, units: dict, budget: int, cov: dict) -> list[_Gov]:
    """the bundle as governing units. A Part or Chapter in the bundle (retrieval maps a match on its heading to it)
    is not a citable unit (INV-4: provisions are): its sections stand for it. Those the bundle already holds keep
    their own rank; the rest are taken in printed order, whole, at most DIVISION_UNITS of them and while they fit
    DIVISION_SHARE of the budget (the first always, if it fits the budget), skipping stubs ('[Omitted]'), so one
    heading match cannot crowd out the bundle's other units."""
    held = {b.unit_id for b in live}
    out: list[_Gov] = []
    for b in live:
        u = units[b.unit_id]
        if u.kind not in ER.DIVISION_KINDS:
            out.append(_Gov(b.unit_id, b.rank, b.rerank_score, b.via_citation,
                            f"bundle rank {b.rank}" + (", named in the question" if b.via_citation else "")))
            continue
        name = division_name(u.kind, u.label, u.heading)
        inner = s.units_within(u.instrument_id, u.path)
        rest = [i for i in inner if i not in held][:DIVISION_READ]
        got = s.units(rest)
        share, taken = 0, []
        for i in rest:
            if i not in got:
                continue
            size = len(render(got[i].nodes, got[i].path))
            if size < STUB_CHARS:
                continue
            if len(taken) >= DIVISION_UNITS:
                break
            if share + size > budget * DIVISION_SHARE:
                if not taken and size <= budget:
                    taken.append(i)
                break
            share += size
            taken.append(i)
        for i in taken:
            units[i] = got[i]
            out.append(_Gov(i, b.rank, b.rerank_score, False,
                            f"in {name}, whose heading matched (bundle rank {b.rank})"))
        cov.setdefault("divisions", []).append({"division": u.unit_id, "name": name, "rank": b.rank,
                                                "sections": len(inner), "in_bundle": len(inner) - len(rest),
                                                "taken": len(taken)})
    return out


def assemble(ctx, connect_fn=None, budget: int | None = None, max_units: int = MAX_UNITS):
    """GroundingContext -> the same context with `evidence` (EvidenceItem, legal order) and `coverage`; or None
    when no bundle unit is law at the context's date (the caller abstains)"""
    t0 = time.perf_counter()
    laps: dict[str, float] = {}

    def lap(name: str, since=[t0]):
        now = time.perf_counter()
        laps[name] = round((now - since[0]) * 1000, 1)
        since[0] = now

    budget = BUDGET_CHARS if budget is None else budget
    f = ctx.filters
    kwargs = {"connect_fn": connect_fn} if connect_fn else {}
    bundle = list(ctx.items)
    cov: dict = {"budget_chars": budget, "max_units": max_units, "omitted": [], "not_operative": [],
                 "references": {"followed": 0, "other_law": 0, "unresolved": [], "not_operative": []},
                 "not_built": list(NOT_BUILT)}
    with ER.session(f, **kwargs) as s:
        units = s.units([b.unit_id for b in bundle])
        cov["not_operative"] = [b.unit_id for b in bundle if b.unit_id not in units]
        live = _governing(s, [b for b in bundle if b.unit_id in units], units, budget, cov)
        if not live:
            return None
        laws = list(dict.fromkeys(units[b.unit_id].instrument_id for b in live))
        text_of = {b.unit_id: _unit_text(units[b.unit_id]) for b in live}

        def head(u) -> str:          # 'Section 4', or 'Article 4' in a constitution
            lf = s._facts.get(u.instrument_id)
            return unit_head(u.kind, u.label, lf.kind if lf else None)
        lap("units")

        # --- references the bundle's words make (provision_reference, D-108): same law or another --------------
        node_unit = {n.provision_id: b.unit_id for b in live for n in units[b.unit_id].nodes}
        out_rows = s.references_from(list(node_unit))
        prevail_rows = s.prevailing_over([b.unit_id for b in live])
        prevail_units = s.units_of([src for _dst, src in prevail_rows])
        per_unit_refs: dict[str, list[tuple[str, str, str]]] = {}
        ref_ids: list[str] = []
        for b in live:
            u = units[b.unit_id]
            seen, lst = {u.unit_id}, []
            mine = [r for r in out_rows if node_unit.get(r[0]) == b.unit_id]
            for kinds, cap, role in ((("notwithstanding", "subject_to"), QUALS_PER_UNIT, "qualification"),
                                     (("refers_to",), REFS_PER_UNIT, None)):
                n = 0
                for _src, kind, target, label, other_law, dst, dst_law in mine:
                    if kind not in kinds or dst in seen or n >= cap:
                        continue
                    seen.add(dst)
                    n += 1
                    printed = (f"{'section' if target == 'unit' else 'Schedule'} {label}".strip()
                               + (f" of {other_law}" if other_law else ""))
                    phrase = {"notwithstanding": "prevails over", "subject_to": "is subject to"}.get(kind, "names")
                    lst.append((dst, role or ("schedule" if target == "schedule" else "reference"),
                                f"{head(u)} {phrase} '{printed}'"))
                    ref_ids.append(dst)
                    cov["references"]["other_law"] += dst_law != u.instrument_id
            # a provision that says 'notwithstanding' this unit prevails over it: a reader of the unit must see it
            n = 0
            for dst, src in prevail_rows:
                pu = prevail_units.get(src)
                if dst != b.unit_id or pu is None or pu[0] in seen or n >= PREVAILS_PER_UNIT:
                    continue
                seen.add(pu[0])
                n += 1
                lst.append((pu[0], "qualification", f"prevails over {head(u)} ('notwithstanding')"))
                ref_ids.append(pu[0])
            per_unit_refs[b.unit_id] = lst
        units.update(s.units([uid for uid in dict.fromkeys(ref_ids) if uid not in units]))
        cov["references"]["followed"] = len({uid for uid in ref_ids if uid in units})
        cov["references"]["not_operative"] = sorted({uid for uid in ref_ids if uid not in units})
        lap("references")

        # --- definitions (provision_definition, D-108): the law's own, then its parent Act's, then its General
        #     Clauses Act's (defaults_from, docs/03b) for a word the law does not define -----------------------
        parents = s.parent_laws(laws)
        gca = s.general_clauses()
        juris = {iid: getattr(s._facts.get(iid), "jurisdiction", None) for iid in laws}
        default_of = {iid: gca.get(juris[iid]) for iid in laws if gca.get(juris[iid]) not in (None, iid)}
        rows = s.definitions_of(set(laws) | set(parents.values()) | set(default_of.values()))
        by_law: dict[str, list[dict]] = {}
        for d in rows:
            by_law.setdefault(d["instrument_id"], []).append(d)
        lap("definition_read")
        def_wanted: dict[str, list] = {}
        chosen_by_unit: dict[str, list] = {}
        for b in live:
            u = units[b.unit_id]
            text = text_of[b.unit_id]
            best: dict[str, tuple] = {}
            sources = [(0, by_law.get(u.instrument_id, []))]
            if parents.get(u.instrument_id):
                sources.append((1, by_law.get(parents[u.instrument_id], [])))
            if default_of.get(u.instrument_id):
                sources.append((2, by_law.get(default_of[u.instrument_id], [])))
            for tier, defs in sources:
                for d in defs:
                    if tier == 0:
                        if d["path"] == u.path or d["path"].startswith(u.path + "."):
                            continue                  # inside the unit: already whole
                        if not _applies((d["scope"], d["scope_path"], d["after_ordinal"]), u.path, u.ordinal):
                            continue
                    elif d["scope"] != "law":
                        continue                      # another law's definition reaches only as a whole-law one
                    key = d["term_key"]
                    if key in DRAFTING_WORDS or (tier == 2 and key in GENERAL_TOO_BROAD):
                        continue                      # a word of the statute's own structure, or too general
                    rank = (tier, ("unit", "division", "law").index(d["scope"]), d["ordinal"])
                    if key in best and best[key][0] <= rank:
                        continue
                    pos = term_use(d["term"], text)
                    if pos is not None:
                        best[key] = (rank, pos, d)
            ordered = sorted(best.values(), key=lambda x: (x[1], -len(x[2]["term"])))
            own = [x for x in ordered if x[0][0] < 2][:DEFS_PER_UNIT]
            general = [x for x in ordered if x[0][0] == 2][:GENERAL_PER_UNIT]
            chosen_by_unit[b.unit_id] = own + general
            for rank, _pos, d in own + general:
                def_wanted.setdefault(d["provision_id"], []).append((u, d, rank[0]))
        subs = s.subtrees(list(def_wanted))
        cont_ids = [c for wants in def_wanted.values() for c in (wants[0][1]["continuation"] or [])]
        cont_nodes = s.nodes_of(cont_ids)
        chains = s.ancestors(list(def_wanted))
        lap("definition_scope")

        # --- candidates, in priority order: each bundle unit, then what it needs ------------------------------
        bundle_rank = {b.unit_id: b for b in live}
        def_cand: dict[str, _Cand] = {}
        for pid, wants in def_wanted.items():
            sub = subs.get(pid)
            if not sub:
                continue
            d = wants[0][1]
            more = [cont_nodes[c] for c in (d["continuation"] or []) if c in cont_nodes]
            if more:
                sub = tuple(sub) + tuple(more)
                cov.setdefault("continued_definitions", []).append({"provision": pid, "siblings": len(more)})
            if len(sub) == 1 and all(w[1]["empty"] for w in wants):
                # '"voter" means--' with nothing under it or after it: its words are not in the corpus's nodes
                cov["omitted"].append({"provision": pid, "role": "definition", "reason": "definition text not in node"})
                continue
            chain = chains.get(pid, ())
            depth = next((a.depth for a in chain if a.provision_id == d["unit_id"]), 0)
            terms = sorted({w[1]["term"] for w in wants}, key=str.lower)
            users = list(dict.fromkeys(head(w[0]) for w in wants))
            tier = min(w[2] for w in wants)
            where = {0: "", 1: " in the parent law (empowers)", 2: " in the General Clauses Act (defaults_from)"}[tier]
            def_cand[pid] = _Cand(pid, d["unit_id"], d["instrument_id"], "definition",
                                  f"defines {', '.join(repr(t) for t in terms)}{where}, used in {', '.join(users)}",
                                  sub, d["path"], chain=tuple((a.kind, a.label) for a in chain if a.depth > depth))
        cands: list = []
        late: list[_Cand] = []
        placed: set = set()
        for b in live:
            u = units[b.unit_id]
            cands.append(_Cand(u.unit_id, u.unit_id, u.instrument_id, "governing", b.note, u.nodes, u.path,
                               rank=b.rank, rerank=b.rerank_score))
            for uid, role, reason in per_unit_refs.get(b.unit_id, []):
                if uid not in units:
                    continue
                r = units[uid]
                also = bundle_rank.get(uid)
                c = _Cand(uid, uid, r.instrument_id, role,
                          reason + (f" (also bundle rank {also.rank})" if also else ""), r.nodes, r.path,
                          rank=also.rank if also else None, rerank=also.rerank_score if also else None)
                (cands if role == "qualification" else late).append(c)
            # a unit's definitions come with it (measured 21 Nov 2026, D-108: deferring all but its first 3 until
            # after every unit's references cost the CPU bundles two necessary units on dev and gained nothing)
            for _rank, _pos, d in chosen_by_unit.get(b.unit_id, []):
                c = def_cand.get(d["provision_id"])
                if c is not None and d["provision_id"] not in placed:
                    placed.add(d["provision_id"])
                    cands.append(c)
        cands = cands + late
        for c in cands:
            if c.role != "definition" and c.unit_id in units:
                c.head_line = unit_line(units[c.unit_id])
            c.size = len(render(c.nodes, c.base_path, c.head_line))
        admitted, omitted, used = select(cands, budget, max_units)
        cov["omitted"] = cov["omitted"] + omitted
        lap("select")

        # --- what each admitted item carries ------------------------------------------------------------------
        divs = s.ancestors(list({c.unit_id for c in admitted}))
        notes = s.amendment_notes([nd.provision_id for c in admitted for nd in c.nodes],
                                  [c.instrument_id for c in admitted])
        lap("notes")
        dele = s.delegated([c.unit_id for c in admitted if c.role == "governing"])
        lap("delegated")
        facts = s.facts({c.instrument_id for c in admitted})
    law_order = {iid: i for i, iid in enumerate(dict.fromkeys(c.instrument_id for c in admitted))}
    items = []
    for c in admitted:
        lf = facts.get(c.instrument_id)
        uchain = divs.get(c.unit_id, ())
        u_anc = uchain[-1] if uchain else None
        text = render(c.nodes, c.base_path, c.head_line)
        printed: list[str] = []
        for nd in c.nodes:
            for a in notes.get(nd.provision_id, ()):
                if a.printed and a.printed not in printed:
                    printed.append(a.printed)
        if len(printed) > NOTES_PER_ITEM:
            cov.setdefault("notes_dropped", {})[c.key] = len(printed) - NOTES_PER_ITEM
        pages = [p for nd in c.nodes for p in (nd.first_page, nd.last_page) if p]
        heading = None if c.role == "definition" else (u_anc.heading if u_anc else None)
        items.append(EvidenceItem(
            unit_id=c.unit_id, provision_id=c.key, instrument_id=c.instrument_id, role=c.role,
            inclusion_reason=c.reason,
            citation=citation(u_anc.kind if u_anc else "section", u_anc.label if u_anc else "",
                              lf.title if lf else "", c.chain, lf.year if lf else None, lf.kind if lf else None),
            heading=heading, text=text,
            nodes=tuple((nd.provision_id, nd.version_id, nd.kind, nd.label) for nd in c.nodes),
            divisions=tuple((a.kind, a.label, a.heading) for a in uchain if a.kind in ER.DIVISION_KINDS),
            law=_law_dict(lf), amendments=tuple(printed[:NOTES_PER_ITEM]),
            delegated=tuple((d.instrument_id, d.title, d.kind, d.year) for d in dele.get(c.unit_id, ())),
            source={"url": lf.source_url if lf else None, "sha256": lf.source_sha256 if lf else None,
                    "document_id": lf.document_id if lf else None,
                    "pages": [min(pages), max(pages)] if pages else None},
            as_of=f.as_of, territory=f.territory, rank=c.rank, rerank_score=c.rerank,
            order=(law_order[c.instrument_id], c.nodes[0].ordinal if c.nodes else 0, c.base_path)))
    items.sort(key=lambda it: it.order)
    lap("build")
    cov.update(used_chars=used, units=sum(1 for c in admitted if c.role != "definition"),
               definitions=sum(1 for c in admitted if c.role == "definition"), over_budget=used > budget,
               timings_ms=laps, assembly_ms=round((time.perf_counter() - t0) * 1000, 1))
    return replace(ctx, evidence=tuple(items), coverage=cov)


def _law_dict(lf: ER.LawFacts | None) -> dict:
    if lf is None:
        return {}
    d = dict(lf.__dict__)
    for k in ("enacted_on", "commenced_on", "text_known_from"):
        if d.get(k) is not None:
            d[k] = d[k].isoformat()
    return d
