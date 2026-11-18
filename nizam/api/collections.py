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


# ---------------------------------------------------------------- Heritage (18 Nov 2026, D-077)
# The Heritage tab: Pakistan's places region by region, and the law that protects them. Each region lists the
# principal heritage statutes the library holds for that jurisdiction, pinned by document id AND title pattern as
# POPULAR is, so a replaced document drops out instead of silently showing another law. Service rules, museum staff
# regulations and amending Ordinances are left out: the list is a way in, not every law that touches heritage.
# Resolved against the corpus on 18 Nov 2026. Islamabad Capital Territory is served federal law (the corpus's
# territorial model, 0095), so its region lists the federal laws; Gilgit-Baltistan holds no heritage law yet and its
# region is listed with none -- the client says so rather than borrowing another jurisdiction's law.
HERITAGE_REGIONS = ['fed', 'punjab', 'sindh', 'kp', 'balochistan', 'ict', 'ajk', 'gb']
HERITAGE_LAWS = {
    'fed': [
        ('Antiquities Act', 3468, r'^(the )?antiquities act, 1975'),
        ('National Fund for Cultural Heritage', 2704, r'national fund for cultural heritage act'),
        ('Lok Virsa', 3017, r'lok virsa'),
        ('National Archives', 2770, r'national archives act'),
    ],
    'punjab': [
        ('Antiquities Act', 3157, r'^(the )?antiquities act, 1975'),
        ('Special Premises', 3080, r'special premises \(preservation\)'),
        ('Walled City of Lahore', 6288, r'^(the )?walled city of lahore act'),
        ('Heritage properties', 1447, r'walled city \(heritage properties\) rules'),
        ('Heritage Foundation', 6139, r'punjab heritage foundation act'),
    ],
    'sindh': [
        ('Cultural Heritage', 1336, r'sindh cultural heritage'),
    ],
    'kp': [
        ('Antiquities Act', 5133, r'khyber pakhtunkhwa antiquities act'),
    ],
    'balochistan': [
        ('Cultural Heritage', 4788, r'balochistan cultural heritage preservation act'),
        ('Antiquities Act', 4986, r'balochistan antiquities act'),
        ('Archives', 5824, r'balochistan archives act'),
    ],
    'ajk': [
        ('Antiquities Act', 10935, r'^(the )?antiquit[a-z]* act, 1986'),
        ('Its amendment, 2001', 9952, r'antiquities \(amendment\) act, 2001'),
    ],
}
# Questions people bring to heritage law, each answered by opening units of a law -- never by a summary. `key` is a
# code the client words (docs/13). Each region asks its OWN law (D-078): the units are read from that law's served
# section index at as_of and in the region's territory (INV-5), by their printed label, so a label -- or a law --
# not served there drops out. Islamabad asks the federal law, read in ICT; Gilgit-Baltistan has no heritage law in
# the corpus and asks none. Every pairing was read against the served text on 18 Nov 2026 (doc 1336 after its
# contents-alignment repair). A region without a section for a question simply does not ask it (Sindh's 1994 Act
# has no repair or export section).
_ANTIQUITIES_1975 = r'^(the )?antiquities act, 1975'
HERITAGE_QUESTIONS = {
    'fed': [
        ('found_object', 3468, _ANTIQUITIES_1975, ['5A', '13A']),
        ('build_near', 3468, _ANTIQUITIES_1975, ['22']),
        ('repair', 3468, _ANTIQUITIES_1975, ['20']),
        ('declared_protected', 3468, _ANTIQUITIES_1975, ['10', '11']),
        ('damage_signs', 3468, _ANTIQUITIES_1975, ['19', '23']),
        ('export', 3468, _ANTIQUITIES_1975, ['26']),
        ('visit', 3468, _ANTIQUITIES_1975, ['31']),
    ],
    # the Antiquities Act, 1975 as the Punjab Code holds it (doc 3157); its printed label is '5-A', not '5A'
    'punjab': [
        ('found_object', 3157, _ANTIQUITIES_1975, ['5-A', '13A']),
        ('build_near', 3157, _ANTIQUITIES_1975, ['22']),
        ('repair', 3157, _ANTIQUITIES_1975, ['20']),
        ('declared_protected', 3157, _ANTIQUITIES_1975, ['10', '11']),
        ('damage_signs', 3157, _ANTIQUITIES_1975, ['19', '23']),
        ('export', 3157, _ANTIQUITIES_1975, ['26']),
        ('visit', 3157, _ANTIQUITIES_1975, ['31']),
    ],
    # Sindh Cultural Heritage (Preservation) Act, 1994: s.5 premises or objects found with no owner; s.11(1) an order
    # against building on or near a protected site against its agreement; s.6 declaration, with its objection
    # procedure printed under the stray '7.'; s.19 the penalty for destroying or defacing; s.18 public access
    'sindh': [
        ('found_object', 1336, r'sindh cultural heritage', ['5']),
        ('build_near', 1336, r'sindh cultural heritage', ['11']),
        ('declared_protected', 1336, r'sindh cultural heritage', ['6', '7']),
        ('damage_signs', 1336, r'sindh cultural heritage', ['19']),
        ('visit', 1336, r'sindh cultural heritage', ['18']),
    ],
    # Khyber Pakhtunkhwa Antiquities Act, 2016: s.66 sends export to the federal laws, and says so
    'kp': [
        ('found_object', 5133, r'khyber pakhtunkhwa antiquities act', ['10', '22', '61']),
        ('build_near', 5133, r'khyber pakhtunkhwa antiquities act', ['55']),
        ('repair', 5133, r'khyber pakhtunkhwa antiquities act', ['16']),
        ('declared_protected', 5133, r'khyber pakhtunkhwa antiquities act', ['15', '19']),
        ('damage_signs', 5133, r'khyber pakhtunkhwa antiquities act', ['18', '24']),
        ('export', 5133, r'khyber pakhtunkhwa antiquities act', ['66']),
        ('visit', 5133, r'khyber pakhtunkhwa antiquities act', ['54']),
    ],
    # Balochistan Antiquities Act, 2014 (its s.41 repeals the 1975 Act in Balochistan; territorial_repeal, D-078)
    'balochistan': [
        ('found_object', 4986, r'balochistan antiquities act', ['6', '15']),
        ('build_near', 4986, r'balochistan antiquities act', ['24']),
        ('repair', 4986, r'balochistan antiquities act', ['22']),
        ('declared_protected', 4986, r'balochistan antiquities act', ['11', '12']),
        ('damage_signs', 4986, r'balochistan antiquities act', ['21', '25']),
        ('export', 4986, r'balochistan antiquities act', ['28']),
        ('visit', 4986, r'balochistan antiquities act', ['33']),
    ],
    # Azad Jammu and Kashmir Antiquities Act, 1986 (printed 'Antiquites')
    'ajk': [
        ('found_object', 10935, r'^(the )?antiquit[a-z]* act, 1986', ['6']),
        ('build_near', 10935, r'^(the )?antiquit[a-z]* act, 1986', ['23']),
        ('repair', 10935, r'^(the )?antiquit[a-z]* act, 1986', ['21']),
        ('declared_protected', 10935, r'^(the )?antiquit[a-z]* act, 1986', ['11', '12']),
        ('damage_signs', 10935, r'^(the )?antiquit[a-z]* act, 1986', ['20', '24']),
        ('export', 10935, r'^(the )?antiquit[a-z]* act, 1986', ['27']),
        ('visit', 10935, r'^(the )?antiquit[a-z]* act, 1986', ['32']),
    ],
}
# Asked in every region, answered only where the Constitution is served in that region's territory (not AJK or GB,
# by the corpus's territorial model, 0095)
HERITAGE_CONSTITUTION_QUESTIONS = [('culture_right', CONSTITUTION_DOCUMENT, CONSTITUTION_TITLE, ['28'])]
# Protecting what Pakistan makes (D-079): the federal laws a maker of a craft or a regional product relies on, and the
# questions makers bring to them, answered by sections read against the served text on 18 Nov 2026. Federal law,
# read without a territorial filter.
MAKER_LAWS = [
    ('Geographical indications', 3433, r'^(the )?geographical indications \(registration and protection\) act, 2020'),
    ('Trade marks', 4338, r'^(the )?trade marks ordinance, 2001'),
    ('Designs', 2722, r'^(the )?registered designs ordinance, 2000'),
    ('Copyright', 3896, r'^(the )?copyright ordinance, 1962'),
]
MAKER_QUESTIONS = [
    # s.11 the Federal Government holds Pakistan's geographical indications; s.26 what registration gives
    ('gi_place', 3433, MAKER_LAWS[0][2], ['11', '26']),
    ('gi_logo', 3433, MAKER_LAWS[0][2], ['28']),           # the national GI logo on registered products
    ('gi_fake', 3433, MAKER_LAWS[0][2], ['30', '41']),     # infringement; false geographical indication
    ('brand', 4338, MAKER_LAWS[1][2], ['22', '39']),       # applying to register a mark; rights conferred
    ('design', 2722, MAKER_LAWS[2][2], ['3', '8']),        # registerable designs; infringement
    ('copyright', 3896, MAKER_LAWS[3][2], ['10', '13']),   # works in which copyright subsists; first owner
]
HERITAGE_DOCUMENTS = sorted({d for laws in HERITAGE_LAWS.values() for _s, d, _p in laws}
                            | {d for qs in HERITAGE_QUESTIONS.values() for _k, d, _p, _l in qs}
                            | {d for _k, d, _p, _l in HERITAGE_CONSTITUTION_QUESTIONS}
                            | {d for _s, d, _p in MAKER_LAWS})


