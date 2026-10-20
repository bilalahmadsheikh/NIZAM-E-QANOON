"""Rule `reviewed_long_suffix_section` (stage 3, agent DE, doc 4225; owner 12 Oct chat: implement the recommended fix).

Doc 4225 (Anti-Terrorism Act, 1997) prints inserted sections 11EEEE and 11EEEEE; every section grammar admits at most
three suffix letters, so both ran into s.11EEE. A reviewed `source_long_suffix_section_openers`
[{block_id, label: digits + 4-8 capitals}] opens exactly those labels -- only at the start of the named block and only
when the contents list prints the label as a row on an earlier page (fail closed otherwise). Inert without the key.
Ported from agent DE's $S/agDE-test-ls.py.
"""
from nizam.corpus import segment as SEG

KEY = "source_long_suffix_section_openers"


def blocks(contents_rows=True):
    rows = [
        (1, "CONTENTS"),
        (1, "1. Short title."),
        (1, "2. Definitions."),
        (1, "3. Powers."),
    ]
    if contents_rows:
        rows += [(1, "3EEEE. Detention for inquiry."), (1, "4. Repeal.")]
    else:
        rows += [(1, "4. Repeal.")]
    rows += [
        (2, "1. Short title. This Act may be called the Test Act."),
        (2, "2. Definitions. In this Act, words have their ordinary meaning."),
        (2, "3. Powers. (1) The Government may arrest any person.\n(2) The order shall be in writing."),
        (2, "3EEEE. Detention for inquiry. (1) The Government may detain any person for inquiry.\n"
            "(2) The inquiry shall be conducted by a police officer."),
        (2, "4. Repeal. The Old Act is repealed."),
    ]
    return [{"id": 9000 + k, "text": t, "page_no": p, "y0": 100 + 40 * k, "page_height": 800, "x0": 60, "x1": 500}
            for k, (p, t) in enumerate(rows)]


def labels(seg):
    return [(n.kind, n.label) for n in seg.flatten() if n.kind == "section"]


def opener_id(bl):
    return next(b["id"] for b in bl if b["text"].startswith("3EEEE. Detention for inquiry. (1)"))


def test_inert_without_key():
    bl = blocks()
    assert ("section", "3EEEE") not in labels(SEG.segment(bl))


def test_opens_a_label_the_contents_prints():
    bl = blocks()
    seg = SEG.segment(bl, structural_overrides={KEY: [{"block_id": opener_id(bl), "label": "3EEEE"}]})
    assert ("section", "3EEEE") in labels(seg)


def test_refuses_a_label_the_contents_does_not_print():
    bl = blocks(contents_rows=False)
    try:
        SEG.segment(bl, structural_overrides={KEY: [{"block_id": opener_id(bl), "label": "3EEEE"}]})
    except ValueError as exc:
        assert "contents list prints no row" in str(exc)
    else:
        raise AssertionError("a label absent from the contents list was opened")


def test_refuses_a_block_the_label_does_not_open():
    bl = blocks()
    other = next(b["id"] for b in bl if b["text"].startswith("4. Repeal. The Old"))
    try:
        SEG.segment(bl, structural_overrides={KEY: [{"block_id": other, "label": "3EEEE"}]})
    except ValueError as exc:
        assert "not the start of its block" in str(exc)
    else:
        raise AssertionError("an opener away from its block was accepted")


def test_refuses_a_short_suffix_label():
    bl = blocks()
    try:
        SEG.segment(bl, structural_overrides={KEY: [{"block_id": opener_id(bl), "label": "3EEE"}]})
    except ValueError as exc:
        assert "lacks exact source evidence" in str(exc)
    else:
        raise AssertionError("a label with 3 suffix letters was accepted")
