---
name: nizam-generation
description: Rules for the Nizam-e-Qanoon generation and grounding layer (L4) — the provider port, structured output with citation identifiers only, DB-rendered citations, the three-tier entailment verifier, the unauthorised-practice register guard, semantic caching, precomputed explainers and the offline answer tier. Load when writing prompts, LLM adapters, answer schemas, verification, or anything that produces text a user will read as legal information.
---

# Nizam-e-Qanoon — generation and grounding

**Reference:** `docs/05-generation-and-grounding.html` · `docs/01-master-architecture.html` Figure 14
**Intent:** Make the model untrustworthy by design. Two components exist purely so that what a reader sees as a quotation was never produced by a model.

## The model never emits a citation

Structured output only. The model returns **citation identifiers**; the renderer substitutes authoritative text from L2 afterwards.

```json
{ "abstain": false,
  "blocks": [
    { "text": "…", "cites": [{ "provision": "pk:fed/act/1860-45/s-302/cl-a", "span": [0, 84] }] }
  ],
  "caveats": ["…"], "followups": ["…"] }
```

- **Every block carries ≥1 citation.** A block without one is dropped before rendering — a schema rule, not a prompt request.
- **An unresolved identifier drops the block and logs a defect.** Fabricated citations are structurally unreachable.
- **Spans point into the retrieved provision text**, which is what makes verification possible.

Forbidden output: any section number, article number, case citation, SRO number, statute date or URL. All rendered from records.

## The verification cascade

| Tier | Method | Runs on |
|---|---|---|
| Cheap | Numeric and lexical overlap — every number, date, duration and amount in the claim must appear in the span | Every block. Catches the most damaging error class: wrong sentence lengths, wrong fines |
| Standard | Cross-lingual NLI, span as premise, claim as hypothesis | Every block. Below threshold → flagged with a visible qualifier, not silently kept |
| Strict | Second model call as adversarial judge, prompted to refute | Claims touching criminal liability or limitation; and the full evaluation run |

**The measured pass rate of this verifier *is* our faithfulness number.** Computed continuously in production, not once for a thesis.

## Register, not just disclaimers

Under the Legal Practitioners and Bar Councils Act only licensed advocates may practise law. The output register is **"the law provides X"**, never **"you should do X"** — enforced at prompt level *and* checked by an output classifier. Never recommend a course of action in the user's own matter.

Never present a machine translation of a statute as the statute. Urdu output is explanation; the enacted English text is shown verbatim alongside.

## The provider port

`ILLMProvider` is the **only** place a vendor SDK may appear. Routing: lookup/explain → hosted small model with cached prefix; scenario/draft → reasoning tier; sovereign/demo → self-hosted open weights with LoRA; offline → no generation, stored artefacts only.

## Cost control is a product feature, not an optimisation

At 50k MAU the server is ~€21/month and the model calls are ~€480. **Deflection is the primary lever on unit economics.**

- Prompt-prefix caching on the static system prompt, schema and few-shots
- Semantic response cache keyed on intent + jurisdiction + `as_of`
- **Precomputed explainers** per provision, batch-generated and verified once
- **The offline answer tier** — ~12k canonical questions with stored verified answers, ~12 MB. Generation happened earlier, on better hardware, and was verified before it shipped.

`stored_answer` carries `CHECK (verifier_score >= 0.97)` — an answer that did not clear the threshold **cannot be inserted**. And `cited_provisions` drives `INVALIDATE` on amendment, so answers and law cannot drift apart.

## Verify online before you claim

- **Model pricing, context limits and IDs** — always via the `claude-api` skill for Anthropic; never from memory.
- **Provider rate limits and concurrency** before sizing a batch job.
- Never publish a claim about hallucination rates without our own measurement on our own golden set.

## Common failures

- A prompt asking the model to "cite accurately". Citations are not the model's job at all.
- Free-text output parsed with a regex instead of a validated schema.
- Verification implemented as a prompt instruction rather than a pipeline stage.
- A fallback that answers from model knowledge when retrieval abstained. That path must not exist.
- Claiming "zero hallucination". The defensible claim is that fabricated citations are structurally impossible and the rest is measured (ADR-6).
