"""A printed CONTENTS marker outranks the peak gate.

Doc 02 §5.1-5.2. `parse_contents` will not treat a fall in numbering as the
contents/body boundary until the numbering has peaked -- 8 for a document with
more than 24 labels. That gate exists to stop a contents list being INVENTED
where the document prints none.

It measures the LEADING INTEGER, and a dotted-decimal contents never raises it:
1., 1.1., 1.2.1., 2.10.2.2. all peak at 2. So a document that prints CONTENTS in
capitals and lists its entries can be refused for want of a peak it cannot
reach, and its own contents rows then become the citable sections while the real
provisions are demoted beneath them.

The fixture is the first four pages of document 2324, a university appointments
and promotions statute, as extracted. Before this change `parse_contents`
returned no list for it at all; its section 1 was kept as the contents row
`1 APPOINTMENT AND PROMOTION 1.1 .1. GENERAL INTRODUCTION` while the real
`1 APPOINTMENTS AND PROMOTIONS:- The University's policy on appointments...`
was demoted beneath it, and its section "2.4" carried the mangled fragment
`.1. salary of existing faculty member on tenure track` instead of the section
2.4.1 the page prints.

Where the marker is printed the evidence for a list is direct. Everything else
still has to prove itself -- the agreement floor, the upside-down guard,
opens_at_first_section and heading corroboration all still run.
"""
import json
from pathlib import Path

from nizam.corpus.segment import parse_contents

FIXTURE = Path(__file__).parent / 'fixtures' / 'contents-marker-low-peak-2324.json'


def blocks():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def test_a_printed_contents_marker_is_found_despite_a_low_peak():
    toc, boundary, found = parse_contents(blocks())
    assert found, 'a document printing CONTENTS must not be refused for want of a peak'
    assert boundary > 0
    # dotted-decimal entries: the leading integer never exceeds 2
    assert max(int(k.split('.')[0]) for k in toc if k[0].isdigit()) <= 2
    assert toc['1.2'] == 'BASES FOR APPOINTMENT AND PROMOTION'


def test_the_marker_is_what_admits_it():
    """Strip the printed CONTENTS line and the gate applies again."""
    stripped = [b for b in blocks()
                if b['text'].strip().upper() not in {'CONTENTS', 'CONTENT'}]
    assert len(stripped) < len(blocks()), 'fixture must contain a CONTENTS block'
    _, _, found = parse_contents(stripped)
    assert not found, 'no printed marker and a low peak: no list may be invented'
