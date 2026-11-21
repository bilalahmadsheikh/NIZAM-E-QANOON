# Retrieval (L3) state — 21 November 2026

L3 is closed for the statute book. Every stage in docs/04 that the current data can support is built, measured and
recorded. The next decision belongs to the owner: what to do with the held-back sources (docs/DEFERRED-SOURCES.md,
D-100). After that comes L4. Figures below are provisional in one respect: golden sets 1–10 are text-checked drafts,
and inter-annotator agreement (κ) is not yet measured (D-095, D-104).

## What L4 receives

```
retrieve(question, Filters(as_of, territory | jurisdictions)) -> GroundingContext | Abstention
```

The function is two-valued (INV-2). There is no third return and no retry at a lower threshold.
`nizam/retrieval/gate.py: retrieve()`, docs/04 §11.1.

**`Abstention`** carries:
- a code from docs/04 §8.1: insufficient evidence, the jurisdiction unresolved, time or source out of scope, records,
  statistics or live figures, or retrieval degraded;
- a public reason and suggestions;
- the nearest units, to be shown apart from any answer;
- the gate's record.

**`GroundingContext`** carries:

| field | what it holds |
|---|---|
| `query` | the parsed question: citations, territory, lexical words, script, Urdu gloss, sub-questions |
| `items` | the gate's bundle (unit, version, scores): what the gate judged (INV-3) |
| `confidence`, `threshold`, `gate` | the calibrated probability, τ, mode, features and decision |
| `evidence` | the assembled packet, in legal order (docs/04 §7) |
| `coverage` | what was admitted, what was skipped and why, sub-questions with their lexical support, and what is not built |
| `conflicts` | `{prevails, over, kind, said_by}`: one admitted unit "notwithstanding" or "subject to" another |
| `trace`, `degraded` | the retrieval trace, and the mode if degraded |

Each item in `evidence` carries:
- a whole citable unit (INV-4), or a definition with its sub-items;
- a citation rendered by the server's rule (INV-1);
- its Part and Chapter, and the law's status and dates at `as_of`;
- its printed amendment notes, and the instruments made under it;
- its source sha256 and pages, and the reason it was included.

Everything is read through `operative_provision` at `as_of` and in the territory (INV-5): 0 violations on every
measured run.

## The pipeline as built

1. **Query understanding.** A text is read for:
   - its citations (fast path, 224/224 golden citations resolve, none wrong, D-097);
   - places in English and Urdu script (D-109);
   - the legal alias index for Urdu and Roman Urdu (D-105, D-109);
   - sub-questions (D-110).
2. **Candidates.**
   - BM25 windows over `operative_provision`, collapsed to units (D-095, D-097).
   - Dense, in one of two spaces:
     - bge-m3 sign bits on the CPU (D-098);
     - Qwen3-Embedding-8B bits with halfvec rescoring on the GPU host (D-099).
   - Fusion: the CPU profile fuses BM25 and dense; the GPU profile takes citations, then dense (D-101).
3. **Reranking** (D-101).
   - GPU: Qwen3-Reranker-8B, 50 units at 1,600 characters.
   - CPU: int8 mMiniLM, 10 units at 800 characters, the most that fits 1 s on a 6-core host.
4. **The gate** (D-102, D-106, refit D-111).
   - Scope vetoes first: time, source, place, records, statistics, live figures.
   - Then a logistic classifier per mode, calibrated on dev for 0.95 answered precision. The `unreranked` mode uses
     the 0.90 fallback.
5. **Assembly** (D-107, D-108, D-110), within a 50,000-character budget:
   - whole units;
   - their definitions in scope, including the parent Act's and the jurisdiction's General Clauses Act;
   - qualifications, references and schedules;
   - provisions that prevail over them;
   - conflicts and sub-questions recorded.
6. **Derived link tables** (D-108, linker `nizam.links/9`): 166k references and 72k scoped definitions, rebuilt from
   the release. Audit A23 checks them.

## Measured (test split scored once per decision)

| stage | measure | GPU profile | CPU profile | source |
|---|---|---|---|---|
| candidates | recall@50 (hybrid / served slate) | .951 | .743 | D-099, D-098 |
| reranking | NDCG@10 | .531 → **.775** | .376 → .449 | D-101 |
| gate | answered precision (passed) | **.944** [.898, .971] (162 of 195) | .909 [.804, .961] (55) | D-111 |
| gate | coverage of answerable questions | .925 | .316 | D-111 |
| gate | unanswerable recall (L3 scope) | .952 (1.0) | 1.0 | D-111 |
| gate | degraded `unreranked` mode | — | 20 pass, all correct | D-111 |
| assembly | necessary units in the packet | .912 → .929 | — | D-107 |
| assembly | relevant units in the packet | .556 → .630 | — | D-107 |
| assembly | additions read correct | 39/40 | — | D-108 |
| vectors | binary vs float after reranking (ADR-1d) | not re-measured | +0.6 [−1.7, +2.9] NDCG: binary stays | D-112 |

