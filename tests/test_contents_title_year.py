"""A title year that wraps onto the contents page is not a contents row.

Doc 1346 (a Khyber Pakhtunkhwa Ordinance of 1981) prints its title so that the
year leads a line on the contents page -- ``1981.`` / ``2[KHYBER PAKHTUNKHWA]
ORDINANCE NO. IV OF 1981.`` -- and the contents reader took it as row 1981, a
promise no body section can keep. The pre-marker rule (doc 1224) only skips a
year printed in a block BEFORE the CONTENTS marker; this one shares the block
or has no marker. The new proofs are narrow: the year precedes the CONTENTS
line in the marker's own block, or the block cites the instrument by that same
year ("ORDINANCE NO. IV OF 1981"). A four-digit row printed inside the list is
still a row (test_contents_boundary covers that).

Measured 24 Sep 2026 over all 15 documents whose contents carried a year-shaped
row: blocked 1346, 1806, 2856 and 3190 resolve completely, several others
lose only that false row. Released 717 and 1565 would lose a fake
title-year node ("clause 1987", "section 2001") on their next replay -- a
correction, recorded for the released-corpus lane, not applied.
"""
import json
import pathlib

from nizam.corpus.segment import _contents_title_year, segment

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "title-year-contents-1346.json"


def test_title_year_proofs():
    # the instrument cited by the same year in the same block (doc 1346)
    assert _contents_title_year(
        "1981", "1981.  \n \n2[KHYBER PAKHTUNKHWA]ORDINANCE NO. IV OF 1981. \n", False)
    # year before the CONTENTS line of the marker block (doc 2856)
    assert _contents_title_year("2010", "2010. \n \n \nCONTENTS \n", True)
    # the same shape outside the marker block proves nothing
    assert not _contents_title_year("2010", "2010. \n \n \nCONTENTS \n", False)
    # a real four-digit row inside the list
    assert not _contents_title_year("1975", "1975. Historical jurisdiction.", True)
    # a bare masthead year under a weak header (doc 1224 with SECTIONS)
    assert not _contents_title_year("1975", "1975. 2[KHYBER PAKHTUNKHWA]", False)
    assert not _contents_title_year("12", "12. Repeal.", True)


def test_wrapped_title_year_is_not_promised():
    blocks = json.loads(FIXTURE.read_text(encoding="utf-8"))["blocks"]
    seg = segment(blocks)
    assert seg.toc_found
    assert "1981" not in seg.toc
    assert seg.missing == []
    assert not any(n.label == "1981" for n in seg.flatten())
