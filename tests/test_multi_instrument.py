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
import json

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


def test_plan_source_anomalies_are_validated():
    # lead decision 8 Oct (doc 1106): printed oddities kept as printed reach the manifest
    plan = copy.deepcopy(_plan())
    anomaly = {"page": 2, "source_block_id": 106, "printed": "LORICULTURE", "note": "sic, kept as printed"}
    plan["expressions"][0]["source_anomalies"] = [anomaly]
    specs = materializer.validate_plan(plan, _plan_blocks(), 7, 70)
    assert specs[0]["source_anomalies"] == [anomaly] and specs[1]["source_anomalies"] == []
    for bad in (dict(anomaly, source_block_id=102),          # in another expression's span
                dict(anomaly, printed=" "), {k: v for k, v in anomaly.items() if k != "note"}):
        plan["expressions"][0]["source_anomalies"] = [bad]
        with pytest.raises(ValueError, match="source anomaly"):
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


# -- Undated expressions (migration 0063; doc 1973 q3 'undated', export -i) ------------------------------------------

def _undated_export(tmp_path, choice="undated", document_id=7):
    export = tmp_path / "decision-review-undated.json"
    export.write_text(json.dumps({"answers": [
        {"document_id": document_id, "question_id": "q3", "choice": choice},
        {"document_id": document_id, "question_id": "q4", "choice": "number-1"}]}), encoding="utf-8")
    return str(export)


def _undated_plan(tmp_path, **changes):
    plan = copy.deepcopy(_plan())
    value = plan["expressions"][2]
    value.update({"year": None, "year_status": "undated",
                  "owner_decision": {"export": _undated_export(tmp_path), "document_id": 7,
                                     "question_id": "q3"}})
    value.update(changes)
    return plan


def test_reviewed_identity_without_a_year_infers_none_and_reads_yundated():
    # Doc 1973 E4's title names 'the Opium Act, 1878' and its text '1956': neither is the notification's year.
    blocks = [{"id": 9201, "page_no": 8, "text": "1. In exercise of the power conferred by section 5 of the Opium Act "
               "1878 read with rule 2 (g) of the Rules published with notification dated the 23rd November 1956.",
               "y0": 10.0, "page_height": 792.0, "x0": 10.0, "x1": 500.0}]
    title = "West Pakistan notification under section 5 of the Opium Act, 1878"
    inst, _ = build(1973, "a" * 64, 2341, "pk-punjab", title, None, None, blocks, "2026-10-10",
                    expression_ordinal=4, expression_role="embedded", profile="default",
                    reviewed_identity={"kind": "notification", "year": None, "number": None})
    assert (inst.kind, inst.year, inst.number) == ("notification", None, None)
    assert inst.provisions
    assert all(row["path"].startswith("punjab.notification.yundated_o2341_e4.") for row in inst.provisions)
    # the same title without a reviewed identity infers 1878: why the identity is taken whole
    inferred, _ = build(1973, "a" * 64, 2341, "pk-punjab", title, None, None, blocks, "2026-10-10",
                        expression_ordinal=4, expression_role="embedded", profile="default")
    assert inferred.year == 1878


def test_plan_admits_no_year_only_on_the_owners_undated(tmp_path):
    specs = materializer.validate_plan(_undated_plan(tmp_path), _plan_blocks(), 7, 70)
    assert specs[2]["year"] is None
    assert specs[2]["year_owner_decision"] == {
        "export": _undated_export(tmp_path), "document_id": 7, "question_id": "q3", "choice": "undated"}
    assert specs[0]["year_owner_decision"] is None and specs[1]["year_owner_decision"] is None


@pytest.mark.parametrize("changes, message", [
    ({"year_status": None}, "year_status 'undated'"),
    ({"year_status": "unknown"}, "year_status 'undated'"),
    ({"owner_decision": None}, "owner_decision must name"),
    ({"owner_decision": {"export": "missing.json", "document_id": 7, "question_id": "q3"}}, "does not exist"),
    ({"owner_decision": {"export": "E", "document_id": 8, "question_id": "q3"}}, "cites document 8"),
    ({"owner_decision": {"export": "E", "document_id": 7, "question_id": "q4"}},
     r"choice 'number-1', not one of \['undated'\]"),
    ({"owner_decision": {"export": "E", "document_id": 7, "question_id": "q9"}}, "holds 0 answers"),
    ({"title_correction": {"from_title": "ORDER", "to_year": None, "basis": "p2"}}, "title_correction"),
])
def test_plan_refuses_an_undated_expression_without_the_owners_undated(tmp_path, changes, message):
    export = _undated_export(tmp_path)
    changes = {k: (dict(v, export=export) if isinstance(v, dict) and v.get("export") == "E" else v)
               for k, v in changes.items()}
    plan = _undated_plan(tmp_path, **changes)
    with pytest.raises(ValueError, match=message):
        materializer.validate_plan(plan, _plan_blocks(), 7, 70)


