"""Doc 02 §5.1: local indentation, parentage and operative source text concur."""
import json
from pathlib import Path

import pytest

from nizam.corpus.segment import segment


def blocks():
    return json.loads((Path(__file__).parent / 'fixtures' / 'dotted-commencement-16.json').read_text(encoding='utf-8'))


def test_dotted_commencement_is_section_one_subpart_not_the_operative_section_two():
    source = blocks()
    result = segment(source)
    sections = [n for n in result.flatten() if n.kind == 'section']
    assert [n.label for n in sections] == ['1', '2']
    assert 'section 9-A shall be omitted' in sections[1].text
    commencement = [n for n in result.flatten() if n.kind == 'subsection' and n.label == '2']
    assert len(commencement) == 1 and commencement[0].parent is sections[0]
    assert commencement[0].text == 'It shall come into force at once.'
    assert sections[1].first_block == 252
    assert sections[1].text == 'In the Sind Civil Servants Act, 1973, section 9-A shall be omitted.'
    assert sections[1].marginal_note == 'Omission of section 9-A Sind Act No.XIV of 1973.'
    assert result.repeated_labels_demoted == 0
    assert set(result.block_roles) == {b['id'] for b in source}
    assert not any(n.kind == 'subsection' and n.parent is result.root for n in result.flatten())
    preamble = next(n for n in result.flatten() if n.kind == 'preamble')
    assert 'clause (1) of Article 128' in preamble.text


def _mutate(source, mutation):
    if mutation == 'aligned_commencement':
        source[8]['x0'] = source[7]['x0']
    elif mutation == 'next_section_three':
        source[9]['text'] = source[9]['text'].replace('2.', '3.', 1)
    elif mutation == 'no_naming_subpart':
        source[7]['text'] = source[7]['text'].replace('may  be  called', 'is applicable as')
    elif mutation == 'next_not_operative':
        source[9]['text'] = '2. Further measures shall be prescribed.'
    elif mutation == 'next_other_page':
        source[9]['page_no'] = 2
    return source


@pytest.mark.parametrize('mutation', ['next_section_three', 'no_naming_subpart'])
def test_unlisted_commencement_repair_requires_all_independent_source_signals(mutation):
    result = segment(_mutate(blocks(), mutation))
    assert not any(n.kind == 'subsection' and n.label == '2' for n in result.flatten())
    sections = [n for n in result.flatten() if n.kind == 'section']
    assert next(n for n in sections if n.label == '2').text == 'It shall come into force at once.'


@pytest.mark.parametrize('mutation', ['aligned_commencement', 'next_not_operative', 'next_other_page'])
def test_typographic_signals_alone_no_longer_decide_the_commencement(mutation):
    """18 Sep 2026: these three mutations used to leave the commencement standing
    as section 2.

    They remove signals the unlisted-commencement repair needs -- indentation,
    an operative next section, the same page -- but none of them touches the
    fact that decides the question: this Ordinance prints TWO things numbered 2,
    and one of them is the sentence "It shall come into force at once." The
    extent/commencement repair reads that second printing as independent proof
    that the first is section 1's sub-part, so the correct tree survives the
    loss of the typographic signals. Asserting the old outcome here would assert
    that the commencement IS section 2, which the source refutes -- see the
    primary test above, which reads the same document unmutated.

    The two mutations that break both rules -- a number that does not continue
    section 1's sub-parts, and an owner that never names the instrument -- still
    suppress the repair, and are tested above.
    """
    result = segment(_mutate(blocks(), mutation))
    sections = [n for n in result.flatten() if n.kind == 'section']
    commencement = [n for n in result.flatten()
                    if n.kind == 'subsection' and n.label == '2'
                    and n.text == 'It shall come into force at once.']
    assert len(commencement) == 1
    assert commencement[0].parent is next(n for n in sections if n.label == '1')
    assert next(n for n in sections if n.label == '2').text != 'It shall come into force at once.'
