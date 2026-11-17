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
