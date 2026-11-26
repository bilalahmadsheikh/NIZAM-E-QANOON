"""How a judgment treats a case it cites, read from the court's own words (D-160; docs/PRECEDENT-MODEL.md §2.1).

    treatment_of(sentence, cite_start, cite_end) -> str | None

The vocabulary is PRECEDENT-MODEL §2.1's; polarity is a fixed map, never stored (§2.1):
  positive  applied, followed, approved
  neutral   explained, distinguished          ('cited' is every resolved citation already: not repeated here)
  negative  overruled, per_incuriam, disapproved
'doubted' is not read: in these judgments 'doubt' is the benefit of the doubt far more often than a treatment.

The grammar is strict because the survey of 33,047 resolved case citations (26 Nov 2026) showed how these words
mislead:
  * the words must be in the SAME sentence as the citation, and be the court's: a sentence reporting what counsel
    contended, argued, submitted or relied on is never a treatment by the court;
  * 'the objection is overruled' overrules an objection, not a case;
  * 'X was overruled in/by Y' reports a THIRD case's treatment of X: it is not the citing judgment's;
  * 'in the following manner', 'the following principle' are not 'followed'.
Every reading is a machine candidate. A negative one is shown only once a lawyer verifies it (§2, docs/06 §5.1).
"""
from __future__ import annotations

import hashlib
import re

POLARITY = {"applied": "positive", "followed": "positive", "approved": "positive",
            "explained": "neutral", "distinguished": "neutral",
            "overruled": "negative", "per_incuriam": "negative", "disapproved": "negative"}
NEGATIVE = frozenset(k for k, v in POLARITY.items() if v == "negative")

# a sentence that reports a party's case, not the court's view
_PARTY = re.compile(r"\b(?:counsel|advocate|a\.?\s?s\.?\s?c\b|contend(?:s|ed|ing)?|argu(?:es|ed|ing)|submit(?:s|ted)|"
                    r"urg(?:es|ed)|plead(?:s|ed)|the\s+petitioners?\s+(?:rel|plac)|the\s+appellants?\s+(?:rel|plac)|"
                    r"the\s+respondents?\s+(?:rel|plac)|learned\s+(?:law\s+officer|d\.?a\.?g|a\.?g\.?|prosecutor))",
                    re.I)
_RULES: list[tuple[str, re.Pattern]] = [
    # the citing court itself overrules: 'is/are/stands (hereby) overruled', 'we overrule'; never an objection,
    # and never 'was/has been overruled in/by' (a third case's act)
    ("overruled", re.compile(r"\b(?:is|are|stands|stand)\s+(?:hereby\s+)?overruled\b(?!\s+(?:in|by)\b)|"
                             r"\bwe\s+(?:hereby\s+)?overrule\b", re.I)),
    ("per_incuriam", re.compile(r"\b(?:is|are|was|were|being)\s+(?:a\s+(?:judgment|decision)\s+)?per\s+incuriam\b|"
                                r"\bwe\s+(?:hold|find|declare)\b[^.;]{0,80}\bper\s+incuriam\b", re.I)),
    ("disapproved", re.compile(r"\b(?:is|was|are|were)\s+not\s+(?:a\s+)?good\s+law\b|"
                               r"\bwe\s+(?:do\s+not|cannot|are\s+unable\s+to)\s+(?:approve|agree\s+with)\b", re.I)),
    ("distinguished", re.compile(r"\b(?:is|are|was|were|being)\s+(?:clearly\s+|quite\s+)?distinguishable\b|"
                                 r"\b(?:is|are)\s+distinguished\b|\bwe\s+(?:would\s+)?distinguish\b", re.I)),
    # only the court's own active voice: a passive 'was followed (by a Bench in ...)' is a third case following it
    ("followed", re.compile(r"\b(?:we|this\s+court)\s+(?:would\s+)?(?:respectfully\s+)?follow(?:ed)?\b(?!\s+the\s+following)|"
                            r"\b(?:we\s+are|this\s+court\s+is)\s+bound\s+by\b", re.I)),
    ("approved", re.compile(r"\bwe\s+(?:fully\s+|respectfully\s+)?approve\b", re.I)),
    # the present 'reliance is placed' is the court's; the past 'reliance was placed' is as often counsel's
    ("applied", re.compile(r"\breliance\s+(?:is|has\s+been)\s+(?:also\s+)?placed\s+(?:up)?on\b|"
                           r"\b(?:we|this\s+court)\s+(?:would\s+)?(?:also\s+)?rel(?:y|ied)\s+(?:up)?on\b", re.I)),
    ("explained", re.compile(r"\bwe\s+(?:would\s+)?explain\b", re.I)),
]
# Measured on 26 Nov 2026 (author read, D-160): passive 'approved' read 0/4 right ('the census is approved'),
# 'it was explained in X' is X explaining the law (not a treatment of X), and passive 'followed' was mostly a third
# case following X; those forms were dropped. 'distinguishable' read 6/6.


def sentence_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    """the sentence holding text[start:end]: from after the last '. ' or '; ' before it to the next after it"""
    a = max(text.rfind(". ", 0, start), text.rfind("; ", 0, start))
    nxt = [x for x in (text.find(". ", end), text.find("; ", end)) if x >= 0]
    b = min(nxt) + 1 if nxt else len(text)
    return a + 2 if a >= 0 else 0, b


def treatment_of(sentence: str) -> str | None:
    """the court's treatment, by the first rule that reads in the sentence; None when it reads none, or when the
    sentence reports a party's case"""
    if _PARTY.search(sentence):
        return None
    for name, rx in _RULES:
        if name == "overruled" and _OVERRULED_OTHER.search(sentence):
            continue                                    # an objection, a plea, an application is overruled
        if rx.search(sentence):
            return name
    return None


_OVERRULED_OTHER = re.compile(r"\b(?:objections?|pleas?|contentions?|arguments?|submissions?|applications?|requests?|"
                              r"prayers?|exceptions?)\b[^.;]{0,80}\boverrul", re.I)


def review_key(sentence: str, dst_case_key: str, treatment: str) -> str:
    """a reviewer's decision outlives a rebuild: keyed by the evidence's words, the case treated and the treatment"""
    words = " ".join(sentence.split())
    return hashlib.sha256(f"{words}\x1f{dst_case_key}\x1f{treatment}".encode()).hexdigest()
