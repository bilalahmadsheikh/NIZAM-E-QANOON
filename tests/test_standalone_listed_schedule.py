"""A title-case ``Schedule II`` alone in its block opens the schedule when the
contents lists it and the next line is the rule it is made under.

Doc 2042 (Punjab Letters of Administration and Succession Certificates Rules,
2021) prints four schedules. Schedule I is a form that ends on its attestation
line -- "Attested by Oath / Commissioner", no full stop -- so the heading
"Schedule II" that follows read as the tail of an unfinished sentence, and the
whole Letter of Administration form was appended to Schedule I's paragraph 3.
Contents row "2 Schedule II" stayed unresolved.

The guard it slipped past exists for wrapped cross-references, and doc 1337
p3 shows why it must stay: "... in accordance with / Schedule-I" puts the
reference in its own block at the foot of the page, followed by the page
number. The statutory reference printed under a real heading -- "(Rule 5)" --
is what separates the two.

Measured 24 Sep 2026 over all 15 documents with a title-case standalone
schedule block and a printed contents: the 11 released ones segment
identically with and without this rule; only blocked doc 2042 changes.
"""
import json
import pathlib

from nizam.corpus.segment import _standalone_listed_schedule, segment

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "standalone-schedule-2042.json"


def test_standalone_listed_schedule_proofs():
    listed = {"i", "ii", "iii", "iv"}
    assert _standalone_listed_schedule("Schedule II \n", "Schedule II", "", listed,
                                       "(Rule 5) \nLETTER OF ADMINISTRATION \n")
    assert _standalone_listed_schedule("Schedule-III\n", "Schedule-III", "", listed,
                                       "(See rule 4(2)(f))")
    # doc 1337: a wrapped cross-reference followed by the page number
    assert not _standalone_listed_schedule("Schedule-I\n", "Schedule-I", "", listed, "3\n")
    # a reference that continues its sentence in the same block
    assert not _standalone_listed_schedule("Schedule II, which may be hunted", "Schedule II",
                                           ", which may be hunted", listed, "(Rule 5)")
    # a schedule the contents does not list
    assert not _standalone_listed_schedule("Schedule V \n", "Schedule V", "", listed, "(Rule 5)")


def test_schedule_after_a_signature_line_opens():
    blocks = json.loads(FIXTURE.read_text(encoding="utf-8"))["blocks"]
    seg = segment(blocks)
    schedules = [n for n in seg.flatten() if n.kind == "schedule"]
    assert [n.label for n in schedules] == ["Schedule I", "Schedule II", "Schedule III", "Schedule IV"]
    second = schedules[1]
    assert "LETTER OF ADMINISTRATION" in second.text
    first_items = [n for n in seg.flatten() if n.parent is schedules[0]]
    assert not any("LETTER OF ADMINISTRATION" in (n.text or "") for n in first_items)
