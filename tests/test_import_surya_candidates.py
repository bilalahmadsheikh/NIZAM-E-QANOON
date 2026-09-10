from nizam.workers.import_surya_candidates import (
    _scaled_blocks,
    html_to_text,
    parse_result_name,
)


def test_html_to_text_preserves_paragraph_and_table_boundaries():
    assert html_to_text("<p>Section 1</p><table><tr><td>A</td><td>B</td></tr></table>") == (
        "Section 1\nA\tB"
    )


def test_rendered_single_page_name_maps_back_to_source_page():
    assert parse_result_name("567-page5", 1) == (567, 5)
    assert parse_result_name("4503", 2) == (4503, 2)


def test_surya_geometry_scales_to_pdf_points_and_keeps_raw_evidence():
    raw = [{"bbox": [100, 200, 300, 400], "reading_order": 0,
            "confidence": 0.9, "label": "Text", "raw_label": "Text",
            "html": "<p>قانون پاکستان</p>"}]
    blocks, text, confidence, words = _scaled_blocks(
        raw, [0, 0, 1200, 1600], 600, 800,
    )
    assert blocks[0]["bbox"] == [50.0, 100.0, 150.0, 200.0]
    assert blocks[0]["script"] == "arabic"
    assert blocks[0]["html"] == "<p>قانون پاکستان</p>"
    assert text == "قانون پاکستان"
    assert confidence == 0.9
    assert words == 2
