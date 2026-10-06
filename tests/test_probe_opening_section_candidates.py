from tools.probe_opening_section_candidates import page_is_contents


def test_contents_page_cannot_become_operative_section() -> None:
    blocks = [
        {"page_no": 1, "text": "THE ACT\nCONTENTS\nSECTIONS:"},
        {"page_no": 1, "text": "l.  \nShort title, extent and commencement."},
        {"page_no": 3, "text": "CHAPTER-I\nPreliminary."},
        {"page_no": 3, "text": " \nShort title, extent and commencement."},
    ]
    assert page_is_contents(blocks, 1)
    assert not page_is_contents(blocks, 3)
