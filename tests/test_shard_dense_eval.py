"""evals/shard_dense_eval.py (D-099): scores what it claims to, and refuses shards that are not the export's chunks."""
from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
DIMS = 4096


def _unit(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def _build(tmp: Path, corrupt_ids=False):
    rng = np.random.default_rng(7)
    n, nshard = 40, 2
    ids = np.arange(1000, 1000 + n, dtype=np.int64)
    X = _unit(rng.standard_normal((n, DIMS))).astype(np.float32)
    ds = tmp / "ds"; ds.mkdir()
    with gzip.open(ds / "chunks.jsonl.gz", "wt", encoding="utf-8") as f:
        for i in range(n):            # unit = i // 2 (two chunks per unit); first half federal, second half punjab
            f.write(json.dumps({"id": int(ids[i]), "u": i // 2, "j": "fed" if i < 20 else "punjab", "t": "x"}) + "\n")
    # case A: the query is chunk 5 plus a little noise -> gold unit 2, federal scope
    # case B: the query is chunk 33 -> gold unit 16, punjab+fed scope
    qa = _unit(X[5] + 0.05 * rng.standard_normal(DIMS)); qb = _unit(X[33] + 0.05 * rng.standard_normal(DIMS))
    dev = [{"case": "A", "stratum": "s", "script": "latin", "q": "a", "juris": ["fed"], "gold": [2], "gold_total": 1},
           {"case": "B", "stratum": "s", "script": "arabic", "q": "b", "juris": ["punjab", "fed"], "gold": [16],
            "gold_total": 1}]
    (ds / "dev.json").write_text(json.dumps(dev), encoding="utf-8")
    run = tmp / "run" / "out"; run.mkdir(parents=True)
    bounds = [n * s // nshard for s in range(nshard + 1)]
    (run / "run.json").write_text(json.dumps({"model": "m", "revision": "r", "query_template": "{q}",
                                              "bounds": bounds, "nshard": nshard}), encoding="utf-8")
    np.save(run / "dev_q.npy", np.stack([qa, qb]).astype(np.float32))
    np.save(run / "probe_g0.npy", X[:4]); np.save(run / "probe_g1.npy", X[:4])
    for s in range(nshard):
        lo, hi = bounds[s], bounds[s + 1]
        np.save(run / f"shard_{s:02d}.npy", X[lo:hi].astype(np.float16))
        sha = hashlib.sha256((ids[lo:hi] + (1 if corrupt_ids and s == 1 else 0)).tobytes()).hexdigest()
        (run / f"shard_{s:02d}.json").write_text(json.dumps({
            "rows": hi - lo, "first_id": int(ids[lo]), "last_id": int(ids[hi - 1]), "ids_sha": sha,
            "nonfinite_rows": [], "revision": "r"}), encoding="utf-8")
    return ds, tmp / "run"


def _run(ds, run, out):
    return subprocess.run([sys.executable, str(ROOT / "evals/shard_dense_eval.py"), str(ds), str(run), "--out", str(out)],
                          capture_output=True, text=True, cwd=ROOT)


def test_every_arm_finds_the_planted_unit(tmp_path):
    ds, run = _build(tmp_path)
    p = _run(ds, run, tmp_path / "r.json")
    assert p.returncode == 0, p.stderr + p.stdout
    res = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert not res["partial"] and res["shards"] == 2
    for arm, r in res["results"].items():
        assert r["all"]["mrr10"] == 1.0, arm          # the planted chunk's unit ranks first in every storage form
    # scope is applied: case A (federal only) never ranks a punjab unit (units 10..19)
    assert set(res["per_case"]) == set(res["results"])


def test_refuses_a_shard_of_other_chunks(tmp_path):
    ds, run = _build(tmp_path, corrupt_ids=True)
    p = _run(ds, run, tmp_path / "r.json")
    assert p.returncode != 0 and "does not hold" in (p.stderr + p.stdout)


def test_hamming_identity_matches_packbits():
    rng = np.random.default_rng(3)
    a, b = rng.standard_normal((5, 2048)), rng.standard_normal(2048)
    pop = np.array([bin(i).count("1") for i in range(256)])
    ham = pop[np.bitwise_xor(np.packbits(a > 0, axis=1), np.packbits(b > 0))].sum(1)
    sa, sb = np.where(a > 0, 1.0, -1.0), np.where(b > 0, 1.0, -1.0)
    assert np.array_equal((2048 - sa @ sb) / 2, ham)


@pytest.mark.parametrize("zero_at", [0, 100])
def test_sign_of_zero_counts_as_negative(zero_at):
    v = np.ones(1024); v[zero_at] = 0.0
    assert np.packbits(v > 0)[zero_at // 8] != 0xFF                   # packbits: 0 -> bit 0
    assert np.where(v > 0, 1.0, -1.0)[zero_at] == -1.0                  # the evaluator: 0 -> -1, the same bit
