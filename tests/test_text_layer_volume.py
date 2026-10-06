"""The text-layer volume measure, on the shape that defeated emptiness.

Document 4573, the Sindh Essential Commodities Price Control and Prevention of
Profiteering and Hoarding Act, 2005, is the worked example: a scan whose PDF
text layer carried nothing but the scanner's "CamScanner" stamp. Counting
characters said the document was full. Counting what can be READ says it was
empty, and that is the measure here.
"""
from nizam.workers.verify_ocr import MIN_WORDS_PER_PAGE
from tools.audit_text_layer_volume import (
    FURNITURE_MAX_WORDS,
    Measurement,
    find_furniture,
    signature,
    substantive_words,
)

HEADER = "SINDH ACT NO.IX OF 2006"
TITLE = ("THE SINDH ESSENTIAL COMMODITIES PRICE CONTROL AND PREVENTION OF "
         "PROFITEERING AND HOARDING ACT, 2005")
PROVISION = (
    "5A. (1) When any authorized officer has reason to believe that any "
    "person has contravened any provision of this Act or of any order made "
    "thereunder, he may enter and search any premises and seize any essential "
    "commodity in respect of which he suspects the contravention.")


def _blocks(pages, *, per_page):
    """(page_no, head, words) for a document of `pages` identical-ish pages."""
    blocks = []
    for page_no in range(1, pages + 1):
        for head, words in per_page(page_no):
            blocks.append((page_no, head, words))
    return blocks


def test_a_page_number_does_not_make_a_header_unique():
    assert signature("Page 3 of 35") == signature("Page 27 of 35")
    assert signature("SINDH ACT NO.IX OF 2006") == signature(
        "SINDH  ACT  NO.IX  OF  2011")


def test_the_scanner_stamp_is_furniture_and_leaves_nothing_behind():
    # What document 4573's PDF text layer actually held, before OCR.
    blocks = _blocks(15, per_page=lambda page: [("CamScanner", 1)])
    furniture = find_furniture(blocks, 15)
    assert signature("CamScanner") in furniture
    per_page = substantive_words(blocks, furniture)
    assert set(per_page.values()) == {0}


def test_a_running_header_is_subtracted_but_the_law_is_not():
    blocks = _blocks(
        15,
        per_page=lambda page: [(HEADER, 5), (TITLE, 16),
                               (f"Page {page} of 15", 4),
                               (PROVISION, 60)])
    furniture = find_furniture(blocks, 15)
    assert signature(HEADER) in furniture
    assert signature(TITLE) in furniture
    per_page = substantive_words(blocks, furniture)
    assert set(per_page.values()) == {60}


def test_a_long_repeated_block_is_never_treated_as_furniture():
    # A recurring schedule form is real text. Subtracting it would hide law.
    long_block = ("FORM A -- application for a licence under these rules, "
                  "to be submitted in duplicate to the licensing authority "
                  "together with the prescribed fee and two photographs")
    blocks = _blocks(8, per_page=lambda page: [(long_block, 60)])
    furniture = find_furniture(blocks, 8)
    assert signature(long_block) not in furniture
    assert set(substantive_words(blocks, furniture).values()) == {60}
    assert 60 > FURNITURE_MAX_WORDS


def test_a_two_page_document_has_no_furniture_to_speak_of():
    blocks = _blocks(2, per_page=lambda page: [(HEADER, 5), (PROVISION, 60)])
    assert find_furniture(blocks, 2) == set()


def test_a_stamped_scan_fails_and_its_ocr_passes():
    stamped = Measurement(
        document_id=4573, page_count=15, lane="E2", char_count=165,
        blocks=_blocks(15, per_page=lambda page: [("CamScanner", 1)]))
    assert stamped.usable_pages == 0
    assert stamped.fails

    recovered = Measurement(
        document_id=4573, page_count=15, lane="E4", char_count=24700,
        blocks=_blocks(15, per_page=lambda page: [(HEADER, 5),
                                                  (PROVISION, 60)]))
    assert recovered.usable_pages == 15
    assert not recovered.fails


def test_the_floor_is_the_one_already_accepted_for_an_ocr_page():
    just_under = Measurement(
        document_id=1, page_count=3, lane="E2", char_count=400,
        blocks=_blocks(3, per_page=lambda page: [
            (f"body {page}", MIN_WORDS_PER_PAGE - 1)]))
    assert just_under.fails

    just_over = Measurement(
        document_id=2, page_count=3, lane="E2", char_count=400,
        blocks=_blocks(3, per_page=lambda page: [
            (f"body {page}", MIN_WORDS_PER_PAGE)]))
    assert not just_over.fails


def test_a_repeal_notice_is_one_line_and_fails_honestly():
    # Documents 2044 and 2046: the federal portal serves a single page reading
    # "THIS LAW HAS BEEN REPEALED" for 21 and 26 catalogued Acts respectively.
    # The capture is faithful; there is simply no law in it to read.
    notice = Measurement(
        document_id=2044, page_count=1, lane="E2", char_count=28,
        blocks=[(1, "THIS LAW HAS BEEN REPEALED", 5)])
    assert notice.fails
    assert notice.substantive_total == 5
