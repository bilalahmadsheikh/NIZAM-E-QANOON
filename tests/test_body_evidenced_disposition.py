"""Rule `body_evidenced_disposition` (stage 3, owner 11 Oct 2026; agent DC; docs/SEGMENTATION-PROFILES.md).

Five released documents (1351 1366 1609 1846 4379) raised 'stale TOC disposition assertion' on every rebuild: each
reviewed assertion names exactly the contents row the parse yields, but the row prints only the section's NAME while
the BODY prints the omission/repeal, and the identity check demanded the lifecycle word in the row's own heading.
A reviewed assertion now also matches a row printing no lifecycle word when the row's heading is exactly the
recorded printed_heading and the assertion's evidence carries the rendered body page (body_render + body_sha256).
"""
import pytest

from nizam.corpus.segment import segment


def blocks(*texts: str) -> list[dict]:
    return [{"id": i, "text": t, "page_no": 1, "y0": 100.0 + i * 20, "page_height": 792.0}
            for i, t in enumerate(texts)]


TOC = ["CONTENTS"] + [f"{n}. Heading number {n}." for n in range(1, 12)]
BODY = [f"{n}. Heading number {n}. Some enacted text here." for n in range(1, 12) if n != 7]


def assertion(**evidence):
    return {"id": 205, "toc_entry_ordinal": 6, "printed_label": "7", "printed_heading": "Heading number 7.",
            "disposition": "omitted", "source_block_id": 7, "source_page": 1, "amending_instrument_id": None,
            "evidence": evidence}


def test_a_name_only_row_with_the_body_page_recorded_is_materialised():
    seg = segment(blocks(*TOC, *BODY), toc_dispositions=[
        assertion(body_render="renders/doc1351-p3.png", body_sha256="fd1fc8d6")])
    entry = next(item for item in seg.toc_entries if item["label"] == "7")
    assert entry["method"] == "source_verified_disposition"
    assert entry["node"].operation == "omitted"
    assert entry["node"].text == ""


@pytest.mark.parametrize("evidence", [{}, {"body_render": "renders/doc1351-p3.png"}, {"body_sha256": "fd1fc8d6"}])
def test_without_the_rendered_body_page_the_assertion_still_fails_closed(evidence):
    with pytest.raises(ValueError, match="stale TOC disposition assertion"):
        segment(blocks(*TOC, *BODY), toc_dispositions=[assertion(**evidence)])


def test_a_different_printed_heading_still_fails_closed():
    stale = dict(assertion(body_render="r.png", body_sha256="x"), printed_heading="Some other heading.")
    with pytest.raises(ValueError, match="stale TOC disposition assertion"):
        segment(blocks(*TOC, *BODY), toc_dispositions=[stale])


def test_a_row_printing_the_other_lifecycle_word_still_refuses():
    toc = ["CONTENTS"] + [f"{n}. {'[Repealed]' if n == 7 else f'Heading number {n}.'}" for n in range(1, 12)]
    record = dict(assertion(body_render="r.png", body_sha256="x"), printed_heading="[Repealed]")
    with pytest.raises(ValueError, match="stale TOC disposition assertion"):
        segment(blocks(*toc, *BODY), toc_dispositions=[record])
