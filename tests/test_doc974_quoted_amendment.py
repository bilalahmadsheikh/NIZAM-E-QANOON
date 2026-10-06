"""Source-backed regression: a quoted replacement section is not a sibling."""

from nizam.corpus.segment import segment


def test_doc974_quoted_section_3_stays_under_amending_section_3():
    # Official PDF p.2, source blocks 45846 and 45847. The first 3 is this
    # Ordinance's section; the indented second 3 is the substituted text.
    blocks = [
        {"id": 45846, "page_no": 2, "text":
         "3. In the said Act, for section 3, the following shall be substituted: -",
         "x0": 75.024, "x1": 406.384, "y0": 230.978,
         "page_height": 800.0},
        {"id": 45847, "page_no": 2, "text":
         "3. “Levy of tax” (1) No tax shall be charged from the owners having a total holding of twelve acres or less in the barrage areas and twenty four acres or less in the non-barrage areas:",
         "x0": 75.024, "x1": 408.784, "y0": 278.858,
         "page_height": 800.0},
    ]
    parsed = segment(blocks, structural_overrides={
        "source_reparent_blocks": [{
            "source_block_id": 45847,
            "parent_block_id": 45846,
            "kind": "clause",
            "source_label": "3",
            "source_kind": "clause",
        }],
    })
    outer = next(node for node in parsed.flatten() if node.first_block == 45846)
    replacement = next(node for node in parsed.flatten() if node.first_block == 45847)
    assert outer.kind == "section" and outer.label == "3"
    assert replacement.kind == "clause" and replacement.label == "3"
    assert replacement.parent is outer
    assert "No tax shall be charged" in replacement.text
    assert all(row.get("settled_by_review") == "reparent"
               for row in parsed.repeated_label_decisions)
