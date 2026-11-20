"""The gate's scope vetoes (D-102; docs/04 §8: "legal vetoes -- time / place / source / authority"): questions the
corpus cannot answer whatever retrieval finds. Pure functions over the question text and the requested date; no
database, no model. Each returns a typed finding or None, and the gate turns a finding into an Abstention.

  time    the law at a future date (as_of after today, or a question asking what the law WILL be)  NO_VALID_VERSION
  place   the law OF a foreign place, with no Pakistani place in the question                        CORPUS_GAP
  source  what a court, tribunal or ombudsman decided, or a law-report citation: no judgments yet    CORPUS_GAP

Latin script only for now: an Urdu-script question meets only the classifier (recorded in D-102).

A mention is not a veto. "My husband lives in Saudi Arabia and sends no maintenance" asks Pakistani family law; only
a LEGAL noun tied to the foreign place ("labour laws in Saudi Arabia", "UAE visa", "theft in the UAE") vetoes, and
any Pakistani place (places.py, or the word Pakistan) lifts it. "British citizenship" is an adjective, not a place.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from nizam.retrieval import places as _places


@dataclass(frozen=True)
class ScopeFinding:
    code: str            # an Abstention code (docs/04 §8.1)
    kind: str            # time | place | source
    reason: str          # for the trace and the public reason
    matched: str         # the words that triggered it (INV-3: replayable)


# Countries in their common English names, a few capitals and the cities Pakistanis most often ask about (the Gulf,
# Afghanistan, the UK). Ordinary English words and personal names that are also countries are left out (Chad, Jordan,
# Georgia, Turkey as a word is kept capitalised only). 'Kashmir' alone is not foreign (AJK, places.py).
_FOREIGN = """Afghanistan Kabul Kandahar Herat Jalalabad|India|New Delhi|Delhi Mumbai Bombay Kolkata Chennai Bangalore
  Bangladesh Dhaka|Sri Lanka|Colombo Nepal Kathmandu Bhutan Maldives Iran Tehran Mashhad Iraq Baghdad Karbala Najaf
  Syria Damascus Lebanon Beirut Israel Palestine Egypt Cairo Libya Tunisia Algeria Morocco Sudan Ethiopia Kenya Nigeria
  |South Africa|Saudi Arabia|Saudi|KSA|Riyadh Jeddah Mecca Makkah Medina Madinah|United Arab Emirates|UAE|Dubai|Abu Dhabi|
  Sharjah Ajman Qatar Doha Kuwait Bahrain Manama Oman Muscat Yemen Turkey Istanbul Ankara China Beijing Shanghai
  |Hong Kong|Japan Tokyo|South Korea|Korea Malaysia|Kuala Lumpur|Singapore Indonesia Jakarta Thailand Bangkok
  Philippines Vietnam Australia Sydney Melbourne|New Zealand|Canada Toronto Vancouver|United States|USA|America
  |New York|Washington|Texas|California|Chicago|United Kingdom|UK|Britain|England London Manchester Birmingham
  Bradford Scotland Glasgow Wales Ireland Dublin France Paris Germany Berlin Italy Rome Spain Madrid Portugal
  Netherlands Amsterdam Belgium Brussels Switzerland Geneva Austria Sweden Norway Denmark Finland Poland Greece
  Russia Moscow Ukraine Kazakhstan Uzbekistan Tajikistan Turkmenistan Kyrgyzstan Azerbaijan Armenia"""
_MULTI = {"New Delhi", "Sri Lanka", "South Africa", "Saudi Arabia", "United Arab Emirates", "Abu Dhabi", "Hong Kong",
          "South Korea", "Kuala Lumpur", "New Zealand", "United States", "New York", "United Kingdom"}


def _names(spec: str) -> list[str]:
    out = []
    for chunk in spec.split("|"):
        chunk = " ".join(chunk.split())
        if chunk in _MULTI:
            out.append(chunk)
        elif chunk:
            out.extend(chunk.split())
    return out


FOREIGN_PLACES = frozenset(_names(_FOREIGN))
_F = "(?:the\\s+)?(" + "|".join(sorted((re.escape(n) for n in FOREIGN_PLACES), key=len, reverse=True)) + ")"
_EDGE_L, _EDGE_R = r"(?<![A-Za-z&-])", r"(?![A-Za-z&-])"
# Nouns naming a body of law, not facts: "my marriage took place in the UK" asks whether Pakistani law recognises it.
_LEGAL = (r"(?:law|laws|legal system|right|rights|punishment|penalty|penalties|rules|regulations|visa|courts|"
          r"constitution|penal code)")
# a legal noun, then within a few words 'in / of / under <foreign place>'
_LOCUS = re.compile(r"\b" + _LEGAL + r"\b[^.?!]{0,45}?\b(?:in|of|under)\s+" + _EDGE_L + _F + _EDGE_R, re.I)
# '<foreign place or its adjective> law(s) / rules / courts / visa / penal code'; '<foreign place>'s law'.
# Adjectives only here: "British citizenship" and "a Saudi employer" name no body of law.
_DEMONYMS = ("Afghan|Indian|Iranian|Iraqi|Saudi|Emirati|Qatari|Kuwaiti|Omani|Bahraini|Turkish|Chinese|Bangladeshi|"
             "British|English|Scottish|American|Canadian|Australian|German|French|Malaysian|Russian")
_ATTR = re.compile(r"(?<![A-Za-z&-])(" + "|".join(sorted((re.escape(n) for n in FOREIGN_PLACES), key=len, reverse=True))
                   + "|" + _DEMONYMS + r")(?:'s)?\s+(?:[a-z]+\s+)?(?:law|laws|rules|courts?|visa|penal code|"
                   r"constitution|labour law|labor law|tax law)\b")
_PAKISTAN = re.compile(r"(?<![A-Za-z])Pakistan(?![A-Za-z])|\bPakistani\s+(?:law|laws|courts?|legal)\b")

_BODY = r"(?:supreme court|high court|federal shariat court|shariat court|court|bench|tribunal|ombudsman|mohtasib|" \
        r"commission|judge|justice|apex court|sc|lhc|shc|phc|bhc|ihc|fsc)"
_DECIDE = r"(?:decide|decided|hold|held|rule|ruled|say|said|order|ordered|direct|directed|find|found|declare|declared|" \
          r"conclude|concluded|observe|observed)"
# Past tense only, and only a question ABOUT a decision: "How do I get the family court to order maintenance?" and
# "Can I appeal the judgment of the civil court?" are procedure questions the statutes answer, not precedent requests.
_SOURCE = [
    re.compile(r"\b(?:what|how)\s+(?:did|has|have)\b[^?]{0,70}?\b" + _BODY + r"s?\b[^?]{0,50}?\b" + _DECIDE + r"\b",
               re.I),
    re.compile(r"\b(?:case law|precedents?|leading cases?|landmark (?:cases?|judgments?))\b", re.I),
    re.compile(r"\b(?:judgment|judgement|verdict|ruling|decision)\s+in\s+(?:the\s+)?[A-Z][^?]{0,60}?\bcase\b"),
    re.compile(r"\b(?:PLD|SCMR|YLR|CLC|PCrLJ|P\s?Cr\.?\s?L\.?\s?J|MLD|PTD|CLD|PLC)\s*\(?\s*(?:19|20)\d{2}\b"),
]

# The law at a future date, not facts in the future: "What will the tax slabs be in 2029?" vetoes, "My rent is due
# next month; will the landlord evict me?" does not (the future is the facts', the law asked is today's).
_MONTHS = r"(?:january|february|march|april|may|june|july|august|september|october|november|december)"
_WHAT_WILL = re.compile(r"\b(?:what|how much|how many|which)\s+will\b[^?]{0,90}?\b(?:be|become|change|rise|increase|"
                        r"go up|apply)\b", re.I)
_NEXT = re.compile(r"\bnext\s+(?:year|month|week|budget|fiscal year|financial year|tax year|" + _MONTHS + r")\b", re.I)
_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


def time_veto(text: str, as_of: date, today: date | None = None) -> ScopeFinding | None:
    today = today or date.today()
    if as_of > today:
        return ScopeFinding("NO_VALID_VERSION", "time",
                            f"the law as at {as_of.isoformat()} is not known yet: the corpus serves law up to today",
                            as_of.isoformat())
    if not _WHAT_WILL.search(text or ""):
        return None
    m = _NEXT.search(text)
    if m:
        return ScopeFinding("NO_VALID_VERSION", "time", "the question asks what the law will be at a future date",
                            m.group(0))
    later = [y for y in _YEAR.findall(text) if int(y) > as_of.year]
    if later:
        return ScopeFinding("NO_VALID_VERSION", "time", f"the question asks about the law in {later[0]}, after the "
                            f"requested date", later[0])
    return None


def pakistani_place(text: str) -> bool:
    return bool(_places.places(text) or _PAKISTAN.search(text or ""))


def place_veto(text: str, cited: bool = False) -> ScopeFinding | None:
    """the law of a foreign place; lifted by any Pakistani place in the question or a resolved citation"""
    if cited or pakistani_place(text):
        return None
    m = _LOCUS.search(text or "") or _ATTR.search(text or "")
    if not m:
        return None
    return ScopeFinding("CORPUS_GAP", "place", f"the question asks about the law of {m.group(1)}; the corpus holds "
                        "the law of Pakistan, its provinces and territories only", m.group(0))


def source_veto(text: str) -> ScopeFinding | None:
    for rx in _SOURCE:
        m = rx.search(text or "")
        if m:
            return ScopeFinding("CORPUS_GAP", "source", "the question asks what a court or tribunal decided; the "
                                "corpus holds no judgments yet (statutes only, D-100)", m.group(0))
    return None


# --- records, statistics and live figures (D-106): facts about particular people or the world, not law -------------
_RECORD_NOUN = r"(?:FIR|F\.I\.R|case|cases|complaint|application|registration|sale deed|deed|licen[cs]e|warrant)"
# "Is a case against my husband maintainable?" is a law question: a record lookup asks whether one EXISTS
_RECORDS = [
    re.compile(r"\b(?:is|are)\s+there\s+(?:any\s+|an?\s+)?" + _RECORD_NOUN +
               r"[^?]{0,40}?\b(?:against|on|for)\s+(?:me|my|him|her|his|us|our)\b", re.I),
    re.compile(r"\bhas\s+(?:any|an?)\s+" + _RECORD_NOUN + r"\s+been\s+(?:registered|filed|lodged)\s+against\b", re.I),
    re.compile(r"\bis\s+my\s+name\s+(?:on|in)\s+(?:the\s+)?(?:[\w-]+\s+){0,3}(?:list|roll|record|register|ECL)\b",
               re.I),
    re.compile(r"\bhas\s+anyone\s+(?:registered|filed|bought|sold)\b", re.I),
    re.compile(r"\bis\s+[A-Z][\w&.'-]*(?:\s+[A-Z(][\w&.'()-]*){0,5}\s+registered\s+with\b"),
    re.compile(r"\bdoes\s+(?:the\s+)?[^?]{0,40}?['\"‘’][^'\"‘’]{2,40}['\"‘’]\s+(?:hold|have)\s+(?:a\s+)?"
               r"(?:[\w-]+\s+){0,3}licen[cs]e", re.I),
    re.compile(r"\bwho\s+are\s+its\s+directors\b", re.I),
]
_STAT_NOUN = r"(?:cases|FIRs|complaints|applications|people|persons|marriages|divorces|prisoners|petitions|suits)"
_STATISTICS = re.compile(r"\bhow\s+many\s+(?:[a-z-]+\s+){0,3}?" + _STAT_NOUN + r"\b[^?]{0,60}?\b(?:were|have\s+been|"
                         r"are|was|has\s+been)?\s*(?:registered|filed|reported|recorded|decided|lodged|instituted)\b",
                         re.I)
# market and live readings only: "the current price of stamp paper" or "the current minimum wage" asks the law
_LIVE_THING = (r"(?:exchange\s+rate|dollar\s+(?:to\s+rupee\s+)?(?:exchange\s+)?rate|policy\s+rate|kibor|"
               r"gold\s+(?:price|rate)|petrol\s+(?:price|rate)|market\s+(?:value|price|rate)|share\s+price|"
               r"air\s+quality(?:\s+index)?|\bworth\b)")
_LIVE_TIME = r"(?:today|today's|now|right\s+now|current|currently|latest|at\s+present|this\s+week)"
_LIVE = [re.compile(_LIVE_THING + r"[^?]{0,50}?\b" + _LIVE_TIME + r"\b", re.I),
         re.compile(r"\b" + _LIVE_TIME + r"\b[^?]{0,50}?" + _LIVE_THING, re.I)]


def records_veto(text: str) -> ScopeFinding | None:
    for rx in _RECORDS:
        m = rx.search(text or "")
        if m:
            return ScopeFinding("CORPUS_GAP", "records", "the question asks about a particular record (a case, "
                                "registration, list or licence); the library holds the law, not records", m.group(0))
    return None


def statistics_veto(text: str) -> ScopeFinding | None:
    m = _STATISTICS.search(text or "")
    if m:
        return ScopeFinding("CORPUS_GAP", "statistics", "the question asks for a count of cases or events; the "
                            "library holds the law, not statistics", m.group(0))
    return None


def live_veto(text: str) -> ScopeFinding | None:
    for rx in _LIVE:
        m = rx.search(text or "")
        if m:
            return ScopeFinding("CORPUS_GAP", "live", "the question asks for a live figure (a rate, price or "
                                "reading); the library holds the law, not market or live data", m.group(0))
    return None


def veto(text: str, as_of: date, cited: bool = False, today: date | None = None) -> ScopeFinding | None:
    """the first finding in a fixed order (time, source, place, records, statistics, live) or None"""
    return (time_veto(text, as_of, today) or source_veto(text) or place_veto(text, cited) or records_veto(text)
            or statistics_veto(text) or live_veto(text))
