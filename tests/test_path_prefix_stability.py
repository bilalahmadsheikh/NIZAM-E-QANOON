"""D-090 (INV-4): a rebuild keeps the path prefix its existing tree was given.

18 Nov 2026: four released laws (docs 6576, 6784, 8173, 8743) rebuilt with every path renamed, because the Act number
inferred from the page head drifted ('fed.act.y1874_VI_o12229' -> 'fed.act.y1874_o12229') although the catalogue still
records Act VI of 1874. Citations are rendered from the instrument's recorded number and year (INV-1); the path is an
identifier and must not move with an inference. Pure: build() with the database lookups stubbed."""
import nizam.workers.segment as worker


def _blocks():
    return [
        {"id": 1, "page_no": 1, "text": "1. Short title.- This Act may be called the Example Act, 2020."},
        {"id": 2, "page_no": 1, "text": "2. Definitions.- In this Act, unless the context otherwise requires."},
    ]


def _build(monkeypatch, kept, **kw):
    monkeypatch.setattr(worker.legal_write, "segmentation_profile_for", lambda _o: "default")
    asked = []

    def prefix(obs, ordinal):
        asked.append((obs, ordinal))
        return kept
    monkeypatch.setattr(worker.legal_write, "released_path_prefix", prefix)
    inst, _seg = worker.build(5, "p" * 64, 314, "pk-federal", "Example Act, 2020", "2020", None, _blocks(),
                              "2026-09-26", **kw)
    return inst, asked


def test_a_rebuild_keeps_the_released_prefix(monkeypatch):
    inst, asked = _build(monkeypatch, "fed.act.y2020_VI_o314")
    assert asked == [(314, 0)]
    assert {p["path"].rsplit(".", 1)[0] for p in inst.provisions} == {"fed.act.y2020_VI_o314"}


def test_a_first_build_infers_its_prefix(monkeypatch):
    inst, _ = _build(monkeypatch, None)
    assert all(p["path"].startswith("fed.act.y2020_o314.") for p in inst.provisions)


def test_the_instrument_fields_still_come_from_inference_and_recorders(monkeypatch):
    # only the identifier is kept; number/year stay what the build reads (recorders correct them afterwards)
    inst, _ = _build(monkeypatch, "fed.act.y1999_IX_o314")
    assert inst.year == 2020


def test_a_reviewed_identity_builds_its_own_prefix(monkeypatch):
    inst, asked = _build(monkeypatch, "fed.act.y2020_VI_o314",
                         reviewed_identity={"kind": "notification", "year": 2003, "number": None})
    assert asked == []
    assert all(p["path"].startswith("fed.notification.y2003_o314.") for p in inst.provisions)


def test_the_caller_can_ask_for_an_inferred_prefix(monkeypatch):
    inst, asked = _build(monkeypatch, "fed.act.y2020_VI_o314", keep_path_prefix=False)
    assert asked == []
    assert all(p["path"].startswith("fed.act.y2020_o314.") for p in inst.provisions)
