"""The explanatory-note guard must read a heading, not the word "note".

Doc 02 §5.1. ``subdivide()`` refuses to cut a block where the text before the
cut ends in ``Note.``, because ``Note. 1. ...`` numbers an explanatory note and
not a section -- the Punjab Prisons Rules 1978 print several.

The guard was written unanchored, so it also matched any sentence merely ENDING
in the word "note". The Contract Act 1872 prints an illustration to section 132
that ends "...is no answer to a suit by C against A upon the note.", and section
133 follows it in the same block: the whole of section 133 was swallowed into
section 132 and became uncitable. Requiring "Note." to stand at the head of its
own line separates the two readings.
"""
from nizam.corpus.segment import subdivide


GENUINE_NOTE = (
    "132. The liability of two persons who are co-sureties is unaffected.\n"
    "Note.\n"
    "1. This rule applies only where the parties have so agreed.\n"
)

ILLUSTRATION_ENDING_IN_NOTE = (
    "132. A and B make a joint and several promissory note to C.\n"
    "A makes it in fact as surety for B, and C knows this at the time when the "
    "note is made. The fact that A, to the knowledge of C, made it as surety "
    "for B, is no answer to a suit by C against A upon the note.\n"
    "133. Discharge of surety by variance in terms of contract.\n"
    "Any variance, made without the surety's consent, in the terms of the "
    "contract between the principal debtor and the creditor, discharges the "
    "surety as to transactions subsequent to the variance.\n"
)


def test_a_numbered_explanatory_note_still_stays_with_its_rule():
    assert subdivide(GENUINE_NOTE) == [GENUINE_NOTE]


def test_a_sentence_ending_in_the_word_note_does_not_swallow_the_next_section():
    pieces = subdivide(ILLUSTRATION_ENDING_IN_NOTE)
    assert len(pieces) == 2
    assert pieces[0].lstrip().startswith('132.')
    assert pieces[1].lstrip().startswith('133.')
    assert 'discharges the surety' in pieces[1]
    # Nothing is dropped by the cut: the pieces reconstitute the source exactly.
    assert ''.join(pieces) == ILLUSTRATION_ENDING_IN_NOTE
