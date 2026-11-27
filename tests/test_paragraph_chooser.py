"""The GPU profile's paragraph chooser (D-176): the 8B picks which paragraph each found judgment presents, from search's
own paragraph and the nearest in the GPU space. The judgment order never changes; a failing reranker leaves search's
paragraphs, said in the trace; the CPU profile never chooses. Skips without the corpus or the GPU question bundle."""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = Path("/mnt/e/nizam-data/embed/bundle-precedent-v2-fp16")


class LastWins:
    """scores every later candidate of a judgment higher: the chooser must move every judgment with a second one"""
    info = type("I", (), {"model": "fake/8B", "revision": "r" * 40})()

    def __init__(self):
        self.calls = []

    def score(self, question, passages, instruction=None):
        self.calls.append((question, len(passages), instruction))
        return [float(i) for i in range(len(passages))]


class Broken:
    info = LastWins.info

    def score(self, question, passages, instruction=None):
        raise OSError("service down")


@pytest.fixture(scope="module")
def setup():
    if not (BUNDLE / "q.npy").exists():
        pytest.skip("no GPU question bundle for precedent dev")
    try:
        sys.path.insert(0, str(ROOT / "evals"))
        from precomputed_encoder import PrecomputedEncoder
        from nizam.storage.judgment_read import JudgmentRead
        enc = PrecomputedEncoder.from_bundle(BUNDLE, vectors="q.npy", questions="questions.json")
        repo = JudgmentRead()
        repo.open()
        with repo.transaction() as conn:
            if not repo.gpu_vectors_held(conn):
                pytest.skip("judgment GPU vectors not loaded")
    except pytest.skip.Exception:
        raise
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    q = json.loads((BUNDLE / "questions.json").read_text(encoding="utf-8"))[1]
    yield repo, enc, q
    repo.close()


def _run(setup, **kw):
    from nizam.retrieval.precedent import search
    repo, enc, q = setup
    return search(q, as_of=dt.date(2026, 11, 27), k=10, repo=repo, encoder=enc, **kw)


def test_the_chooser_moves_paragraphs_never_judgments(setup):
    plain = _run(setup, choose_paragraph=False)
    fake = LastWins()
    chosen = _run(setup, paragraph_reranker=fake)
    assert [h.judgment_id for h in chosen.hits] == [h.judgment_id for h in plain.hits]
    t = chosen.trace["paragraph_chooser"]
    assert t["used"] and t["pairs"] <= 30 and t["moved"] >= 1
    assert fake.calls[0][2].startswith("Given a question about Pakistani law, retrieve the court judgment")
    moved = [a for a, b in zip(chosen.hits, plain.hits) if a.paragraph_id != b.paragraph_id]
    assert len(moved) == t["moved"]
    for h in moved:                                             # the presented paragraph is that judgment's own
        assert h.text and h.citation


def test_a_failing_reranker_keeps_search_paragraphs(setup):
    plain = _run(setup, choose_paragraph=False)
    r = _run(setup, paragraph_reranker=Broken())
    assert [h.paragraph_id for h in r.hits] == [h.paragraph_id for h in plain.hits]
    assert r.trace["paragraph_chooser"]["used"] is False and "service down" in r.trace["paragraph_chooser"]["reason"]


def test_the_cpu_profile_never_chooses(setup):
    from nizam.retrieval.precedent import search
    repo, _enc, q = setup
    r = search(q, as_of=dt.date(2026, 11, 27), k=10, repo=repo, paragraph_reranker=LastWins())
    assert "paragraph_chooser" not in r.trace and r.trace.get("dense_space") != "gpu"
