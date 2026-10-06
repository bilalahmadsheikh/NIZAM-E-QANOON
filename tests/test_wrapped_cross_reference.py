"""A number that continues a sentence is not a section (doc 02 §5.1).

Two shapes of one defect: a line-initial number that ``subdivide`` cuts out of
the middle of a paragraph -- correctly, for what it can see -- and that the
body walk then opened as a section.

1. A CROSS-REFERENCE WRAPPED onto its own line.  Five rendered-page reviews,
   every block verbatim in ``fixtures/wrapped-cross-reference.json``:

       2271 p4   "...functions provided in section" / "12." / "(2) The general ..."
       2489 p11  "...field operations of the Rescue" / "1122." / "(2) No person ..."
       3193 p16  "...incentives outlined in sections 20 and" / "21." / "(2) With ..."
       3862 p39  "...shall affect the provisions of section" / "49." / "(3) Where ..."
       1357 p12  "...funds established under section" / "20. Such rules and ..."

   Each phantom took the host's later subsections with it and collided with
   the real section of its number -- a collision no S7 decision can close.

2. A YEAR at the start of a line: a wrapped marginal-note citation ("...Punjab
   Act V of" / "1912."), a title line ("1973." / "An Act to amend ..."), the
   instrument's own title wrapped behind its last word ("...Oil Tankers)" /
   "Rules 2018."), debris.
   Genuine numbering passes 1000 -- the Punjab Prisons Rules print real rules
   1249 and 1250 -- so the discriminator is the body's running sequence, not a
   ceiling.

The reverse failure is the worse one: a genuine section read as prose loses
its citation.  Every guard that keeps a section is pinned below, with the
real corpus shapes that motivated it.

Rule: nizam/corpus/segment.py ``_wraps_a_cross_reference`` and
``_year_is_not_a_provision_number``, applied by the wrapped-reference guard in
``segment``'s body walk.  Patch: .patch_xref.py.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from nizam.corpus.segment import (_wraps_a_cross_reference,
                                  _year_is_not_a_provision_number, segment,
                                  subdivide)

FIXTURE = Path(__file__).parent / "fixtures" / "wrapped-cross-reference.json"


def blocks(case: str) -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))[case]["blocks"]


def build(case: str):
    # A window is not a whole instrument, so it has no contents list to find.
    return segment(blocks(case), detect_contents=False)


def labelled(seg, label: str, kinds=("section", "article", "clause")):
    return [n for n in seg.flatten() if n.kind in kinds and n.label == label]


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def subtree_text(node) -> str:
    return " ".join(" ".join(n.text or "" for n in walk(node)).split())


def pieces(case: str, block_id: int) -> list[str]:
    block = next(b for b in blocks(case) if b["id"] == block_id)
    return subdivide(block["text"])


# ------------------------------------------------ 1. the wrapped cross-reference

WRAPPED = [
    # case, host, phantom label(s), wrapped block, reference that must read on,
    # subsections that must stay the host's
    ("2271-section-12", "5", ("12",), 178576, r"section\s+12\.", ("2", "3")),
    ("2489-rescue-1122", "14", ("1122", "22"), 206645, r"Rescue\s+1122\.",
     ("2", "3")),
    ("3193-sections-20-and-21", "18", ("21",), 323675,
     r"sections\s+20\s+and\s+21\.", ("2", "3", "4", "5")),
    ("3862-section-49", "47", ("49",), 501503, r"section\s+49\.", ("2", "3")),
    ("1357-section-20", "21", ("20",), 76437,
     r"section\s+20\.\s+Such rules and regulations", ("2",)),
]


@pytest.mark.parametrize("case,host,phantoms,block,reads_on,subsections", WRAPPED)
def test_a_wrapped_reference_number_is_not_a_section(
        case, host, phantoms, block, reads_on, subsections):
    seg = build(case)
    for label in phantoms:
        assert not [n for n in labelled(seg, label) if n.first_block == block], (
            f"{case}: the wrapped number opened a unit labelled {label}")
    (owner,) = labelled(seg, host, kinds=("section",))
    # The number is where the page prints it: inside the host's sentence.
    assert re.search(reads_on, subtree_text(owner)), subtree_text(owner)[:300]
    # And the subsections the phantom used to take are the host's again.
    kept = {n.label for n in walk(owner) if n.kind == "subsection"}
    assert set(subsections) <= kept, (case, sorted(kept))


def test_the_1357_clauses_stay_under_the_subsection_that_introduces_them():
    seg = build("1357-section-20")
    (owner,) = labelled(seg, "21", kinds=("section",))
    (sub2,) = [n for n in owner.children if n.kind == "subsection" and n.label == "2"]
    assert {"a", "b", "c"} <= {n.label for n in sub2.children}


@pytest.mark.parametrize("case,block,index,owner,keys", [
    ("2271-section-12", 178576, 1, "5", ("12", "12")),
    # The host's own bare number is a piece of its own, so the wrapped
    # number is the third piece in 2489 and the fourth in 3862.
    ("2489-rescue-1122", 206645, 2, "14", ("1122", "22")),
    ("3193-sections-20-and-21", 323675, 1, "18", ("21", "21")),
    ("3862-section-49", 501503, 3, "47", ("49", "49")),
    ("1357-section-20", 76437, 1, "21", ("20", "20")),
])
def test_the_rule_reads_each_shape_from_the_pieces_subdivide_makes(
        case, block, index, owner, keys):
    cut = pieces(case, block)
    text = cut[index]
    rest = text.split(".", 1)[1]
    following = cut[index + 1] if index + 1 < len(cut) else None
    seen = {str(n) for n in range(1, int(owner) + 1)}
    assert _wraps_a_cross_reference(cut[index - 1], text, rest, following,
                                    keys, owner, seen, {})


# ------------------------------------------ 2. genuine openers must survive
#
# Each of these is a reason the rule KEEPS a section, stated on the smallest
# text that shows it.  The first is the reverse failure named in the brief.

HOST = "5. Powers.—(1) The Board may act under "


@pytest.mark.parametrize("before,text,following,owner,seen,toc,why", [
    (HOST + "this section.\n", "12. Definitions.—In this Act,", None,
     "5", {"1", "2", "3", "4", "5"}, {}, "the sentence is finished"),
    (HOST + "this section\n", "12. Definitions.—In this Act,", None,
     "5", {"1", "2", "3", "4", "5"}, {}, "a heading follows, full stop lost"),
    (HOST + "this section\n", "6. The Board shall meet monthly.", None,
     "5", {"1", "2", "3", "4", "5"}, {}, "6 is the next section"),
    (HOST + "this section\n", "5A. The Board shall meet monthly", None,
     "5", {"1", "2", "3", "4", "5"}, {}, "5A is inserted after 5"),
    (HOST + "section\n", "12. (1) The Board shall meet monthly", None,
     "5", {"1", "2", "3", "4", "5"}, {}, "it opens its own first subsection"),
    (HOST + "section\n", "12.\n", "(1) The Board shall meet monthly", "5",
     {"1", "2", "3", "4", "5"}, {}, "the stranded number heads its own (1)"),
    (HOST + "section\n", "12.\n", "(a) the Board shall meet monthly", "5",
     {"1", "2", "3", "4", "5"}, {}, "nothing shows the sentence carried on"),
    (HOST + "section\n", "12. [Omitted.]", None, "5",
     {"1", "2", "3", "4", "5"}, {}, "an omission placeholder is a section"),
    (HOST + "section\n", "12. The Board shall meet monthly", None, "11",
     {str(n) for n in range(1, 12)}, {}, "12 follows the high-water mark"),
    (HOST + "section\n", "7. The Board shall meet monthly", None, "5",
     {"1", "2", "3", "4", "5"},
     {"5": "Powers", "6": "Omitted", "7": "Meetings"},
     "a forward number with text after it: s.6 was never printed"),
    (HOST + "section\n", "6. The Board shall meet monthly", None, "5",
     {"1", "2", "3", "4", "5"},
     {"5": "Powers", "6": "Meetings"}, "the contents puts it next"),
    (HOST + "the Government\n", "12. The Board shall meet monthly", None, "5",
     {"1", "2", "3", "4", "5"}, {}, "a name before TEXT is how a list row reads"),
    ("28. Match Box/Lighter\n", "29. Yogurt (Dehi)", None, "28",
     {"28"}, {}, "doc 4474's diet scale: a table row, not a reference"),
    (HOST + "these rules\n", "12. The Board shall meet monthly", None, "5",
     {"1", "2", "3", "4", "5"}, {}, "a plural noun demands no number"),
])
def test_a_genuine_opener_is_never_read_as_a_reference(
        before, text, following, owner, seen, toc, why):
    rest = text.split(".", 1)[1]
    key = text.split(".", 1)[0].strip()
    assert not _wraps_a_cross_reference(before, text, rest, following,
                                        (key, key), owner, seen, toc), why


def test_a_heading_block_without_its_full_stop_is_not_the_same_paragraph():
    # Doc 1357 prints real sections 16, 25, 38 and 39 after marginal headings
    # that lost their full stop -- "Government Banking Arrangements" / "16." --
    # but the heading is its own block, so the walk passes before=None.
    assert not _wraps_a_cross_reference(
        None, "16. Government shall maintain", " Government shall maintain",
        None, ("16", "16"), "15", {str(n) for n in range(1, 16)}, {})


def _block(block_id, text, page=1, y0=100.0):
    return {"id": block_id, "text": text, "page_no": page, "y0": y0,
            "page_height": 842.0, "x0": 72.0, "x1": 520.0}


def test_the_whole_walk_keeps_a_real_section_after_a_reference_line():
    # The brief's own reverse case, end to end: the host's last line is a
    # reference that lost its full stop, and the next line is the real s.6.
    seg = segment([
        _block(1, "5. Powers of the Board.—(1) The Board may act.\n"
                  "(2) Nothing shall limit the powers under this section\n"
                  "6. Meetings of the Board.—(1) The Board shall meet.\n"),
        _block(2, "7. Quorum.—Five members shall form a quorum.\n", y0=300.0),
    ], detect_contents=False)
    assert [n.label for n in seg.flatten() if n.kind == "section"] == ["5", "6", "7"]


def test_the_whole_walk_reunites_a_wrapped_reference_with_its_sentence():
    seg = segment([
        _block(1, "5. Powers of the Board.—(1) The Board may act as provided in section\n"
                  "12.\n"
                  "(2) The Board shall meet monthly.\n"),
        _block(2, "6. Quorum.—Five members shall form a quorum.\n", y0=300.0),
    ], detect_contents=False)
    assert [n.label for n in seg.flatten() if n.kind == "section"] == ["5", "6"]
    (owner,) = labelled(seg, "5", kinds=("section",))
    assert re.search(r"section\s+12\.", subtree_text(owner))
    assert "2" in {n.label for n in owner.children if n.kind == "subsection"}


# ----------------------------------------------------------- 3. the year label

@pytest.mark.parametrize("case,year", [
    ("372-year-title", "1973"),       # "1973." / "An Act to amend the Sind ..."
    ("1627-year-citation", "1912"),   # "...Punjab Act V of" / "1912."
    ("1110-year-citation", "1966"),   # "...Ordinance XX of" / "1966."
])
def test_a_year_at_a_line_start_is_not_a_section(case, year):
    assert not labelled(build(case), year)


@pytest.mark.parametrize("case,year,rule_one_says", [
    # "...(Pension" / "Regulations 1997." -- the instrument's own title, whose
    # last word `_INNER_RULE` cuts as if it were "Regulation 1997."
    ("42-regulations-1997", "1997", r"Pension\)?\s*Regulations 1997\."),
    # "...Oil Tankers)" / "Rules 2018."
    ("1765-rules-2018", "2018", r"Tankers\)\s*Rules 2018\."),
])
def test_an_instrument_s_own_title_year_is_not_a_rule(case, year, rule_one_says):
    seg = build(case)
    assert not labelled(seg, year)
    (rule_one,) = labelled(seg, "1", kinds=("section",))
    assert re.search(rule_one_says, subtree_text(rule_one)), subtree_text(rule_one)[:300]


def test_a_substituted_section_stays_with_the_section_substituting_it():
    # Doc 1627: the phantom "1912" had swallowed the quoted new section 3 that
    # section 4 of the amending Act substitutes.
    seg = build("1627-year-citation")
    (owner,) = labelled(seg, "4", kinds=("section",))
    assert "“3. In this Act" in subtree_text(owner)


def test_the_prisons_rules_keep_rules_1249_and_1250():
    seg = build("4474-rules-1248-1250")
    sections = {n.label: n.first_block for n in seg.flatten() if n.kind == "section"}
    assert sections.get("1249") == 848809
    assert sections.get("1250") == 848812
    # "...sub-head (c) of rules 1247, 1248 and" / "1249." is a reference inside
    # rule 1250's list; it reads on in whichever unit holds that line.
    assert not [n for n in labelled(seg, "1249") if n.first_block == 848815]
    holders = [n for n in seg.flatten() if 848815 in n.blocks]
    assert any(re.search(r"rules 1247, 1248 and 1249\.", " ".join((n.text or "").split()))
               for n in holders)


@pytest.mark.parametrize("text,keys,owner,seen,toc,expected,why", [
    ("1966. Amendment", ("1966", "1966"), "5", {"1", "2", "3", "4", "5"}, {},
     True, "a year far above section 5"),
    ("1973.\n", ("1973", "1973"), None, set(), {}, True, "a title line at the root"),
    ("1894. Note.", ("1894", "1894"), "5", {str(n) for n in range(1, 1107)},
     {}, True, "below-sequence years are citations, not rules"),
    ("1850. Remission.", ("1850", "1850"), "1849",
     {str(n) for n in range(1, 1850)}, {}, False, "a real rule 1850 follows 1849"),
    ("1853. Remission.", ("1853", "1853"), "1849",
     {str(n) for n in range(1, 1850)}, {}, False, "a small gap is still the sequence"),
    ("1966. Levy.", ("1966", "1966"), "5", {"1", "2", "3", "4", "5"},
     {"1966": "Levy"}, False, "the contents promises it"),
    ("1966. Levy.", ("1966", "6"), "5", {"1", "2", "3", "4", "5"}, {},
     False, "the fusion-repaired reading is the next section"),
    ("1249. Form No. 49.", ("1249", "1249"), "13", {"13"}, {}, False,
     "not year-shaped: this rule does not decide it"),
    ("Rules 2018. \n", ("2018", "2018"), "1", {"1"}, {}, True,
     "the instrument's own title year, wrapped behind its last word"),
    ("Rule 1850. Remission.", ("1850", "1850"), "1849",
     {str(n) for n in range(1, 1850)}, {}, False,
     "a real prefixed rule 1850 follows rule 1849"),
])
def test_the_year_rule_is_relative_to_the_running_sequence(
        text, keys, owner, seen, toc, expected, why):
    rest = text.split(".", 1)[1]
    assert _year_is_not_a_provision_number(text, rest, keys, owner, seen,
                                           toc) is expected, why
