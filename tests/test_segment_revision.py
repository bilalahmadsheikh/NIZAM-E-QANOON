"""Regression tests for non-destructive observation-scoped segmentation."""

from nizam.workers.segment import build


def test_build_keeps_official_observation_identity_and_url():
    blocks = [
        {"id": 1, "text": "THE EXAMPLE ACT, 2020", "page_no": 1,
         "y0": 40.0, "page_height": 792.0},
        {"id": 2, "text": "1. Short title. This Act may be called the Example Act, 2020.",
         "page_no": 1, "y0": 100.0, "page_height": 792.0},
    ]
    inst, _ = build(
        77, "a" * 64, 123, "pk-punjab", "The Example Act, 2020", "2020",
        "https://punjabcode.punjab.gov.pk/example.pdf", blocks, "2026-08-28",
    )

    assert inst.source_observation_id == 123
    assert inst.source_url == "https://punjabcode.punjab.gov.pk/example.pdf"
    assert inst.document_id == 77
    assert inst.provisions
    assert all("o123" in row["path"] for row in inst.provisions)


def test_byte_identical_observations_get_distinct_stable_paths():
    blocks = [{"id": 1, "text": "1. Short title. Example text.", "page_no": 1,
               "y0": 100.0, "page_height": 792.0}]
    first, _ = build(77, "b" * 64, 201, "pk-federal", "Example Act, 2020", "2020",
                     "https://pakistancode.gov.pk/a.pdf", blocks, "2026-08-28")
    second, _ = build(77, "b" * 64, 202, "pk-punjab", "Example Act, 2020", "2020",
                      "https://punjabcode.punjab.gov.pk/a.pdf", blocks, "2026-08-28")

    assert first.provisions[0]["path"] != second.provisions[0]["path"]
    assert "o201" in first.provisions[0]["path"]
    assert "o202" in second.provisions[0]["path"]


def test_build_exposes_item_level_repeated_label_evidence():
    blocks = [
        {"id": 10, "text": "1. Application. These rules apply.", "page_no": 1,
         "y0": 100.0, "page_height": 792.0},
        {"id": 11, "text": "2. Principal rule. The rule applies.", "page_no": 1,
         "y0": 130.0, "page_height": 792.0},
        {"id": 12, "text": "1. Clerk  2. Typist  3. Driver", "page_no": 2,
         "y0": 100.0, "page_height": 792.0},
    ]
    inst, seg = build(
        77, "c" * 64, 203, "pk-punjab", "Example Rules, 2020", "2020",
        "https://punjabcode.punjab.gov.pk/example.pdf", blocks, "2026-08-28",
    )
    assert seg.repeated_labels_demoted == 1
    assert len(inst.structural_decisions) == 1
    decision = inst.structural_decisions[0]
    assert decision["source_block_id"] == 12
    assert decision["canonical_source_block_id"] == 10
    assert decision["printed_label"] == "1"
    assert decision["evidence"]["same_parent"] is True
