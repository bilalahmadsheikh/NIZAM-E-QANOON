"""The body floor must not be advanced past enacted law.

Doc 02 §5.1-5.2.  `parse_contents` chooses the boundary between the printed
contents and the body by AGREEMENT, and breaks a tie by POSITION: the LAST tied
candidate wins, on the argument that "a later split scoring no worse consumed
only labels the body already had, and that is what more contents looks like".

That argument holds for a genuine two-page contents list.  It fails whenever a
document prints a SECOND numbered run repeating the contents labels -- a
Schedule of standing orders, a form, an appendix table restarting at 1.
Agreement is then identical at the true boundary and at the late one, heading
corroboration is equal (usually 0.0000 at both), and position alone hands the
boundary to the late run.  Everything between the two is filed `role='contents'`
attached to no provision: present in `text_block` in the PDF's own words, and
reachable by no citation.  That is an INV-4 failure, and it is invisible to the
contents-gap queue, which only asks whether a promised entry resolved.

Document 2846, the Sindh Terms of Employment (Standing Orders) Act 2015, is the
case these tests are built from.  Its contents list is page 1; its fourteen
sections run pages 2-8; the standing orders in its own Schedule restart at 1 on
page 8 and carry the labels the contents promises.  Candidates at blocks 6, 15
and 80 all score 1.0000 with corroboration 0.0000, so position took block 80 --
page 8.  The preamble, the definitions, the penalty section and the repeal were
all "contents", and the only citable sections the document had were the rows of
its own Schedule.

The repair fences POSITION only.  Heading corroboration still dominates, because
corroboration is source evidence; position may advance the boundary only while
what it absorbs is apparatus.  The reverse failure is worse than the defect --
a contents entry promoted to a provision is a phantom section -- so the frontier
test is narrow, and the guards below are what keep it narrow.
"""
import json
import re
from pathlib import Path

import pytest

from nizam.corpus import segment as S
from nizam.corpus.segment import parse_contents, segment

FIXTURES = Path(__file__).parent / 'fixtures'

frontier = getattr(S, '_swallowed_body_frontier', None)
needs_patch = pytest.mark.skipif(
    frontier is None,
    reason='_swallowed_body_frontier is not present: .patch_floor.py not applied')


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


def blocks(*texts, page_size=10):
    return [dict(id=i, text=t + ' \n', page_no=1 + i // page_size,
                 y0=60.0 + (i % page_size) * 18, page_height=792.0,
                 x0=72.0, x1=520.0)
            for i, t in enumerate(texts)]


def stranded(seg, source):
    """Blocks filed as contents and attached to nothing -- the defect itself."""
    return [b for b in source
            if seg.block_roles.get(b['id'], (None, None)) == ('contents', None)]


# --------------------------------------------------------------- the defect

def test_a_schedule_repeating_the_contents_labels_does_not_take_the_body_floor():
    """Doc 2846: the Act's own sections must not be filed as its contents.

    Fails on the unpatched parser, which puts the boundary at block 80 (page 8)
    because the Schedule's standing orders restart at 1 and tie the vote.
    """
    source = load('contents-floor-2846.json')
    toc, boundary, found = parse_contents(source)
    assert found
    assert source[boundary]['page_no'] == 2, (
        'the body floor is past the printed contents list: page '
        f"{source[boundary]['page_no']}")

    seg = segment(source)
    # The Act's operative sections are citable units, not apparatus.
    labels = {n.label for n in seg.flatten() if n.kind == 'section'}
    assert {str(n) for n in range(2, 15)} <= labels, (
        f'the Act\'s own sections are still uncitable: {sorted(labels)}')

    left = stranded(seg, source)
    assert max((b['page_no'] for b in left), default=0) <= 2, (
        'enacted pages are still filed as contents: '
        f"{sorted({b['page_no'] for b in left})}")
    # 16,971 characters over pages 1-8 before; page 1-2 front matter after.
    assert sum(len(b['text']) for b in left) < 4000


