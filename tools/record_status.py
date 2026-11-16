"""Record 'in_force' for a released Act whose commencement is established and against which no repeal is known
(migration 0082, instrument_metadata_assertion field 'status').

WHAT 'in_force' RESTS ON -- all of these, for the expression:
  1. it is an Act (or the Constitution). Ordinances, President's Orders and Martial Law Regulations are not asserted:
     whether one lapsed, was continued or was protected is a constitutional question its own text does not settle.
     Rules, regulations, orders and notifications are not asserted either: a subordinate instrument stands or falls
     with its enabling law, which the corpus does not link it to;
  2. it has commenced, by one of:
       commenced_on_established    -- a standing commenced_on (tools/record_commencement.py) on or before today;
       commences_at_once           -- its own text: 'This Act shall come into force at once' (the same sentence
                                      record_commencement.py reads), when the day is not established;
       general_clauses_silent_act  -- it is silent about its commencement and a general clauses statute the corpus
                                      holds puts its commencement at its assent or first publication
                                      (record_commencement.silent_under_general_clauses), when the day is not
                                      established;
     never: commencement by notification, appointment, in parts, a deemed date, or two sentences that disagree;
  3. NO REPEAL IS KNOWN. Each of these stops the claim:
       * a standing statutory repeal of it (0066), dated or undated;
       * the official portal's catalogue title carries a repeal note ('(Repealed by Act XIV of 2016)');
       * any released provision of ANOTHER law names it -- its title and year -- in a repeal clause (0066's
         pattern), whole or limited by territory or extent, by an instrument of any kind, held repealer or not; or
         says it 'shall cease to have effect' / 'cease to be in force' / 'is hereby omitted'. Wider than 0066's
         recording rule on purpose: a mention this tool cannot settle stops the claim. Only a clause about a
         PROVISION of the law ('section 4 of the X Act, 1990 is hereby repealed') is not counted: it repeals the
         provision, not the law.
What it does NOT cover, carried in the evidence and declared by operative_provision: a repeal by a law the corpus
does not hold, judicial invalidation, and territorial extent.

Recheck: an earlier assertion this run no longer reproduces is withdrawn (a later repeal clause, a withdrawn
commencement). Run after record_commencement.py and record_statutory_repeals.py; then
tools/apply_instrument_metadata.py derives instrument.status.

    python tools/record_status.py            # report
    python tools/record_status.py --apply    # write
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from record_commencement import classify, silent_under_general_clauses  # noqa: E402
from record_instrument_numbers import latest_withdrawn, withdraw  # noqa: E402
from record_statutory_repeals import (KIND, PART_BEFORE, PORTAL_REPEAL_NOTE, REPEAL, norm,  # noqa: E402
                                      title_key)

METHOD = "nizam.status_in_force/1"
KINDS = {"act", "constitution"}
# An Act made before Independence is a law of Pakistan only as continued and adapted; the official consolidated code
# of its jurisdiction publishing it is the evidence of that. A Gazette of India scan of 'The Oudh Courts Act, 1891' or
# 'The Pegu and Sittang Canal Act, 1881' (places in India and Burma) is a historical text, not that evidence.
CONSOLIDATED_CODES = {"pakistancode.gov.pk", "punjabcode.punjab.gov.pk", "sindhlaws.gov.pk", "kpcode.kp.gov.pk",
                      "balochistancode.gob.pk", "www.pakistancode.gov.pk"}
INDEPENDENCE_YEAR = 1947
CEASE = re.compile(r"(?:^|[.;:]\s+|\(\d+\)\s*|\b(?:The|the)\s+)"
                   r"(?P<title>(?:the\s+)?[A-Z][^.;:()\n]{2,160}?\b" + KIND + r"),?\s*(?P<year>1[89]\d\d|20\d\d)"
                   r"[^.;]{0,160}?\b(?:shall\s+cease\s+to\s+(?:have\s+effect|be\s+in\s+force|operate|apply)|"
                   r"(?:is|are|shall\s+stand|stands)\s+(?:hereby\s+)?omitted)", re.S)
NOT_COVERED = ("a repeal by a law the corpus does not hold; judicial invalidation; territorial extent "
               "(operative_provision declares invalidation_coverage 'not_tracked' and extent 'jurisdiction_default')")

# ---- 'lapsed' (migration 0085): an Ordinance the Constitution has repealed by lapse of time ------------------------
# Constitution of 1973 as held (doc 4419): Art. 89(2) -- a President's Ordinance 'shall stand repealed at the
# expiration of one hundred and twenty days from its promulgation', extendable once by 120 days; Art. 128(2) -- a
# Governor's Ordinance, ninety days, extendable once by ninety. Art. 270A (1977-1985) and Art. 270AA (12 Oct 1999 -
# 31 Dec 2003, 'and still in force') continue the Ordinances of their windows; the 1973 text does not govern earlier
# regimes; AJK and GB constitutions are not held. So only federal and provincial Ordinances of 2004 onward.
LAPSE_JURISDICTIONS = {"fed": (240, "stood_repealed_art89_2"), "punjab": (180, "stood_repealed_art128_2"),
                       "sindh": (180, "stood_repealed_art128_2"), "kp": (180, "stood_repealed_art128_2"),
                       "balochistan": (180, "stood_repealed_art128_2")}
# The 120/90-day wording (and its single extension) was inserted by the Constitution (Eighteenth Amendment) Act, 2010
# -- doc 4419's footnotes: 'Ins. and subs. by the Constitution (Eighteenth Amendment) Act, 2010 (Act No. X of 2010),
# s. 27' -- which the corpus holds commenced on 2010-04-20 (doc 4434). The footnotes do not print the words replaced,
# so the corpus does not state the rule for an Ordinance made before then: only Ordinances promulgated under the
# current text are asserted (an established promulgation date on or after 2010-04-20, or a printed year 2011+).
CURRENT_TEXT_FROM = date(2010, 4, 20)
FIRST_UNPROTECTED_YEAR = 2011
AJK_IC = dict(url="https://law.gok.pk/wp-content/uploads/2023/10/AJK-interim-constitution.pdf",
              sha256="5901ea0643fba2bd44af41906ab440b7d52a4937e6a4c9b2ed1ebc165be9867f",
              quote="shall be laid before the Assembly and shall stand repealed at the expiration of four months from "
                    "its promulgation ... Provided that the Assembly may by a resolution extend the Ordinance for a "
                    "further period of four months")
ART = {"stood_repealed_art89_2":"Art. 89(2): 'shall stand repealed at the expiration of one hundred and twenty days "
                                 "from its promulgation' (extendable once by a further one hundred and twenty days)",
       "stood_repealed_art128_2": "Art. 128(2): 'shall stand repealed at the expiration of ninety days from its "
                                  "promulgation' (extendable once by a further ninety days)",
       "stood_repealed_art89_2_four_months": "Art. 89(2) as it stood 1986-2010: 'four months' from promulgation, no "
                                             "extension -- the Eighteenth Amendment, s.27 (doc 4434), substitutes 'for "
                                             "the words \"four months\"'",
       "stood_repealed_art128_2_three_months": "Art. 128(2) as it stood 1986-2010: 'three months' from promulgation, no "
                                               "extension -- the Eighteenth Amendment, s.41 (doc 4434), substitutes 'for "
                                               "the words \"three months\"'",
       "stood_repealed_ajk_interim_constitution_art41": "AJK Interim Constitution, 1974, Art. 41(2)(a): '" + AJK_IC["quote"]
                                                        + "' -- " + AJK_IC["url"] + " (sha256 " + AJK_IC["sha256"] + ")"}
CONTINUE = re.compile(r"(?:^|[.;:]\s+|\(\d+\)\s*|\b(?:The|the)\s+)"
                      r"(?P<title>(?:the\s+)?[A-Z][^.;:()\n]{2,160}?\bOrdinance),?\s*(?P<year>20\d\d)"
                      r"[^.;]{0,200}?\b(?:shall\s+continue|continue\s+to\s+(?:be\s+in\s+force|have\s+effect)|"
                      r"(?:be\s+)?deemed\s+to\s+(?:be|have\s+been)\s+(?:an?\s+)?Act|shall\s+have\s+effect\s+as\s+if)",
                      re.S)


def reason_code(reason: str, kind: str) -> str:
    """The basis an 'unknown' status assertion carries (0088): a stable code for why no status could be asserted."""
    r = reason.strip()
    if r.startswith("kind_not_asserted"):
        if kind == "ordinance":
            return "ordinance_not_assessed"
        # 0089: the enabling law's own currency, where the instrument's enacting formula links one
        parent = r.split(":", 1)[1] if ":" in r else None
        return f"subordinate_{kind}_enabling_law_" + {"current": "in_force", "current_unverified": "unverified",
                                                       "not_current": "not_current",
                                                       "historical": "historical"}.get(parent or "", "not_linked")
    if r.startswith("not_commenced:"):
        r = r.split(":", 1)[1].strip()
        if r.startswith("silent:"):
            return "silent_on_commencement_" + r.split(":", 1)[1].strip()
        return {"partial_or_notified": "commencement_by_notification_or_in_parts",
                "unrecognised_form": "commencement_form_not_recognised",
                "disagreeing_sentences": "commencement_sentences_disagree",
                "at_once_block_not_found": "commencement_source_block_not_found"}.get(r, "commencement_" + r)
    if r.startswith("ordinance_") or r in ("statutory_repeal_stands", "continued_or_deemed_an_act"):
        return r
    return re.sub(r"[^a-z0-9_]+", "_", r.lower()).strip("_")


def continued_against(texts: list[tuple[str, str]]) -> dict[tuple[str, int], list[str]]:
    """(title words, year) -> ids of instruments whose provisions continue an Ordinance or deem it an Act."""
    hits: dict = collections.defaultdict(list)
    for iid, text in texts:
        for m in CONTINUE.finditer(text or ""):
            hits[(norm(m.group("title")), int(m.group("year")))].append(iid)
    return hits


# Before the Eighteenth Amendment. Its own text (doc 4434, s.27 and s.41) substitutes, in Art. 89(2)(a)(i)/(ii), 'for the
# words "four months" the words "one hundred and twenty days"' and inserts the extension proviso; in Art. 128(2)(a),
# 'for the words "three months" the words "ninety days"'. doc 4419's footnotes list every amendment of Art. 89 --
# P.O. 14 of 1985, the Constitution (Second Amendment) Order, 1985 (P.O. 20, which wrote sub-paragraphs (i)/(ii)), and
# the Eighteenth Amendment -- so from 1986 to 2010-04-19 a President's Ordinance stood repealed four months after
# promulgation, a Governor's three, with no extension. Not under that text: 1977-1985 (Art. 270A), 12 Oct 1999 - 31
# Dec 2003 (Art. 270AA), and anything before 1986 (the original 1973 wording is not in the corpus).
OLD_TEXT_WINDOWS = ((date(1986, 1, 1), date(1999, 10, 11)), (date(2004, 1, 1), date(2010, 4, 19)))
OLD_MONTHS = {"fed": 4}
OLD_BASIS = {"fed": "stood_repealed_art89_2_four_months", "prov": "stood_repealed_art128_2_three_months"}


def protected_reason(year: int, d: date | None) -> str:
    """Why an Ordinance outside the lapse windows stays unasserted -- the window it falls in."""
    if (d and date(1977, 7, 5) <= d <= date(1985, 12, 31)) or (not d and 1978 <= year <= 1985):
        return "ordinance_continued_by_art270A_1977_1985"
    if (d and date(1999, 10, 12) <= d <= date(2003, 12, 31)) or (not d and 2000 <= year <= 2003):
        return "ordinance_continued_by_art270AA_1999_2003"
    if year < 1973 or (d and d < date(1973, 8, 14)):
        return "ordinance_of_a_pre_1973_regime"
    return "ordinance_period_boundary_not_established"


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    import calendar
    return date(d.year + y, m + 1, min(d.day, calendar.monthrange(d.year + y, m + 1)[1]))


# AJK: the Azad Jammu and Kashmir Interim Constitution, 1974, Art. 41(2)(a) -- read from the official file
# https://law.gok.pk/wp-content/uploads/2023/10/AJK-interim-constitution.pdf (sha256 5901ea06...e1a4c9b2ed1ebc165be9867f,
# staged 14 Nov 2026; not landed because preflight predicted held structure): an Ordinance 'shall stand repealed at the
# expiration of four months from its promulgation', and the proviso 'the Assembly may by a resolution extend the
# Ordinance for a further period of four months'. At most eight months. The text has no affirmation or validation
# article (no 'affirm' or 'validat' in 115 pages), and no AJK law in the corpus continues Ordinances generally (only
# named ones: 'the ... Ordinance, 1987 ... or its succeeding Ordinance issued from time to time'). Art. 51 continues
# only laws in force before the Constitution commenced (1974): Ordinances of 1975 onward.
AJK_FROM_YEAR = 1975
# A continued Ordinance (Art. 270A, Art. 270AA, an earlier regime's 'existing law' Art. 268 keeps) that a held law
# amends in or after this year was alive when amended: 270A's continues laws in force at 1985; 270AA's those 'still in
# force' at the Eighteenth Amendment (2010); Art. 268's those in force at 14 August 1973.
SURVIVAL_CUT = {"ordinance_continued_by_art270A_1977_1985": 1986, "ordinance_continued_by_art270AA_1999_2003": 2010,
                "ordinance_of_a_pre_1973_regime": 1974}


def ordinance_lapse(jur: str, year: int | None, enacted: str | None, titles: list[str], today: date
                    ) -> tuple[str | None, str, date | None]:
    """(basis or None, refusal, latest possible lapse)."""
    if jur == "ajk":
        if year is None or year < AJK_FROM_YEAR:
            return None, "ajk_ordinance_before_interim_constitution", None
        if not any(re.search(rf"\b{year}\b", t or "") for t in titles):
            return None, "ordinance_year_not_printed_in_title", None
        latest = add_months(date.fromisoformat(enacted) if enacted else date(year, 12, 31), 8)
        if latest + timedelta(days=365) > today:
            return None, "ordinance_may_still_run", latest
        return "stood_repealed_ajk_interim_constitution_art41", "ok", latest
    rule = LAPSE_JURISDICTIONS.get(jur)
    if rule is None:
        return None, "ordinance_outside_art89_128", None
    if year is None:
        return None, "ordinance_without_year", None
    if not any(re.search(rf"\b{year}\b", t or "") for t in titles):
        return None, "ordinance_year_not_printed_in_title", None
    months = OLD_MONTHS.get(jur, 3)
    old_basis = OLD_BASIS["fed" if jur == "fed" else "prov"]
    if enacted:
        d = date.fromisoformat(enacted)
        if d >= CURRENT_TEXT_FROM:
            basis, latest = rule[1], d + timedelta(days=rule[0])
        elif any(a <= d <= b for a, b in OLD_TEXT_WINDOWS):
            basis, latest = old_basis, add_months(d, months)
        else:
            return None, protected_reason(d.year, d), None
    else:
        if year >= 2010:     # under either text an Ordinance of 2010 had gone by mid-2011
            basis, latest = rule[1], date(year, 12, 31) + timedelta(days=rule[0])
        elif any(a.year <= year and date(year, 12, 31) <= b for a, b in OLD_TEXT_WINDOWS) or 2004 <= year <= 2009:
            basis, latest = old_basis, add_months(date(year, 12, 31), months)
        else:
            return None, protected_reason(year, None), None
    if latest + timedelta(days=365) > today:
        return None, "ordinance_may_still_run", latest
    return basis, "ok", latest


PROVISION_LEVEL = re.compile(r"\b(?:sections?|clauses?|sub-sections?|rules?\s+\d|articles?|schedules?|paragraphs?|"
                             r"provisos?|words?|expressions?|entr(?:y|ies)|items?|chapters?|parts?\s+[IVX\d])\b", re.I)


# savings language that only follows the repeal of a WHOLE law: 9296 (Sales Tax Act, 1951) s.40(4) '... unpaid at
# the date of the repeal of that Act' -- its repeal sentence itself is OCR-damaged ('Pakistan G Sales Tax Act')
SAVINGS = re.compile(r"repeal\s+of\s+(?:that|the\s+said)\s+(?:Act|Ordinance)|notwithstanding\s+the\s+repeal|"
                     r"the\s+repealed\s+(?:Act|Ordinance)|repealed\s+by\s+this\s+(?:Act|Ordinance)", re.I)
YEAR = re.compile(r"\b(1[89]\d\d|20\d\d)\b")


def named_against(texts: list[tuple[str, str]]) -> dict[tuple[str, int], list[str]]:
    """(title words, year) -> ids of the instruments whose provisions name a law in a repeal, cease or omit clause,
    or in whole-law savings language. texts: (instrument id, provision text). The key's first element is the normed
    title as printed (for a clause) or the 100 characters before the year (for savings language). A clause about a
    PROVISION of the law ('section 4 of the X Act, 1990 is hereby repealed', '... section 309 is hereby omitted') is
    not a clause about the law and is skipped; a whole repeal, or one limited by territory or extent ('in its
    application to ...'), is counted."""
    hits: dict = collections.defaultdict(list)
    for iid, text in texts:
        text = text or ""
        for rx in (REPEAL, CEASE):
            for m in rx.finditer(text):
                before = text[max(0, m.start() - 60):m.start()]
                gap = m.group(0)[m.end("year") - m.start():]
                if PART_BEFORE.search(before) or PROVISION_LEVEL.search(gap):
                    continue
                hits[(norm(m.group("title")), int(m.group("year")))].append(iid)
        if SAVINGS.search(text):
            for y in YEAR.finditer(text):
                hits[(norm(text[max(0, y.start() - 100):y.start()]), int(y.group(1)))].append(iid)
    return hits


def same_law(mine: str, printed: str) -> bool:
    """mine: the instrument's normed title key; printed: the normed words a clause names. Equal; or one inside the
    other (three words or more in the shorter); or -- OCR, 'Pakistan G Sales Tax Act' -- at least 80% of mine's words
    present in what was printed, mine having three words or more."""
    if not mine or not printed:
        return False
    if mine == printed:
        return True
    short, long_ = sorted((mine, printed), key=len)
    if len(short.split()) >= 3 and _contains(long_, short):
        return True
    words = mine.split()
    return len(words) >= 3 and sum(w in set(printed.split()) for w in words) / len(words) >= 0.8


def _contains(longer: str, shorter: str) -> bool:
    return f" {shorter} " in f" {longer} "


def screen(keys: set[str], year: int, own: set[str], hits: dict, portal_title: str) -> str | None:
    """The reason no 'in_force' may be claimed, or None. keys: the instrument's title keys; own: its own id and its
    twins' (a law's own text naming itself is not a repeal of it). A clause naming the law by a longer or shorter
    form of its title -- 'the General Sales Tax Act, 1948' for 'The Pakistan General Sales Tax Act, 1948' -- also
    stops it: same year, one title's words inside the other's, at least three words in the shorter."""
    if PORTAL_REPEAL_NOTE.search(portal_title or ""):
        return "portal_repeal_note"
    for k, ids in by_year(hits).get(year, ()):
        if all(i in own for i in ids):
            continue
        if any(same_law(mine, k) for mine in keys):
            return "named_in_a_repeal_or_cease_clause"
    return None


_BY_YEAR: dict = {}


def by_year(hits: dict) -> dict:
    """hits indexed by year (cached per hits object)."""
    cached = _BY_YEAR.get(id(hits))
    if cached is None or cached[0] is not hits:
        index: dict = collections.defaultdict(list)
        for (k, y), ids in hits.items():
            index[y].append((k, ids))
        cached = (hits, index)
        _BY_YEAR.clear(); _BY_YEAR[id(hits)] = cached
    return cached[1]


def commencement(cur, iid: str, kind: str, year: int, jur: str, title: str, commenced: str | None,
                 commenced_row) -> tuple[str | None, str, str | None, int | None, int | None]:
    """(basis or None, refusal or quote, ..., block, page)."""
    if commenced and date.fromisoformat(commenced) <= date.today() and commenced_row:
        quote, block, page = commenced_row
        return "commenced_on_established", quote, None, block, page
    cur.execute("""SELECT p.label, concat_ws(' ', p.heading, p.marginal_note), v.text_en, p.first_block, p.first_page
                     FROM provision p
                     LEFT JOIN provision_version v ON v.provision_id = p.id AND upper_inf(v.validity)
                    WHERE p.instrument_id = %s AND p.is_active ORDER BY p.ordinal, p.path""", (iid,))
    every = cur.fetchall()
    first15 = "\n".join(" ".join(filter(None, (r[1], r[2]))) for r in every[:15])
    _value, basis, sentence = classify(first15, None, year)
    if basis == "at_once_without_enacted_date":
        probe = " ".join(sentence.split())[:40]          # the match can open on the newline that joins provisions
        for r in every[:15]:
            if r[3] is not None and probe in " ".join(" ".join(filter(None, (r[1], r[2]))).split()):
                return "commences_at_once", " ".join(sentence.split())[:300], None, r[3], r[4]
        return None, "at_once_block_not_found", None, None, None
    if basis == "no_commencement_sentence":
        refusal = silent_under_general_clauses(jur, kind, year, [(r[0], r[1], r[2]) for r in every], title)
        if refusal is None:
            s1 = next(r for r in every if (r[0] or "").strip() == "1")
            return ("general_clauses_silent_act", " ".join(" ".join(filter(None, s1[:3])).split())[:200], None,
                    s1[3], s1[4])
        return None, f"silent: {refusal}", None, None, None
    return None, basis, None, None, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dump")
    args = ap.parse_args()
    from nizam.storage.db import connect
    counts: collections.Counter = collections.Counter()
    dumped = []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = 0")
        cur.execute("""SELECT i.id::text, i.source_observation_id, i.expression_ordinal, i.document_id,
                              i.jurisdiction::text, i.kind::text, i.year, i.short_title, i.display_title,
                              i.commenced_on::text, i.repealed_by_id IS NOT NULL OR i.status = 'repealed',
                              coalesce(i.text_language, 'en'), coalesce(o.source_metadata->>'title', ''),
                              lower(substring(coalesce(i.source_url, '') from '^https?://([^/:]+)'))
                         FROM v_release_instrument i JOIN source_observation o ON o.id = i.source_observation_id""")
        todo = cur.fetchall()
        cur.execute("""SELECT instrument_id::text, quote, source_block_id, source_page
                         FROM v_instrument_metadata_current WHERE field = 'commenced_on'""")
        comm_rows = {r[0]: r[1:] for r in cur.fetchall()}
        cur.execute("""SELECT DISTINCT repealed_instrument_id::text FROM v_statutory_repeal_current""")
        repealed = {r[0] for r in cur.fetchall()}
        cur.execute("SELECT as_made_instrument_id::text, consolidated_instrument_id::text FROM v_consolidated_twin_current")
        twin: dict = collections.defaultdict(set)
        for a, b in cur.fetchall():
            twin[a].add(b); twin[b].add(a)
        cur.execute("""SELECT i.id::text, v.text_en
                         FROM v_release_instrument i JOIN provision p ON p.instrument_id = i.id AND p.is_active
                         JOIN provision_version v ON v.provision_id = p.id AND upper_inf(v.validity)
                        WHERE v.text_en ~* '(repeal|cease\\s+to|omitted)'""")
        texts = cur.fetchall()
        hits = named_against(texts)
        cur.execute("""SELECT i.id::text, v.text_en
                         FROM v_release_instrument i JOIN provision p ON p.instrument_id = i.id AND p.is_active
                         JOIN provision_version v ON v.provision_id = p.id AND upper_inf(v.validity)
                        WHERE v.text_en ~* '(continue|deemed\\s+to)' AND v.text_en ~* 'Ordinance'""")
        continued = continued_against(cur.fetchall())
        cur.execute("""SELECT instrument_id::text, enacted_on FROM (SELECT id AS instrument_id, enacted_on::text
                         FROM v_release_instrument) e""")
        enacted_of = dict(cur.fetchall())
        cur.execute("""SELECT d.delegated_instrument_id::text, c.currency FROM v_delegation_current d
                         JOIN v_instrument_currency c ON c.instrument_id = d.enabling_instrument_id""")
        parent_currency = dict(cur.fetchall())
        # the latest year a held law amended each instrument (survival evidence for continued Ordinances)
        cur.execute("""SELECT a.amended_instrument_id::text, max(am.year) FROM v_amendment_reference_current a
                         JOIN instrument am ON am.id = a.amending_instrument_id GROUP BY 1""")
        amended_after = dict(cur.fetchall())
        cur.execute("""SELECT source_observation_id, expression_ordinal, value, basis FROM v_instrument_metadata_current
                        WHERE field = 'status'""")
        standing = {(r[0], r[1]): (r[2], r[3]) for r in cur.fetchall()}
        withdrawn = latest_withdrawn(cur, "status")

        def record_unknown(obs, ordinal, iid, reason, kind):
            """0088: an expression this tool cannot assert gets a standing 'unknown' with WHY as its basis, so its
            currency (v_instrument_currency) and every operative row say so. Replaces the old silent withdrawal."""
            code = reason_code(reason, kind)
            if standing.get((obs, ordinal)) == ("unknown", code):
                counts["unknown_unchanged"] += 1; return
            cur.execute("""SELECT p.first_block, p.first_page, concat_ws(' ', p.heading, v.text_en)
                             FROM provision p
                             LEFT JOIN provision_version v ON v.provision_id = p.id AND upper_inf(v.validity)
                            WHERE p.instrument_id = %s AND p.is_active AND p.first_block IS NOT NULL
                            ORDER BY p.ordinal, p.path LIMIT 1""", (iid,))
            fb = cur.fetchone()
            if not fb:
                counts["unknown_no_source_block"] += 1; return
            cur.execute("""INSERT INTO instrument_metadata_assertion
                             (source_observation_id, expression_ordinal, field, value, assertion, basis,
                              source_block_id, source_page, quote, method, evidence, recorded_by)
                           VALUES (%s, %s, 'status', 'unknown', 'asserted', %s, %s, %s, %s, %s, %s::jsonb, 'claude')""",
                        (obs, ordinal, code, fb[0], fb[1], " ".join((fb[2] or "").split())[:300] or "(first provision)",
                         METHOD, json.dumps(dict(reviewer_type="tool", reason=reason, kind=kind,
                                                 screened_on=date.today().isoformat(),
                                                 meaning="no status asserted; the basis says why"))))
            counts["unknown_recorded"] += 1
        def record_lapsed(obs, ordinal, iid, doc, jur, kind, year, short, display, lb, latest):
            counts[f"lapsed: {lb}"] += 1
            if (obs, ordinal) in withdrawn:
                counts["withdrawn_kept"] += 1; return
            if standing.get((obs, ordinal)) == ("lapsed", lb):
                counts["unchanged"] += 1; return
            cur.execute("""SELECT p.first_block, p.first_page, concat_ws(' ', p.heading, v.text_en)
                             FROM provision p
                             LEFT JOIN provision_version v ON v.provision_id = p.id AND upper_inf(v.validity)
                            WHERE p.instrument_id = %s AND p.is_active AND p.first_block IS NOT NULL
                            ORDER BY p.ordinal, p.path LIMIT 1""", (iid,))
            fb = cur.fetchone()
            if not fb:
                counts["no_source_block"] += 1; return
            evidence = dict(reviewer_type="tool", kind=kind, year=year, jurisdiction=jur,
                            promulgated_on=enacted_of.get(iid), latest_possible_lapse=latest.isoformat(),
                            constitution=ART[lb],
                            not_protected="promulgated outside the Art. 270A (1977-1985) and Art. 270AA "
                                          "(12 Oct 1999 - 31 Dec 2003) windows, from 1986 (AJK: 1975)",
                            screened_on=date.today().isoformat(),
                            screen="no statutory repeal standing; no law in the corpus continues it or deems it an Act")
            cur.execute("""INSERT INTO instrument_metadata_assertion
                             (source_observation_id, expression_ordinal, field, value, assertion, basis,
                              source_block_id, source_page, quote, method, evidence, recorded_by)
                           VALUES (%s, %s, 'status', 'lapsed', 'asserted', %s, %s, %s, %s, %s, %s::jsonb, 'claude')""",
                        (obs, ordinal, lb, fb[0], fb[1], " ".join((fb[2] or short or "").split())[:300],
                         METHOD, json.dumps(evidence)))
            counts["recorded"] += 1
            dumped.append(dict(document_id=doc, jur=jur, year=year, title=display or short, basis=lb,
                               quote=f"latest lapse {latest}"))

        for (iid, obs, ordinal, doc, jur, kind, year, short, display, commenced, is_repealed, lang,
             portal_title, host) in todo:
            reason, basis = None, None
            survived = None
            if kind == "ordinance":
                value = "lapsed"
                lb, why, latest = ordinance_lapse(jur, year, enacted_of.get(iid), [short or "", display or ""],
                                                  date.today())
                if lb and (is_repealed or iid in repealed):
                    lb, why = None, "statutory_repeal_stands"
                if lb:
                    keys = {k for k in (title_key(short), title_key(display) if display else None) if k}
                    own = {iid} | twin[iid]
                    if any(any(same_law(mine, k) for mine in keys) and not all(x in own for x in ids)
                           for (k, y), ids in continued.items() if y == year):
                        lb, why = None, "continued_or_deemed_an_act"
                if not lb and why in SURVIVAL_CUT and (amended_after.get(iid) or 0) >= SURVIVAL_CUT[why]:
                    # a continued Ordinance a held later law amends after its window was alive then: it is tested
                    # as an Act is (commenced, and no repeal known)
                    counts[f"ordinance_survived: {why}"] += 1
                    lb = None
                    survived = why
                else:
                    survived = None
                if not lb and not survived:
                    counts[f"ordinance: {why}"] += 1
                    record_unknown(obs, ordinal, iid, why, kind)
                    continue
                if not survived:
                    record_lapsed(obs, ordinal, iid, doc, jur, kind, year, short, display, lb, latest)
                    continue
            if kind not in KINDS and not (kind == "ordinance" and survived):
                reason = "kind_not_asserted" + (f":{parent_currency[iid]}" if iid in parent_currency else "")
            elif year is None:
                reason = "no_year"
            elif year < INDEPENDENCE_YEAR and host not in CONSOLIDATED_CODES:
                reason = "pre_independence_not_from_a_consolidated_code"
            elif is_repealed or iid in repealed:
                reason = "statutory_repeal_stands"
            else:
                keys = {k for k in (title_key(short), title_key(display) if display else None) if k}
                reason = screen(keys, year, {iid} | twin[iid], hits, " ".join((short or "", display or "",
                                                                              portal_title)))
            if reason is None and lang != "en" and not commenced:
                reason = "non_english_text_without_established_commencement"
            if reason is None:
                basis, quote, _x, block, page = commencement(cur, iid, kind, year, jur, display or short or "",
                                                             commenced, comm_rows.get(iid))
                if basis is None:
                    reason = f"not_commenced: {quote}"
            if reason:
                counts[reason.split(":")[0] if reason.startswith("not_commenced") else reason] += 1
                if reason.startswith("not_commenced"):
                    counts[reason] += 1
                record_unknown(obs, ordinal, iid, reason, kind)
                continue
            counts[f"in_force: {basis}"] += 1
            if (obs, ordinal) in withdrawn:
                counts["withdrawn_kept"] += 1; continue
            if standing.get((obs, ordinal), (None,))[0] == "in_force":
                counts["unchanged"] += 1; continue
            if block is None:
                counts["no_source_block"] += 1; continue
            evidence = dict(reviewer_type="tool", kind=kind, year=year, jurisdiction=jur, commencement=basis,
                            continued_ordinance_alive_when_amended=(
                                {"window": survived, "last_amended_by_held_law_in": amended_after.get(iid)}
                                if survived else None),
                            commenced_on=commenced, screened_on=date.today().isoformat(),
                            repeal_screen="no standing statutory repeal; no portal repeal note; no released "
                                          "provision of another law names it in a repeal, cease or omit clause",
                            not_covered=NOT_COVERED)
            cur.execute("""INSERT INTO instrument_metadata_assertion
                             (source_observation_id, expression_ordinal, field, value, assertion, basis,
                              source_block_id, source_page, quote, method, evidence, recorded_by)
                           VALUES (%s, %s, 'status', 'in_force', 'asserted', %s, %s, %s, %s, %s, %s::jsonb,
                                   'claude')""",
                        (obs, ordinal, basis, block, page, quote, METHOD, json.dumps(evidence)))
            counts["recorded"] += 1
            dumped.append(dict(document_id=doc, jur=jur, year=year, title=display or short, basis=basis,
                               quote=quote[:160]))
        if not args.apply:
            conn.rollback()
    if args.dump:
        Path(args.dump).write_text(json.dumps(dumped, ensure_ascii=False, indent=0), encoding="utf-8")
    print(json.dumps(dict(sorted(counts.items())), indent=1))
    print("applied" if args.apply else "dry run (rolled back); pass --apply to write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
