"""Query understanding, first step (D-097; docs/04 R0): what a question cites, where it is, what to search for.

A QuerySpec is what L3 retrieves from. Today it carries:
  citations   recognised citations, to be resolved from the database (nizam.retrieval.citations)
  territory   the one territory a place in the question names (nizam.retrieval.places), else None
  lexical     the words the lexical search reads: the question with its frame stripped when it reads as a sentence
  script      'latin' or 'arabic' (Urdu script is recorded; the lexical index is English and cannot match it)

Frame stripping (pronouns, question words, auxiliaries) is applied only to a question that reads as a sentence: seven
or more words, or a question mark. Measured (D-097): on everyday questions it lifted recall@50 from 0.225 to 0.325,
while stripping short statutory phrases cost professional queries (0.750 -> 0.667); a short phrase keeps its words.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from nizam.retrieval import citations as _cit
from nizam.retrieval import places as _places

FRAME = frozenset("""i me my mine we us our you your he him his she her they them their it its this that these those
what which who whom whose when where why how can could may might must shall should will would do does did done is
am are was were be been being have has had having a an the of to in on at for from by with about as into than then
so if or and but not no yes there here want wants wanted get gets got let tell know please any some someone anyone
also just still even only very really allowed legal law laws rule rules""".split())
SENTENCE_WORDS = 7


@dataclass
class QuerySpec:
    text: str
    lexical: str
    citations: list = field(default_factory=list)
    territory: str | None = None
    places: list = field(default_factory=list)
    script: str = "latin"
    sentence: bool = False


def strip_frame(q: str) -> str:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", q)
    kept = [w for w in words if w.lower().strip("'") not in FRAME]
    return " ".join(kept) or q


def parse(text: str) -> QuerySpec:
    t = " ".join((text or "").split())
    words = re.findall(r"[^\W_]+", t)
    sentence = len(words) >= SENTENCE_WORDS or "?" in t or "؟" in t
    script = "arabic" if re.search(r"[؀-ۿ]", t) else "latin"
    found = _places.places(t)
    return QuerySpec(text=t, lexical=strip_frame(t) if sentence else t, citations=_cit.find(t),
                     territory=_places.territory_of(t), places=found, script=script, sentence=sentence)