def test_the_printed_contents_still_resolves_after_the_floor_moves():
    """The repair must improve the acceptance test doc 02 §5 names, not evade it."""
    source = load('contents-floor-2846.json')
    seg = segment(source)
    assert seg.agreement > 0.90, seg.agreement
    resolved = sum(1 for e in seg.toc_entries if e.get('node') is not None)
    assert resolved >= len(seg.toc_entries) - 1, (
        f'{resolved}/{len(seg.toc_entries)} printed entries resolved')


# --------------------------------------------------------------- the guards
#
# A contents entry promoted to a provision is a phantom section, and this corpus
# already has that problem. Everything below exists to keep the frontier from
# causing it.

@pytest.mark.parametrize('document,boundary', [(1438, 15), (2581, 14)])
def test_known_good_boundaries_do_not_move(document, boundary):
    """The fence must not disturb a boundary the source already proved."""
    source = load(f'contents-{document}.json')
    _toc, actual, found = parse_contents(source)
    assert found and actual == boundary


def test_a_contents_list_is_not_promoted_into_the_body():
    """Doc 2846's twenty-three printed entries stay apparatus.

    The failure this guards is the opposite of the defect: dragging the floor
    too early leaves contents rows to open as sections, and the document gains
    provisions the legislature never enacted.
    """
    source = load('contents-floor-2846.json')
    toc, boundary, _found = parse_contents(source)
    assert len(toc) == 23, sorted(toc)
    seg = segment(source)
    page_one = [b for b in source if b['page_no'] == 1]
    assert all(seg.block_roles.get(b['id'], (None, None))[0] == 'contents'
               for b in page_one), 'a printed contents page became body'


def test_an_inner_numbered_run_inside_the_contents_still_loses_to_position():
    """The Bolan University shape: an inner list, still inside the contents.

    Sections are listed, then the First Statute's own items are listed, still
    inside the printed contents. The inner fall ties with the real boundary, and
    preferring it would leave those items in the body as duplicate sections.
    Position must still be free to move the boundary past pure apparatus.
    """
    body = ('No person shall carry on the business of a dealer in any '
            'controlled article except under and in accordance with the '
            'conditions of a licence issued under this section, and every '
            'such licence shall be in the prescribed form.')
    doc = (['THE EXAMPLE UNIVERSITY ACT, 2017', 'CONTENTS']
           + [f'{n}. Promised heading {n}.' for n in range(1, 13)]
           + ['THE FIRST STATUTE']
           + [f'{n}. Statute item {n}.' for n in range(1, 9)]
           + ['THE EXAMPLE UNIVERSITY ACT, 2017',
              'WHEREAS it is expedient to establish a university; '
              'It is hereby enacted as follows:']
           + [f'{n}. Promised heading {n}. {body}' for n in range(1, 13)])
    source = blocks(*doc)
    _toc, boundary, found = parse_contents(source)
    assert found
    seg = segment(source)
    tops = [n.label for n in seg.root.children if n.kind == 'section']
    assert tops == [str(n) for n in range(1, 13)], tops
    assert 'Statute item' not in ' '.join(
        n.heading or '' for n in seg.root.children)


_OPERATIVE = re.compile(r'\b(?:shall|means|is hereby|are hereby)\b', re.I)


def _operative(text):
    """The audit's definition of stranded law: long, with an operative verb."""
    t = S._norm(text)
    return len(t) > 200 and bool(_OPERATIVE.search(t))


def test_the_fence_never_revives_a_contents_hypothesis_over_enacted_text():
    """Doc 3392: enacted text before the earliest candidate stands the fence down.

    The first version of this repair scanned for enacted text only from the
    EARLIEST tied candidate. In 3392 that candidate is itself on page 3, past
    the operative text of s.13 of the West Pakistan Finance Act 1964 on pages
    2-3 ("Electricity Duty shall not be leviable ...", '"Consumer" means ...').
    Choosing it pulled the boundary into the front-matter window, the post-walk
    refutation no longer withdrew the contents hypothesis, and ~3,600 characters
    of operative law were filed as contents attached to nothing. Doc 4473 lost
    its rules 1-26 the same way. This is the worse direction -- invisible law --
    and a positive net count of sections hid it.

    Whatever else changes, no operative block on pages 2-3 may be left as
    contents attached to nothing.
    """
    source = load('contents-floor-3392.json')
    seg = segment(source)
    buried = [b for b in stranded(seg, source)
              if b['page_no'] in (2, 3) and _operative(b['text'])]
    assert not buried, (
        f'{len(buried)} operative blocks filed as contents: '
        f"{[S._norm(b['text'])[:60] for b in buried]}")


