---
name: nizam-evals
description: Rules for Nizam-e-Qanoon evaluation and quality — the golden set and its strata, graded relevance and inter-annotator agreement, retrieval and gate metrics, attribution and faithfulness measurement, bilingual parity, red-team suites, statistical decision rules, and the CI gates that block a merge. Load when writing tests, running benchmarks, reporting a metric, tuning a threshold, or making any quality claim.
---

# Nizam-e-Qanoon — evaluation and quality

**Reference:** `docs/10-evaluation-and-quality.html`
**Intent:** Nothing can be tuned, thresholded or defended without the instrument. Build it before the thing it measures. Pakistan has no public legal IR benchmark, so the golden set is publishable on its own.

## The golden set

**500 queries**, stratified:

| Stratum | Share |
|---|---|
| Citizen scenario | 40% |
| Professional lookup | 25% |
| Procedural | 15% |
| Urdu / Roman Urdu | 10% |
| **Deliberately unanswerable from our corpus** | **10%** |

That last stratum is the one everyone forgets and **the only way to measure abstention honestly**. Without it a system that always answers looks perfect.

- Graded relevance 0–3 over **provisions**, annotated by two people independently, with **Cohen's κ reported**. If agreement is poor the metric is noise — better to know in week 4.
- Frozen test split, never used for tuning. Separate dev split for threshold calibration and reranker training.
- Annotated by all four team members together — that session is also how everyone learns the domain.

## Metrics and what each one catches

| Layer | Metric | Target | Catches |
|---|---|---|---|
| Corpus | Segmentation F1 on 100 hand-labelled instruments | ≥0.97 | The base rate for everything downstream |
| Retrieval | NDCG@10 · Recall@50 · MRR@10 | ≥0.75 · ≥0.90 · ≥0.70 | Wrong or missing law reaching the model |
| Gate | Abstention precision / recall on the unanswerable stratum | ≥0.90 / ≥0.85 | Confident answers with no legal basis |
| Grounding | Span-entailment pass rate | ≥0.97 | Claims that overreach their source |
| Citation | Resolution / applicability | 1.00 / ≥0.95 | Resolution is 1.00 by construction; applicability needs human review |
| Temporal | Point-in-time accuracy on 50 known amendments | ≥0.95 | Serving the wrong version of a section |
| **Bilingual** | **NDCG gap between paired Urdu and English queries** | **≤0.05** | **Whether the equity claim is actually true** |
| Latency | p50 / p95 | <1.5 s / <4 s | A correct system nobody waits for |

**Bilingual parity is the metric worth putting in the thesis.** It is a direct, honest measure of whether the equity claim holds, and no competitor reports anything like it.

## Ablations that make the argument

Each isolates one architectural claim and each is a figure:

- BM25 only → dense only → hybrid → + rerank → + graph expansion
- Off-the-shelf reranker vs fine-tuned — **this is the fine-tuning contribution, quantified**
- Gate on vs off, on the unanswerable stratum — **the anti-hallucination claim, quantified**
- Translation-pipeline CLIR vs direct cross-lingual retrieval — tests ADR-4 rather than assuming it
- Full-precision vs `halfvec(384)` vs `bit(1024)` — required before binary quantisation ships (ADR-1d). If binary costs more than 2 NDCG points after reranking, fall back and narrow corpus scope.

## CI gates

The golden set runs on **every change to retrieval, prompts or the corpus**. A regression in NDCG@10 or faithfulness **blocks the merge**, regardless of who wrote it. The red-team suite is a CI test suite, not a one-off exercise.

Also gated: APK size, cold start, frame budget, public-page byte budget, contract diff against the OpenAPI spec, import-linter layer boundaries.

## Report honestly

- State confidence intervals. A 3-point NDCG difference on 500 queries may be noise.
- Report the **abstention rate** as a headline number, not a footnote.
- Report coverage alongside any precedent metric — missing judgments must never read as "no precedent".
- Never publish a hallucination-rate claim that is not our own measurement on our own held-out data.

## Verify online before you claim

- **Metric definitions and significance tests** — do not recall a formula for NDCG discount or a paired bootstrap; check it.
- **Comparable published benchmarks** before positioning our numbers against anyone else's.
- Any external hallucination or legal-IR study cited in the thesis: verify the figure and the sample before repeating it.

## Common failures

- Tuning on the test split.
- Dropping the unanswerable stratum because it "lowers the score".
- Reporting a single number without agreement statistics or an interval.
- Measuring retrieval on queries the corpus was built from.
- Treating a CI gate as advisory.
