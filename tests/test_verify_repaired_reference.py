"""Repaired-reference fallback of the independent extraction checks (agent JE, doc 4608; lead decision 15 Oct 2026).

Poppler cannot read a blob whose cross-reference table is broken.  Only for a blob with an ACTIVE decode_damage
assertion, the verifiers compare against Poppler's text of a MuPDF xref-rebuilt copy of the same bytes, and accept
page-local differences only through page-scoped 'repaired-reference-difference' assertions that list the exact
strings.  Everything else is unchanged.
"""
import shutil

import pytest

pymupdf = pytest.importorskip("pymupdf")
pytestmark = pytest.mark.skipif(shutil.which("pdftotext") is None, reason="needs poppler pdftotext")

from nizam.workers import verify_extraction as VE  # noqa: E402
from nizam.workers import verify_order as VO  # noqa: E402

TEXT = ("The Sindh Local Government Amendment Act shall come into force at once. "
        "In section two the following clause shall be inserted after clause eleven.")


def _pdf(path, text=TEXT):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=11)
    doc.save(str(path))
    doc.close()


def _break_xref(path):
    """Cut the cross-reference table and trailer: Poppler then reads nothing, MuPDF repairs on open."""
    data = path.read_bytes()
    cut = data.rfind(b"\nxref")          # the table, not 'startxref'
    assert cut > 0
    path.write_bytes(data[:cut])


class FakeCur:
    """Answers the verifiers' read queries from fixtures; refuses writes."""

    def __init__(self, blocks, sha, damage=True, assertions=()):
        self.blocks, self.sha, self.damage, self.assertions = blocks, sha, damage, list(assertions)
        self.rows = []

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        assert not s.upper().startswith(("INSERT", "UPDATE", "DELETE"))
        if "FROM extraction_assertion a LEFT JOIN LATERAL" in s:
            self.rows = [(3, 1, "damaged", None, None, None, None, None)] if self.damage else []
        elif "kind='decode_damage'" in s:
            self.rows = [(3,)] if self.damage else []
        elif "detail->>'purpose'" in s:
            self.rows = list(self.assertions)
        elif "kind='source_content_confirmed'" in s:
            self.rows = []
        elif s.startswith("SELECT text,inside_cropbox,confidence FROM text_block"):
            self.rows = [(t, True, None) for _, t in self.blocks]
        elif s.startswith("SELECT page_no,text FROM text_block"):
            self.rows = list(self.blocks)
        elif s.startswith("SELECT sha256 FROM document"):
            self.rows = [(self.sha,)]
        else:
            raise AssertionError(f"unexpected query {s[:80]}")

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        r, self.rows = self.rows, []
        return r


@pytest.fixture
def broken(tmp_path, monkeypatch):
    monkeypatch.setattr(VE, "CORPUS_ROOT", tmp_path)
    monkeypatch.setattr(VO, "CORPUS_ROOT", tmp_path)
    p = tmp_path / "blob.pdf"
    _pdf(p)
    _break_xref(p)
    return p


def test_poppler_reads_nothing_and_the_rebuilt_copy_reads_the_text(broken):
    assert not VE._chars(VE.pdftotext(broken))
    assert VE._chars(TEXT) == VE._chars(VE.rebuilt_reference(broken))


def test_no_decode_damage_means_no_fallback(broken):
    r = VE.check(FakeCur([(1, TEXT)], "s" * 64, damage=False), 1, "s" * 64, broken.name, 1, None)
    assert r["recall"] is None and "reference_extractor" not in r
    assert any("pdftotext found no text" in p for p in r["problems"])


def test_decode_damage_takes_the_rebuilt_reference_and_passes_when_identical(broken):
    r = VE.check(FakeCur([(1, TEXT)], "s" * 64), 1, "s" * 64, broken.name, 1, None)
    assert r["reference_extractor"] == VE.REPAIRED_REFERENCE_EXTRACTOR
    assert r["reference_repair"]["decode_assertion_id"] == 3
    assert r["recall"] == 1.0 and r["ok"]


def _assertion(page_text, missing=(), extra=(), aid=7, page=1):
    return (aid, page, {"purpose": VE.REPAIRED_REFERENCE_PURPOSE, "missing_strings": list(missing),
                        "extra_strings": list(extra), "reference_page_sha256": VE.page_text_sha256(page_text)})


