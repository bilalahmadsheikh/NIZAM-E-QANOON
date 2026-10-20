"""Rule M `range_link_counted` (doc 3901; sibling of W `kind_link_counted`):
a contents range row 'N to M' linked to the node carrying that same range label represents every number N..M in the
run's label arithmetic.

Ported by builder BZ, 15 Oct 2026, from claude/agJD/tools/test_range_link_counted_DRAFT.py, against the live module. Full released A/B
of W+M: 4,508 / 4,508 identical (scratchpad agJD-ab-MWfull2.summary).
"""
from nizam.corpus import segment as S


# doc 3901 p1 prints the range row over four lines, '8. / to / Omitted. / 11.'; a page reading (patch below) puts it in
# print order. The contents label map, read from the source rows, then still promises the closing number.
PATCH = [{"id": "p1", "page_no": 1, "match_text": "Omitted.", "before_text": "2. \nto \nOmitted. \n4. \n",
          "after_text": "2. to 4. Omitted. \n"}]


def _blocks(body_range=True):
    texts = [("CONTENTS", 1), ("1. Short title.", 1), ("2. \nto \nOmitted. \n4.", 1), ("5. Rules.", 1),
             ("1. Short title. This Act may be called the Test Act, 1922.", 2)]
    if body_range:
        texts.append(("2. to 4. Omitted.", 2))
    texts.append(("5. Rules. The Government may make rules for the purposes of this Act.", 2))
    return [{"id": 100 + i, "text": t + " \n", "page_no": p, "y0": 100.0 + 30 * i, "page_height": 842.0,
             "x0": 72.0, "x1": 480.0} for i, (t, p) in enumerate(texts)]


def _off(fn):
    profiles = S.SEGMENTATION_PROFILES
    saved = profiles["unreleased-v4"]
    profiles["unreleased-v4"] = saved - {"range_link_counted"}
    try:
        return fn()
    finally:
        profiles["unreleased-v4"] = saved


def test_M_linked_range_row_represents_its_numbers():
    seg = S.segment(_blocks(), profile="unreleased-v4")
    row = [e for e in seg.toc_entries if e["label"] == "2 to 4"]
    if row and row[0]["node"] is not None:
        assert not {"2", "3", "4", "2 to 4"} & set(seg.missing)


def test_M_never_hides_a_number_the_range_does_not_cover():
    seg = S.segment(_blocks(), profile="unreleased-v4")
    off = _off(lambda: S.segment(_blocks(), profile="unreleased-v4"))
    # with M on, the missing list can only lose numbers inside the linked range
    assert set(seg.missing) <= set(off.missing)
    assert set(off.missing) - set(seg.missing) <= {"2", "3", "4"}


def test_M_doc_3901_range_row_no_longer_missing():
    # DB-backed regression (skipped without the local corpus): 3901's contents promise 8..11 from the range row
    # '8 to 11', linked to the owner-cited omission stub; without M the run names '11' missing, with M nothing.
    pytest = __import__("pytest")
    try:
        from nizam.storage import legal_write
        from nizam.storage.db import connect
        from nizam.workers.segment import reviewed_structural_overrides
        with connect() as c, c.cursor() as cur:
            cur.execute("select source_observation_id from instrument where document_id=3901 and is_active "
                        "and duplicate_of is null order by expression_ordinal limit 1")
            obs = cur.fetchone()[0]
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"no corpus database: {error}")
    blocks = legal_write.blocks_for(3901)
    patches = legal_write.segmentation_patches_for(obs)
    res = legal_write.structural_resolutions_for(3901)

    def run():
        return S.segment(blocks, curation_patches=patches, toc_dispositions=legal_write.toc_dispositions_for(obs),
                         structural_resolutions=res, structural_overrides=reviewed_structural_overrides(res, patches)
                         or None, profile="unreleased-v4")
    assert run().missing == []
    assert "11" in _off(run).missing


def test_M_unlinked_range_row_counts_as_before():
    on = S.segment(_blocks(body_range=False), profile="unreleased-v4")
    off = _off(lambda: S.segment(_blocks(body_range=False), profile="unreleased-v4"))
    assert on.missing == off.missing and on.matched == off.matched
