"""Agent JF's rule G `reviewed_row_cells_in_unit` (extends rule D `reviewed_schedule_row_cells`, key
source_schedule_row_cells; doc 4497 E9 p229, rule 11(2)'s quota table). Ported by builder BZ (group 29, 17 Oct 2026)
from claude/agJF/test_jf_rule_g_DRAFT.py (91297273). Pure: segment() over hand-made blocks shaped like doc 4497 p229,
under the DEFAULT profile."""
import pytest

from nizam.corpus.segment import segment


def _b(i, text, y, x=126.0):
    return {"id": i, "page_no": 1, "y0": y, "page_height": 792.0, "x0": x, "x1": x + 80.0, "text": text}


BLOCKS = [
    _b(1, "10.  Seniority.- The seniority shall be fixed by the Government. \n", 60.0),
    _b(2, "11.  Vacancies.-(1) Vacancies shall be announced by the Commission. \n", 90.0),
    _b(3, "(2) \n Provincial quotas shall be as under:— \n", 120.0),
    _b(10, "1.  \nPunjab (including Federal \nArea of Islamabad)  \n50% \nNil \n50% \n", 150.0, 133.0),
    _b(11, "8.2% \n", 175.0, 419.0),
    _b(12, "Sindh  \nThe share of Sindh will be \nfurther sub-allocated:  \n", 168.0, 161.0),
    _b(13, "2.  \n", 185.0, 134.0),
    _b(14, "20.5% \n", 185.0, 454.0),
    _b(15, "3.  \nKPK  \n11.5%  \n1%  \n12.5%   \n", 220.0, 134.0),
    _b(20, "12.  Domicile.- Vacancies shall be allocated on the basis of domicile. \n", 260.0),
]
ROWS = [{"row_block_id": 10, "row_prefix": "1.  \nPunjab", "label": "1", "cell_block_ids": [], "kind": "clause"},
        {"row_block_id": 13, "row_prefix": "2.", "label": "2", "cell_block_ids": [12, 11, 14], "kind": "clause"},
        {"row_block_id": 15, "row_prefix": "3.  \nKPK", "label": "3", "cell_block_ids": [], "kind": "clause"}]
UNITS = [{"source_block_id": 11, "kind": "section", "label": "8"},
         {"source_block_id": 14, "kind": "section", "label": "20"}]


def _sub2(seg):
    s11 = next(n for n in seg.flatten() if n.kind == "section" and n.label == "11")
    return next(c for c in s11.children if c.kind == "subsection" and c.label == "2")


def test_rows_open_as_clauses_of_the_open_unit_with_their_own_cells():
    seg = segment(BLOCKS, structural_overrides={"source_schedule_row_cells": ROWS, "source_text_units": UNITS})
    rows = {c.label: c for c in _sub2(seg).children if c.kind == "clause"}
    assert set(rows) == {"1", "2", "3"}
    two = " ".join((rows["2"].text or "").split())
    assert two.startswith("Sindh The share of Sindh") and "8.2%" in two and two.endswith("20.5%")
    assert "Sindh" not in (rows["1"].text or "")
    assert not [n for n in seg.flatten() if n.kind == "section" and n.label in ("1", "2", "3", "8", "20")]
    assert [n.label for n in seg.flatten() if n.kind == "section"] == ["10", "11", "12"]


def test_specs_without_kind_still_need_a_schedule():
    rows = [dict(r) for r in ROWS]
    for r in rows:
        r.pop("kind")
    with pytest.raises(ValueError):
        segment(BLOCKS, structural_overrides={"source_schedule_row_cells": rows, "source_text_units": UNITS})


def test_a_serial_only_prefix_must_be_exactly_the_label_and_stop():
    rows = [ROWS[0], dict(ROWS[1], row_prefix="2"), ROWS[2]]
    with pytest.raises(ValueError):
        segment(BLOCKS, structural_overrides={"source_schedule_row_cells": rows, "source_text_units": UNITS})


def test_an_unknown_kind_fails_closed():
    rows = [dict(ROWS[0], kind="part")] + ROWS[1:]
    with pytest.raises(ValueError):
        segment(BLOCKS, structural_overrides={"source_schedule_row_cells": rows, "source_text_units": UNITS})


def test_rule_g_worker_shape_admits_kind_and_serial_only_prefix():
    import nizam.workers.segment as W
    ok = W._bz_schedule_row_cells_ok
    base = {"row_block_id": 13, "row_prefix": "2.", "label": "2", "cell_block_ids": [12, 14]}
    assert ok({**base, "kind": "clause"})
    assert ok({**base, "row_prefix": "Sindh row six", "kind": "section"})
    assert ok({**base, "row_prefix": "Sindh row six"})      # rule D's shape, unchanged
    assert not ok({**base, "kind": "table"})
    assert not ok({**base, "row_prefix": "3."})             # a serial-only prefix must be the row's own label
    assert not ok({**base, "row_prefix": "2"})
