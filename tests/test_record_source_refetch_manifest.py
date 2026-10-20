"""tools/record_source_refetch.py: the URL of an observation landed without one
comes from the scraper manifest row of the held blob (doc 3533, observation 370).

Pure tests: no portal, no database."""
from __future__ import annotations

import csv
import io
import zipfile

import pytest

from tools.record_source_refetch import manifest_url, read_manifest

HELD = "7c62b3e7afd82f5707e348d91b9b1927e1d096102b364a98c93bb15416c06cd1"
URL = "https://pakistancode.gov.pk/pdffiles/administratora522f8db17a8fa28b29b5444ded32b3c.pdf"


def row(sha, url, status="success", path="output\\1965\\Provincial Employees' Social Security Ordinance, 1965.pdf"):
    return {"sha256": sha, "pdf_url": url, "status": status, "local_path": path}


def test_one_url_for_the_held_blob():
    url, r = manifest_url([row("0" * 64, "https://pakistancode.gov.pk/other.pdf"), row(HELD, URL)], HELD)
    assert url == URL and r["sha256"] == HELD


def test_the_same_url_twice_is_one_url():
    """Doc 3533's manifest lists the page twice, 'success' then 'skipped'."""
    url, _ = manifest_url([row(HELD, URL), row(HELD.upper(), URL, status="skipped")], HELD)
    assert url == URL


def test_no_row_for_the_held_blob_refuses():
    with pytest.raises(ValueError):
        manifest_url([row("0" * 64, URL)], HELD)


def test_two_urls_for_the_held_blob_refuse():
    with pytest.raises(ValueError):
        manifest_url([row(HELD, URL), row(HELD, "https://pakistancode.gov.pk/pdffiles/x.pdf")], HELD)


def test_a_row_without_a_url_does_not_count():
    with pytest.raises(ValueError):
        manifest_url([row(HELD, "")], HELD)


def _csv(rows):
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=["sha256", "pdf_url", "status", "local_path"])
    w.writeheader()
    w.writerows(rows)
    return out.getvalue().encode("utf-8")


def test_read_manifest_from_a_file_and_from_a_zip(tmp_path):
    data = _csv([row(HELD, URL)])
    path = tmp_path / "manifest.csv"
    path.write_bytes(data)
    rows, sha = read_manifest(str(path), None)
    assert manifest_url(rows, HELD)[0] == URL and len(sha) == 64
    archive = tmp_path / "laws.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Federal Laws/output/manifest.csv", data)
    rows2, sha2 = read_manifest("Federal Laws/output/manifest.csv", str(archive))
    assert rows2 == rows and sha2 == sha
