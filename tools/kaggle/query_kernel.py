"""Kaggle kernel: the DEV questions encoded at full precision by each bake-off model (D-098).

The bake-off (embed_kernel.py) scored full precision and sign-bit binary; it did not keep the float query vectors.
The binary-vs-full ablation (ADR-1d) also needs a third arm -- Hamming shortlist, then the FLOAT query scored against
the stored +-1 bits (asymmetric rescoring: no float corpus vector is kept, docs/03) -- and that is scored locally
against the run's bits.npy. This kernel only encodes the 108 dev questions, in dev.json order, with each model at the
revision and query template its bake-off run recorded (substituted by kg.sh querypush from the runs' metrics.json).
CPU only; TEST questions are never exported (docs/10).

Writes /kaggle/working/q-<slug>.npy (float32 [n, 1024], unit length) and queries.json (slug -> model, revision,
template, n).
"""
import glob
import json
import time

import numpy as np
from sentence_transformers import SentenceTransformer

SPECS = json.loads('__SPECS__')   # [{"slug", "model", "revision", "query_template"}], from the runs' metrics.json
dev = json.load(open(glob.glob("/kaggle/input/**/dev.json", recursive=True)[0], encoding="utf-8"))
out = {}
for s in SPECS:
    t = time.time()
    m = SentenceTransformer(s["model"], device="cpu", revision=s["revision"])
    m.max_seq_length = 512
    qv = m.encode([s["query_template"].format(q=c["q"]) for c in dev], batch_size=16, normalize_embeddings=True,
                  convert_to_numpy=True)[:, :1024].astype(np.float32)
    assert np.isfinite(qv).all()
    np.save(f"/kaggle/working/q-{s['slug']}.npy", qv)
    out[s["slug"]] = {**s, "n": len(dev), "cases": [c["case"] for c in dev], "seconds": round(time.time() - t)}
    print(s["slug"], qv.shape, out[s["slug"]]["seconds"], "s", flush=True)
    del m
json.dump(out, open("/kaggle/working/queries.json", "w"), indent=1)
print("done")