def heritage_page(rows: list[dict], sections_of) -> dict:
    """The Heritage tab from released rows of HERITAGE_DOCUMENTS. `sections_of(instrument_id, territory)` returns
    that law's served section index items (each with id, kind, label, heading, citation) at the page's as_of in that
    territory (None: no territorial filter), or None.

    Returns {regions, makers}: each region {jurisdiction, laws_from, laws: [{short_name, instrument}], questions:
    [{key, instrument, units}]}, where `laws_from` names the jurisdiction whose laws are listed and asked ('fed' for
    Islamabad). A region's questions come from its own law, then the Constitution's; units keep the order
    HERITAGE_QUESTIONS gives, and a question none of whose units is served in the region is left out. `makers` is
    {laws, questions} from MAKER_LAWS and MAKER_QUESTIONS, read without a territorial filter (D-079)."""
    def pick(doc, pattern):
        return next((r for r in rows if r['document_id'] == doc
                     and re.search(pattern, (r.get('title') or '').lower())), None)

    def laws_of(jurisdiction):
        return [dict(short_name=short, instrument=hit) for short, doc, pattern in HERITAGE_LAWS.get(jurisdiction, [])
                if (hit := pick(doc, pattern)) is not None]

    indexes = {}

    def questions_of(source, territory, asked=None):
        out = []
        for key, doc, pattern, labels in (asked if asked is not None
                                          else HERITAGE_QUESTIONS.get(source, []) + HERITAGE_CONSTITUTION_QUESTIONS):
            law = pick(doc, pattern)
            if law is None:
                continue
            if (law['id'], territory) not in indexes:
                indexes[law['id'], territory] = sections_of(law['id'], territory) or []
            by_label = {s['label']: s for s in indexes[law['id'], territory]}
            units = [dict(id=by_label[l]['id'], kind=by_label[l]['kind'], label=l,
                          heading=by_label[l].get('heading') or None, citation=by_label[l].get('citation'),
                          preview=by_label[l].get('preview') or None)
                     for l in labels if l in by_label]
            if units:
                out.append(dict(key=key, instrument=law, units=units))
        return out

    regions = []
    for j in HERITAGE_REGIONS:
        source = 'fed' if j == 'ict' else j
        regions.append(dict(jurisdiction=j, laws_from=source, laws=laws_of(source),
                            questions=questions_of(source, None if j == 'fed' else j)))
    makers = dict(laws=[dict(short_name=short, instrument=hit) for short, doc, pattern in MAKER_LAWS
                        if (hit := pick(doc, pattern)) is not None],
                  questions=questions_of('fed', None, MAKER_QUESTIONS))
    return dict(regions=regions, makers=makers)
