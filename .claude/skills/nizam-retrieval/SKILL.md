---
name: nizam-retrieval
description: Rules for the Nizam-e-Qanoon retrieval layer (L3) — query understanding, the citation fast path, Roman Urdu handling, the four parallel candidate generators, reciprocal rank fusion, cross-encoder reranking, the calibrated abstention gate, and context assembly. Load when working on search, ranking, the gate, threshold calibration, query parsing, or anything that decides what reaches the model.
---

# Nizam-e-Qanoon — retrieval

**Reference:** `docs/04-retrieval.html` · `docs/01-master-architecture.html` Figure 12 (DFD level 2)
**Intent:** Retrieval quality sets the ceiling on everything downstream. A perfect generator on bad context produces a confident wrong answer; a mediocre generator on perfect context produces a useful one.

## The contract

```
retrieve(QuerySpec) → GroundingContext | Abstention
```

**Two-valued. Never add a third.** This is INV-2 expressed as a type signature and it is the single most load-bearing line in the interface table.

## Stage 0 — resolve before you search

- **Citation grammar first.** `s.302 PPC`, `section 9(c) CNSA`, `Art 184(3)`, `PLD 2016 SC 1`, `SRO 745(I)/2023` → direct fetch, ~5 ms, 100% precision, **no model involved**. Roughly a quarter of professional queries.
- **Jurisdiction is a hard filter.** Punjab rent law and Sindh rent law are different statutes. Returning the wrong province is a wrong answer, not a near miss.
- **`as_of` defaults to today** and filters version validity on every path (INV-5).
- **Roman Urdu is first-class.** Transliteration normalisation plus a curated alias index (~400–600 concepts × Urdu / romanised / English). Most Pakistanis type Urdu in Latin script; a system that handles `طلاق` but not `talaq` or `talak` fails the majority of its users on the first keystroke.

## Stage 1 — four generators, optimise for recall only

BM25 lexical · dense vector · **definition expansion** · **graph expansion**. Target ~150 candidates. Precision is the reranker's job.

Graph expansion is what a pure embedding system cannot do: ask about s.302 and you need s.299 (definitions), s.304 (proof), s.311. No encoder retrieves those; the cross-reference graph does, for free.

## Stage 2 — RRF, not score normalisation

```
score(d) = Σ 1 / (k + rank_r(d))      k = 60
```

BM25 scores and cosine similarities are not commensurable. Any hand-tuned weighting between them is overfitted to whatever queries you happened to test. RRF uses rank position only, needs no tuning, and is robust when one retriever fails badly on a given query.

## Stage 3 — the reranker must be small

A 560M-parameter cross-encoder reranking 50 pairs costs ~**3.3 core-seconds** per query on CPU — nine times the rest of the pipeline combined, and enough to make CPU the binding constraint. A fine-tuned MiniLM-class cross-encoder does the same job at ~0.15. Since ADR-2 already commits to fine-tuning the reranker, training the small one is strictly better: domain adaptation *and* a twentieth of the latency.

## Stage 4 — the gate

Two conditions, both **calibrated on held-out data**, never hand-set:

- Absolute threshold τ chosen for a target precision (start at 95%)
- Coverage: each identified sub-question needs a passing provision, or the answer is partial and says so

Below threshold: abstain with a specific message, offer nearest non-passing results **visibly separated** from an answer. **Abstention rate is a headline metric we publish, not a failure we hide.** A system that never abstains is guessing.

## Stage 5 — assembly

Never hand the model a half-section. Expand each passing chunk to its **full parent provision**, attach act title, chapter heading, in-force dates and any repeal or amendment warning. Order by statutory sequence, not by score — a model reads law better in its own order.

## Verify online before you claim

- **Reranker and embedding model options** — sizes, licences and multilingual coverage move quickly. Confirm before committing to a checkpoint.
- **Binary-quantisation recall behaviour** for the specific model in use; the 32× compression claim needs an ablation on our golden set, not a citation.
- Anything Anthropic-related goes through the `claude-api` skill.

## Common failures

- Adding a retry that lowers τ after an abstention. That is INV-2 violated and it is the most tempting bug in the system.
- Weighting BM25 against cosine scores directly.
- Reranking 150 candidates instead of ~50 when latency is the complaint — cut candidates before adding hardware.
- Returning a clause without its section, or a proviso without what it qualifies.
- Treating Roman Urdu as a nice-to-have rather than the primary input path for citizen queries.