def test_plan_refuses_year_status_on_a_dated_expression():
    plan = copy.deepcopy(_plan())
    plan["expressions"][2]["year_status"] = "undated"
    with pytest.raises(ValueError, match="year_status is only for an undated"):
        materializer.validate_plan(plan, _plan_blocks(), 7, 70)


def _stub_storage(monkeypatch, blocks, outer):
    monkeypatch.setattr(materializer.legal_write, "blocks_for", lambda _d: blocks)
    monkeypatch.setattr(materializer.legal_write, "segmentation_patches_for", lambda _o: [])
    monkeypatch.setattr(materializer.legal_write, "structural_resolutions_for", lambda _d: [])
    monkeypatch.setattr(materializer.legal_write, "observed_on", lambda _o: "2026-10-10")
    monkeypatch.setattr(materializer.legal_write, "toc_dispositions_for", lambda _o, _n: [])
    monkeypatch.setattr(materializer, "_outer", lambda _d, _o: outer)
    # migration 0064: no active manifest of the stub observation declares a historical window
    monkeypatch.setattr(materializer, "active_historical_manifests", lambda _o: {})


def _laid(i, page, text):
    return {"id": i, "page_no": page, "text": text, "y0": 10.0 + i % 50, "page_height": 792.0,
            "x0": 10.0, "x1": 500.0}


