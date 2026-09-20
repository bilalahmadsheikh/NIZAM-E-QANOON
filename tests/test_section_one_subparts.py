"""Section 1's extent and commencement sub-parts are not sections 2 and 3.

Doc 02 §5.1. The Pakistan Code and the KP Code print section 1's extent and
commencement sentences with bare numbers, flush with the body::

    1. Short title, extent and commencement.- (1) This Act may be called ...
    2. It extends to the whole of Pakistan.
    3. It shall come into force at once.
    2. Definitions.- In this Act ...

Read as sections they collide with the real sections 2 and 3. On 17 Sep 2026
that collision was found decided the wrong way round in 26 released instruments:
"section 2" answered with the extent sentence while the Definitions section sat
demoted beneath it. The repair needs no indentation -- there is none -- so it
rests instead on the sentence being closed and complete, the owner naming the
instrument, the number continuing section 1's own sub-part sequence, and the
instrument independently printing a different section under that number.
"""
import json
from pathlib import Path

import pytest

from nizam.corpus.segment import segment


def blocks():
    path = Path(__file__).parent / 'fixtures' / 'section-one-subparts-flush.json'
    return json.loads(path.read_text(encoding='utf-8'))


def test_extent_and_commencement_are_subparts_of_section_one():
    result = segment(blocks())
    sections = [n for n in result.flatten() if n.kind == 'section']
    assert [n.label for n in sections] == ['1', '2', '3']

    # The citable sections 2 and 3 are the operative ones, not the sub-parts.
    assert 'Definitions' in (sections[1].marginal_note or '') + sections[1].text
    assert '"Authority" means' in sections[1].text
    assert 'shall apply to every person' in sections[2].text

    subparts = [n for n in result.flatten()
                if n.kind == 'subsection' and n.parent is sections[0]]
    by_label = {n.label: n.text for n in subparts}
    assert by_label['2'] == 'It extends to the whole of Pakistan.'
    assert by_label['3'] == 'It shall come into force at once.'

    # Nothing was demoted or dropped: every source block still has a role.
    assert result.repeated_labels_demoted == 0
    assert set(result.block_roles) == {b['id'] for b in blocks()}


@pytest.mark.parametrize('mutation', [
    'owner_does_not_name_the_instrument',
    'number_breaks_the_subpart_sequence',
    'sentence_is_not_closed',
    'label_never_printed_again',
])
def test_repair_requires_every_independent_signal(mutation):
    source = blocks()
    if mutation == 'owner_does_not_name_the_instrument':
        source[1]['text'] = source[1]['text'].replace(
            'This Act may be called the Model Regulation Act, 2026',
            'The Authority is established by this enactment')
    elif mutation == 'number_breaks_the_subpart_sequence':
        source[2]['text'] = source[2]['text'].replace('2.', '7.', 1)
    elif mutation == 'sentence_is_not_closed':
        # An extent clause that runs on into operative law is not a sub-part.
        source[2]['text'] = ('2. It extends to the whole of Pakistan and the '
                             'Authority shall regulate every activity to which '
                             'this Act applies, and may by order prohibit any '
                             'such activity. \n')
    elif mutation == 'label_never_printed_again':
        # No contents, and no second section 2 anywhere: the bare "2." is the
        # only section 2 the instrument has, so it must be left standing.
        source = source[:4]

    result = segment(source)
    twos = [n for n in result.flatten()
            if n.kind == 'subsection' and n.label == '2'
            and n.text.startswith('It extends')]
    assert twos == [], f'{mutation} must not be repaired into a sub-part'


def test_the_ordinary_case_is_untouched():
    """A genuine section 2 that happens to follow section 1 stays a section."""
    source = [
        dict(id=1, text='THE ORDINARY ACT, 2026 \n', page_no=1, y0=60.0,
             page_height=792.0, x0=150.0, x1=450.0),
        dict(id=2, text='1. Short title.- This Act may be called the Ordinary '
                        'Act, 2026. \n',
             page_no=1, y0=120.0, page_height=792.0, x0=72.0, x1=520.0),
        dict(id=3, text='2. It extends to the whole of Pakistan. \n',
             page_no=1, y0=150.0, page_height=792.0, x0=72.0, x1=320.0),
    ]
    result = segment(source)
    labels = [n.label for n in result.flatten() if n.kind == 'section']
    assert labels == ['1', '2']