On dev after today's repairs (D-110), GPU assembly keeps .942 of necessary units (none lost) and .457 of relevant
units. CPU keeps .620.

**Latency, this laptop:**
- hybrid candidates p50 0.8–1.0 s and p95 1.0–1.5 s;
- CPU rerank p50 about 680 ms;
- assembly p50 155 ms and p95 243 ms on GPU bundles.

No end-to-end figure has been measured as one number. The 8B reranker on a Kaggle T4 (a proxy, not the serving host)
takes 4.5 s for 10 passages.

## Against docs/10's targets

**Met on the GPU profile:**
- NDCG@10 ≥ 0.75 (.775);
- recall@50 ≥ 0.90 (.951);
- unanswerable recall ≥ 0.85 (.952);
- answered precision at the 0.95 target within its interval (.944).

**Not met:**
- the CPU profile's ranking (NDCG .449) and recall (.743);
- the CPU gate's 0.95 target (.909 point estimate; the interval contains 0.95);
- strict abstention precision ≥ 0.90 (GPU .61);
- docs/04 §9's ≤ 25 ms for validate, assemble and gate (assembly alone is about 155 ms here).

The CPU profile is the offline and low-cost path. Its limits are recorded, not hidden: it abstains where it cannot meet
precision.

## Open, in the order they bite

1. **The serving host.** The 8B reranker's latency and the CPU reranker's depth must be measured on real hardware
   (D-101). ADR-1d re-runs for bge-m3 if the CPU reranker reads deeper (D-112).
2. **Abstention precision** (strict .61 on GPU). Most extra abstentions are answerable questions the gate is unsure
   of. This needs annotated gold, not tuning.
3. **Golden-set annotation and κ** (docs/10 §4). Until then every figure is provisional, and fine-tuning the reranker
   (ADR-2) waits.
4. **Coverage per sub-question.** Sub-questions are split and traced, but no verdict is drawn (D-110). It needs
   multi-issue gold and a calibrated judge.
5. **Corpus queue from D-110:**
   - 6625: false rules likely;
   - 3712: the print's own numbering is off from s.15;
   - 7416, 8481, 9315: OCR label misreads;
   - notes left in the text of five laws.

   The other corpus defects in the decision log's open list also stand: the Constitution's Chapter 3A, merged
   definition nodes, and flattened sub-items.
6. **Not built:**
   - matched-span offsets;
   - Urdu-script definitions;
   - the General Clauses Acts of Sindh, Balochistan, AJK and GB (not held);
   - the authority, treatment and delegated-instrument vetoes (they need judgments).
7. **The held-back sources** (D-100): FBR, SECP and PSX drops, the AJK and GB scans, and about 69k judgments. This is
   the owner's decision, and it comes next.

## How to re-measure

```
./nz audit                                                   # 45 criteria, all pass on 21 Nov
.venv/bin/python -m pytest -q tests                          # dots only on this host; exit 0 = pass
.venv/bin/python evals/gate_features.py --split dev          # all modes; GPU needs replayed vectors and scores
.venv/bin/python evals/gate_fit.py --features <dev file>     # dev only; writes nizam/retrieval/gate_calibration.json
.venv/bin/python evals/gate_eval.py --split test --features <test file>   # ONCE per frozen calibration
.venv/bin/python evals/assembly_eval.py --split dev --features <dev file>
.venv/bin/python evals/adr1d_eval.py <export dir> <Kaggle run dir>        # ADR-1d, after a float run
```

- After any replay, run in order: the full `tools/post_replay_sequence.sh`, then `nizam.workers.links --apply`, the
  8B top-up (`tools/embed_topup.py`, Kaggle, `load_embeddings_gpu.py --topup`), the golden builders
  (`evals/golden/build_set*.py`), and finally the audit.
- A replay re-identifies provisions, so gate features and golden ids must follow it (D-110, D-111).

## What changed on 21 November

- **D-110:** conflicts, sub-questions, lead-in definition scope, and the rejected budget reservation. Footnote false
  sections were repaired in seven laws, including the CrPC and the General Clauses Act 1897; "Federal Government" and
  "Provincial Government" now have their own units. Two worker fixes: the links worker's stale check runs in seconds,
  and it sweeps read-marks that left the release.
- **D-111:** the gate refitted on the repaired corpus.
- **D-112:** ADR-1d after reranking; the CPU generation keeps its sign bits.
