"""Names withheld in sensitive judgments (D-131; D-122; docs/PRECEDENT-MODEL.md §6.3). Pure functions.

Used by the builder (nizam.workers.judgment_privacy), which decides once per judgment what is withheld, and by the
readers (nizam.storage.judgment_read), which redact text and refuse a search that names a withheld person.

- `parties(text)`: the first 'A v. B' pair printed in a header, with role words ('...Petitioner(s)') dropped.
- `is_institution(side)`: the State, a government, an office, a court, a company: never withheld.
- `names_of(side)`: the persons named on one side ('Ch. X (deceased) through his widow Mst. Y' -> X, Y).
- `victim_names(texts)`, `minor_names(texts)`: persons the body names as a victim, prosecutrix or abductee, every
  'Mst.'/'Miss' name (sexual offences), or as a minor or juvenile. Best effort: a name the text never ties to those
  words is not found, and the limits are reported (D-131).
- `redact(text, names)`: each withheld name replaced by WITHHELD, longest first, whole words only.
- `names_queried(query, names)`: whether a query names a withheld person (a whole name, or two of its words).
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

WITHHELD = "[name withheld]"


@lru_cache(maxsize=1)
def common_words() -> frozenset[str]:
    """The words typed in at least 3 released SC judgments (the J9 list, D-130): a one-word name that is one of them
    ('Muhammad', 'Ali') is not withheld wherever it occurs, only as part of the full name."""
    path = Path(__file__).resolve().parents[1] / "corpus" / "data" / "judgment_vocab.txt"
    try:
        return frozenset(path.read_text(encoding="utf-8").split())
    except OSError:
        return frozenset()

_VS = re.compile(r"\s(?:versus|vs\.?|v/s|v\.)\s", re.I)
# one character class for the dots, dashes and spaces before a role word: '(?:\.{2,}|-{2,}|\s)*' split a long run of
# dashes in exponentially many ways ('... etc. ----------------', D-131)
_ROLE = re.compile(r"[\s.…\-]*\(?\b(?:petitioners?|appellants?|applicants?|respondents?|complainants?|"
                   r"accused|convicts?|plaintiffs?|defendants?|decree[- ]holders?|judgment[- ]debtors?)\b\s*(?:\(s\))?"
                   r"\)?\.?\s*$", re.I)
_STOP_LEFT = re.compile(r".*(?:\)|\]|/\s*\d{4}\b|\b(?:of\s*\d{4}|\d{4}\.)|(?:jurisdiction|department)\s*[\])]?)\s*",
                        re.I | re.S)
# 'JUDGMENT' spelled out (spaced or not), never 'Judge': 'Learned District Judge' is a party
_STOP_RIGHT = re.compile(r"\s*(?:\(|…|\.{3,}|\b(?:date\s+of\s+hearing|for\s+the|petitioners?\s+by|appellants?\s+by|"
                         r"respondents?\s+by|present\b|order\s+with|sr\.?\s*no|s\.\s*no|"
                         r"j\s*u\s*d\s*g\s*e?\s*m\s*e\s*n\s*t\b|order\b|in\s+the\s+matter|criminal\s+appeal|"
                         r"writ\s+petition|murder\s+reference))", re.I)

_INSTITUTION = re.compile(
    r"\b(?:the\s+state|state\b|government|govt|province|federation|pakistan|punjab|sindh|khyber|balochistan|"
    r"islamabad|azad|secretary|commissioner|collector|director|inspector|police|s\.?h\.?o|station\s+house|"
    r"registrar|judge|court|tribunal|board|authority|commission|council|corporation|company|ltd|limited|bank|"
    r"university|college|school|department|ministry|wapda|nab|fbr|c\.?i\.?r|election|municipal|committee|"
    r"district|officer|chairman|union|society|association|trust|m/s|messrs|pvt|private|enterprises?|industries|"
    r"mills|tehsil|cantonment|hospital|institute|agency|federal|provincial|cooperative|insurance|estate|"
    r"development|ltd\.|deputy|assistant|chief|minister|president|accountability|customs|revenue|excise|"
    r"municipality|town|cda|lda|pda|rda|kda|k-electric|lesco|pesco|fesco|iesco|gepco|mepco|hesco|sngpl|ssgc|"
    r"railways?|post|nadra|ogra|pta|pemra|secp)\b", re.I)
_HONORIFIC = re.compile(r"^\s*(?:mst\.?|mrs\.?|mr\.?|miss|ms\.?|ch\.?|chaudhry|rana|malik|mian|syed|hafiz|haji|"
                        r"dr\.?|sardar|raja|khawaja|kh\.?|sh\.?|sheikh|qazi|pir|sahibzada|nawab|begum|bibi)\s+", re.I)


def parties(text: str) -> tuple[str, str] | None:
    """The first 'A v. B' printed in `text` (a header), each side cut at what plainly is not a name."""
    if not text:
        return None
    t = " ".join(text.split())
    m = _VS.search(t)
    if not m:
        return None
    left = t[max(0, m.start() - 300):m.start()]     # the name sits just before 'versus'; a long header is not rescanned
    sm = _STOP_LEFT.match(left)
    if sm and sm.end() < len(left):
        left = left[sm.end():]
    left = _ROLE.sub("", left[-160:]).strip(" .,;:-…()[]")
    right = t[m.end():]
    rm = _STOP_RIGHT.search(right)
    right = _ROLE.sub("", right[:rm.start()] if rm else right[:160]).strip(" .,;:-…()[]")
    if not left or not right or len(left) > 160 or len(right) > 160:
        return None
    return left, right


def is_institution(side: str) -> bool:
    return bool(_INSTITUTION.search(side))


def names_of(side: str) -> list[str]:
    """The persons named on one side, each as printed without an honorific, 'etc.' or 'and others'."""
    s = re.sub(r"(?i)\(\s*deceased\s*\)|\b(?:etc\.?|and\s+(?:\d+\s+)?(?:another|others?))|&\s*(?:\d+\s+)?(?:another|others?)"
               r"|\b\d+\s+others?\b", " ", side)
    # an order sheet's column labels can stick to a name ('where necessary. Munawar Hussain'); an honorific's stop is
    # kept, every other full stop ends a part
    s = re.sub(r"(?i)order\s+with\s+signatures?\s+of\s+(?:the\s+)?judges?|(?:and\s+)?that\s+of\s+parties(?:\s+or\s+counsel)?|"
               r"where\s+necessary|s\.?\s*no\.?\s+of\s+order|date\s+of\s+order|proceedings?", " ", s)
    s = re.sub(r"(?i)\b(Mst|Mrs|Mr|Ms|Dr|Ch|Sh|Kh|M)\.\s*", r"\1 ", s)
    out = []
    for part in re.split(r"(?i)\s*(?:,|&|\.\s+|\band\b|\bthrough\s+(?:his|her|their)?\s*\w*|\balias\b|\bs/o\b|\bd/o\b|"
                         r"\bw/o\b|\bson\s+of\b|\bdaughter\s+of\b|\bwife\s+of\b|\bwidow\b)\s*", s):
        part = _HONORIFIC.sub("", part.strip(" .,;:()-")).strip(" .,;:()-")
        if len(part) >= 3 and not is_institution(part) and re.search(r"[A-Za-z]{3}", part):
            out.append(" ".join(part.split()))
    return list(dict.fromkeys(out))


# one space between words (texts are whitespace-folded first): '\s+' beside an optional part and '\s*' backtracks
# without end on a long run of spaces, which OCR text has (D-131)
_NAME = r"(?:(?:Mst|Mrs|Miss|Ms|Mr)\.? )?[A-Z][a-z]+(?: (?:(?:ul|ud|un|ur)[- ])?[A-Z][a-z]+){0,3}"
# a name of two words or more, or one word after an honorific: a capitalised word that opens a sentence before 'the
# victim' ('Oftentimes the victim's husband') is not a name
_NAME2 = (r"(?:(?:Mst|Mrs|Miss|Ms|Mr)\.? [A-Z][a-z]+(?: [A-Z][a-z]+){0,2}|"
          r"[A-Z][a-z]+(?: (?:(?:ul|ud|un|ur)[- ])?[A-Z][a-z]+){1,3})")
_KIN = r"(?:\s+(?:son|daughter|child|girl|boy|brother|sister|niece|nephew))?"
_VICTIM_BEFORE = re.compile(r"\b(?:victim|prosecutrix|abductee|the\s+deceased\s+girl)\s*(?:namely|i\.e\.?|viz\.?|,)?\s*"
                            r"\(?\s*(" + _NAME + r")")
_VICTIM_AFTER = re.compile(r"(" + _NAME2 + r")\s*\(?\s*(?:the\s+)?(?:victim|prosecutrix|abductee)\b")
_MST = re.compile(r"\b(?:Mst|Miss)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})")
_MINOR_BEFORE = re.compile(r"\b(?:minor|juvenile)" + _KIN + r"\s*(?:namely|i\.e\.?|viz\.?|,)?\s*\(?\s*(" + _NAME + r")")
_MINOR_AFTER = re.compile(r"(" + _NAME2 + r")\s*\(\s*[“\"']?\s*(?:the\s+|a\s+)?(?:minor|juvenile)\b")
_NOT_A_NAME = re.compile(r"^(?:The|This|That|He|She|It|In|On|At|By|For|And|But|Under|Section|Article|Court|State|Police)$")


def _clean(names) -> list[str]:
    out = []
    for raw in names:
        raw = re.sub(r"(?i)^(?:mst|mrs|miss|ms|mr)\.?\s+", "", " ".join(raw.split())).strip(" .,")
        n = _HONORIFIC.sub("", raw).strip(" .,")
        # 'Mian Gul': stripping a title-like word leaves one word, so the name is also kept as printed
        for cand in ([n, raw] if len(n.split()) == 1 and len(raw.split()) > 1 else [n]):
            if len(cand) >= 3 and not _NOT_A_NAME.match(cand.split()[0]) and not is_institution(cand):
                out.append(cand)
    return list(dict.fromkeys(out))


def victim_names(texts: list[str]) -> list[str]:
    found = []
    for t in (" ".join(x.split()) for x in texts):
        found += [m.group(1) for m in _VICTIM_BEFORE.finditer(t)] + [m.group(1) for m in _VICTIM_AFTER.finditer(t)]
        found += [m.group(1) for m in _MST.finditer(t)]
    return _clean(found)


def minor_names(texts: list[str]) -> list[str]:
    found = []
    for t in (" ".join(x.split()) for x in texts):
        found += [m.group(1) for m in _MINOR_BEFORE.finditer(t)] + [m.group(1) for m in _MINOR_AFTER.finditer(t)]
    return _clean(found)


def redact(text: str, names: list[str], common: frozenset[str] = frozenset()) -> str:
    """Each withheld name replaced by WITHHELD, longest first, whole words, case-insensitive. A one-word name is
    replaced only when it is not a common word (`common`, e.g. the judgment vocabulary): 'Muhammad' alone is not
    withheld everywhere, 'Muhammad Arslan' is."""
    if not text or not names:
        return text
    for n in sorted(set(names), key=len, reverse=True):
        words = n.split()
        if len(words) == 1 and (len(n) < 4 or n.lower() in common):
            continue
        text = re.sub(r"(?<![\w])" + r"\.?\s+".join(map(re.escape, words)) + r"(?![\w])", WITHHELD, text, flags=re.I)
    return text


def names_queried(query: str, names: list[str]) -> bool:
    """Whether a query names a withheld person: a whole name, or two words of one name."""
    q = " " + " ".join(re.findall(r"[a-z]+", query.lower())) + " "
    qw = set(q.split())
    for n in names:
        words = re.findall(r"[a-z]+", n.lower())
        if len(words) >= 2 and (" " + " ".join(words) + " " in q or len(qw & set(w for w in words if len(w) >= 3)) >= 2):
            return True
    return False
