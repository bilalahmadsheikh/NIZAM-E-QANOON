from nizam.workers.verify_text_quality import score


def test_statutory_prose_is_plausible():
    text = ("The Government may by notification make rules under this Act and "
            "the provisions shall apply to any person prescribed by the court. ") * 10
    assert not score(text)["problems"]


def test_printable_gibberish_is_flagged():
    text = ("xqz vrrt plmk zzzq brqx nnnv klpz wrqx mzzq trrk ") * 20
    assert "legal/function-word rate" in score(text)["problems"][0]


def test_table_heavy_law_uses_multiple_narrative_pages_as_corroboration():
    legal_page = ("The Government may by notification make rules under this Act and "
                  "the provisions shall apply to any person. ") * 12
    schedule = ("Khairpur Sukkur Rohri Kharif Rabi acre canal district 1975 1983 ") * 500
    result = score(legal_page * 3 + schedule,
                   [legal_page, legal_page, legal_page, schedule, schedule])
    assert result["legal_rate"] < 0.15
    assert result["narrative_page_floor"] >= 0.15
    assert not result["problems"]


def test_one_clean_cover_cannot_mask_garbled_body_pages():
    legal_page = ("The Government may by notification make rules under this Act and "
                  "the provisions shall apply to any person. ") * 12
    gibberish = ("xqz vrrt plmk zzzq brqx nnnv klpz wrqx mzzq trrk ") * 20
    result = score(legal_page + gibberish * 8,
                   [legal_page, gibberish, gibberish, gibberish, gibberish,
                    gibberish, gibberish, gibberish, gibberish])
    assert result["problems"]


def test_urdu_is_not_scored_with_an_english_lexicon():
    text = "قانون کے تحت حکومت قواعد بنا سکتی ہے۔ " * 40
    assert not score(text)["problems"]


def test_replacement_glyph_is_always_reported():
    assert score("قانون \ufffd")["replacement_glyphs"] == 1
    assert score("قانون \ufffd")["problems"]
