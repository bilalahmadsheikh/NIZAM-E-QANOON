"""Record partial repeals the corpus's own released laws print (migration 0102).

A clause is recorded only when ALL of these hold:

  * it is a plain list of units of ONE named enactment, then the verb, and nothing else in the sentence except an
    optional territorial qualifier:
        'Sections 121 to 147 contained in Chapter XVI of the Sindh Local Government Ordinance 1979 are hereby repealed'
        'section 2 and sections 43, 44, 45 ... 54 of the Patents and Designs Act, 1911 (II of 1911) are hereby repealed'
        'section 7, sub-section (2) of section 27 and section 28 of the Punjab Development of Cities Act, 1976 ...'
    -- units: section(s), sub-section(s) (n) of section N, Part(s), Chapter(s), Article(s); numbers as printed
    ('13-A', '51B', '103A'), lists, and ranges ('121 to 147', '12 to 21 (both inclusive)'). Anything else in the
    units ('in section 2, the words ...', 'Part III of the Second Schedule to ...') is an amendment of words or a unit
    this tool does not read, and the clause is skipped;
  * the repealing law is an Act, or a law that is itself current (an Ordinance that lapsed does not count here, as
    0066 does not count one for a whole repeal);
  * title and year match exactly one released canonical law (resolve_hits, 0066's rules), the repealer's own
    jurisdiction first, else the federation's -- and it is not the repealer;
  * every unit the clause names resolves to exactly one held provision of that law (outside its schedules), and the
    held text of that unit is neither already printed as omitted/repealed (the consolidation reflects it: reported,
    not recorded) nor carrying an amendment mark (it may have been re-enacted after: skipped, reported);
  * territory: the same jurisdiction -> wherever the law runs; a province's law repealing part of a federal-text
    law -> that province (as 0095); a qualifier naming another place, or another jurisdiction's law -> skipped.

No date is inferred beyond the repealer's: v_provision_repeal_current uses its commencement, enactment, or 1 January
of its year. Dry run by default; --apply writes rows not already standing.

    python tools/record_provision_repeals.py            # report
    python tools/record_provision_repeals.py --apply    # record
    python tools/record_provision_repeals.py --clauses  # print every recordable clause for review
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from record_statutory_repeals import norm, resolve_hits, title_key  # noqa: E402
from record_territorial_repeals import PROVINCES, clause_territory  # noqa: E402

METHOD = "nizam.provision_repeal_text/1"
KIND = r"(?:Act|Ordinance|Regulations?|Rules|Order|Code)"

# letter suffixes are matched case-SENSITIVELY and only attached or hyphenated ('51A', '13-A'): under re.I a free
# '[A-Z]{1,2}' after a space read the word 'to' of '121 to 147' as a suffix
NUM = r"\d{1,4}(?:(?-i:[A-Z]{1,2})|-\s*(?-i:[A-Z]{1,2}))?\b"
ROM = r"(?-i:[IVXL]{1,7}(?:-?[A-Z])?)\b"
YEAR = r"(?:1[89]\d\d|20\d\d)"
CITE = r"(?:\s*,?\s*\((?:[^()]|\([^()]*\))*\))?"
SEP = r"\s*(?:,\s*(?:and\s+)?|and\s+|&\s*)"
PAREN = r"\(\s*\w{1,5}\s*\)"
PARENLIST = PAREN + r"(?:(?:" + SEP + r"|\s*to\s*)" + PAREN + r")*"
NUMLIST = NUM + r"(?:\s*(?:,\s*(?:and\s+)?|and\s+|to\s+|-\s*)" + NUM + r")*(?:\s*\(\s*both\s+inclusive\s*\))?"
ROMLIST = ROM + r"(?:" + SEP + ROM + r")*"
ITEM = (r"(?:sub-?\s*sections?\s*" + PARENLIST + r"\s+of\s+section\s+" + NUM +
        r"|clauses?\s*" + PARENLIST + r"\s+of\s+(?:sub-?\s*section\s*" + PAREN + r"\s+of\s+)?section\s+" + NUM +
        r"|sections?\s+" + NUMLIST +
        r"|parts?\s+" + ROMLIST +
        r"|chapters?\s+" + ROMLIST +
        r"|articles?\s+" + NUMLIST + r")"
        r"(?:\s+contained\s+in\s+(?:chapter|part)\s+" + ROM + r")?")
UNIT_LIST = re.compile(r"(?:the\s+provisions\s+of\s+)?(?:the\s+)?" + ITEM + r"(?:" + SEP + ITEM + r")*", re.I)
ITEM_RX = re.compile(ITEM, re.I)
UNIT_WORDS = (r"(?i:(?:the\s+provisions\s+of\s+)?(?:the\s+)?"
              r"(?:sub-?\s*sections?|sections?|parts?|chapters?|articles?|clauses?))")
OF_LAW = (r"(?P<units>" + UNIT_WORDS + r"\s*[^.;:]{1,250}?)\s+of\s+the\s+(?P<title>[A-Z][^.;:()]{2,160}?\b" + KIND +
          r")\s*,?\s*(?P<year>" + YEAR + r")(?P<num>" + CITE + r")")

# 17 Nov 2026: a clause may start after a dash ('- Section 12 of ...'), inside a list ('... (LVII of 2002) and section
# 15-A of the Capital Development Authority Ordinance, 1960 ... are hereby repealed'), and other enactments -- whole or
# by units -- may follow before the verb ('..., and the Balochistan ... Ordinance, 1991 (I of 1991), are hereby
# repealed'; '... of the Lahore Development Authority Act, 1975 (XXX of 1975), and clause (xvi) of sub-section (2) of
# section 7 ... of the Punjab Development of Cities Act, 1976 (XIX of 1976) are hereby repealed'). A printed date
# between 'shall' and 'stand' ('shall, as from the first day of July, 1962, stand repealed') is the repeal's date.
CLAUSE = re.compile(
    r"(?:^[\W_]*|(?<=[.;:])\s+|\(\s*\w{1,4}\s*\)\s*|[–—-]\s*|\band\s+|,\s+)" + OF_LAW +
    r"(?P<more>(?:\s*,?\s*and\s+(?:the\s+)?[^.;:]{0,250}?\b" + YEAR + CITE + r"\s*,?)*)"
    r"\s*,?\s*(?:(?i:shall)\s*,?\s*(?i:as\s+from)\s+(?P<from>[^;.]{4,40}?\d{4})\s*,\s*(?i:stand)"
    r"|(?i:is|are|shall\s+stand|stand|stands|shall\s+be))\s+(?i:hereby\s+)?(?P<verb>(?i:repealed|omitted))\b"
    r"(?P<after>[^.;]{0,200})", re.S)
MORE_ITEM = re.compile(r"(?:^|,|\band\b)\s*" + OF_LAW, re.S)

ORDINALS = {w: i + 1 for i, w in enumerate(
    "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth "
    "fifteenth sixteenth seventeenth eighteenth nineteenth twentieth twenty-first twenty-second twenty-third "
    "twenty-fourth twenty-fifth twenty-sixth twenty-seventh twenty-eighth twenty-ninth thirtieth thirty-first".split())}
MONTHS = "january february march april may june july august september october november december".split()

OMITTED_TEXT = re.compile(r"^[\W\d_]*(?:omitted|repealed|deleted)[\W\d_]*$", re.I)
MARK = re.compile(r"(?<![0-9.,])[0-9]{1,2}\s*\[")


def label_key(label: str) -> str:
    """'13-A' / '13 A' / '13a' / '282.D' / '282_A' -> '13A' ... '282D', '282A'; Roman labels upper-cased."""
    return re.sub(r"[\s\-._]", "", label or "").upper()


def _num_parts(label: str) -> tuple[int, str] | None:
    m = re.fullmatch(r"(\d{1,4})([A-Z]{0,2})", label_key(label))
    return (int(m.group(1)), m.group(2)) if m else None


def printed_from(text: str | None):
    """'the first day of July, 1962' / '1st July, 1962' -> date, else None."""
    import datetime
    t = " ".join((text or "").lower().replace(",", " ").split())
    m = re.fullmatch(r"(?:the\s+)?([a-z-]+|\d{1,2})(?:st|nd|rd|th)?(?:\s+day)?(?:\s+of)?\s+([a-z]+)\s+(\d{4})", t)
    if not m or m.group(2) not in MONTHS:
        return None
    d = ORDINALS.get(m.group(1)) or (int(m.group(1)) if m.group(1).isdigit() else None)
    try:
        return datetime.date(int(m.group(3)), MONTHS.index(m.group(2)) + 1, d) if d else None
    except ValueError:
        return None


def _parens(rest: str) -> list[str] | None:
    """'(2) to (6)' -> ['2','3','4','5','6']; '(a), (b) and (c)' -> ['A','B','C']; a range of non-numbers -> None."""
    tokens = re.findall(r"\(\s*(\w{1,5})\s*\)|(\bto\b)", rest.split(" of ")[0])
    flat = [a or b for a, b in tokens]
    out, i = [], 0
    while i < len(flat):
        if flat[i] == "to" and out and i + 1 < len(flat):
            lo, hi = out[-1], flat[i + 1]
            if not (lo.isdigit() and hi.isdigit()) or int(hi) < int(lo):
                return None
            out += [str(n) for n in range(int(lo) + 1, int(hi) + 1)]
            i += 2
            continue
        if flat[i] != "to":
            out.append(flat[i])
        i += 1
    return [label_key(x) for x in out]


def parse_units(units: str) -> list[dict] | None:
    """The units a clause names, or None when the text is not a plain unit list. Each unit is
    {'kind': 'section'|'part'|'chapter'|'article', 'label': '27'}, {'kind': 'subsection', 'section': '27',
    'label': '2'}, {'kind': 'clause', 'section': '2', 'sub': None|'2', 'label': 'XIX'} or
    {'kind': 'range', 'unit': 'section'|'article', 'lo': 121, 'hi': 147}."""
    text = " ".join((units or "").split())
    text = re.sub(r"^the\s+provisions\s+of\s+", "", text, flags=re.I)
    if not UNIT_LIST.fullmatch(text):
        return None
    out = []
    for item in ITEM_RX.finditer(text):
        s = re.sub(r"\s+contained\s+in\s+(?:chapter|part)\s+\S+$", "", item.group(0), flags=re.I)
        word = s.split()[0].lower()
        rest = s[len(s.split()[0]):]
        if word.startswith("sub"):
            labels = _parens(rest)
            sec = re.search(r"of\s+section\s+(" + NUM + r")", rest, re.I).group(1)
            if labels is None:
                return None
            out += [{"kind": "subsection", "section": label_key(sec), "label": x} for x in labels]
            continue
        if word.startswith("clause"):
            labels = _parens(rest)
            if labels is None or re.search(r"\bto\b", rest.split(" of ")[0]):
                return None
            sec = re.search(r"of\s+section\s+(" + NUM + r")", rest, re.I).group(1)
            sub = re.search(r"of\s+sub-?\s*section\s*\(\s*(\w{1,5})\s*\)", rest, re.I)
            out += [{"kind": "clause", "section": label_key(sec), "sub": label_key(sub.group(1)) if sub else None,
                     "label": x} for x in labels]
            continue
        unit = {"sections": "section", "section": "section", "parts": "part", "part": "part",
                "chapters": "chapter", "chapter": "chapter", "articles": "article", "article": "article"}[word]
        body = re.sub(r"\(\s*both\s+inclusive\s*\)", "", rest, flags=re.I)
        if unit in ("part", "chapter"):
            out += [{"kind": unit, "label": label_key(x)} for x in re.findall(ROM, body)]
            continue
        # numbers, with 'a to b' / 'a-b' ranges between plain numbers
        tokens = re.findall(r"(" + NUM + r")|(\bto\b)|(?<=\d)\s*(-)\s*(?=\d)", body)
        nums, i = [], 0
        flat = [(a or b or c) for a, b, c in tokens]
        while i < len(flat):
            if flat[i] in ("to", "-") and nums and i + 1 < len(flat):
                lo, hi = _num_parts(nums[-1]["label"]), _num_parts(flat[i + 1])
                if lo and hi and lo[0] == hi[0] and len(lo[1]) == 1 and len(hi[1]) == 1 and lo[1] <= hi[1]:
                    # inserted sections of one number: 'sections 282A to 282N' (Companies Ordinance Part VIIIA)
                    nums[-1] = {"kind": "letter_range", "unit": unit, "num": lo[0], "lo": lo[1], "hi": hi[1]}
                    i += 2
                    continue
                if not lo or not hi or lo[1] or hi[1] or hi[0] < lo[0]:
                    return None
                nums[-1] = {"kind": "range", "unit": unit, "lo": lo[0], "hi": hi[0]}
                i += 2
                continue
            if flat[i] not in ("to", "-"):
                nums.append({"kind": unit, "label": label_key(flat[i])})
            i += 1
        out += nums
    return out or None


def _item(units_text, title, year, num, verb, after, frm, clause):
    num = (num or "").strip(" ,")
    return {"units_text": " ".join(units_text.split()), "units": parse_units(units_text), "title": title.strip(),
            "year": int(year), "verb": verb.lower(), "after": after,
            "runs_on": bool(num and not re.search(r"\d|\b[IVXLC]+\b", num)),
            "from": printed_from(frm), "from_text": frm, "clause": clause}


def clauses(text: str) -> list[dict]:
    """Every partial-repeal clause in `text`: the first enactment's units, and each later enactment in the same list
    that is named by units too (a whole enactment in the list is 0066's)."""
    found = []
    t = " ".join((text or "").split())
    for m in CLAUSE.finditer(t):
        clause = " ".join(m.group(0).split())[:600]
        args = (m.group("verb"), m.group("after"), m.group("from"), clause)
        found.append(_item(m.group("units"), m.group("title"), m.group("year"), m.group("num"), *args))
        for x in MORE_ITEM.finditer(m.group("more") or ""):
            if parse_units(x.group("units")) is not None:
                found.append(_item(x.group("units"), x.group("title"), x.group("year"), x.group("num"), *args))
    return found


def resolve_units(units: list[dict], held: list[tuple]) -> tuple[list[tuple[str, str]], str | None, int]:
    """held: (relative path, kind, label, text) of the target law's active provisions. Returns ([(relative path,
    unit as printed)], None, missing) -- each unit that resolves to exactly one held provision, and how many named
    units the held text lacks (usually already removed by the consolidation) -- or ([], why, missing) when a unit
    is ambiguous or none resolves. A unit inside a schedule is never matched (a schedule's 'section 5' is not
    the law's)."""
    body = [(rp, k, label_key(lb), tx or "") for rp, k, lb, tx in held if "sch_" not in rp.lower()]

    def one(kinds, label, parent=None):
        c = [h for h in body if h[1] in kinds and h[2] == label
             and (parent is None or h[0].rsplit(".", 1)[0] == parent)]
        return c[0] if len(c) == 1 else (None if not c else "ambiguous")

    picked, missing = [], 0
    for u in units:
        if u["kind"] == "letter_range":
            kinds = ("section",) if u["unit"] == "section" else ("article", "section")
            span = [h for h in body if h[1] in kinds and (_num_parts(h[2]) or (-1, ""))[0] == u["num"]
                    and (_num_parts(h[2]) or (-1, ""))[1][:1] and u["lo"] <= _num_parts(h[2])[1][:1] <= u["hi"]
                    and "." not in h[0].split("s_")[-1]]
            if len(collections.Counter(h[2] for h in span)) != len(span):
                return [], "ambiguous unit", missing
            if not span:
                missing += 1
            picked += [(h, f"{u['unit']} {h[2]}") for h in span]
            continue
        if u["kind"] == "range":
            kinds = ("section",) if u["unit"] == "section" else ("article", "section")
            span = [h for h in body if h[1] in kinds and (_num_parts(h[2]) or (-1,))[0] in range(u["lo"], u["hi"] + 1)
                    and "." not in h[0].split("s_")[-1]]
            labels = collections.Counter(h[2] for h in span)
            if any(n > 1 for n in labels.values()):
                return [], "ambiguous unit"
            if not span:
                missing += 1
            picked += [(h, f"{u['unit']} {h[2]}") for h in span]
            continue
        if u["kind"] == "subsection":
            sec = one(("section",), u["section"])
            if sec == "ambiguous":
                return [], "ambiguous unit", missing
            h = one(("subsection",), u["label"], parent=sec[0]) if sec else None
            if h == "ambiguous":
                return [], "ambiguous unit", missing
            if h is None:
                missing += 1; continue
            picked.append((h, f"sub-section ({u['label']}) of section {u['section']}"))
            continue
        if u["kind"] == "clause":
            sec = one(("section",), u["section"])
            if sec == "ambiguous":
                return [], "ambiguous unit", missing
            if sec is None:
                missing += 1; continue
            parent, where = sec[0], f"section {u['section']}"
            if u["sub"]:
                ss = one(("subsection",), u["sub"], parent=sec[0])
                if ss == "ambiguous":
                    return [], "ambiguous unit", missing
                if ss is None:
                    missing += 1; continue
                parent, where = ss[0], f"sub-section ({u['sub']}) of section {u['section']}"
            h = one(("clause",), u["label"], parent=parent)
            if h == "ambiguous":
                return [], "ambiguous unit", missing
            if h is None:
                missing += 1; continue
            picked.append((h, f"clause ({u['label'].lower()}) of {where}"))
            continue
        kinds = {"section": ("section",), "article": ("article", "section"), "part": ("part",),
                 "chapter": ("chapter",)}[u["kind"]]
        h = one(kinds, u["label"])
        if h == "ambiguous":
            return [], "ambiguous unit", missing
        if h is None:
            missing += 1; continue
        picked.append((h, f"{u['kind']} {u['label']}"))
    if not picked:
        return [], "unit not in the held text", missing
    return [(h[0], printed) for h, printed in picked], None, missing


def unit_state(rel: str, held_text: dict) -> str:
    """'reflected' when the held text already prints the unit as omitted, 'marked' when it carries an amendment mark
    (it may have been re-enacted after the repeal), else 'live'."""
    own = held_text.get(rel, "")
    if OMITTED_TEXT.match(own or ""):
        return "reflected"
    sub = " ".join(t for p, t in held_text.items() if p == rel or p.startswith(rel + "."))
    if not sub.strip() or OMITTED_TEXT.match(sub):
        return "reflected"
    if MARK.search(sub):
        return "marked"
    return "live"


# ----------------------------------------------------------------------------------- survivals (migration 0103)
# A WHOLE repeal that excepts named units of the law it repeals:
#   'The Companies Ordinance, 1984 (XLVII of 1984), hereinafter called as repealed Ordinance, shall stand repealed,
#    except Part VIIIA consisting of sections 282A to 282N, from the date of coming into force of this Act'
#   'The Pakistan International Airlines Corporation (Conversion) Act, 2016 (XV of 2016) is hereby repealed except
#    sub-section (1) of section 7 of the repealed Act'
#   '... Act, 2016 (XV of 2016), except sub-section (1) of section 7 is hereby repealed'
SAVE_TITLE = r"(?P<title>[A-Z](?:[^.;:()]|\([A-Za-z ,&'-]{1,60}\)){2,160}?\b" + KIND + r")"
SAVE = re.compile(
    r"(?:^[\W_]*|(?<=[.;:])\s+|\(\s*\w{1,4}\s*\)\s*)" + SAVE_TITLE + r"\s*,?\s*(?P<year>" + YEAR + r")(?P<num>" + CITE +
    r")(?:\s*,\s*hereinafter[^,]{0,80})?"
    r"(?:\s*,?\s*(?i:except)\s+(?P<pre>[^.;]{1,200}?)\s*,?)?"
    r"\s*,?\s+(?i:is|shall\s+stand|stands)\s+(?i:hereby\s+)?(?i:repealed)"
    r"(?:\s*,?\s*(?i:except)\s+(?P<post>[^.;]{1,200}?))?(?=\s*(?:,|\.|;|$|\s+from\b|\s+with\b))", re.S)


def save_clauses(text: str) -> list[dict]:
    """Every 'X is repealed except <units>' clause: the repealed law, its year, and the excepted units' text in the
    candidate readings to try in order ('Part VIIIA', then 'sections 282A to 282N' from 'consisting of ...')."""
    out = []
    t = " ".join((text or "").split())
    for m in SAVE.finditer(t):
        units = (m.group("pre") or m.group("post") or "").strip(" ,")
        if not units or (m.group("pre") and m.group("post")):
            continue
        units = re.sub(r"\s+of\s+the\s+(?:said|repealed)\s+(?:Act|Ordinance|Order|Regulation)\b.*$", "", units, flags=re.I)
        readings = [units]
        cons = re.match(r"(?P<head>.+?)\s+consisting\s+of\s+(?P<body>.+)$", units, re.I)
        if cons:
            readings = [cons.group("head"), cons.group("body")]
        out.append({"title": m.group("title").strip(), "year": int(m.group("year")), "num": m.group("num") or "",
                    "readings": readings, "clause": " ".join(m.group(0).split())[:600]})
    return out


def resolve_survivals(readings: list[str], held: list[tuple]) -> tuple[list[tuple[str, str, bool]], str | None]:
    """The first reading whose units ALL resolve: [(relative path, unit as printed, subtree)]. A sub-section the held
    text keeps as its section's own words ('(1) The name of the Company ...' on s_7, s_7.ss_2 a child) is that
    section node alone (subtree False): its later sub-sections were repealed with the rest."""
    body = [(rp, k, label_key(lb), tx or "") for rp, k, lb, tx in held if "sch_" not in rp.lower()]
    for reading in readings:
        units = parse_units(reading)
        if not units:
            continue
        got, ok = [], True
        for u in units:
            if u["kind"] == "subsection":
                secs = [h for h in body if h[1] == "section" and h[2] == u["section"]]
                if len(secs) != 1:
                    ok = False; break
                kids = [h for h in body if h[1] == "subsection" and h[2] == u["label"]
                        and h[0].rsplit(".", 1)[0] == secs[0][0]]
                if len(kids) == 1:
                    got.append((kids[0][0], f"sub-section ({u['label']}) of section {u['section']}", True)); continue
                # held text is 'heading text': the sub-section's number opens the text, after at most the heading
                own = secs[0][3]
                first = re.search(r"\(\s*(\w{1,4})\s*\)", own[:200])
                if not kids and first and label_key(first.group(1)) == u["label"]:
                    got.append((secs[0][0], f"sub-section ({u['label']}) of section {u['section']}", False)); continue
                ok = False; break
            found, why, missing = resolve_units([u], held)
            if why or missing:
                ok = False; break
            got += [(rp, printed, True) for rp, printed in found]
        if ok and got:
            return got, None
    return [], "an excepted unit is not in the held text"


def plan_survivals(instruments, provisions, held_of, currency, skipped=None,
                   twins: frozenset = frozenset()) -> tuple[list[dict], list[dict], dict]:
    """(whole repeals, survivals, stats) for 'repealed except <units>' clauses in current released Acts. When the
    named law is held as twin texts (0075: the as-made Gazette and the consolidated text), the whole repeal is
    recorded for each (A14) and the excepted units in each text that holds them (the as-made 1984 Companies
    Ordinance has no Part VIIIA, inserted in 2002)."""
    by_key: dict = collections.defaultdict(list)
    meta = {}
    for iid, jur, kind, title, year, obs, ordinal, display in instruments:
        meta[iid] = (jur, kind, title, obs, ordinal, year)
        for t in {title_key(title), title_key(display) if display else ""}:
            if t and iid not in by_key[(jur, t, year)]:
                by_key[(jur, t, year)].append(iid)
    stats: collections.Counter = collections.Counter()
    repeals, survivals, seen = [], [], set()
    for iid, rel_path, block, text in provisions:
        jur, kind, _t, obs, ordinal, _y = meta[iid]
        for c in save_clauses(text):
            stats["except clauses"] += 1
            if kind != "act" or currency.get(iid) != "current":
                stats["skipped: repealer is not a current Act"] += 1
                if skipped is not None:
                    skipped.append(("except: repealer is not a current Act", c["clause"]))
                continue
            hits = [h for h in by_key.get((jur, norm(c["title"]), c["year"]), []) if h != iid]
            targets = resolve_hits(hits, c["title"], {k: v[:5] for k, v in meta.items()}, twins)
            if not targets:
                stats["skipped: law not held or ambiguous"] += 1
                if skipped is not None:
                    skipped.append(("except: law not held or ambiguous", c["clause"]))
                continue
            resolved = {t: resolve_survivals(c["readings"], held_of(t)) for t in targets}
            if not any(why is None for _u, why in resolved.values()):
                # the whole repeal is still the law's own words; an unresolvable exception would leave it served in
                # full, which is worse than not serving the excepted unit -- reported for review, nothing recorded
                why = next(iter(resolved.values()))[1]
                stats[f"skipped: {why}"] += 1
                if skipped is not None:
                    skipped.append((f"except: {why}", c["clause"]))
                continue
            for target in targets:
                t_jur, _k, t_title, t_obs, t_ord, _ty = meta[target]
                key = (t_obs, t_ord, obs, ordinal, rel_path)
                if key not in seen:
                    seen.add(key)
                    repeals.append(dict(repealed_observation_id=t_obs, repealed_expression_ordinal=t_ord,
                                        repealing_observation_id=obs, repealing_expression_ordinal=ordinal,
                                        repealing_source_block_id=block, repealing_relative_path=rel_path,
                                        clause_text=c["clause"], matched_title=t_title, matched_year=c["year"],
                                        repealed_instrument_id=target, repealing_instrument_id=iid))
                units, why = resolved[target]
                for rel, printed, subtree in (units if why is None else []):
                    survivals.append(dict(survived_observation_id=t_obs, survived_expression_ordinal=t_ord,
                                          survived_relative_path=rel, subtree=subtree, unit_as_printed=printed,
                                          repealing_observation_id=obs, repealing_expression_ordinal=ordinal,
                                          repealing_source_block_id=block, repealing_relative_path=rel_path,
                                          clause_text=c["clause"], matched_title=t_title, matched_year=c["year"],
                                          survived_instrument_id=target, repealing_instrument_id=iid))
                    stats["surviving units"] += 1
    stats["laws repealed except units"] = len({r["repealed_instrument_id"] for r in repeals})
    return repeals, survivals, dict(stats)


def plan(instruments, provisions, held_of, currency, reach, skipped=None) -> tuple[list[dict], dict]:
    """instruments: (id, jurisdiction, kind, title, year, observation, ordinal, display title);
    provisions: (repealer id, relative path, first block, text) mentioning a repeal;
    held_of(target id) -> [(relative path, kind, label, text)]; currency: id -> currency; reach: id -> territories."""
    by_key: dict = collections.defaultdict(list)
    meta = {}
    for iid, jur, kind, title, year, obs, ordinal, display in instruments:
        meta[iid] = (jur, kind, title, obs, ordinal, year)
        for t in {title_key(title), title_key(display) if display else ""}:
            if t and iid not in by_key[(jur, t, year)]:
                by_key[(jur, t, year)].append(iid)
    stats: collections.Counter = collections.Counter()
    rows, seen = [], set()

    def skip(why, c):
        stats[why] += 1
        if skipped is not None:
            skipped.append((why, c["clause"]))

    for iid, rel_path, block, text in provisions:
        jur, kind, _title, obs, ordinal, r_year = meta[iid]
        for c in clauses(text):
            stats["clauses"] += 1
            if c["units"] is None:
                skip("skipped: not a plain list of units", c); continue
            if c["runs_on"]:
                skip("skipped: the title runs on", c); continue
            if kind != "act" and currency.get(iid) != "current":
                skip("skipped: repealer is neither an Act nor current", c); continue
            key = norm(c["title"])
            hits = [h for h in by_key.get((jur, key, c["year"]), []) if h != iid]
            same = bool(hits)
            if not hits and jur != "fed":
                hits = [h for h in by_key.get(("fed", key, c["year"]), []) if h != iid]
            targets = resolve_hits(hits, c["title"], {k: v[:5] for k, v in meta.items()}, frozenset())
            if len(targets) != 1:
                skip("skipped: not held" if not hits else "skipped: ambiguous law", c); continue
            target = targets[0]
            t_jur, _k, t_title, t_obs, t_ord, t_year = meta[target]
            if r_year is not None and t_year is not None and r_year < t_year:
                skip("skipped: repealer older than the law", c); continue
            # territory
            after = (c["after"] or "").strip(" ,")
            if same:
                # words after the verb are allowed only when they are (a) a further, separate change joined by
                # 'and' that substitutes nothing ('... are hereby repealed and entries at Sr. No. 5 of the Schedule
                # ...'; 'repealed and the following substituted' re-enacts and is never read), or (b) a territorial
                # qualifier naming the law's own territory ('omitted in its application to the Province of the
                # Punjab' in a Punjab law: wherever it runs)
                own_place = bool(after) and clause_territory("", after, jur)[0] == jur
                further = bool(re.match(r"and\b", after, re.I)) and not re.search(
                    r"substitut|follow|replac|insert|re-?enact", after, re.I)
                if after and re.search(r"\w", after) and not (own_place or further):
                    skip("skipped: words follow the verb", c); continue
                terr, why = None, "same jurisdiction: wherever the law runs"
            elif t_jur == "fed" and jur in PROVINCES:
                terr, why = clause_territory("", after, jur)
                if terr is None:
                    skip(why, c); continue
            else:
                skip("skipped: another jurisdiction's law", c); continue
            if terr and terr not in (reach.get(target) or []):
                skip("skipped: the law does not reach that territory", c); continue
            held = held_of(target)
            units, why_not, missing = resolve_units(c["units"], held)
            if why_not:
                skip(f"skipped: {why_not}", c); continue
            if missing:
                stats["units not in the held text (others recorded)"] += missing
            texts = {rp: tx or "" for rp, _k, _l, tx in held}
            for rel, printed in units:
                state = unit_state(rel, texts)
                if state != "live":
                    stats[f"unit {state}"] += 1
                    if skipped is not None:
                        skipped.append((f"unit {state} ({rel})", c["clause"]))
                    continue
                k = (t_obs, t_ord, rel, terr, obs, ordinal, rel_path)
                if k in seen:
                    continue
                seen.add(k)
                stats["recordable units"] += 1
                rows.append(dict(repealed_observation_id=t_obs, repealed_expression_ordinal=t_ord,
                                 repealed_relative_path=rel, repealed_unit_as_printed=printed,
                                 repealing_observation_id=obs, repealing_expression_ordinal=ordinal,
                                 repealing_source_block_id=block, repealing_relative_path=rel_path, territory=terr,
                                 clause_text=c["clause"], verb=c["verb"], matched_title=t_title,
                                 matched_year=c["year"], why=why, repealed_instrument_id=target,
                                 repealing_instrument_id=iid, repealed_on=c["from"],
                                 repealed_on_basis=(f"the clause prints that the unit shall, as from "
                                                    f"{c['from_text'].strip()}, stand repealed" if c["from"] else None)))
    stats["laws"] = len({r["repealed_instrument_id"] for r in rows})
    return rows, dict(stats)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--clauses", action="store_true", help="print every recordable row's clause")
    ap.add_argument("--skipped", action="store_true", help="print every skipped clause with why")
    a = ap.parse_args()
    from nizam.storage.db import connect
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('provision_repeal')")
        if cur.fetchone()[0] is None:
            print("migration 0102 is not applied"); return 1
        cur.execute("SET statement_timeout = 0")
        cur.execute("""SELECT i.id::text, i.jurisdiction::text, i.kind::text, i.short_title, i.year,
                              i.source_observation_id, i.expression_ordinal, i.display_title
                         FROM v_release_instrument r JOIN instrument i ON i.id = r.id""")
        instruments = cur.fetchall()
        cur.execute("SELECT instrument_id::text, currency, territory_reach FROM mv_instrument_serving")
        serving = cur.fetchall()
        currency = {r[0]: r[1] for r in serving}
        reach = {r[0]: list(r[2] or []) for r in serving}
        cur.execute("""SELECT i.id::text, subpath(p.path, 3)::text, p.first_block, v.text_en
                         FROM v_release_instrument r JOIN instrument i ON i.id = r.id
                         JOIN provision p ON p.instrument_id = i.id AND p.is_active AND nlevel(p.path) > 3
                         JOIN provision_version v ON v.provision_id = p.id AND upper_inf(v.validity)
                        WHERE v.text_en ~* '(repealed|omitted)'
                          AND v.text_en ~* '(section|part|chapter|article)s?\\s+\\S+.{0,250}of\\s+the'
                          AND p.first_block IS NOT NULL""")
        provisions = cur.fetchall()
        cache: dict = {}

        def held_of(target: str):
            if target not in cache:
                cur.execute("""SELECT subpath(p.path, 3)::text, p.kind::text, p.label,
                                      concat_ws(' ', p.heading, v.text_en)
                                 FROM provision p
                                 LEFT JOIN provision_version v ON v.provision_id = p.id AND upper_inf(v.validity)
                                WHERE p.instrument_id = %s AND p.is_active AND nlevel(p.path) > 3""", (target,))
                cache[target] = cur.fetchall()
            return cache[target]

        skipped: list = []
        rows, stats = plan(instruments, provisions, held_of, currency, reach, skipped)
        print(json.dumps(stats, indent=1))
        # 0103: whole repeals that except named units
        has_survival = False
        cur.execute("SELECT to_regclass('provision_survival')")
        if cur.fetchone()[0]:
            has_survival = True
            cur.execute("""SELECT i.id::text, subpath(p.path, 3)::text, p.first_block, v.text_en
                             FROM v_release_instrument r JOIN instrument i ON i.id = r.id
                             JOIN provision p ON p.instrument_id = i.id AND p.is_active AND nlevel(p.path) > 3
                             JOIN provision_version v ON v.provision_id = p.id AND upper_inf(v.validity)
                            WHERE v.text_en ~* '\\mexcept\\M' AND v.text_en ~* '\\mrepealed\\M'
                              AND p.first_block IS NOT NULL""")
            texts = cur.fetchall()
            cur.execute("""SELECT as_made_instrument_id::text, consolidated_instrument_id::text
                             FROM v_consolidated_twin_current""")
            twins = frozenset(frozenset(r) for r in cur.fetchall())
            repeals, survivals, sstats = plan_survivals(instruments, texts, held_of, currency, skipped, twins)
        else:
            repeals, survivals, sstats = [], [], {"migration 0103": "not applied"}
        print(json.dumps(sstats, indent=1))
        title = {i[0]: (i[1], i[7] or i[3]) for i in instruments}
        if a.clauses:
            for s in survivals:
                print(f"  [survives] {title[s['survived_instrument_id']][1][:55]!r} {s['unit_as_printed']} "
                      f"({'with its subtree' if s['subtree'] else 'that node only'}) "
                      f"<- {title[s['repealing_instrument_id']][1][:50]!r}")
        title = {i[0]: (i[1], i[7] or i[3]) for i in instruments}
        if a.clauses:
            for r in rows:
                print(f"  [{r['territory'] or 'everywhere'}] {title[r['repealed_instrument_id']][1][:55]!r} "
                      f"{r['repealed_unit_as_printed']} <- {title[r['repealing_instrument_id']][1][:50]!r}\n"
                      f"      {r['clause_text'][:220]}")
        if a.skipped:
            for why, clause in skipped:
                print(f"  SKIP {why}: {clause[:200]}")
        written = 0
        if a.apply:
            for r in rows:
                cur.execute("""SELECT 1 FROM v_provision_repeal_current
                                WHERE repealed_observation_id = %s AND repealed_expression_ordinal = %s
                                  AND repealed_relative_path = %s AND territory IS NOT DISTINCT FROM %s
                                  AND repealing_observation_id = %s AND repealing_expression_ordinal = %s
                                  AND repealing_relative_path = %s""",
                            (r["repealed_observation_id"], r["repealed_expression_ordinal"],
                             r["repealed_relative_path"], r["territory"], r["repealing_observation_id"],
                             r["repealing_expression_ordinal"], r["repealing_relative_path"]))
                if cur.fetchone():
                    continue
                cur.execute("""INSERT INTO provision_repeal
                    (repealed_observation_id, repealed_expression_ordinal, repealed_relative_path,
                     repealed_unit_as_printed, repealing_observation_id, repealing_expression_ordinal,
                     repealing_source_block_id, repealing_relative_path, territory, clause_text, verb, matched_title,
                     matched_year, repealed_on, repealed_on_basis, assertion, method, evidence, recorded_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'repealed',%s,%s,
                            'tools/record_provision_repeals.py')""",
                            (r["repealed_observation_id"], r["repealed_expression_ordinal"],
                             r["repealed_relative_path"], r["repealed_unit_as_printed"], r["repealing_observation_id"],
                             r["repealing_expression_ordinal"], r["repealing_source_block_id"],
                             r["repealing_relative_path"], r["territory"], r["clause_text"], r["verb"],
                             r["matched_title"], r["matched_year"], r["repealed_on"], r["repealed_on_basis"], METHOD,
                             json.dumps({"reviewer_type": "rule", "why": r["why"],
                                         "rule": "plain unit list of one named law; Act or current repealer; exact "
                                                 "match; every unit one held provision, live (not printed omitted, "
                                                 "no amendment mark)",
                                         "repealed_instrument_id_at_record": r["repealed_instrument_id"],
                                         "repealing_instrument_id_at_record": r["repealing_instrument_id"]})))
                written += 1
            s_written = r_written = 0
            for r in repeals:
                cur.execute("""SELECT 1 FROM statutory_repeal WHERE repealed_observation_id=%s
                                 AND repealed_expression_ordinal=%s AND repealing_observation_id=%s
                                 AND repealing_expression_ordinal=%s AND repealing_relative_path=%s""",
                            (r["repealed_observation_id"], r["repealed_expression_ordinal"],
                             r["repealing_observation_id"], r["repealing_expression_ordinal"],
                             r["repealing_relative_path"]))
                if cur.fetchone():
                    continue
                cur.execute("""INSERT INTO statutory_repeal
                    (repealed_observation_id, repealed_expression_ordinal, repealing_observation_id,
                     repealing_expression_ordinal, repealing_source_block_id, repealing_relative_path, clause_text,
                     matched_title, matched_year, repealed_on, repealed_on_basis, assertion, method, evidence,
                     recorded_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,NULL,'repealed',%s,%s,'tools/record_provision_repeals.py')""",
                            (r["repealed_observation_id"], r["repealed_expression_ordinal"],
                             r["repealing_observation_id"], r["repealing_expression_ordinal"],
                             r["repealing_source_block_id"], r["repealing_relative_path"], r["clause_text"],
                             r["matched_title"], r["matched_year"], "nizam.repeal_except_units/1",
                             json.dumps({"reviewer_type": "rule",
                                         "rule": "whole repeal in a current released Act that excepts named units; "
                                                 "the units are recorded in provision_survival (0103)",
                                         "repealing_instrument_id_at_record": r["repealing_instrument_id"],
                                         "repealed_instrument_id_at_record": r["repealed_instrument_id"]})))
                r_written += 1
            for s in survivals if has_survival else []:
                cur.execute("""SELECT 1 FROM v_provision_survival_current
                                WHERE survived_observation_id = %s AND survived_expression_ordinal = %s
                                  AND survived_relative_path = %s AND repealing_observation_id = %s
                                  AND repealing_expression_ordinal = %s AND repealing_relative_path = %s""",
                            (s["survived_observation_id"], s["survived_expression_ordinal"],
                             s["survived_relative_path"], s["repealing_observation_id"],
                             s["repealing_expression_ordinal"], s["repealing_relative_path"]))
                if cur.fetchone():
                    continue
                cur.execute("""INSERT INTO provision_survival
                    (survived_observation_id, survived_expression_ordinal, survived_relative_path, subtree,
                     unit_as_printed, repealing_observation_id, repealing_expression_ordinal,
                     repealing_source_block_id, repealing_relative_path, clause_text, matched_title, matched_year,
                     assertion, method, evidence, recorded_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'survives',%s,%s,'tools/record_provision_repeals.py')""",
                            (s["survived_observation_id"], s["survived_expression_ordinal"],
                             s["survived_relative_path"], s["subtree"], s["unit_as_printed"],
                             s["repealing_observation_id"], s["repealing_expression_ordinal"],
                             s["repealing_source_block_id"], s["repealing_relative_path"], s["clause_text"],
                             s["matched_title"], s["matched_year"], "nizam.repeal_except_units/1",
                             json.dumps({"reviewer_type": "rule",
                                         "rule": "a unit a whole repeal expressly excepts; resolved to exactly one "
                                                 "held provision",
                                         "survived_instrument_id_at_record": s["survived_instrument_id"],
                                         "repealing_instrument_id_at_record": s["repealing_instrument_id"]})))
                s_written += 1
            conn.commit()
            print(f"recorded {r_written} whole repeal(s) that except units, {s_written} surviving unit(s)")
        print(f"{'recorded' if a.apply else 'would record'} {written if a.apply else len(rows)} partial-repeal row(s); "
              f"{len(repeals)} except-repeal(s), {len(survivals)} surviving unit(s) found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
