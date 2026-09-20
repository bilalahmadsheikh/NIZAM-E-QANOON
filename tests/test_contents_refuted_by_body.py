"""A contents hypothesis the body disproves is withdrawn.

Doc 02 §5.1-5.2. `parse_contents` scores a boundary on a PRE-walk label-overlap
score that must clear `_TOC_MIN_AGREEMENT`. The agreement the body walk actually
achieves is recorded on the Segmentation and then never checked, so a boundary
can be accepted on a promise the body never keeps.

Measured 19 Sep 2026: 21 active instruments carried `toc_found = true` with
post-walk agreement below the floor -- seven at exactly 0.0000, meaning not one
promised label was found after the split -- and they held 245 of 1,547 pending
contents gaps, 16% of the queue from 0.67% of instruments. The K.D.A. Disposal
of Land Rules print rule 1 on page 2 and had `body_starts_page = 15`, so
thirteen pages of rules were filed as contents owned by nothing.

The rule is the one the comment above the pre-walk floor already argues: if the
evidence is too thin to claim a contents list, it is too thin to cut the body on.

It carries a do-no-harm guard. Withdrawing the hypothesis must hand the body
back, so the refuted parse has to carry at least as many citable units as the
one it replaces; where it would not, the hypothesis stands and the document
stays visible in the review queue instead of being quietly made smaller.
"""
from nizam.corpus.segment import segment


def blocks(*texts, page_size=40):
    return [dict(id=i, text=t + " \n", page_no=1 + i // page_size,
                 y0=60.0 + (i % page_size) * 18, page_height=792.0,
                 x0=72.0, x1=520.0)
            for i, t in enumerate(texts)]


def test_a_contents_list_the_body_never_keeps_is_withdrawn():
    """The contents promises rules 1-12; the body prints sections 1-8."""
    doc = (["THE EXAMPLE CODE, 1908", "CONTENTS"]
           + [f"{n}. Main section {n}." for n in range(1, 9)]
           + ["ORDER VII"]
           + [f"{n}. Printed order-rule heading {n}." for n in range(1, 13)]
           + ["THE EXAMPLE CODE, 1908",
              "WHEREAS it is expedient to consolidate the law; "
              "It is hereby enacted as follows:"]
           + [f"{n}. Main section {n}. Enacted text." for n in range(1, 9)])
    seg = segment(blocks(*doc))
    assert not seg.toc_found, 'a hypothesis keeping none of its promises must go'
    assert seg.agreement == 0.0
    # and the body is still read correctly -- the point of withdrawing it
    assert [n.label for n in seg.root.children if n.kind == "section"] == [
        str(n) for n in range(1, 9)]
    assert seg.repeated_labels_demoted == 0
    assert len(seg.block_roles) == len(blocks(*doc))


def test_a_contents_list_the_body_keeps_is_retained():
    """The same shape, with the Order's rules actually printed in the body."""
    doc = (["THE EXAMPLE CODE, 1908", "CONTENTS"]
           + [f"{n}. Main section {n}." for n in range(1, 9)]
           + ["ORDER VII"]
           + [f"{n}. Printed order-rule heading {n}." for n in range(1, 13)]
           + ["THE EXAMPLE CODE, 1908",
              "WHEREAS it is expedient to consolidate the law; "
              "It is hereby enacted as follows:"]
           + [f"{n}. Main section {n}. Enacted text." for n in range(1, 9)]
           + ["THE FIRST SCHEDULE", "ORDER VII"]
           + [f"{n}. Printed order-rule heading {n}. The rule text follows."
              for n in range(1, 13)])
    seg = segment(blocks(*doc))
    assert seg.toc_found, 'a contents list the body keeps must be retained'
    assert seg.agreement > 0.30


def test_a_numbered_footnote_run_is_not_a_contents_list():
    """Footnote lines at the foot of a page must not become contents entries.

    Document 1918's printed contents is page 1 alone; the extractor manufactured
    sixteen more entries, eleven of them the numbered footnote lines at the foot
    of page 2. One phantom was LINKED to a provision while the genuine printed
    row "Local extent." was left as a gap.

    The run shape alone cannot be the test -- a genuine contents list is also
    consecutive ascending numbered blocks. The vocabulary separates them.
    """
    contents = ['THE EXAMPLE ACT, 1882', 'CONTENTS',
                '1. Short title.', '2. Local extent.', '3. Definitions.',
                '4. Power to fix fees.']
    body = ['THE EXAMPLE ACT, 1882',
            '1. Short title. This Act shall be called the Example Act, 1882.',
            '2. Local extent. It shall extend to any ports in the Province.',
            '3. Definitions. In this Act the term "Government" means.',
            '4. Power to fix fees. Government may from time to time fix fees.']
    footnotes = ['1. For Statement of Objects and Reasons, see B.G.G., 1881.',
                 '2. Subs. by the Sind Laws (Adaptation) Order, s.3(i).',
                 '3. Subs. ibid, s.3(i), for "Bombay".',
                 '4. Subs. by the amending Act, 1895, sch. II.',
                 '5. Ins. ibid.']
    seg = segment(blocks(*contents, *body, *footnotes, page_size=6))
    labels = {e['label'] for e in seg.toc_entries}
    assert labels <= {'1', '2', '3', '4'}, (
        f'footnote markers became contents entries: {sorted(labels)}')
    assert len(seg.toc_entries) <= 4
