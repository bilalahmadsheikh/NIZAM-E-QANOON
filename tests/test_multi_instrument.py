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
    assert infer_year(
        "Income Tax Ordinance, 2001 (Same as official website dated 31-07-2025)",
        "2001", "",
    ) == 2001


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
        expression_ordinal=2, expression_role="embedded", profile="default")
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


# --------------------------------------------------- reviewed expression plans
import copy

import pytest

from tools import materialize_multi_instrument as materializer


def _plan_blocks(first=101, count=12):
    return [{"id": first + i, "page_no": 1 + i // 4, "text": f"block {first + i} text"}
            for i in range(count)]


def _plan(**changes):
    plan = {
        "schema": materializer.PLAN_SCHEMA, "document_id": 7, "source_observation_id": 70,
        "review_basis": "source_verified",
        "expressions": [
            {"ordinal": 0, "role": "primary", "title": "Example Rules, 1996",
             "kind": "rules", "year": 1996, "number": None,
             "spans": [{"start_block_id": 105, "end_block_id": 108}],
             "title_correction": {"from_title": "EXAMPLE RULES 1981", "from_year": 1981,
                                  "to_year": 1996, "basis": "p2 prints 1996"}},
            {"ordinal": 1, "role": "embedded", "title": "Notification dated 2003",
             "kind": "notification", "year": 2003, "number": "N-1",
             "spans": [{"start_block_id": 101, "end_block_id": 104},
                       {"start_block_id": 111, "end_block_id": 112}],
             "relations": [{"type": "amends", "target_ordinal": 0,
                            "effect": "substitutes the Schedule",
                            "source_block_id": 102, "basis": "p1 prints it"}]},
            {"ordinal": 2, "role": "embedded", "title": "Order dated 1998",
             "kind": "order", "year": 1998, "number": "O-1",
             "spans": [{"start_block_id": 109, "end_block_id": 110}]},
        ],
    }
    plan.update(changes)
    return plan


def test_plan_resolves_primary_that_does_not_start_the_document():
    specs = materializer.validate_plan(_plan(), _plan_blocks(), 7, 70)
    assert [s["ordinal"] for s in specs] == [0, 1, 2]
    assert specs[0]["role"] == "primary" and specs[0]["ranges"] == [(4, 7)]
    assert specs[1]["ranges"] == [(0, 3), (10, 11)]
    assert specs[0]["title_correction"]["to_year"] == 1996
    assert specs[1]["relations"][0]["type"] == "amends"


@pytest.mark.parametrize("mutate, message", [
    (lambda p: p["expressions"][2]["spans"].__setitem__(
        0, {"start_block_id": 108, "end_block_id": 110}), "is in expressions"),
    (lambda p: p["expressions"][1]["spans"].reverse(), "out of reading order"),
    (lambda p: p["expressions"][2].__setitem__("kind", "circular"), "instrument_kind"),
    (lambda p: p["expressions"][2]["spans"].__setitem__(
        0, {"start_block_id": 999, "end_block_id": 110}), "outside document"),
    (lambda p: p["expressions"][2].__setitem__("role", "primary"), "at most one primary"),
    (lambda p: p["expressions"][0]["title_correction"].__setitem__("to_year", 1981),
     "title_correction"),
    (lambda p: p["expressions"][1]["relations"][0].__setitem__("target_ordinal", 1),
     "unknown or self"),
    (lambda p: p["expressions"][1]["relations"][0].__setitem__("type", "repeals"),
     "is not one of"),
    (lambda p: p["expressions"][1]["relations"][0].__setitem__("source_block_id", 106),
     "not inside its own span"),
    (lambda p: p["expressions"][2].pop("number"), "must state number"),
    (lambda p: p.__setitem__("source_observation_id", 71), "observation"),
])
def test_plan_refuses_what_it_does_not_state_exactly(mutate, message):
    plan = copy.deepcopy(_plan())
    mutate(plan)
    with pytest.raises(ValueError, match=message):
        materializer.validate_plan(plan, _plan_blocks(), 7, 70)


def _patch(pid, page, match, before, after, apparatus=None):
    evidence = ({"structural_overrides": {"source_apparatus_blocks": apparatus}}
                if apparatus else {})
    return {"id": pid, "page_no": page, "match_text": match, "before_text": before,
            "after_text": after, "evidence": evidence}


def test_patches_go_only_to_the_expression_whose_span_they_read():
    blocks = _plan_blocks()
    owner = {b["id"]: (0 if b["id"] <= 104 else 1) for b in blocks if b["id"] <= 108}
    patches = [_patch("a", 1, "block 102 text", "102", "102x", apparatus=[103]),
               _patch("b", 2, "block 106 text", "106", "106y"),
               _patch("c", 3, "block 110 text", "110", "110z")]       # apparatus
    assigned, outside = materializer.assign_patches(blocks, patches, owner)
    assert [p["id"] for p in assigned[0]] == ["a"]
    assert [p["id"] for p in assigned[1]] == ["b"]
    assert [p["id"] for p in outside] == ["c"]
    assert blocks[1]["text"] == "block 102 text"      # source blocks untouched


def test_patch_assignment_still_fails_closed():
    blocks = _plan_blocks()
    owner = {b["id"]: 0 for b in blocks}
    with pytest.raises(ValueError, match="matched 0 blocks"):
        materializer.assign_patches(blocks, [_patch("x", 1, "not printed", "a", "b")], owner)
    owner = {b["id"]: (0 if b["id"] <= 104 else 1) for b in blocks}
    reach = _patch("y", 1, "block 102 text", "102", "102x", apparatus=[106])
    with pytest.raises(ValueError, match="structural overrides name"):
        materializer.assign_patches(blocks, [reach], owner)


def test_patch_assignment_follows_earlier_rewrites_in_order():
    blocks = _plan_blocks()
    owner = {b["id"]: 0 for b in blocks}
    first = _patch("1", 1, "block 101 text", "101", "unique-marker")
    second = _patch("2", 1, "unique-marker", "unique-marker", "done")
    assigned, _ = materializer.assign_patches(blocks, [first, second], owner)
    assert [p["id"] for p in assigned[0]] == ["1", "2"]


def test_unrecorded_readings_carry_structural_overrides_and_skip_recorded():
    stored = [{"page_no": 1, "match_text": "m1", "before_text": "b1"}]
    readings = [
        {"document_id": 7, "page_no": 1, "match_text": "m1", "before_text": "b1",
         "after_text": "a1"},
        {"document_id": 7, "page_no": 2, "match_text": "m2", "before_text": "b2",
         "after_text": "a2", "source_apparatus_blocks": [5, 6], "observed": "x"},
    ]
    shaped = materializer.unrecorded_readings(readings, stored, 7)
    assert len(shaped) == 1
    assert shaped[0]["evidence"] == {"structural_overrides": {"source_apparatus_blocks": [5, 6]}}
    with pytest.raises(ValueError, match="document 7"):
        materializer.unrecorded_readings(readings, [], 8)


def _boundary(block, resolution, on_active=False):
    return {"candidate_id": f"c{block}", "start_block_id": block, "resolution": resolution,
            "on_active": on_active, "detector": "review"}


def test_boundaries_must_agree_with_the_plan():
    blocks = _plan_blocks()
    specs = materializer.validate_plan(_plan(), blocks, 7, 70)
    found = materializer.plan_boundaries(
        specs, blocks, [_boundary(105, "confirmed_split"), _boundary(109, "confirmed_split"),
                        _boundary(111, "confirmed_split"), _boundary(107, "not_boundary")])
    assert found[0]["candidate_id"] == "c105" and found[2]["candidate_id"] == "c109"
    assert found[1] is None                      # 111 is a second-span start, not an anchor
    with pytest.raises(ValueError, match="not a span start"):
        materializer.plan_boundaries(specs, blocks, [_boundary(107, "confirmed_split")])
    with pytest.raises(ValueError, match="not a span start"):
        materializer.plan_boundaries(specs, blocks, [_boundary(107, None, on_active=True)])
    with pytest.raises(ValueError, match="adjudicated not_boundary"):
        materializer.plan_boundaries(specs, blocks, [_boundary(109, "not_boundary")])


def test_reviewed_identity_overrides_title_inference_and_path():
    blocks = [{"id": 9101, "page_no": 1, "text": "1. These rules may be called the X Rules.",
               "y0": 10.0, "page_height": 792.0, "x0": 10.0, "x1": 500.0}]
    title = "Notification dated 27-06-2003 (amending the X Rules, 1996)"
    inferred, _ = build(268, "a" * 64, 2767, "pk-punjab", title, "2003",
                        None, blocks, "2026-10-06", expression_ordinal=1,
                        expression_role="embedded", profile="default")
    assert (inferred.kind, inferred.year) == ("rules", 1996)
    inst, _ = build(268, "a" * 64, 2767, "pk-punjab", title, "2003",
                    None, blocks, "2026-10-06", expression_ordinal=1,
                    expression_role="embedded", profile="default",
                    reviewed_identity={"kind": "notification", "year": 2003,
                                       "number": "SOR-III-1-10/95"})
    assert (inst.kind, inst.year, inst.number) == ("notification", 2003, "SOR-III-1-10/95")
    assert inst.short_title == title
    assert inst.provisions
    assert all(row["path"].startswith("punjab.notification.y2003_SORIII11095_o2767_e1.")
               for row in inst.provisions)


def test_document_268_plan_partitions_its_blocks():
    plan = materializer.load_plan(268)
    assert plan is not None and 268 in materializer.REVIEWED_DOCUMENTS
    assert 268 not in materializer.PRIMARY_DOCUMENTS | materializer.COMPILATION_DOCUMENTS
    blocks = [{"id": i, "page_no": 1, "text": ""} for i in range(11925, 12049)]
    specs = materializer.validate_plan(plan, blocks, 268, 2767)
    covered = sorted(i for s in specs for a, b in s["ranges"] for i in range(a, b + 1))
    assert covered == list(range(124))
    assert [(s["role"], s["kind"], s["year"]) for s in specs] == [
        ("primary", "rules", 1996), ("embedded", "notification", 2003),
        ("embedded", "order", 1998)]
    assert specs[1]["relations"][0]["target_ordinal"] == 0
    assert specs[0]["title_correction"]["from_year"] == 1981
