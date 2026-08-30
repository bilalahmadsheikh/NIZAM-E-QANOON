---
name: nizam-invariants
description: The five system invariants and architecture decision records that govern ALL Nizam-e-Qanoon work. Load this before writing or reviewing any code, schema, prompt, endpoint or screen in this project — it is the rule set every layer inherits. Triggers on any work touching provisions, citations, retrieval, answers, abstention, as_of dates, repealed law, offline packs, or anything in docs/.
---

# Nizam-e-Qanoon — system invariants

**Reference:** `docs/01-master-architecture.html` §0.3 (invariants), §4.1 (interface contracts), Appendix B (ADR index)
**Intent:** These are rejection criteria, not preferences. A design that violates one is wrong regardless of how well it performs or how elegant it looks. Reviewers should reject on this basis alone.

## The five invariants

| | Rule | What it forbids |
|---|---|---|
| **INV-1** | No generated citation | Section numbers, article numbers, case citations, SRO numbers, statute dates and URLs are **rendered from database records**. The model emits identifiers only. Any code that builds a citation string from parts is a defect. |
| **INV-2** | No answer without a passing gate | There is **no code path** from an abstained retrieval to a generated answer. L3 returns `GroundingContext | Abstention` — a two-valued return. Never add a third. Never lower τ to produce an answer. |
| **INV-3** | Every answer is replayable | Persist query, resolved filters, retrieved provision IDs with scores, gate decision, prompt hash, model version, verifier result — for every response. |
| **INV-4** | Provisions are the citable unit | Nothing above L2 may reference a chunk identifier. Re-chunking must never invalidate a stored citation, bookmark or generated document. |
| **INV-5** | Law is answered as at a date | Every retrieval carries `as_of`, defaulting to today. No query path may read `provision_version` without a validity filter. Read `operative_provision`, never the base table. |

## Layer dependency rule

`L1 corpus → L2 storage → L3 retrieval → L4 generation → L5 services → L6 API → L7 clients`

A layer may call **only the layer immediately below it**, plus the shared inference worker. An import-linter config in CI enforces this; a violation fails the build, not review. Cross-cutting concerns (09 platform, 10 evaluation, 11 security, 12 design) constrain every layer but own none.

## Decisions already made — do not relitigate

- **ADR-1** one Postgres for relational, vector, lexical and graph. No second datastore.
- **ADR-1a** hosting is a four-stage ladder; lexical search sits behind `ILexicalSearch` so the host stays swappable.
- **ADR-1d** vectors stored binary-quantised as `bit(1024)`; precision recovered by the cross-encoder reading text.
- **ADR-2** fine-tune the retriever and reranker, not the answer model. Generation goes through a provider port.
- **ADR-4** direct cross-lingual retrieval — no translate-search-translate pipeline.
- **ADR-6** attributed generation with a **measured** faithfulness rate. Never claim "zero hallucination".
- **ADR-7** bitemporal provisions; the GiST exclusion constraint is the enforcement.
- **ADR-10** provision is the canonical citable unit; chunks are derived.

## Verify online before you claim

Never state any of the following from memory — they have all changed during this project:

- **Vendor pricing and free-tier limits.** Hetzner raised cloud prices ~2.5× in June 2026; Oracle halved its Always Free tier in 2026. Search before quoting a figure.
- **Extension capabilities.** `pgvector` binary quantisation semantics, ParadeDB `pg_search` availability per platform and architecture.
- **Model pricing and context limits.** Use the `claude-api` skill for anything Anthropic-related.
- **Pakistani statutory status.** Whether an Act has been amended, repealed, or declared repugnant is a live question — never assert it from training data. Delegate to the `legal-source-scout` agent.

## Common failures to watch for

- A helper that formats `f"s.{num} {act}"` — that is INV-1 violated.
- A retry path that re-runs retrieval with a lower threshold after an abstention — INV-2.
- A repository read that omits `as_of` — INV-5.
- Presenting a machine translation of a statute as the statute. Urdu is explanation; the enacted text is shown verbatim.
- Marketing or thesis copy asserting hallucination is "impossible". The defensible claim is that fabricated *citations* are structurally unreachable, and everything else is measured.
