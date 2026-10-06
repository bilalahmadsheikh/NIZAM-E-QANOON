"""An asterisk-only contents heading is no evidence of a different unit.

Punjab service rules print their contents as ``1. ****** 2. ****** 3. ******``:
the number is promised, the heading withheld. The section-one sub-part rule
(``_SECTION_ONE_SUBPART``) demotes a bare-numbered "2. They shall come into
force at once." to s.1(2) when the contents promises a *different* section 2.
A withheld heading was being read as that promise, so rule 2 of documents 1105
and 4060 was demoted and their contents row 2 stayed unresolved.

Measured 24 Sep 2026 over all 63 documents with asterisk-only contents rows:
the 47 released ones segment identically with and without this rule; only
blocked documents 1078, 1105 and 4060 change, each resolving a contents gap.
"""
import json
import pathlib

from nizam.corpus.segment import _withheld_heading, segment

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "withheld-contents-1105.json"


def test_asterisk_only_heading_is_withheld():
    assert _withheld_heading("******")
    assert _withheld_heading(" * * * ")
    assert not _withheld_heading("Short title and commencement.")
    assert not _withheld_heading("[Omitted]")
    assert not _withheld_heading("")
    assert not _withheld_heading(None)


def test_rule_two_of_a_starred_contents_stays_a_rule():
    """Doc 1105, official PDF p.2: '1. These rules may be called ...',
    '2. They shall come into force at once.', '3. The method of recruitment
    ...', '4. The following rules are hereby repealed'. Contents p.1 lists
    rules 1-4 with '******' headings."""
    blocks = json.loads(FIXTURE.read_text(encoding="utf-8"))["blocks"]
    seg = segment(blocks)
    assert seg.toc_found
    assert seg.missing == []
    top = [(n.kind, n.label) for n in seg.root.children if n.kind == "section"]
    assert top[:4] == [("section", "1"), ("section", "2"),
                       ("section", "3"), ("section", "4")]
    rule_two = [n for n in seg.root.children if n.kind == "section" and n.label == "2"][0]
    assert "come into force at once" in rule_two.text
    rule_one = [n for n in seg.root.children if n.kind == "section" and n.label == "1"][0]
    assert not any(c.kind == "subsection" and c.label == "2" for c in rule_one.children)


def test_schedule_row_two_does_not_demote_the_only_rule_two():
    """Doc 1886 PDF pp.2-4: rule 2 is commencement; Schedule row 2 is a job.

    The 1105 source fixture has the same withheld TOC and numbered main body;
    a later schedule row models doc 1886's independently seen row 2.
    """
    blocks = json.loads(FIXTURE.read_text(encoding="utf-8"))["blocks"]
    blocks.extend([
        dict(id=900001, text="SCHEDULE\n", page_no=3, y0=120.0,
             page_height=842.25, x0=72.0, x1=400.0),
        dict(id=900002, text="2. Director Architecture (BS-19).\n",
             page_no=4, y0=150.0, page_height=842.25,
             x0=72.0, x1=400.0),
    ])
    seg = segment(blocks, profile="unreleased-v4")
    rules = {n.label: n for n in seg.root.children if n.kind == "section"}
    assert "2" in rules
    assert "come into force at once" in rules["2"].text
    assert not any(c.kind == "subsection" and c.label == "2"
                   for c in rules["1"].children)
    assert any(n.kind == "clause" and n.label == "2"
               and "Director Architecture" in n.text
               for n in seg.flatten())
