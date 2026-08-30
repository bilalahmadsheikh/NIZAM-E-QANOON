# Nizam-e-Qanoon

Pakistan's first intelligent legal infrastructure — a bilingual, offline-capable platform over the
statutory corpus and judicial precedent of the federation and four provinces. Final Year Project,
GIKI FCSE, four developers.

**Current state: the specification set is complete; application code has not started.** Sixteen
documents in `docs/` fix the architecture. `data/` holds the scrapers and 1.6 GB of source archives
(gitignored). There is no `nizam/` package yet — the first one written should follow §8 of doc 01.

---

## How to work here

**Build one small component at a time, completely, before starting the next.**

This is the standing rule, and it overrides any instinct to sketch the whole system. A prompt that
names several things is a prompt to decompose, pick the first slice, and take it all the way to done —
not to produce nine half-built files.

- Depth over breadth, always. One finished parser beats an outline of seven modules.
- Finish means finished: it runs, it is tested, it enforces the invariants it touches, and its
  behaviour matches the doc it came from.
- Work in dependency order. L1 corpus → L2 storage → L3 retrieval → L4 generation → L5 services →
  L6 API → L7 clients. Building L3 against a corpus that is not yet trustworthy wastes both.
- If the next step is unclear, say so and pick the smallest defensible slice rather than widening.

The full procedure — decomposition, definition of done, when to stop — is in the `nizam-workflow`
skill. Load it when implementing anything.

**Every decision traces to a document.** Cite the doc and section when you make one (`docs/03 §2.3`).
If the docs do not cover it, say so explicitly rather than inventing a convention — then propose one
and record it. The documents are the contract; code that contradicts them is a defect in one or the
other, and which one is a decision, not an accident.

**Never assert an external fact from memory.** Vendor prices, free-tier limits, extension
availability, model pricing, and the current status of any Pakistani statute are all things that
changed during this project and were quoted wrongly at first. Verify, or delegate to
`legal-source-scout` / `vendor-verifier`.

---

## The five invariants

These are rejection criteria. A design that violates one is wrong regardless of how well it performs.

| | Rule |
|---|---|
| **INV-1** | **No generated citation.** Section numbers, article numbers, case citations, dates and URLs are rendered from database records. The model emits identifiers only. |
| **INV-2** | **No answer without a passing gate.** `retrieve()` returns `GroundingContext \| Abstention` — two-valued. No third return, no retry at a lower threshold, no fallback to model knowledge. |
| **INV-3** | **Every answer is replayable.** Query, filters, retrieved IDs with scores, gate decision, prompt hash, model version, verifier result — persisted for every response. |
| **INV-4** | **Provisions are the citable unit.** No chunk identifier above L2. Re-chunking must never break a stored citation. |
| **INV-5** | **Law is answered as at a date.** Every retrieval carries `as_of`. Read `operative_provision`, never the base table. |

Layer rule: a layer calls **only** the layer immediately below it, plus the shared inference worker.

---

## The documents

| Doc | Covers |
|---|---|
| `01-master-architecture` | Layers, domain model, interface contracts, 20 UML/C4 views, ADR index |
| `02-corpus-and-ingestion` | Sources, extraction, segmentation, enrichment, the seven QA gates |
| `03-data-and-storage` | Schema, extensions, indexes, publish transaction, migrations |
| `03a-capacity-plan` | Measured corpus sizing, free-tier analysis, hosting ladder |
| `03b-legal-data-model` | 14 legal edge types, 9 facets, schedules as tables, SQLite projection |
| `04-retrieval` | Query understanding, candidates, fusion, rerank, the gate |
| `05-generation-and-grounding` | Provider port, typed answers, verification cascade, offline answers |
| `06-domain-services` | Citator, limitation engine, calculators, document factory, procedures |
| `07-backend-api` | HTTP contract, identity, orchestration, audit, sync engines, SLOs |
| `08-client-architecture` | Four surfaces, seven sublayers, offline pack, bidi, accessibility |
| `09a-local-environment` | Machine requirements, the one-time build job, bootstrap |
| `09b-production-deployment` | Consumption model, provider pricing, capacity, operations |
| `10-evaluation-and-quality` | Golden set, metrics, ablations, CI gates |
| `11-security-and-privacy` | Classification, threat model, anonymous proof, RLS, evidence integrity |
| `12-design-system` | Stamp-paper palette, Spectral/Karla, spacing, components |
| `13-ux-and-interaction-architecture` | Journeys, answer anatomy, uncertainty, voice, content system |

Skills mirror these: `nizam-invariants` (always), `nizam-corpus`, `nizam-database`,
`nizam-retrieval`, `nizam-generation`, `nizam-services`, `nizam-api`, `nizam-client`,
`nizam-security`, `nizam-design`, `nizam-ux`, `nizam-evals`, `nizam-deploy`, `nizam-workflow`.

Agents: `legal-source-scout`, `vendor-verifier`, `grounding-reviewer`, `schema-reviewer`,
`corpus-auditor`, `client-reviewer`, `eval-runner`.

---

## Measured facts — do not re-derive

From `data/`, measured 28 Aug 2026:

- **4,710 PDFs · 1,857 MB · 243 MB extracted text · 113,158 top-level sections**
- **~96% carry a clean text layer** — OCR is a ~150-document fallback, not a pillar
- Legal text compresses **4.17×**; federal corpus has 1,030 paths but **982 unique SHA-256**
- Full statutory corpus in Postgres with indexes: **~744 MB**. With case law: **~10 GB**
- Production needs **~14 GB RAM**, well under one core at 50k MAU. RAM buys latency, not correctness
- A single €21–40 VPS carries **50,000–100,000 MAU**; at scale infrastructure is ~3% of the bill

---

## Repo layout

```
docs/          the specification set — the contract
data/          scrapers + source archives (archives gitignored, 1.6 GB)
design/        design canvas working files
.claude/       skills and agents
```

Schema lives in migrations in git, never in a GUI. The Postgres image is digest-pinned so a laptop
and the server cannot drift. Commits end with the `Co-Authored-By` trailer; branch before pushing.
