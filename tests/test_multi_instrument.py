from tools.detect_multi_instrument import detect
from nizam.workers.segment import build, infer_kind


def _blocks(*texts):
    return [
        {"id": i + 1, "page_no": 1 if i < 8 else 4 + i // 4,
         "reading_order": i, "text": text, "citable_start": i < 8}
        for i, text in enumerate(texts)
    ]


def test_detects_internal_act_with_independent_legal_form_evidence():
    blocks = _blocks(
        *(["Earlier compilation material."] * 8),
        "THE PUNJAB SERVICE TRIBUNALS ACT, 1974",
        "ACT IX OF 1974",
        "Whereas it is expedient to provide for Service Tribunals;",
        "It is hereby enacted as follows:-",
        "1. Short title, extent and commencement.- This Act may be called...",
    )
    found = detect(blocks, "ESTACODE COMPILATION")
    assert len(found) == 1
    assert found[0].year == 1974
    assert found[0].number == "IX"
    assert found[0].confidence >= 0.85


def test_rejects_amendment_footnote_and_bare_citation():
    blocks = _blocks(
        *(["Earlier body."] * 8),
        "Section 3 of the Punjab Civil Servants Act, 1974",
        "Inserted by the Finance Act, 2006",
        "1. Short title.- quoted words",
    )
    assert detect(blocks) == []


def test_repeated_running_header_needs_formula_and_reset():
    blocks = _blocks(
        *(["Earlier body."] * 8),
        "THE CUSTOMS ACT, 1969", "ordinary continuation",
        "THE CUSTOMS ACT, 1969", "ordinary continuation",
        "THE CUSTOMS ACT, 1969", "ordinary continuation",
    )
    assert detect(blocks) == []


def test_detects_enactment_and_self_naming_section_one_in_same_block():
    blocks = _blocks(
        *(["Earlier Finance Act provision."] * 8),
        "A\nBill",
        "to impose a provincial excise duty on un-manufactured tobacco produced",
        "WHEREAS it is expedient to impose a provincial excise duty on tobacco;",
        "It is hereby enacted by the Provincial Assembly as follows:\n\n"
        "1.\nShort title, extent and commencement.---(1) This Act may be called "
        "the Provincial\nExcise Duty (Un-manufactured Tobacco) Act, 2024.",
    )
    found = detect(blocks, "THE KHYBER PAKHTUNKHWA FINANCE ACT, 2024")
    assert len(found) == 1
    assert found[0].title == "Provincial Excise Duty (Un-manufactured Tobacco) Act, 2024"
    assert "section_one_self_names_instrument" in found[0].evidence["rules"]


def test_detects_split_short_title_and_self_name_blocks():
    blocks = _blocks(
        *(["Earlier compilation material."] * 8),
        "WHEREAS it is expedient to establish a commission;",
        "NOW, THEREFORE, in exercise of all powers enabling him in that behalf:",
        "PRELIMINARY",
        "1. Short title and commencement.—",
        "(1) This Ordinance may be called the Federal Public Service Commission\n"
        "Ordinance, 1977.",
    )
    found = detect(blocks, "ESTACODE")
    assert len(found) == 1
    assert found[0].title == "Federal Public Service Commission Ordinance, 1977"


def test_detects_self_naming_constitutional_order():
    blocks = _blocks(
        *(["Earlier constitutional text."] * 8),
        "In exercise of all powers enabling him in that behalf, the President "
        "is pleased to make the following Order:",
        "1. Short title and commencement.— (1) This Order may be called the "
        "Constitution (Second Amendment) Order, 1979.",
    )
    found = detect(blocks, "CONSTITUTION OF PAKISTAN")
    assert len(found) == 1
    assert found[0].kind == "order"


def test_instrument_kind_uses_terminal_legal_form():
    assert infer_kind("Constitution (Eighteenth Amendment) Act, 2010") == "act"
    assert infer_kind("Constitution (Second Amendment) Order, 1979") == "order"
    assert infer_kind("Civil Servants (Appeal) Rules, 1977") == "rules"
    assert infer_kind("CONSTITUTION OF PAKISTAN") == "constitution"


def test_instrument_year_uses_terminal_legal_form_year():
    from nizam.workers.segment import infer_year
    assert infer_year("Revival of the Constitution of 1973 Order, 1985",None,"") == 1985


