"""Agent JD's rule `reviewed_division_line` (F; doc 4142 pp7, 9; ported 14 Oct 2026 by builder BZ, group 6): a page-read
block named in `source_division_line_blocks` whose first line is '(PART - IV)' opens part IV, or whose first line is the
letter-spaced 'A N N E X T U R E – A' opens annexure 'ANNEXURE A' -- only when the contents prints 'Part IV' / 'Annexure';
every listed block must open, else the build raises. A v4 profile rule, data-gated by the key."""
import pytest

import nizam.corpus.segment as S
from nizam.workers.segment import reviewed_structural_overrides
from tools import materialize_multi_instrument as materializer
from tools.record_curation_patch import GENERIC_STRUCTURAL_KEYS, STRUCTURAL_KEYS


def blocks(*texts):
    return [{"id": 100 + i, "text": t, "page_no": 1 + (i > 2), "y0": 100 + 40 * i, "page_height": 800, "x0": 50, "x1": 500}
            for i, t in enumerate(texts)]


DOC = blocks("CONTENTS \n1. Short title. \nPart-IV. \n18. Committees. \nAnnexure. \n",
             "REGULATIONS \n",
             "1. Short title. These regulations may be called the Test Regulations. \n",
             "(PART - IV) \nCOMMITTEES \n",
             "18. Committees. The University shall have the following committees. \n",
             "A N N E X T U R E – A \nList of committees \n")


def test_division_lines_open_only_when_listed_and_printed_in_the_contents():
    plain = [(n.kind, n.label) for n in S.segment(DOC, profile="unreleased-v4").flatten()]
    assert ("part", "IV") not in plain
    seg = S.segment(DOC, profile="unreleased-v4", structural_overrides={"source_division_line_blocks": [103, 105]})
    got = [(n.kind, n.label) for n in seg.flatten()]
    assert ("part", "IV") in got and ("annexure", "ANNEXURE A") in got


def test_division_line_fails_closed_and_is_wired():
    with pytest.raises(ValueError):
        S.segment(DOC, profile="unreleased-v4", structural_overrides={"source_division_line_blocks": [104]})
    assert "reviewed_division_line" in S.SEGMENTATION_PROFILES["unreleased-v4"]
    key = "source_division_line_blocks"
    assert key in STRUCTURAL_KEYS and key in GENERIC_STRUCTURAL_KEYS and key in materializer.STRUCTURAL_PATCH_KEYS
    assert reviewed_structural_overrides([], [{"evidence": {"structural_overrides": {key: [5]}}},
                                              {"evidence": {"structural_overrides": {key: [7, 5]}}}])[key] == [5, 7]