# ----------------------------------------------------- the frontier itself

@needs_patch
def test_frontier_ignores_front_matter_between_the_contents_and_the_body():
    """Every exclusion is apparatus that legitimately sits in that gap.

    Without them the frontier lands on a preamble and drags the floor too early.
    """
    preamble = ('WHEREAS it is expedient to provide for the regulation of '
                'industrial and commercial employment in the Province of the '
                'Sindh and for matters connected therewith or ancillary '
                'thereto; It is hereby enacted as follows and this Act shall '
                'come into force at once on the date of its publication in '
                'the official Gazette of the Province.')
    # Doc 2846's whole contents page arrives as one layout block of this shape.
    fused_list = ('1. Classification of worker. 2. Terms and conditions of '
                  'service to be given in writing. 3. Cards. 4. Publication of '
                  'working time. 5. Publication of holidays and pay days. '
                  '6. Shift working. 7. Attendance and late coming. '
                  '8. Notification of periods of work shall be displayed. '
                  '9. Stoppage of work. 10. Payment of wages. 11. Termination '
                  'of employment. 12. Certificate of service. 13. Penalty. '
                  '14. Repeal and savings of the repealed Ordinance.')
    leaders = ('1. Short title, extent and commencement ......................'
               ' 1  2. Definitions ...................................... 2  '
               '3. The Authority shall be a body corporate ............... 3  '
               '4. Powers of the Authority .............................. 4  '
               '5. Meetings of the Authority ........................... 5  '
               '6. Funds of the Authority .............................. 6  '
               '7. Power to make rules ................................. 7')
    marker = ('CONTENTS 1. Short title and commencement 2. Definitions '
              '3. Establishment of the Authority which shall be a body '
              'corporate having perpetual succession and a common seal '
              '4. Powers 5. Functions 6. Meetings of the Authority and the '
              'procedure it shall follow 7. Committees 8. Funds of the '
              'Authority 9. Budget 10. Accounts and audit 11. Annual report '
              '12. Delegation of powers 13. Power to make rules 14. Repeal')
    for text in (preamble, fused_list, leaders, marker):
        assert len(S._norm(text)) >= S._SWALLOW_MIN_CHARS, len(S._norm(text))
        source = blocks(text, 'tail')
        assert frontier(source, 0) == len(source), (
            f'front matter was mistaken for enacted text: {text[:60]!r}')


@needs_patch
def test_frontier_finds_enacted_text():
    enacted = ('3. Terms and conditions of service to be given in writing. '
               'Every employer shall, within two months of the commencement '
               'of this Act, issue to each worker employed by him a written '
               'statement of the terms and conditions of his service, and no '
               'such statement shall be altered to the disadvantage of the '
               'worker except in accordance with section 4.')
    source = blocks('1. Short title.', '2. Definitions.', enacted)
    assert len(S._norm(enacted)) >= S._SWALLOW_MIN_CHARS
    assert frontier(source, 0) == 2


@needs_patch
def test_frontier_starts_where_it_is_told():
    enacted = ('Every employer shall, within two months of the commencement '
               'of this Act, issue to each worker employed by him a written '
               'statement of the terms and conditions of his service, and no '
               'such statement shall be altered to the disadvantage of the '
               'worker except in accordance with the provisions of section 4.')
    source = blocks(enacted, 'tail', enacted)
    assert frontier(source, 0) == 0
    assert frontier(source, 1) == 2
    assert frontier(source, 3) == len(source)
