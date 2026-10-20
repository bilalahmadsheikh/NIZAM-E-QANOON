"""A block all of whose units are set aside is 'footnote', never 'unassigned' (group 25; lead 17 Oct, audit C5 option A).

Doc 4397 p98, block 738861: '188PUNJAB AMENDMENT / In rule 262, the words ... / 188 Vide Notification ...'. Agent K2's
reviewed bound note (use 'text') binds the amendment to rule 262 -- the law text is in the tree -- and agent JE's
reviewed set-aside unit takes the '188 Vide ...' footnote out of the walk. The bound note gives a role only to a block
it consumes whole, and the set-aside run left the walk with no mark(), so the closing pass called the block
'unassigned' (277 characters, C5). Now the block is marked 'footnote' with no owner, as the walk-stage set-aside does.
A block that keeps any unit in the walk is left to first-writer-wins.
"""
from nizam.corpus import segment as S


def _b(i, text, y0, page=1):
    return {"id": i, "text": text, "page_no": page, "x0": 72.0, "x1": 480.0, "y0": y0, "page_height": 842.0}


def _blocks():
    return [_b(1, "261. General stands.-- No transport vehicle shall be refused admittance to a stand. \n", 40.0),
            _b(2, "262. Inspection of stands.-- Every stand shall be open to any inspection at any time by the "
                  "District Magistrate. \n", 80.0),
            _b(3, "188PUNJAB AMENDMENT \nIn rule 262, the words “District Magistrate” wherever occurring shall be "
                  "substituted by the words “District Co-ordination Officer”. \n"
                  "188 Vide Notification NO SOTR-/1-5-4/2000(P), dated 9.3.2002. \n", 120.0),
            _b(4, "263. Company stands.-- A company may maintain a stand. \n", 160.0)]


OVERRIDES = {
    "source_bound_notes": [{"use": "text", "source_block_id": 3, "source_prefix": "188PUNJA", "end_block_id": 3,
                            "end_prefix": "188 Vi", "owner_kind": "section", "owner_label": "262"}],
    "source_set_aside_units": [{"source_block_id": 3, "source_prefix": "188 Vide Not"}],
}


def test_a_block_left_only_with_a_set_aside_run_is_footnote():
    seg = S.segment(_blocks(), profile="unreleased-v4", structural_overrides=OVERRIDES)
    role, owner = seg.block_roles[3][0], seg.block_roles[3][1]
    assert role == "footnote" and owner is None
    s262 = next(n for n in seg.flatten() if n.kind == "section" and n.label == "262")
    assert "District Co-ordination Officer" in s262.text          # the bound note's law text stays on rule 262
    assert "Vide Notification" not in " ".join(n.text or "" for n in seg.flatten())
    assert not [b for b, (r, _n) in seg.block_roles.items() if r == "unassigned"]


def test_a_block_keeping_a_walk_unit_is_not_reclassified():
    blocks = _blocks()
    blocks[2] = _b(3, "264. Fees.-- The fees shall be paid in advance. \n188 Vide Notification NO SOTR, dated 9.3.2002. \n",
                   120.0)
    overrides = {"source_set_aside_units": [{"source_block_id": 3, "source_prefix": "188 Vide Not"}]}
    seg = S.segment(blocks, profile="unreleased-v4", structural_overrides=overrides)
    assert seg.block_roles[3][0] == "body"                          # rule 264 opens there: first writer wins
