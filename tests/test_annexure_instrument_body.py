"""A notification's ANNEXURE can be the instrument itself, not a schedule.

Doc 02 §5.1. Pakistani gazettes often promulgate rules as an annexure to the
notification that makes them::

    PART 1
    SECRETARY PROVINCIAL OMBUDSMAN (MOHTASIB) SINDH
    N O T I F I C A T I O N
    ... In pursuance of the provisions of sub-section (2) of section 8 ...
    ANNEXURE A PART-I
    PRELIMINARY
    1. (1) These rules may be called the Provincial Ombudsman (Employees)
       Service Rules, 1997.

The annexure heading opens auxiliary mode, in which a numbered opener is a
schedule row rather than a section. Both existing exits from that mode need
evidence this document does not have: the first needs a contents list naming
the section, the second a ``schedule`` node carrying a printed "Rule N" prefix.
So every rule of the instrument became a schedule-row clause -- document 2754
kept all 329 of its blocks and 0 citable sections, including "No person shall be
appointed by initial appointment to a post unless he is a citizen of...".

A schedule row never names the instrument. The naming formula at label 1 is
therefore proof that the auxiliary was the instrument's own body.
"""
import pytest

from nizam.corpus.segment import segment


def gazette_blocks(naming_text):
    """The Sindh Gazette shape: notification, ANNEXURE A, then the rules."""
    rows = [
        'THE SINDH GOVERNMENT GAZETTE \n',
        ' DATED MONDAY MARCH 31, 1997. \n',
        ' PART 1 \n',
        ' SECRETARY PROVINCIAL OMBUDSMAN (MOHTASIB) SINDH \n',
        'N O T I F I C A T I O N \n',
        ' Karachi the 17th March, 1997 No. 5/25/96 Admn.--In pursuance of the '
        'provisions of sub-section (2) of section 8 of the Act, the Ombudsman '
        'is pleased to make the following rules. \n',
        'ANNEXURE A PART-I \n',
        'PRELIMINARY \n',
        'Short title and commencement. \n',
        naming_text,
        '(2) They shall come into force at once. \n',
        'Definition. \n',
        '2. They shall apply to all employees of the Office of the Ombudsman '
        'but shall not apply to casual or work-charge staff. \n',
        '3. No person shall be appointed by initial appointment to a post '
        'unless he is a citizen of Pakistan. \n',
    ]
    return [
        dict(id=9200 + i, text=text, page_no=1, y0=60.0 + i * 24,
             page_height=792.0, x0=72.0, x1=520.0)
        for i, text in enumerate(rows)
    ]


NAMING = ('1. (1) These rules may be called the Provincial Ombudsman '
          '(Employees) Service Rules, 1997. \n')


def test_rules_promulgated_in_an_annexure_stay_citable():
    result = segment(gazette_blocks(NAMING))
    sections = [n for n in result.flatten() if n.kind == 'section']
    assert [n.label for n in sections] == ['1', '2', '3']
    assert 'shall not apply to casual' in sections[1].text
    assert 'citizen of Pakistan' in sections[2].text

    # The annexure heading is kept, not deleted: nothing leaves the record.
    assert any(n.kind == 'annexure' for n in result.flatten())
    assert set(result.block_roles) == {b['id'] for b in gazette_blocks(NAMING)}


def test_an_annexure_without_the_naming_formula_stays_a_schedule():
    """Only the instrument names itself; a genuine annexure keeps its rows."""
    plain = '1. Scale of pay for clerical staff. \n'
    result = segment(gazette_blocks(plain))
    sections = [n for n in result.flatten() if n.kind == 'section']
    assert sections == [], 'a schedule row must not be promoted to a section'


@pytest.mark.parametrize('naming', [
    '1. (1) These regulations may be called the Ombudsman Regulations, 1997. \n',
    '1. (1) This scheme may be cited as the Ombudsman Scheme, 1997. \n',
])
def test_the_formula_is_recognised_in_its_common_spellings(naming):
    result = segment(gazette_blocks(naming))
    labels = [n.label for n in result.flatten() if n.kind == 'section']
    assert labels == ['1', '2', '3']
