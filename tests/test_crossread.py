"""D-114 cross-read: two OCR readings of the same pages agree, or the disagreeing pages are named."""
from nizam.corpus.crossread import MIN_REFERENCE_CHARS, compare_pages

PAGE = ("1. Short title, extent and commencement.-(1) This Act may be called the Azad Jammu and Kashmir "
        "Test Act, 2025. (2) It extends to the whole of Azad Jammu and Kashmir. (3) It shall come into force at once.")


def test_identical_readings_agree():
    r = compare_pages([PAGE, PAGE], [PAGE, PAGE])
    assert r["verdict"] == "agree" and r["compared_pages"] == 2 and r["bigram_precision"] == 1.0


def test_ordinary_ocr_noise_still_agrees():
    noisy = PAGE.replace("Kashmir", "Kashmlr", 1).replace("(2)", "{2)").replace("—", "-")
    assert compare_pages([PAGE], [noisy])["verdict"] == "agree"


def test_a_dropped_paragraph_is_named_by_page():
    short = PAGE.split("(2)")[0]
    r = compare_pages([PAGE, short], [PAGE, PAGE])
    assert r["disagree"] == [2] and "pages disagree: 2" in r["verdict"]


def test_invented_text_fails_precision():
    r = compare_pages([PAGE + " Provided that the Government may exempt any person by notification."], [PAGE])
    assert r["disagree"] == [1] and r["pages"][0]["precision"] < 0.90


def test_interleaved_columns_fail_word_order():
    words = PAGE.split()
    shuffled = " ".join(words[::2] + words[1::2])
    r = compare_pages([shuffled], [PAGE])
    assert r["disagree"] == [] and "word order" in r["verdict"]


def test_a_page_the_second_reader_could_not_read_does_not_vote():
    r = compare_pages([PAGE, "Gazette stamp"], [PAGE, "x" * (MIN_REFERENCE_CHARS - 1)])
    assert r["verdict"] == "agree" and r["pages"][1]["compared"] is False
    assert compare_pages(["a"], [""])["verdict"] == "no page the second reader could read"


def test_page_count_mismatch_is_not_agreement():
    assert compare_pages([PAGE], [PAGE, PAGE])["verdict"] == "page count differs"


def test_urdu_is_compared_by_its_own_letters():
    ur = "یہ ایکٹ آزاد جموں و کشمیر ٹیسٹ ایکٹ ۲۰۲۵ کہلائے گا اور فوری طور پر نافذ ہوگا۔ " * 3
    assert compare_pages([ur], [ur])["verdict"] == "agree"
    assert compare_pages([ur[: len(ur) // 2]], [ur])["disagree"] == [1]
