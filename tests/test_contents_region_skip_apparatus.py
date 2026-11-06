"""`source_contents_region` with the optional `skip_apparatus: true` (doc 9281, 6 Nov 2026).

The contents parse runs before reviewed apparatus blocks are removed, so a raw OCR contents block inside the region that
a page reading set aside ('Sactions, 1, Short title, ...', '51. 52.') adds rows the page does not print, and those rows
then stay as unlinked contents gaps. With the field, the region's rows are read without the reviewed apparatus blocks.
Without it the rule reads exactly as before (36 released documents carry a region)."""
import pytest

import nizam.corpus.segment as SEG


def blk(i, text, p=1, y=10):
    return {"id": i, "text": text, "page_no": p, "y0": y, "page_height": 800, "x0": 50, "x1": 500}


DOC = [blk(1, "THE TEST ACT, 1881.\n", y=10),
       blk(2, "PREAMBLE.\nSECTIONS.\n1. Short title.\n2. Definitions.\n3. Repeal.\n", y=40),
       blk(3, "51. Probate.\n52. Letters.\n", y=80),             # raw OCR row block the page reading set aside
       blk(4, "It is hereby enacted as follows:-\n", p=2, y=10),
       blk(5, "1. This Act may be called the Test Act, 1881.\n", p=2, y=40),
       blk(6, "2. In this Act words have their usual meaning.\n", p=2, y=70),
       blk(7, "3. The Old Act is repealed.\n", p=2, y=100)]
BASE = {"first_block_id": 2, "last_block_id": 3, "body_start_block_id": 4, "rows": "sections"}


def sections(seg):
    return [n.label for n in seg.flatten() if n.kind == "section"]


def test_without_the_field_the_aside_block_still_promises_rows():
    seg = SEG.segment(DOC, structural_overrides={"source_contents_region": dict(BASE), "source_apparatus_blocks": [3]})
    assert sections(seg) == ["1", "2", "3"]
    assert {"51", "52"} & set(seg.toc), seg.toc


def test_skip_apparatus_reads_the_rows_without_the_aside_block():
    seg = SEG.segment(DOC, structural_overrides={"source_contents_region": dict(BASE, skip_apparatus=True),
                                                 "source_apparatus_blocks": [3]})
    assert sections(seg) == ["1", "2", "3"]
    assert sorted(seg.toc) == ["1", "2", "3"], seg.toc


@pytest.mark.parametrize("bad", [dict(BASE, skip_apparatus=False), dict(BASE, skip_apparatus="yes"), dict(BASE, other=True)])
def test_the_field_is_exact(bad):
    with pytest.raises(ValueError, match="malformed"):
        SEG.segment(DOC, structural_overrides={"source_contents_region": bad, "source_apparatus_blocks": [3]})
