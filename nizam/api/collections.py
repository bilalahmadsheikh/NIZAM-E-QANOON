"""Editorial collections for the home page (17 Nov 2026).

`POPULAR` is an editorial selection of the codes and statutes most consulted in Pakistani practice, in a fixed
order. It is a starting point, not a claim of completeness or of importance in law. Each entry names the
consolidated, served text by document id AND a title pattern: a law is listed only when that document's released
instrument still carries the expected title -- a re-extracted or replaced document drops out (and is reported by
the test) instead of silently showing another law. Resolved against the corpus on 17 Nov 2026, where the as-made
Gazette copies, historical expressions and older consolidations of the same works were excluded in favour of the
current consolidated text.
"""
import re

# (short name shown on the card, document id, title pattern)
POPULAR = [
    ('Constitution', 4419, r'^(the )?constitution of the islamic republic of pakistan'),
    ('PPC', 4441, r'^(the )?pakistan penal code'),
    ('CrPC', 4501, r'^(the )?code of criminal procedure'),
    ('CPC', 4463, r'^(the )?code of civil procedure'),
    ('Qanun-e-Shahadat', 4166, r'^(the )?qanun-e-shahadat'),
    ('Contract Act', 4337, r'^(the )?contract act'),
    ('Specific Relief', 3944, r'^(the )?specific relief act'),
    ('Limitation Act', 4237, r'^(the )?limitation act'),
    ('Transfer of Property', 3991, r'^(the )?transfer of property act'),
    ('Family Laws', 3283, r'^(the )?muslim family laws ordinance'),
    ('Family Courts', 2944, r'family courts act'),
    ('Guardians & Wards', 4283, r'^(the )?guardians and wards act'),
    ('Anti-Terrorism', 4225, r'^(the )?anti-terrorism act'),
    ('Narcotics', 4036, r'^(the )?control of narcotic substances act'),
    ('Income Tax', 4489, r'^(the )?income tax ordinance'),
    ('Companies Act', 4486, r'^(the )?companies act'),
    ('Registration Act', 3876, r'^(the )?registration act'),
    ('Stamp Act', 4345, r'^(the )?stamp act'),
]


# ---------------------------------------------------------------- the Constitution's page (17 Nov 2026, D-070)
# "Explore constitutional texts" opens one page: the Constitution itself, then the texts around it, each group saying
# how it relates. Membership is pinned by document id and title pattern, as POPULAR is, so a replaced document drops
# out instead of silently showing another law. Resolved against the corpus on 17 Nov 2026:
#   4419  the Constitution of 1973 as consolidated in the Pakistan Code (to the 27th Amendment, 2025)
#   4434  the Punjab Code's compilation: e0 the Constitution as amended to the 22nd Amendment (a historical expression,
#         served only inside its window, 0064) and e1..e45 the amending Acts and Orders it reproduces
#   9287  the Revival of the Constitution of 1973 Order, 1985
#   6541, 6982, 8093, 8691  constitutional instruments made before 1973
#   AJK   the Interim Constitution's amending Acts (the Interim Constitution Act, 1974 itself is not landed)
CONSTITUTION_DOCUMENT = 4419
CONSTITUTION_TITLE = r'^(the )?constitution of the islamic republic of pakistan'
CONSTITUTION_EDITION_DOCUMENT = 4434
REVIVAL_ORDER = (9287, r'^(the )?revival of the constitution of 1973 order')
BEFORE_1973 = [
    ('Provisional Constitution Order', 6541, r'^(the )?pakistan \(provisional constitution\) order'),
    ('Its amendment, 1949', 6982, r'^(the )?pakistan provisional constitution \(amendment\) order'),
    ('Presidential (Election and Constitution) Order', 8093, r'^(the )?presidential \(election and constitution\) order'),
    ('Interim Constitution Order', 8691, r'^(the )?interim constitution order'),
]
_AMENDMENT = r'^(the )?constitution \(([a-z-]+ )?amendment\) (act|order)'
_AJK_AMENDMENT = r'interim constitution \(([a-z-]+ )?amendment\) act'
# One pattern for the database (Postgres ARE, case-insensitive): every title the page may list.
FAMILY_TITLE_PATTERN = f'{_AMENDMENT}|{_AJK_AMENDMENT}|{CONSTITUTION_TITLE}'
FAMILY_DOCUMENTS = [CONSTITUTION_DOCUMENT, CONSTITUTION_EDITION_DOCUMENT, REVIVAL_ORDER[0]] + [d for _s, d, _p in BEFORE_1973]

