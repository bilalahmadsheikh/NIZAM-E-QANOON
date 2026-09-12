# Nizam-e-Qanoon

Pakistan's first intelligent legal infrastructure — a bilingual, offline-capable platform over the
statutory corpus and judicial precedent of the federation and four provinces. Final Year Project,
GIKI FCSE, four developers.

**Current state: L1 extraction and L2 base segmentation are built and measured; L2 production qualification remains open, and L3 upward has not started.** Sixteen documents
in `docs/` fix the architecture, and where implementation has diverged the docs carry an "as built"
correction rather than a quiet edit. The corpus lives in Postgres: 4,596 documents, 63,878 pages,
128,654,015 characters, 4,695 active expressions and 517,171 active provisions. `./nz audit`
runs 30 criteria; 29 pass. Only S7 structural adjudication remains red, and the
remaining 1,531 units need source review of documents that print no contents
list — no aggregate can settle them. Acquisition is fully accounted: every
catalogued item either landed or carries a declared, evidence-backed exception. There is no
`chunk`, `embedding`, `legal_edge`, facet or judgment table yet — those are the next layers.

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
| `02-corpus-and-ingestion` | Sources, extraction, segmentation, enrichment, quality gates (§8 as built: 30 criteria) |
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

From the built corpus (`nizam_clean`), measured 11 Sep 2026. These supersede the 28 Aug estimates,
which were scaled from a 144-PDF sample:

- **4,757 effective catalogue items · 4,717 landed (99.16%) · 4,596 distinct blobs · 40 genuinely unresolved**
- **63,878 pages · 128,654,015 extracted characters · 969,053 text blocks**
- **517,171 active provisions from 103,169 sections** — tree expansion **4.99×**, not the 3.2× estimated
- **Statutory corpus on disk: 1,912 MB** after multi-expression materialisation and restore-tested pruning of superseded
  derived trees and removal of 1,563,444 synthetic ancestor-prefix rows. The 744 MB
  estimate in 03a predates `provision_block`, `instrument_toc_entry`, `provision_ancestor` and
  append-only revisions — see 03a §2A. **Supabase's 500 MB free tier no longer holds it**
- **~96% carry a clean text layer** — OCR evidence covers 106 documents and remains a fallback, not a pillar
- Character evidence against an independent extractor: **minimum recall 0.9991600; minimum precision 0.9976800 under the accepted evidence policy**
- Contents agreement: **median 1.0000**, with **1,988 canonical gaps across 607 expressions**
  (**2,120** when redundant provenance trees are included);
  all active printed entries retain their exact source block/page
- **3,992 expressions / 358,365 provisions** are in the fail-closed legal release;
  **1,533 S7 units across 252 observations** and **1,443 contents gaps** remain blocked.
  `docs/RELEASING-THE-BLOCKED-INSTRUMENTS.md` maps every blocked expression to the repair that
  frees it; `tools/audit/blocked-release-worklist.sql` re-derives it
- Production needs **~14 GB RAM**, well under one core at 50k MAU. RAM buys latency, not correctness
- A single €21–40 VPS carries **50,000–100,000 MAU**; at scale infrastructure is ~3% of the bill

---

## Repo layout

```
docs/          the specification set — the contract, plus SCHEMA.md and CORPUS-CRITERIA.md
nizam/         the package: corpus/ (extract, ocr, segment), storage/, workers/, shared/
infra/         compose file, Postgres image, migrations (0000–0041), scripts
tools/         audit/criteria.sql and state.sql, the corpus browser, diagnostics
tests/         pure-function tests; the segmenter's regressions live here
data/          scrapers + source archives (archives gitignored, 1.6 GB)
.claude/       skills and agents
nz  ·  nz.ps1  one command: up status psql extract ocr verify audit state browse test snapshot
```

Schema lives in migrations in git, never in a GUI. The Postgres image is digest-pinned so a laptop
and the server cannot drift. Commits end with the `Co-Authored-By` trailer; branch before pushing.

Two rules the corpus taught, both after shipping the mistake:

- **Source and decision evidence is append-only.** Re-extracting or re-segmenting first *retires*
  the previous revision (`is_active`, `supersedes_*_id`, `retired_at`). Superseded derived trees may
  be pruned only by the archive-manifest plus restore-proof workflow; current-state queries still
  use active views, and application queries use the narrower release views.
- **A criterion that encodes today's measurement is a tripwire, not a test.** Two were written as
  fixed counts and both failed on healthy data within a day. Assert the rule; report the number.