def test_expression_ordinal_makes_paths_distinct_and_retains_source_span():
    blocks = [
        {"id": 9001, "page_no": 12, "text": "1. Short title.—This Act may be called the Example Act, 2024.",
         "y0": 10.0, "page_height": 792.0, "x0": 10.0, "x1": 500.0},
        {"id": 9002, "page_no": 12, "text": "2. Definitions.—In this Act, example means example.",
         "y0": 30.0, "page_height": 792.0, "x0": 10.0, "x1": 500.0},
    ]
    inst, _ = build(
        99, "a" * 64, 77, "pk-federal", "Example Act, 2024", "2024",
        "https://example.invalid/official.pdf", blocks, "2026-09-09",
        expression_ordinal=2, expression_role="embedded")
    assert inst.expression_ordinal == 2
    assert inst.expression_role == "embedded"
    assert inst.source_start_block_id == 9001
    assert inst.source_end_block_id == 9002
    assert all("o77_e2" in row["path"] for row in inst.provisions)


def test_compilation_can_open_with_embedded_instrument_before_outer_body_guess():
    blocks = [
        {"id": 1, "page_no": 1, "reading_order": 0, "text": "CONTENTS", "citable_start": False},
        {"id": 2, "page_no": 2, "reading_order": 1,
         "text": "In exercise of the powers conferred by section 13, Government is pleased to make the following rules:",
         "citable_start": False},
        {"id": 3, "page_no": 2, "reading_order": 2,
         "text": "1. Short title and commencement.—", "citable_start": False},
        {"id": 4, "page_no": 2, "reading_order": 3,
         "text": "These rules may be called the Example Conduct Rules, 2005.",
         "citable_start": False},
    ]
    found = detect(blocks, "EXAMPLE RULES & REGULATIONS", body_starts_page=10)
    assert [p.title for p in found] == ["Example Conduct Rules, 2005"]


def test_does_not_split_outer_instrument_opening_on_page_two():
    blocks = [
        {"id": 1, "page_no": 1, "reading_order": 0,
         "text": "THE EXAMPLE (AMENDMENT) ACT, 2018", "citable_start": True},
        {"id": 2, "page_no": 1, "reading_order": 1,
         "text": "Earlier publication metadata", "citable_start": True},
        {"id": 3, "page_no": 2, "reading_order": 2,
         "text": "The Example Act, 2014, in the manner hereinafter appearing", "citable_start": False},
        {"id": 4, "page_no": 2, "reading_order": 3,
         "text": "Whereas it is expedient to amend the Example Act, 2014", "citable_start": False},
        {"id": 5, "page_no": 2, "reading_order": 4,
         "text": "It is hereby enacted as follows", "citable_start": False},
        {"id": 6, "page_no": 2, "reading_order": 5,
         "text": "1. Short title.—This Act may be called the Example (Amendment) Act, 2018.",
         "citable_start": False},
    ]
    assert detect(blocks,"THE EXAMPLE (AMENDMENT) ACT, 2018") == []


def test_detects_cited_as_rules_and_compilation_omitted_formula():
    cited = _blocks(
        *( ["Earlier compilation material."] * 8),
        "1.2 Civil Service of Pakistan (Composition and Cadre) Rules, 1954",
        "NOW, THEREFORE, in exercise of the powers conferred, the President is pleased to make the following Rules:",
        "1. These Rules may be cited as the Civil Service of Pakistan (Composition and Cadre) Rules, 1954.",
        "2. In these Rules, unless the context otherwise requires:",
    )
    assert [p.title for p in detect(cited,"ESTACODE")] == [
        "Civil Service of Pakistan (Composition and Cadre) Rules, 1954"]

    omitted = _blocks(
        *( ["Earlier compilation material."] * 8),
        "22.3 Civil Servants (Service in International Organizations) Rules,2016",
        "1. Short title.—These rules may be called the Civil Servants (Service in International Organizations) Rules, 2016.",
        "2. Definitions.—In these rules, unless the context otherwise requires—",
    )
    found = detect(omitted,"ESTACODE")
    assert len(found) == 1
    assert "compilation_title_self_name_and_rule_two_sequence" in found[0].evidence["rules"]


def test_outer_title_ocr_spelling_variants_are_not_split():
    blocks = _blocks(
        *( ["Earlier opening material."] * 8),
        "It is hereby enacted as follows:",
        "1. Short title.—This Act may be called the Nawab Shaheed Ghous Bakksh Raisani Hospital Act, 2012.",
    )
    assert detect(blocks,"Nawab Shaeed Ghous Bakhsh Raisani Memorial Hospital Act 2012") == []