_ORDINALS = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth',
             'eleventh', 'twelfth', 'thirteenth', 'fourteenth', 'fifteenth', 'sixteenth', 'seventeenth',
             'eighteenth', 'nineteenth', 'twentieth']
_TENS = {'twenty': 20, 'thirty': 30}


def amendment_number(title: str) -> int | None:
    """The amendment's printed ordinal ('(Eighteenth Amendment)' -> 18, '(Twenty-First Amendment)' -> 21); None for
    an unnumbered '(Amendment)'. Read from the stored title only."""
    m = re.search(r'\(([a-z-]+) amendment\)', title.lower())
    if not m:
        return None
    word = m.group(1)
    if word in _ORDINALS:
        return _ORDINALS.index(word) + 1
    tens, _, unit = word.partition('-')
    if tens in _TENS and unit in _ORDINALS[:9]:
        return _TENS[tens] + _ORDINALS.index(unit) + 1
    return None


def _ordinal_suffix(n: int) -> str:
    return 'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')


def _amendment_name(title: str) -> str:
    number = amendment_number(title)
    order = re.search(r'\)\s+order\b', title.lower()) is not None
    name = f'{number}{_ordinal_suffix(number)} Amendment' if number else 'Amendment'
    return name + (' Order' if order else '')


def constitution_page(rows: list[dict]) -> dict:
    """Group the released rows of FAMILY_DOCUMENTS / FAMILY_TITLE_PATTERN into the Constitution's page.

    Returns {constitution, groups}; each group is {key, items}, each item {short_name, instrument, amends_units}.
    Group keys are codes -- the client words them (docs/13): 'amendments' (Acts and Orders that amend it, oldest
    first), 'edition' (an earlier consolidated text, present only inside its window), 'before_1973' (constitutional
    instruments it replaced), 'ajk' (Azad Jammu and Kashmir's Interim Constitution amendments)."""
    def title(r):
        return (r.get('title') or '').lower()

    def item(short, r):
        return dict(short_name=short, instrument=r, amends_units=int(r.get('amends_units') or 0))

    constitution = next((r for r in rows if r['document_id'] == CONSTITUTION_DOCUMENT
                         and re.search(CONSTITUTION_TITLE, title(r))), None)
    edition = [item('As amended to 2016', r) for r in rows
               if r['document_id'] == CONSTITUTION_EDITION_DOCUMENT and re.search(CONSTITUTION_TITLE, title(r))]
    amendments = sorted(
        (r for r in rows
         if r['jurisdiction'] != 'ajk' and r['document_id'] != CONSTITUTION_DOCUMENT
         and (re.search(_AMENDMENT, title(r))
              or (r['document_id'] == REVIVAL_ORDER[0] and re.search(REVIVAL_ORDER[1], title(r))))),
        key=lambda r: (r.get('year') or 0, amendment_number(title(r)) or 0, title(r)))
    before = []
    for short, doc, pattern in BEFORE_1973:
        hit = next((r for r in rows if r['document_id'] == doc and re.search(pattern, title(r))), None)
        if hit:
            before.append(item(short, hit))
    ajk = sorted((r for r in rows if r['jurisdiction'] == 'ajk' and re.search(_AJK_AMENDMENT, title(r))),
                 key=lambda r: (amendment_number(title(r)) or 0, r.get('year') or 0))
    groups = [
        dict(key='amendments', items=[
            item('Revival Order' if r['document_id'] == REVIVAL_ORDER[0] else _amendment_name(title(r)), r)
            for r in amendments]),
        dict(key='edition', items=edition),
        dict(key='before_1973', items=before),
        dict(key='ajk', items=[item(f'AJK {_amendment_name(title(r))}', r) for r in ajk]),
    ]
    return dict(constitution=constitution, groups=[g for g in groups if g['items']])


def resolve(rows: list[dict]) -> list[dict]:
    """Order released instrument rows by POPULAR, keeping one per entry whose title matches its pattern."""
    by_doc: dict[int, list[dict]] = {}
    for r in rows:
        by_doc.setdefault(r['document_id'], []).append(r)
    out = []
    for short, doc, pattern in POPULAR:
        hit = next((r for r in by_doc.get(doc, []) if re.search(pattern, (r['title'] or '').lower())), None)
        if hit:
            out.append(dict(short_name=short, instrument=hit))
    return out
