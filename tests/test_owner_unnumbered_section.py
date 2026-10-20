"""Agent JD's tests (14 Oct 2026) for rule `owner_unnumbered_section` (G; doc 2491 pp116-117; owner export j q2
'unnumbered-unit'), ported into nizam/corpus/segment.py by builder BZ (group 6). JD's draft ran them against its
in-memory ON copy; here `S` is the live module, as JD's note directs. Assertions unchanged."""
import pytest

import nizam.corpus.segment as S

CITE = {"export": ".artifacts/decision-review/exports/decision-review-2026-10-12-j.json", "document_id": 2491,
        "question_id": "q2"}


def _b(i, text, page, y0):
    return {"id": i, "text": text, "page_no": page, "x0": 72.0, "x1": 480.0, "y0": y0, "page_height": 842.0}


def _blocks():
    # doc 2491 pp115-116, shortened: s.45, s.46 (1)-(2), then the reproduced saving clause of the amending Act.
    return [
        _b(1, "45. Transitory provisions. The Senate shall be constituted under this Act. \n", 1, 40.0),
        _b(2, "46. Removal of difficulties. (1) If any question arises it shall be placed before the Chancellor. \n",
           1, 80.0),
        _b(3, "(2) If any difficulty arises the Chancellor may make such order.] \n", 1, 120.0),
        _b(4, "1[Saving.\n24.\nUpon coming into force of the provisions of the Ordinance as amended anything done "
              "shall be continued. \n", 2, 40.0),
        _b(5, "(2) All institutes shall continue to function. \n", 2, 120.0),
        _b(6, "(3) Any statutes made shall be deemed to be statutes made under the said Ordinance. \n", 2, 160.0)]


def _opener(**changes):
    item = {"source_block_id": 4, "label": "Saving", "heading": "Saving.", "source_prefix": "1[Saving.",
            "after_section_label": "46", "owner_decision": CITE}
    return {"source_unnumbered_section_openers": [dict(item, **changes)]}


def _tops(seg):
    return [(n.kind, n.label) for n in seg.flatten() if n.parent is not None and n.parent.kind == "instrument"]


def test_G_inert_without_the_key():
    tops = _tops(S.segment(_blocks(), profile="unreleased-v4"))
    assert ("section", "Saving") not in tops


def test_G_opens_a_word_labelled_top_level_section_keeping_the_printed_number_in_its_text():
    seg = S.segment(_blocks(), profile="unreleased-v4", structural_overrides=_opener())
    assert _tops(seg) == [("section", "45"), ("section", "46"), ("section", "Saving")]
    saving = [n for n in seg.flatten() if n.label == "Saving"][0]
    assert saving.heading == "Saving." and saving.first_block == 4
    assert saving.text.startswith("24. Upon coming into force")
    assert [(c.kind, c.label) for c in saving.children] == [("subsection", "2"), ("subsection", "3")]
    assert not any(n.label == "24" for n in seg.flatten())


@pytest.mark.parametrize("changes", [
    {"after_section_label": "45"},                 # not the open top-level section
    {"label": "24"},                               # a number is never a word label
    {"label": "Savings"},                          # not the printed lead word
    {"heading": "Repeal."},                        # heading lead differs from the prefix
    {"source_prefix": "Saving."},                  # the block does not start with the prefix
    {"owner_decision": {"export": "x.json"}},      # malformed owner citation
])
def test_G_refuses_without_matching_evidence(changes):
    with pytest.raises(ValueError):
        S.segment(_blocks(), profile="unreleased-v4", structural_overrides=_opener(**changes))


def test_G_needs_its_profile_rule():
    # v3 has neither this rule nor a mid-body word opener: the reviewed opener fails closed
    with pytest.raises(ValueError):
        S.segment(_blocks(), profile="unreleased-v3", structural_overrides=_opener())
