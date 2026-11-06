"""The script of a reviewer's correction blocks.

`corrected_blocks` builds the blocks a reviewed correction adds to a page, and
`promote_ocr_adjudicated` carries each block's `script` into `text_block`. An
Urdu page the engine read nothing on (doc 7742 p31) must not come back tagged
Latin, so the spec may say "arabic" -- the value the engine writes for Urdu --
and nothing else changes for the Latin pages every earlier export corrected.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MODULE = Path(__file__).resolve().parents[1] / "tools" / "evidence" / "adjudicate_ocr_review_export.py"
_spec = importlib.util.spec_from_file_location("adjudicate_ocr_review_export", _MODULE)
adjudicate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adjudicate)

corrected_blocks = adjudicate.corrected_blocks
ENGINE_BLOCK = {"bbox": [36.0, 100.0, 400.0, 120.0], "text": "1. Short title.", "html": "", "script": "latin"}


def test_lines_default_to_latin():
    out = corrected_blocks([ENGINE_BLOCK], {"position": "below", "lines": ["2. Definitions."]}, 800.0)
    assert [b["script"] for b in out] == ["latin", "latin"]


def test_empty_page_lines_take_the_spec_script():
    out = corrected_blocks([], {"position": "below", "script": "arabic", "lines": ["31", "نمونہ رسید وصولی درخواست"]},
                           800.0)
    assert [b["script"] for b in out] == ["arabic", "arabic"]
    assert all(b["owner_supplied"] for b in out)


def test_transcription_takes_the_spec_script():
    out = corrected_blocks([ENGINE_BLOCK], {"transcription": ["باب نمبر 3"], "script": "arabic"}, 800.0)
    assert [b["script"] for b in out] == ["arabic"]


def test_engine_blocks_keep_their_own_script():
    """Only the reviewer's added lines take the spec's script; the engine's blocks are not relabelled."""
    out = corrected_blocks([ENGINE_BLOCK], {"position": "above", "script": "arabic", "lines": ["31"]}, 800.0)
    assert [b["script"] for b in out] == ["arabic", "latin"]


def test_unknown_script_is_refused():
    with pytest.raises(ValueError, match="unsupported script"):
        corrected_blocks([], {"position": "below", "script": "urdu", "lines": ["x"]}, 800.0)
