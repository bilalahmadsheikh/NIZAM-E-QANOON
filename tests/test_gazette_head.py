"""Rule `gazette_running_head` (DECISION-LOG D-072): Gazette page furniture is not the law's text."""
from nizam.corpus.segment import gazette_furniture


def _b(i, text, page=1):
    return {"id": i, "page_no": page, "text": text}


def test_odd_and_even_page_heads_are_furniture():
    blocks = [_b(1, "PART I] THE GAZETTE OF PAKISTAN, EXTRA., JAN. 29, 2025 23 \n"),
              _b(2, "24 THE GAZETTE OF PAKISTAN, EXTRA., JAN. 29, 2025 [PART I\n", 2),
              _b(3, "Part I] THE GAZETTE OF PAKISTAN, EXTRA., OCT. 28, 1984 609”", 3),
              _b(4, "466 THE SINDH GOVERNMENT GAZETTE, JULY 7, 2021 [Part IV", 4)]
    out, furniture = gazette_furniture(blocks)
    assert furniture == {1, 2, 3, 4}
    assert [b["text"] for b in out] == [b["text"] for b in blocks]      # whole blocks are only flagged, not edited


def test_a_head_fused_onto_the_first_line_is_cut_from_the_copy_only():
    original = _b(5, "Part I] THE GAZETTE OF PAKISTAN, EXTRA, JAN. 28, 1997 63 \n(e) in section 209, in sub-section (5),—")
    out, furniture = gazette_furniture([original])
    assert furniture == set()
    assert out[0]["text"] == "(e) in section 209, in sub-section (5),—"
    assert original["text"].startswith("Part I]")                       # the extracted block is untouched


def test_a_head_broken_over_lines_is_furniture_but_never_takes_the_law_line_after_it():
    # the 26th and 27th Amendment Acts' Gazettes (na.gov.pk scans, 18 Nov 2026)
    blocks = [_b(13, "PART I]\nTHE GAZETTE OF PAKISTAN, EXTRA.,\nocToBER 21,2024 545\n", 5),
              _b(14, "PART I]\nTHE GAZETTE OF PAKISTAN, EXTRA,, NOV, 13, 2025 't89\n13. Amendment of Article 175A.—In the "
                     "Constitution, in Article 175A,", 7)]
    out, furniture = gazette_furniture(blocks)
    assert furniture == {13}
    assert out[1]["text"] == "13. Amendment of Article 175A.—In the Constitution, in Article 175A,"
    # the text layer's misreadings of THE and of the Part numeral
    _, furniture = gazette_furniture([_b(16, "PART Il\n]'IIE GAZETTE OF PAKISTAN, EXTRA., NOV. 13, 2025 183\n", 9)])
    assert furniture == {16}
    # a one-line head followed by law text: only the head line goes, even when the law line is short
    out, _ = gazette_furniture([_b(15, "PART I] THE GAZETTE OF PAKISTAN, EXTRA., JAN. 28, 1997 63\n(b) omitted;")])
    assert out[0]["text"] == "(b) omitted;"


def test_the_issue_part_heading_is_furniture_only_over_its_part_title():
    blocks = [_b(6, "PART I \n"), _b(7, "Acts, Ordinances, President’s Orders and Regulations \n"),
              _b(8, "SENATE SECRETARIAT")]
    _, furniture = gazette_furniture(blocks)
    assert furniture == {6, 7}
    # a law's own Part heading is law text
    _, furniture = gazette_furniture([_b(9, "PART I"), _b(10, "PRELIMINARY")])
    assert furniture == set()


def test_law_text_naming_the_gazette_is_not_a_head():
    blocks = [_b(11, "(2) It shall be published in the official Gazette."),
              _b(12, "5. Notification in the Gazette of Pakistan.—The Federal Government may, by notification")]
    out, furniture = gazette_furniture(blocks)
    assert furniture == set() and out == blocks