def test_a_loss_fails_without_an_assertion_and_passes_only_with_the_exact_strings(broken):
    stored = TEXT.replace("shall be inserted", "be inserted")      # the stored layer lost 'shall '
    sha = "s" * 64
    r = VE.check(FakeCur([(1, stored)], sha), 1, sha, broken.name, 1, None)
    assert not r["ok"] and any(p.startswith("loss:") for p in r["problems"])
    page = VE.reference_pages(VE.rebuilt_reference(broken))[0]
    ok = VE.check(FakeCur([(1, stored)], sha, assertions=[_assertion(page, missing=["shall"])]),
                  1, sha, broken.name, 1, None)
    assert ok["ok"] and ok["recall"] == 1.0 and ok["raw_recall"] < VE.MIN_CHAR_RECALL
    assert ok["repaired_reference_assertion_ids"] == [7]
    # a string the page does not print credits nothing
    bad = VE.check(FakeCur([(1, stored)], sha, assertions=[_assertion(page, missing=["shalt"])]),
                   1, sha, broken.name, 1, None)
    assert not bad["ok"]
    # a stale assertion (reference page text changed) credits nothing
    stale = (7, 1, dict(_assertion(page, missing=["shall"])[2], reference_page_sha256="0" * 64))
    assert not VE.check(FakeCur([(1, stored)], sha, assertions=[stale]), 1, sha, broken.name, 1, None)["ok"]


def test_extra_stored_text_needs_the_exact_extra_strings(broken):
    stored = TEXT + " Invented words."
    sha = "s" * 64
    r = VE.check(FakeCur([(1, stored)], sha), 1, sha, broken.name, 1, None)
    assert not r["ok"] and any(p.startswith("fabrication:") for p in r["problems"])
    page = VE.reference_pages(VE.rebuilt_reference(broken))[0]
    ok = VE.check(FakeCur([(1, stored)], sha, assertions=[_assertion(page, extra=["Invented words."])]),
                  1, sha, broken.name, 1, None)
    assert ok["ok"]
    # the extra string must be in the stored page
    assert not VE.check(FakeCur([(1, stored)], sha, assertions=[_assertion(page, extra=["Other words."])]),
                        1, sha, broken.name, 1, None)["ok"]


def test_credited_page_differences_refuses_malformed_and_out_of_range():
    page = "alpha beta"
    out = VE.credited_page_differences({1: "alpha"}, [page], [
        (1, 2, {"purpose": VE.REPAIRED_REFERENCE_PURPOSE, "missing_strings": ["beta"],
                "reference_page_sha256": VE.page_text_sha256(page)}),           # page 2 does not exist
        (2, 1, {"purpose": VE.REPAIRED_REFERENCE_PURPOSE, "missing_strings": [],
                "reference_page_sha256": VE.page_text_sha256(page)}),           # lists nothing
        (3, 1, {"purpose": "other", "missing_strings": ["beta"]}),              # another purpose: ignored
        (4, 1, {"purpose": VE.REPAIRED_REFERENCE_PURPOSE, "missing_strings": ["beta"],
                "reference_page_sha256": VE.page_text_sha256(page)})])
    assert out["used"] == [4] and [a for a, _ in out["rejected"]] == [1, 2]
    assert out["missing"] == VE._chars("beta")


def test_an_undamaged_blob_is_compared_as_before(tmp_path, monkeypatch):
    monkeypatch.setattr(VE, "CORPUS_ROOT", tmp_path)
    p = tmp_path / "good.pdf"
    _pdf(p)
    r = VE.check(FakeCur([(1, TEXT)], "s" * 64), 1, "s" * 64, p.name, 1, None)
    assert "reference_extractor" not in r and r["ok"]


def test_order_check_uses_the_rebuilt_reference_only_with_decode_damage(broken):
    plain = VO.check(FakeCur([(1, TEXT)], "s" * 64, damage=False), 1, broken.name, None)
    assert plain.get("unverifiable_reason")
    r = VO.check(FakeCur([(1, TEXT)], "s" * 64), 1, broken.name, None)
    assert r["reference_repair"]["reference_extractor"] == VE.REPAIRED_REFERENCE_EXTRACTOR + "-sequence"
    assert r["comparison_unit"] == "character" and not r["problems"]
