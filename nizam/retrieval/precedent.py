"""Precedent search: which judgments bear on a question (docs/PRECEDENT-MODEL.md §4, §6; docs/04 §6).

    search(question, as_of=date, court=None, forum=None, k=10) -> PrecedentResult

Three generators, fused by reciprocal rank (RRF, k = 60, docs/04 §3), then grouped so a judgment appears once, by its
best paragraph:
1. **BM25** over released judgment paragraphs (ix_judgment_paragraph_bm25).
2. **Dense:** the question's bge-m3 sign bits against judgment chunks (the statutes' own generation, D-121).
3. **Cited:** when the question names a provision ('s.497 CrPC', 'Article 199'), the judgments that cite it or a
   unit inside it (judgment_statute_reference, D-119), through the same citation grammar as statute retrieval.
A printed case number or reporter citation ranks its case first (D-137, D-150). When the question is asked for a
forum, the fused judgments whose court binds that forum on `as_of` (the recorded rules, never a court's name) take
one more reciprocal-rank vote, in their fused order (D-154). A persuasive judgment keeps its place; none is removed.

What a result carries, and what it never does:
- **Citations from records only (INV-1):** court, case as printed, decision date, printed paragraph number.
- **Decided on or before `as_of`:** a later judgment did not exist on that date. An undated judgment (D-124) is
  returned only once `as_of` reaches the latest day it can have been decided, and carries decided_on None.
- **Binding status** for the forum the user names (a court code, or Subordinate(territory)), from authority_rule as
  at `as_of` (D-116): Binding, NotBinding or NotRecorded. It is never inferred from a court's name.
- **The law it read:** for each provision the judgment cites, whether that text is still the operative text on
  `as_of` (amended since, no longer operative, same text, or the decision-date text not held).
- **Coverage:** the courts and years searched (D-122). "Nothing found" is always "nothing found in this coverage".
- **The case** each hit decides (D-125), and whether the hit gives the reasons for the court's short order. A
  second copy of one decision is never a hit beside the copy kept.

This is precedent discovery, not an answer. It returns evidence for a reader or for L4/L5. It is not a
GroundingContext and passes no gate (INV-2). L5's citator owns treatment and "good law" (docs/04 §6.5).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import date

from nizam.storage import authority as A
from nizam.storage import citations as C
from nizam.storage import privacy as PV
from nizam.storage import unit_search
from nizam.storage.judgment_read import JudgmentRead
from nizam.storage.lexical import Filters

RRF_K = 60
WINDOW = 50


@dataclass
class PrecedentHit:
    judgment_id: str
    paragraph_id: str
    citation: str
    court: str
    case_type: str | None
    decided_on: date | None           # None: the judgment prints no usable decision date (D-124)
    disposition: str | None
    reported: bool | None
    text: str
    score: float
    generators: list[str]
    authority: dict | None = None
    statutes_cited: list[dict] = field(default_factory=list)
    undated: bool = False
    decided_no_later_than: date | None = None
    decided_not_before: date | None = None
    parties_display: str | None = None  # 'A v. B', withheld names replaced (D-131)
    privacy: dict = field(default_factory=dict)  # names_withheld, and each category's recorded basis
    case_key: str | None = None       # the case it decides, as printed ('SC/CA/1507/2024'); None if not placed (D-125)
    gives_reasons: bool = False       # it gives the reasons for the court's short order in that case
    short_order_on: date | None = None  # that short order's printed date, when printed
    subjects: list = field(default_factory=list)  # its areas, read from the laws it cites (judgment_subject, D-163)


@dataclass
class PrecedentResult:
    question: str
    as_of: date
    hits: list[PrecedentHit]
    cited_provisions: list[dict]
    coverage: list[dict]
    mode: str                         # 'hybrid' | 'lexical_only' (no encoder on this host)
    trace: dict
    # the question names a court whose judgments are not held: no hit is shown as that court's view (D-137)
    coverage_gap: dict | None = None
    cases_named: list[str] = field(default_factory=list)   # case keys the question prints and the corpus holds


# ------------------------------------------------------------------------------------- query understanding (D-137)

def _fold(s: str) -> str:
    t = " ".join(re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).split())
    return re.sub(r"\bsind\b", "sindh", re.sub(r"\bbaluchistan\b", "balochistan", t))


_ASKED_AFTER = re.compile(r"^(?:s\s+)?(?:judgments?|precedents?|rulings?|case\s+law|decisions|jurisprudence|view|"
                          r"held|holds?|ruled|rules?|decided|decides?|said|says?|on|in)\b")
_ASKED_BEFORE = re.compile(r"(?:judgments?|decisions|rulings?|precedents?|case\s+law|view)\s+(?:of|by|from|in)\s+"
                           r"(?:the\s+)?$")
_OPENS = re.compile(r"^\s*(?:(?:the|in|by|from)\s+){0,2}$")


def courts_named(conn, question: str) -> list[str]:
    """The courts whose judgments a question asks for (D-137), by their recorded names and observed header forms
    (court_alias), 'of Pakistan' dropped and the Sind/Sindh, Baluchistan/Balochistan spellings folded. A court is
    asked for when the question opens with it ('Lahore High Court Writ Petition No. ...'), when a verb of deciding
    follows it ('what has the Sindh High Court held'), or when its judgments are named ('the Supreme Court's
    precedent', 'judgments of the Peshawar High Court'). A court mentioned in passing is not ('a ceiling after the
    Federal Shariat Court's decision'). A spaced-out header form ('l a h o r e') is not a way of asking."""
    q = f" {_fold(question)} "
    keys = []
    for r in conn.execute("SELECT code, name FROM court").fetchall():
        code, name = r["code"], r["name"]
        keys += [(code, _fold(name)), (code, _fold(re.sub(r"(?i)\s+of\s+pakistan$", "", name)))]
    keys += [(r["court_code"], _fold(r["alias_key"])) for r in conn.execute(
        "SELECT court_code, alias_key FROM court_alias WHERE withdrawn_at IS NULL").fetchall()]
    found = {}
    for code, key in keys:
        words = key.split()
        if not words or sum(len(w) == 1 for w in words) > len(words) / 2:
            continue
        start = 0
        while True:
            at = q.find(f" {key} ", start)
            if at < 0:
                break
            start = at + 1
            before, after = q[:at + 1], q[at + len(key) + 2:]
            verb_soon = re.match(r"^(?:\w+\s+){0,1}(?:held|hold|ruled|rule|decided|decide|said|say)\b", after)
            if (_OPENS.match(before) or _ASKED_AFTER.match(after) or verb_soon
                    or _ASKED_BEFORE.search(before)) and (code not in found or at < found[code]):
                found[code] = at
    return sorted(found, key=found.get)


def cases_named(conn, question: str, courts: list[str] | None = None) -> list[str]:
    """Held case keys a question prints ('Civil Appeal No. 415 of 2018'), read by the case-line grammar
    (nizam.storage.case_key.read_case_line) after any held court's printed case-type form, in any court the question
    names or else every court; and the cases its reporter citations report (D-150). Only keys of held cases
    (judicial_case) are returned."""
    from nizam.storage.case_key import _fold_map, case_key, read_case_line
    f, idx = _fold_map(question)
    if not f:
        return []
    out: list[str] = []
    rows = conn.execute("SELECT court_code, code, printed_forms FROM case_type").fetchall()
    for r in rows:
        if courts and r["court_code"] not in courts:
            continue
        for form in sorted(r["printed_forms"] or [], key=len, reverse=True):
            for m in re.finditer(r"(?:^| )" + re.escape(form) + r"(?= |$)", f):
                at = m.start() + (1 if m.group(0).startswith(" ") else 0)
                line = read_case_line(question[idx[at]:], [form])
                if line and line.lead and line.year:
                    out += [case_key(r["court_code"], r["code"], n, line.year) for n in [line.lead] + line.joined]
    # a reporter citation the question prints ('2026 SCMR 715', 'PLD 2016 SC 1'), through the law-report index the
    # court publishes for its own judgments (D-150)
    from nizam.storage import judgment_linking as JL
    for c in JL.case_citations(question):
        rk = JL.reporter_key(c)
        if rk:
            out += [x["case_key"] for x in conn.execute(
                """SELECT DISTINCT case_key FROM reporter_citation
                    WHERE series = %s AND year = %s AND court = %s AND page = %s AND case_key IS NOT NULL""",
                rk).fetchall()
                if not courts or x["case_key"].split("/")[0] in courts]
    out = list(dict.fromkeys(out))
    if not out:
        return []
    held = {x["case_key"] for x in conn.execute("SELECT case_key FROM judicial_case WHERE case_key = ANY(%s)",
                                                 (out,)).fetchall()}
    return [k for k in out if k in held]


def _authority(deciding: str, forum, as_of: date, registry) -> dict | None:
    if forum is None:
        return None
    courts, rules, sup = registry
    r = A.authority(deciding, forum, as_of, courts=courts, rules=rules, superintendence=sup)
    if isinstance(r, A.Binding):
        return dict(status="binding", basis=r.rule.basis, subject_to=list(r.subject_to),
                    source_unit=r.rule.source.get("source_unit"), source_quote=r.rule.source.get("source_quote"))
    if isinstance(r, A.NotBinding):
        return dict(status="not_binding", rules_considered=[x.id for x in r.rules_considered])
    return dict(status="not_recorded", reason=r.reason)


def _cpu_encoder():
    from nizam.inference.encoder import encoder as _encoder
    return _encoder()


def _default_encoder(trace: dict):
    """the profile statute retrieval uses (candidates.profile: gpu when NIZAM_GPU_ENCODER_URL is set); a GPU encoder
    that cannot load falls back to the CPU one, marked"""
    from nizam.retrieval.candidates import profile
    if profile() == "gpu":
        try:
            from nizam.inference.remote import remote_encoder
            return remote_encoder()
        except Exception as exc:                                # noqa: BLE001
            trace["dense_fell_back"] = f"gpu encoder: {type(exc).__name__}"
    return _cpu_encoder()


def search(question: str, *, as_of: date, court: str | None = None, forum=None, k: int = 10,
           repo: JudgmentRead | None = None, encoder=None, subject: str | None = None,
           bm25: bool = True) -> PrecedentResult:
    if type(as_of) is not date:
        raise ValueError("as_of is mandatory (INV-5) and is a date")
    t0 = time.time()
    trace: dict = {}
    stage: dict = {}                                 # ms per stage (D-167): where a search spends its time
    clock = [time.time()]

    def mark(name):
        now = time.time()
        stage[name] = round((now - clock[0]) * 1000)
        clock[0] = now
    trace["stage_ms"] = stage
    own = repo is None
    repo = repo or JudgmentRead()
    if own:
        repo.open()
    try:
        with repo.transaction() as conn:
            cur = repo.tuple_cursor(conn)
            # 3. the provisions the question names, resolved from records (D-097)
            cited = []
            session = unit_search.Session(cur, Filters(as_of=as_of))
            for c in C.find(question):
                r = C.resolve(session, c)
                if r.resolved_unit:
                    cited.append(dict(raw=c.raw, provision_id=r.resolved_unit.unit_id, law=r.resolved_law))
            mark("citations")
            # the court the question names (D-137): one held court narrows the search to it; one that is not held
            # is a coverage gap, and no other court's judgment is shown as its view
            named = courts_named(conn, question)
            mark("courts_named")
            trace["courts_named"] = named
            if court is None and len(named) == 1:
                held = conn.execute("SELECT EXISTS (SELECT 1 FROM v_release_judgment WHERE court_code = %s) AS h",
                                    (named[0],)).fetchone()["h"]
                if not held:
                    name = conn.execute("SELECT name FROM court WHERE code = %s", (named[0],)).fetchone()["name"]
                    gap = dict(court=named[0], name=name, reason="no judgment of this court is held")
                    return PrecedentResult(question=question, as_of=as_of, hits=[], cited_provisions=cited,
                                           coverage=_coverage(conn), mode="none", coverage_gap=gap,
                                           trace=dict(trace, ms=int((time.time() - t0) * 1000)))
                court = named[0]
            lists = {}
            # a case the question prints, by its number, ahead of anything found by likeness (D-137)
            cases = cases_named(conn, question, [court] if court else None)
            if cases:
                lists["case"] = conn.execute("""
                    SELECT DISTINCT ON (p.judgment_id) p.id, p.judgment_id, p.decided_on
                      FROM judgment_case c
                      JOIN v_shown_judgment j ON j.id = c.judgment_id AND j.decided_on = c.decided_on
                      JOIN v_release_judgment_paragraph p ON p.judgment_id = j.id AND p.decided_on = j.decided_on
                     WHERE c.case_key = ANY(%s) AND j.decided_on <= %s AND p.kind = 'body'
                     ORDER BY p.judgment_id, p.ordinal""", (cases, as_of)).fetchall()
            mark("cases_named")
            # The question as asked. The statute path's Urdu gloss (D-105) and an English dense rendering were measured
            # here on dev and did not help (D-137); the measured route for Urdu is the 8B space (D-099).
            if bm25:                                            # bm25=False: the D-167 measurement's variant
                lists["bm25"] = repo.bm25_paragraphs(conn, question, WINDOW, as_of, court)
            mark("bm25")
            mode = "lexical_only"
            try:
                enc = encoder if encoder is not None else _default_encoder(trace)
                if getattr(getattr(enc, "info", None), "dims", 1024) == 4096:
                    # the GPU generation (D-158): the statutes' GPU space; until its judgment vectors are loaded the
                    # CPU generation is searched instead, and the trace says so (never passed off as the GPU path)
                    if repo.gpu_vectors_held(conn):
                        lists["dense"] = repo.dense_paragraphs_gpu(conn, enc.bits(question, 4096), WINDOW, as_of,
                                                                   court)
                        trace["dense_space"] = "gpu"
                    else:
                        trace["dense_fell_back"] = "the GPU generation's judgment vectors are not loaded"
                        enc = _cpu_encoder()
                if "dense" not in lists:
                    lists["dense"] = repo.dense_paragraphs(conn, enc.bits(question), WINDOW, as_of, court)
                    trace["dense_space"] = "cpu"
                mode = "hybrid"
            except Exception as exc:                            # noqa: BLE001  no encoder bundle on this host
                trace["dense_unavailable"] = type(exc).__name__
            mark("dense")                                       # the question's encoding and the HNSW scan
            if cited:
                lists["cited"] = repo.citing_paragraphs(conn, [c["provision_id"] for c in cited], WINDOW, as_of,
                                                        court)
            mark("cited")
            fused: dict = {}
            for name, rows in lists.items():
                for rank, r in enumerate(rows, 1):
                    f = fused.setdefault(r["id"], dict(score=0.0, gens=[], judgment_id=r["judgment_id"]))
                    # a case named by its number is an identification, not a likeness: it ranks first
                    f["score"] += 1.0 if name == "case" else 1.0 / (RRF_K + rank)
                    f["gens"].append(name)
            registry = A.load(cur) if forum is not None else None
            if registry is not None and fused:
                # for a forum, the judgments that bind it take one more vote, in their fused order (D-154)
                court_of = {r["id"]: r["court_code"] for r in conn.execute(
                    "SELECT id, court_code FROM v_release_judgment WHERE id = ANY(%s)",
                    (list({f["judgment_id"] for f in fused.values()}),)).fetchall()}
                binds = {c for c in set(court_of.values())
                         if ((_authority(c, forum, as_of, registry) or {}).get("status")) == "binding"}
                voted: set = set()
                for f in sorted(fused.values(), key=lambda f: -f["score"]):
                    if f["judgment_id"] in voted or court_of.get(f["judgment_id"]) not in binds:
                        continue
                    voted.add(f["judgment_id"])
                    f["score"] += 1.0 / (RRF_K + len(voted))
                    f["gens"].append("binding")
                trace["binding_voted"] = len(voted)
            # the judgments' areas (D-163); a subject the user names narrows to its judgments, as a named court does
            subj_of: dict = {}
            if fused:
                for r in conn.execute("""SELECT judgment_id, array_agg(value ORDER BY share DESC) AS v
                                           FROM judgment_subject WHERE judgment_id = ANY(%s) GROUP BY 1""",
                                      (list({f["judgment_id"] for f in fused.values()}),)).fetchall():
                    subj_of[r["judgment_id"]] = r["v"]
            if subject:
                trace["subject"] = subject
            best: dict = {}
            for pid, f in sorted(fused.items(), key=lambda x: -x[1]["score"]):
                if subject and subject not in subj_of.get(f["judgment_id"], ()):
                    continue
                if f["judgment_id"] not in best:
                    best[f["judgment_id"]] = (pid, f)
                if len(best) >= k:
                    break
            mark("fusion")                                      # RRF, the binding vote, subjects
            details = repo.paragraph_hits(conn, [pid for pid, _ in best.values()])
            mark("details")
            statutes = repo.statutes_cited(conn, list(best), as_of)
            mark("statutes_cited")
            hits = []
            withheld_queries = 0
            for jid, (pid, f) in best.items():
                d = details.get(pid)
                if not d:
                    continue
                if d["_names_withheld"] and PV.names_queried(question, d["_names_withheld"]):
                    # a search that names a person whose name this judgment withholds never finds it (D-131)
                    withheld_queries += 1
                    continue
                hits.append(PrecedentHit(
                    judgment_id=str(jid), paragraph_id=str(pid), citation=d["citation"], court=d["court_name"],
                    case_type=d["case_type_name"], decided_on=d["decided_on"], disposition=d["disposition"],
                    reported=d["reported_flag"], text=d["text"], score=round(f["score"], 6), generators=f["gens"],
                    authority=_authority(d["court_code"], forum, as_of, registry),
                    statutes_cited=[dict(citation=s["citation"], provision_id=str(s["dst_provision_id"]),
                                         role=s["role"], status_now=s["status_now"], mentions=s["mentions"])
                                    for s in statutes.get(jid, [])][:12],
                    undated=d["undated"], decided_no_later_than=d["decided_no_later_than"],
                    decided_not_before=d["decided_not_before"], case_key=d["case_key"],
                    parties_display=d["parties_display"], privacy=d["privacy"],
                    gives_reasons=d["gives_reasons"], short_order_on=d["reasons_for_short_order_on"],
                    subjects=list(subj_of.get(jid, []))))
            mark("hits")
            coverage = _coverage(conn)
            mark("coverage")
        trace.update(generators={n: len(v) for n, v in lists.items()}, ms=int((time.time() - t0) * 1000),
                     withheld_by_name=withheld_queries, court_searched=court)
        return PrecedentResult(question=question, as_of=as_of, hits=hits, cited_provisions=cited,
                               coverage=coverage, mode=mode, trace=trace, cases_named=cases)
    finally:
        if own:
            repo.close()


_COVERAGE: dict = {}


def _coverage(conn) -> list[dict]:
    """The courts and years searched (D-122): 'nothing found' is always 'nothing found in this coverage'.

    Cached per process (D-167): coverage changes only when a judgment is released or retired, so it is keyed by the
    release's fingerprint (the latest creation and retirement of a judgment row); a landing or a re-read changes the
    key and the next search reads it afresh. The key costs one indexed-free scan of judgment's two timestamps, about
    a tenth of the aggregate it replaces."""
    key = tuple(conn.execute("SELECT max(created_at) AS c, max(retired_at) AS r, count(*) AS n FROM judgment")
                .fetchone().values())
    if key not in _COVERAGE:
        _COVERAGE.clear()
        _COVERAGE[key] = _coverage_now(conn)
    return [dict(c) for c in _COVERAGE[key]]


def _coverage_now(conn) -> list[dict]:
    return [dict(c) for c in conn.execute("""
        SELECT v.court_code, min(first_decided) AS first_decided, max(last_decided) AS last_decided,
               sum(judgments_released) AS judgments,
               coalesce(sum(judgments_released) FILTER (WHERE year IS NULL), 0) AS undated,
               (SELECT count(*) FROM judicial_case k WHERE k.court_code = v.court_code) AS cases
          FROM v_judgment_coverage v GROUP BY v.court_code ORDER BY v.court_code""").fetchall()]
