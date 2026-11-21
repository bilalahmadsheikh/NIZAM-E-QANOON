"""D-110 `reviewed_lettered_insertion_subsection`: a page-read opener opens an inserted definition numbered with
lower-case letters ('3[(8ab) “Federal Government.”'), and one behind a bare note marker ('4(20) “Good faith.”').

General Clauses Act 1897 (doc 4392) s.3: inserted definitions printed '1[(8aa)', '3[(8ab)', '*5[(43a)', '4(20)' ran on
inside the definition before them, so 'Federal Government' and 'Provincial Government' had no unit of their own. The
reviewed printed-rule opener accepted only upper-case suffixes ('8AB') and a marker inside a bracket. Readings carry the
new forms; nothing changes for a document without them.
"""
import pytest

from nizam.corpus import segment as S


def _b(i, text, y0, page=5):
    return {"id": i, "text": text, "page_no": page, "x0": 72.0, "x1": 480.0, "y0": y0, "page_height": 842.0}


def _blocks():
    return [_b(1, "3. Definitions.__In this Act, unless there is anything repugnant in the subject or context,__ \n", 40.0),
            _b(2, "(7) “British India.” “British India” shall mean the territories then so governed:] \n"
                  "(8) “British possession.” “British possession” shall mean any part of Her Majesty's dominions: \n", 80.0),
            _b(3, "1[(8aa) “Central Act.” “Central Act” shall mean an Act of the Central legislature:] \n"
                  "3[(8ab) “Federal Government.” “Federal Government” shall mean the Federal Government: \n", 120.0),
            _b(4, "(19) “Financial year.” “financial year” means the year commencing on the first day of July:] \n"
                  "4(20) “Good faith.” a thing shall be deemed to be done in “good faith” where it is done honestly: \n"
                  "*5[(43a) “Provincial Government”. “Provincial Government” shall mean the Provincial Government: \n",
               160.0),
            _b(5, "4. Application of foregoing definitions.__The definitions in section 3 apply. \n", 200.0)]


OPENERS = {"source_printed_rule_openers": [
    {"source_block_id": 2, "label": "8", "source_prefix": "(8) “British poss", "kind": "subsection"},
    {"source_block_id": 3, "label": "8ab", "source_prefix": "3[(8ab) “Federal Gove", "kind": "subsection"},
    {"source_block_id": 4, "label": "20", "source_prefix": "4(20) “Good faith.", "kind": "subsection"},
    {"source_block_id": 4, "label": "43a", "source_prefix": "*5[(43a) “Provincial Government”", "kind": "subsection"}]}


def _subsections(seg):
    s3 = next(n for n in seg.flatten() if n.kind == "section" and n.label == "3")
    return {n.label: n.text for n in s3.children if n.kind == "subsection"}


def test_without_readings_the_inserted_definitions_run_on():
    subs = _subsections(S.segment(_blocks(), profile="unreleased-v4"))
    assert "8ab" not in subs and "43a" not in subs


def test_reviewed_openers_open_each_inserted_definition():
    subs = _subsections(S.segment(_blocks(), profile="unreleased-v4", structural_overrides=OPENERS))
    assert {"8", "8ab", "20", "43a"} <= set(subs)
    assert subs["8ab"].startswith("“Federal Government.”")            # the marker '3[' and the label are not text
    assert subs["20"].startswith("“Good faith.”")                     # the bare marker '4' is the note's
    assert subs["43a"].startswith("“Provincial Government”")
    assert "Federal Government" not in subs.get("8aa", "")            # (8ab) no longer runs on inside (8aa)
    assert "Good faith" not in subs.get("19", "")


def test_a_bare_marker_is_read_only_before_its_own_label():
    # '4(20)' is a marker and (20); a reading naming label 21 at '4(20)' is malformed and refused
    bad = {"source_printed_rule_openers": [
        {"source_block_id": 4, "label": "21", "source_prefix": "4(20) “Good faith.", "kind": "subsection"}]}
    with pytest.raises(ValueError):
        S.segment(_blocks(), profile="unreleased-v4", structural_overrides=bad)


def test_an_upper_case_lettered_label_is_unchanged():
    # the existing grammar: '(8AB)' upper case still reads as before; a lower-case label never matches it
    with pytest.raises(ValueError):
        S.segment(_blocks(), profile="unreleased-v4", structural_overrides={"source_printed_rule_openers": [
            {"source_block_id": 3, "label": "8AB", "source_prefix": "3[(8ab) “Federal Gove", "kind": "subsection"}]})
