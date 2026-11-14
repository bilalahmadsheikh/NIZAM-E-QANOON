"""tools/recrawl/land_missing.py: landing staged bytes (14 Nov 2026) never lands bytes under the wrong identity."""
import hashlib
import importlib.util
import os
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "land_missing", Path(__file__).resolve().parents[1] / "tools" / "recrawl" / "land_missing.py")
lm = importlib.util.module_from_spec(spec); spec.loader.exec_module(lm)

PDF = b"%PDF-1.4\n% a staged file\n"


def staged(tmp_path, body=PDF, name=None):
    sha = hashlib.sha256(PDF).hexdigest()
    (tmp_path / "files").mkdir()
    p = tmp_path / "files" / f"{name or sha}.pdf"
    p.write_bytes(body)
    os.utime(p, (1_763_100_000, 1_763_100_000))
    return sha


def test_staged_bytes_are_taken_with_their_fetch_time(tmp_path):
    sha = staged(tmp_path)
    data, at = lm.staged_bytes(tmp_path, {"staged_sha256": sha})
    assert data == PDF and at.startswith("2025-11-14T")


def test_a_staged_file_changed_since_staging_is_refused(tmp_path):
    sha = staged(tmp_path, body=PDF + b"tampered", name=hashlib.sha256(PDF).hexdigest())
    with pytest.raises(ValueError, match="no longer hashes"):
        lm.staged_bytes(tmp_path, {"staged_sha256": sha})


def test_no_staged_file_means_fetch(tmp_path):
    (tmp_path / "files").mkdir()
    assert lm.staged_bytes(tmp_path, {"staged_sha256": "0" * 64}) is None
    assert lm.staged_bytes(tmp_path, {}) is None


def test_quoted_matches_the_url_the_fetch_records_and_refuses_foreign_hosts():
    assert lm._quoted("https://law.gok.pk/wp-content/uploads/a b.pdf") == "https://law.gok.pk/wp-content/uploads/a%20b.pdf"
    assert lm._quoted("https://example.com/a.pdf") is None
