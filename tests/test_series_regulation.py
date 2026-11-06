"""Rule `reviewed_series_regulation` (SBP prudential regulations; owner chat 28 Oct 2026 'release 6 with 1 numbering
rule'): a reviewed printed opener whose label is a lettered series identifier -- 'R-1', 'SME R-1', 'HF 1', 'IPF.1.1'."""
import pytest

import nizam.corpus.segment as S


def _b(i, text, page=1, y0=40.0):
    return {"id": i, "text": text, "page_no": page, "x0": 72.0, "x1": 480.0, "y0": y0, "page_height": 842.0}


def _blocks():
    return [_b(1, "1. Short title.-These Regulations may be called the Test Regulations.\n", y0=40.0),
            _b(2, "Regulation R – 1: Minimum Capital Requirements\nBanks shall maintain capital.\n", y0=80.0),
            _b(3, "Regulation R-2  Exposure Limits\nThe exposure shall not exceed ten per cent.\n", y0=120.0),
            _b(4, "IPF.1 -- CREDIT APPRAISAL\nA thorough appraisal shall be carried out.\n", y0=160.0),
            _b(5, "IPF.1.1 -- Analysis of Financial Models\nBanks shall evaluate the model.\n", y0=200.0)]


def _openers(*items):
    return {"source_printed_rule_openers": [
        {"source_block_id": b, "kind": "section", "label": l, "source_prefix": p} for b, l, p in items]}


ALL = [(2, "R-1", "Regulation R – 1: Minimum"), (3, "R-2", "Regulation R-2  Exposure"),
       (4, "IPF.1", "IPF.1 -- CREDIT"), (5, "IPF.1.1", "IPF.1.1 -- Analysis")]


def test_inert_without_openers():
    labels = [n.label for n in S.segment(_blocks()).flatten() if n.kind == "section"]
    assert "R-1" not in labels and "IPF.1" not in labels


def test_series_labels_open_sections_with_their_text():
    seg = S.segment(_blocks(), structural_overrides=_openers(*ALL))
    secs = {n.label: n for n in seg.flatten() if n.kind == "section"}
    assert ["1", "R-1", "R-2", "IPF.1", "IPF.1.1"] == [n.label for n in seg.flatten() if n.kind == "section"]
    assert secs["R-1"].text.startswith("Minimum Capital Requirements")
    assert secs["IPF.1"].text.startswith("CREDIT APPRAISAL")
    assert secs["IPF.1.1"].text.startswith("Analysis of Financial Models")


def test_ipf_1_does_not_match_the_start_of_ipf_1_1():
    with pytest.raises(ValueError):
        S.segment(_blocks(), structural_overrides=_openers((5, "IPF.1", "IPF.1.1 -- Analysis")))


@pytest.mark.parametrize("label", ["R1x", "r-1", "1-R", "R-"])
def test_malformed_series_label_refused(label):
    with pytest.raises(ValueError):
        S.segment(_blocks(), structural_overrides=_openers((2, label, "Regulation R – 1: Minimum")))


def test_numbered_paragraphs_inside_a_series_regulation_are_its_subsections():
    blocks = _blocks()[:2] + [_b(6, "1. Single Obligor Limit\nThe limit shall be 25 per cent.\n", y0=100.0),
                              _b(7, "2. Related Party Limit\nThe limit shall be 10 per cent.\n", y0=110.0)]
    seg = S.segment(blocks, structural_overrides=_openers((2, "R-1", "Regulation R – 1: Minimum")))
    r1 = [n for n in seg.flatten() if n.label == "R-1"][0]
    assert [(c.kind, c.label) for c in r1.children] == [("subsection", "1"), ("subsection", "2")]
    assert [n.label for n in seg.flatten() if n.kind == "section"] == ["1", "R-1"]


def test_a_group_heading_over_a_numbered_list_opens_and_holds_its_items():
    blocks = [_b(1, "1. Bank means a banking company.\n", y0=20.0), _b(2, "2. Borrower means an individual.\n", y0=30.0),
              _b(3, "PRE-OPERATIONS:\n", y0=40.0), _b(4, "1. Banks shall establish risk management.\n", y0=50.0),
              _b(5, "2. Banks shall prepare a credit policy.\n", y0=60.0), _b(6, "OPERATIONS:\n", y0=70.0),
              _b(7, "1. Consumer financing shall be subject to risk management.\n", y0=80.0)]
    seg = S.segment(blocks, structural_overrides=_openers((3, "PRE-OPERATIONS", "PRE-OPERATIONS:\n"),
                                                          (6, "OPERATIONS", "OPERATIONS:\n")))
    secs = {n.label: n for n in seg.flatten() if n.kind == "section"}
    assert list(secs) == ["1", "2", "PRE-OPERATIONS", "OPERATIONS"]
    assert [(c.kind, c.label) for c in secs["PRE-OPERATIONS"].children] == [("subsection", "1"), ("subsection", "2")]
    assert [(c.kind, c.label) for c in secs["OPERATIONS"].children] == [("subsection", "1")]


@pytest.mark.parametrize("label", ["IV", "XII", "PART"])
def test_short_or_roman_words_are_not_group_headings(label):
    assert not S._SERIES_LABEL.fullmatch(label)
