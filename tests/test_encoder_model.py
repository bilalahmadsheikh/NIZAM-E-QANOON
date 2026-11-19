"""D-098: the installed query encoder reproduces, on this host, the int8 vectors the Kaggle export validated.

The export (tools/kaggle/export_kernel.py) saved its kept variant's dev query vectors (dev_query_int8.npy) and the raw
questions (dev_questions.json) beside the model. Here the HOST's path -- the `tokenizers` library reading
tokenizer.json, onnxruntime on the CPU, nizam.inference.encoder's pooling and query template -- encodes the same
questions. If tokenisation, the template or pooling differed, the vectors would differ and the dev numbers the model
was chosen on would not describe what the host serves. Skips when no encoder is installed (a fresh clone).
"""
import json

import numpy as np
import pytest


@pytest.fixture(scope="module")
def installed():
    from nizam.inference.encoder import Encoder, model_dir
    d = model_dir()
    if not (d / "model.onnx").exists() or not (d / "dev_query_int8.npy").exists():
        pytest.skip(f"no validated encoder installed at {d}")
    return Encoder(d), d


def test_the_host_reproduces_the_validated_int8_query_vectors(installed):
    enc, d = installed
    questions = json.loads((d / "dev_questions.json").read_text(encoding="utf-8"))
    ref = np.load(d / "dev_query_int8.npy")
    got = np.stack([enc.embed(q) for q in questions])
    cos = (got * ref).sum(1)
    agree = ((got > 0) == (ref > 0)).mean(1)
    # the same int8 graph on another CPU: float summation order may differ, nothing else may
    assert cos.min() > 0.999, f"min cosine {cos.min():.5f}"
    assert agree.mean() > 0.995, f"sign bits agree {agree.mean():.4f}"


def test_the_installed_encoder_is_the_active_generation(installed):
    enc, _ = installed
    from datetime import date

    from nizam.inference.encoder import check_generation
    from nizam.storage import unit_search
    from nizam.storage.lexical import Filters
    try:
        with unit_search.session(Filters(as_of=date(2026, 11, 19))) as s:
            active = s.active_generation()
    except Exception as exc:                                    # noqa: BLE001
        pytest.skip(f"corpus not reachable: {type(exc).__name__}")
    if active is None:
        pytest.skip("no embedding generation loaded yet")
    check_generation(active, enc.info)
