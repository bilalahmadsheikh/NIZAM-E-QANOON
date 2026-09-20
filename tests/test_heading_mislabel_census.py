from tools.census_heading_mislabel import find_hits


def row(*, printed, heading, label="17", instrument="00000000-0000-0000-0000-000000000001"):
    return (
        4331,
        "Example Act",
        "00000000-0000-0000-0000-000000000002",
        label,
        4,
        instrument,
        "section",
        heading,
        f"{label}. {printed}.-- Enacted text follows.",
        1,
    )


def test_same_name_with_minor_extraction_damage_is_not_a_finding():
    rows = [row(
        printed="Duties of Suprintendent of vaccination",
        heading="Duties of Superintendent of vaccination",
    )]
    assert find_hits(rows) == []


def test_different_printed_name_is_recordable_with_instrument_identity():
    instrument = "00000000-0000-0000-0000-000000000123"
    hits = find_hits([row(
        printed="Application for mineral permit",
        heading="Power of Delegation",
        instrument=instrument,
    )])
    assert len(hits) == 1
    assert hits[0]["class"] == "different_name"
    assert hits[0]["instrument_id"] == instrument
    assert hits[0]["toc_linked"] is True
