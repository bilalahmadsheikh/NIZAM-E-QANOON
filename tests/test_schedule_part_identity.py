"""A contents row "Schedule VI" is the body's "SCHEDULE PART-VI".

The Punjab Auqaf Organization (Appointment & Conditions of Service) Rules,
1994 (docs 2374 and 3929) print one schedule in nine parts, headed
"SCHEDULE PART-I" to "SCHEDULE PART-IX", and their contents name the parts
"25. Schedule I" to "33. Schedule IX". The schedule identity read nothing from
"SCHEDULE PART-VI", so no contents row could link to a part, and PART-VI --
printed after the title-case table caption "Functional unit / Medical
Establishment" -- could not be proved a heading and was read as a
cross-reference, its whole table appended to PART-V.

The part ordinal is read only when no plain ordinal is printed, so
"Schedule II, Part I" keeps identity "ii".

Measured 24 Sep 2026 over all 16 documents whose text prints "Schedule Part":
the 12 released ones segment identically; only blocked docs 2374 and 3929
change, each linking all nine schedule rows.
"""
import json
import pathlib

from nizam.corpus.segment import _schedule_identity, segment

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "schedule-parts-2374.json"


def test_schedule_part_identity():
    assert _schedule_identity("SCHEDULE PART-VI") == "vi"
    assert _schedule_identity("ADMINISTRATION AND MANAGEMENT SCHEDULE PART- I") == "i"
    assert _schedule_identity("Schedule VI") == "vi"
    # a plain ordinal wins over a part
    assert _schedule_identity("Schedule II, Part I") == "ii"
    assert _schedule_identity("THE SCHEDULE") is None
    assert _schedule_identity("Part VI") is None


def test_every_schedule_part_opens_and_links():
    blocks = json.loads(FIXTURE.read_text(encoding="utf-8"))["blocks"]
    seg = segment(blocks)
    parts = [n.heading for n in seg.flatten() if n.kind == "schedule"]
    assert parts == ["PART-I", "PART-II", "PART-III", "PART-IV", "PART-V",
                     "PART-VI", "PART-VII", "PART-VIII", "PART-IX"]
    rows = [e for e in seg.toc_entries if e.get("label") in {str(n) for n in range(25, 34)}]
    assert len(rows) == 9
    assert all(e.get("node") is not None for e in rows)
    assert seg.missing == []