def test_the_manifest_of_an_undated_expression_carries_the_owners_undated(tmp_path, monkeypatch):
    blocks = [_laid(101 + i, 1 + i // 4, f"{i + 1}. Rule {i + 1} of these rules applies to the Collector.")
              for i in range(12)]
    outer = {"source_observation_id": 70, "sha256": "a" * 64, "source_id": "pk-punjab", "source_url": None}
    _stub_storage(monkeypatch, blocks, outer)
    monkeypatch.setattr(materializer, "_boundary_rows", lambda _o: [])
    monkeypatch.setattr(materializer, "plan_boundaries", lambda specs, _b, _r: {s["ordinal"]: None for s in specs})
    plan = _undated_plan(tmp_path)
    plan["expressions"][0].pop("title_correction")
    insts, _segs, manifests, _ = materializer.prepare_from_plan(7, plan, profile="default", allow_empty=True)
    assert [i.year for i in insts] == [1996, 2003, None]
    assert all(r["path"].startswith("punjab.order.yundated_O1_o70_e2.") for r in insts[2].provisions)
    assert manifests[2]["detected_year"] is None
    assert manifests[2]["evidence"]["year_status"] == "undated"
    assert manifests[2]["evidence"]["year_owner_decision"] == {
        "export": _undated_export(tmp_path), "document_id": 7, "question_id": "q3", "choice": "undated"}
    assert "year_status" not in manifests[0]["evidence"] and "year_owner_decision" not in manifests[1]["evidence"]


def test_a_listed_document_never_fills_a_missing_year_from_the_catalogue(monkeypatch):
    # The legacy listing (PRIMARY/COMPILATION) builds from stored years; one missing is refused, not
    # filled from the catalogue's meta_year (INV-1).
    blocks = [_laid(201 + i, 1, f"{i + 1}. Section {i + 1} of this Act applies.") for i in range(6)]
    outer = {"instrument_id": "x", "source_observation_id": 77, "document_id": 977, "sha256": "a" * 64,
             "jurisdiction": "fed", "kind": "act", "number": None, "year": 1990,
             "short_title": "The Example Act, 1990", "source_url": None, "source_id": "pk-fed",
             "meta_year": "1990"}
    boundary = {"candidate_id": "c", "start_block_id": 204, "source_page": 1, "title": "The Schedule Rules",
                "kind": "rules", "year": None, "number": None, "confidence": 1.0, "detector": "plan",
                "evidence": {}}
    _stub_storage(monkeypatch, blocks, outer)
    monkeypatch.setattr(materializer, "_load", lambda _d, _o=None: (outer, [boundary]))
    with pytest.raises(ValueError, match="has no year; an undated expression is built only from a reviewed plan"):
        materializer.prepare(977)


def test_plan_admits_the_empowers_relation():
    # docs/03b edge `empowers` (lead decision 11 Oct 2026, doc 4428: the Act's s.26 empowers the 2010 Rules)
    assert materializer.PLAN_RELATIONS == {"amends", "empowers"}
    plan = copy.deepcopy(_plan())
    plan["expressions"][0]["title_correction"] = None
    plan["expressions"][0]["relations"] = [{"type": "empowers", "target_ordinal": 1, "source_block_id": 106,
                                            "source_provision_path": "x.s_26", "effect": "s.26 empowers the rules",
                                            "basis": "p2 prints s.26"}]
    specs = materializer.validate_plan(plan, _plan_blocks(), 7, 70)
    assert specs[0]["relations"][0]["type"] == "empowers"
    plan["expressions"][0]["relations"][0]["type"] = "made_under"
    with pytest.raises(ValueError, match="is not one of"):
        materializer.validate_plan(plan, _plan_blocks(), 7, 70)


def test_a_plan_expression_may_state_its_own_jurisdiction():
    # doc 4347 E3, a Punjab notification printed inside a Sindh booklet (lead decision 12 Oct 2026; agent DF)
    plan = copy.deepcopy(_plan())
    plan["expressions"][0]["title_correction"] = None
    specs = materializer.validate_plan(plan, _plan_blocks(), 7, 70)
    assert specs[0]["jurisdiction"] is None                         # absent: the observation's source jurisdiction
    plan["expressions"][0]["jurisdiction"] = "punjab"
    with pytest.raises(ValueError, match="jurisdiction_basis"):
        materializer.validate_plan(plan, _plan_blocks(), 7, 70)
    plan["expressions"][0]["jurisdiction_basis"] = "the page prints 'Government of the Punjab'"
    specs = materializer.validate_plan(plan, _plan_blocks(), 7, 70)
    assert specs[0]["jurisdiction"] == "punjab"
    plan["expressions"][0]["jurisdiction"] = "Punjab"
    with pytest.raises(ValueError, match="must be one of"):
        materializer.validate_plan(plan, _plan_blocks(), 7, 70)


def test_document_4434_is_materialised_from_its_plan():
    # owner export j q2 (12 Oct 2026): expression 11 split into the 13th, 14th and 16th Amendment Acts; agent K5's plan
    # (lead 15-16 Oct): e3/e10/e20/e39 at their printed titles, e38 split (e45 = P.O. 11 of 1985), e0 'fed' and the
    # 2016 historical window -- 46 expressions
    plan = materializer.load_plan(4434)
    assert plan is not None and 4434 in materializer.REVIEWED_DOCUMENTS
    assert 4434 not in materializer.PRIMARY_DOCUMENTS | materializer.COMPILATION_DOCUMENTS
    assert len(plan["expressions"]) == 46
    e0 = next(e for e in plan["expressions"] if e["ordinal"] == 0)
    vv = e0["version_validity"]
    assert (vv["from"], vv["to"]) == ("2016-06-08", "2017-01-07") and vv["owner_decision"]["question_id"] == "q3"


def test_documents_4431_and_3782_are_materialised_from_their_plans():
    # 4431 (agent K2; export l q5 'split-fee-notification'): the Rules + three notifications; 3782 (agent K4; delegated
    # q4 'undated' for E1): the Rules + five amending notifications
    for doc, n in ((4431, 4), (3782, 6)):
        plan = materializer.load_plan(doc)
        assert plan is not None and doc in materializer.REVIEWED_DOCUMENTS
        assert doc not in materializer.PRIMARY_DOCUMENTS | materializer.COMPILATION_DOCUMENTS
        assert len(plan["expressions"]) == n
        assert not (materializer.PLAN_DIRECTORY / f"doc-{doc}-DRAFT.json").exists()


def test_documents_3730_and_3696_are_materialised_from_their_plans():
    # 3730 (agent K4; owner export j q1 'split', delegated q2 'rows-by-group'): the Rules, the completion notification
    # and the rates notification with Annexures A-E; 3696 (agent K4; delegated q2 'split-and-realign', q3 'keep-both';
    # lead 16 Oct: a released change, the 128 path moves approved): six instruments of the 1998 gazette
    for doc, n in ((3730, 3), (3696, 6)):
        plan = materializer.load_plan(doc)
        assert plan is not None and doc in materializer.REVIEWED_DOCUMENTS
        assert doc not in materializer.PRIMARY_DOCUMENTS | materializer.COMPILATION_DOCUMENTS
        assert len(plan["expressions"]) == n
        assert not (materializer.PLAN_DIRECTORY / f"doc-{doc}-DRAFT.json").exists()


def test_document_3949_is_materialised_from_its_plan():
    # agent JF (owner export m q1 keep-both, q2 keep-printed; owner 17 Oct q3 rows-by-post, q4 release-with-gap): the
    # Punjab Education Foundation compilation's five instruments, on the DEFAULT profile (its E1/E2 are released)
    plan = materializer.load_plan(3949)
    assert plan is not None and 3949 in materializer.REVIEWED_DOCUMENTS
    assert 3949 not in materializer.PRIMARY_DOCUMENTS | materializer.COMPILATION_DOCUMENTS
    assert len(plan["expressions"]) == 5
    assert not (materializer.PLAN_DIRECTORY / "doc-3949-DRAFT.json").exists()


def test_materializer_refuses_unknown_patch_keys_rather_than_dropping_them():
    # lead 13 Oct (agent JE, doc 4431): a key the materializer does not know is refused and named, never dropped
    from tools.record_curation_patch import READING_KEYS, STRUCTURAL_KEYS
    assert set(materializer.STRUCTURAL_PATCH_KEYS) == set(STRUCTURAL_KEYS)
    assert materializer.NON_STRUCTURAL_READING_KEYS == set(READING_KEYS) - set(STRUCTURAL_KEYS)
    for key in ("source_figure_subsections", "source_margin_note_pieces"):
        assert key in materializer.STRUCTURAL_PATCH_KEYS
    known = {"id": 1, "evidence": {"structural_overrides": {"source_apparatus_blocks": [5]}}}
    bogus = {"id": 2, "evidence": {"structural_overrides": {"source_bogus_blocks": [5]}}}
    assert materializer.unknown_patch_key_problem([known]) is None
    problem = materializer.unknown_patch_key_problem([known, bogus])
    assert problem and "source_bogus_blocks" in problem and "patch 2" in problem
    # the legacy route applies none: any structural override is refused there
    assert "legacy route" in materializer.unknown_patch_key_problem([known], structural_allowed=False)
    assert materializer.unknown_patch_key_problem([{"id": 3, "evidence": {}}], structural_allowed=False) is None
    reading = {"document_id": 7, "page_no": 1, "match_text": "m", "before_text": "b", "after_text": "b",
               "source_bogus_blocks": [5]}
    with pytest.raises(ValueError, match=r"reading 0 carries key\(s\) \['source_bogus_blocks'\]"):
        materializer.unrecorded_readings([reading], [], 7)


def test_document_3423_is_materialised_from_its_plan():
    # agent K3 (owner export j q1 'main-plus-notifications'; delegated q2 'split-annexes-v-vi'; 16 Oct 2026): 3423 left
    # COMPILATION_DOCUMENTS for its reviewed three-expression plan -- the 2015 Guidebook notification (two spans, its
    # annex pages around the embedded notifications) and the embedded 2013 and 2007 notifications
    plan = materializer.load_plan(3423)
    assert plan is not None and 3423 in materializer.REVIEWED_DOCUMENTS
    assert 3423 not in materializer.PRIMARY_DOCUMENTS | materializer.COMPILATION_DOCUMENTS
    assert [e["ordinal"] for e in plan["expressions"]] == [0, 1, 2]
    assert not (materializer.PLAN_DIRECTORY / "doc-3423-DRAFT.json").exists()


def test_document_3389_is_materialised_from_its_plan():
    # agent JB (owner export j; 14 Oct 2026): 3389 left PRIMARY_DOCUMENTS for its reviewed two-expression plan
    plan = materializer.load_plan(3389)
    assert plan is not None and 3389 in materializer.REVIEWED_DOCUMENTS
    assert 3389 not in materializer.PRIMARY_DOCUMENTS | materializer.COMPILATION_DOCUMENTS
    assert [e["ordinal"] for e in plan["expressions"]] == [0, 1]
