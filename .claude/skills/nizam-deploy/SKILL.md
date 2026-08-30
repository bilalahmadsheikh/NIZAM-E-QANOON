---
name: nizam-deploy
description: Rules for running Nizam-e-Qanoon — the local development environment, the one-time corpus build job, Postgres configuration, the four-stage hosting ladder, provider selection and pricing, the consumption model, capacity per host, cost of ownership, scaling triggers and operations. Load when setting up a machine, sizing hardware, choosing a host, quoting a cost, configuring Postgres, or planning a deployment or migration.
---

# Nizam-e-Qanoon — environments and deployment

**Reference:** `docs/09a-local-environment.html` · `docs/09b-production-deployment.html` · `docs/03a-capacity-plan.html`
**Intent:** Build the production database locally at full scale, then move it as a restore rather than a rebuild. Size for memory and disk, not cores.

## There is one machine and one job

**Parsing the corpus is a job, not a machine profile.** It runs three or four times in the project's entire life.

| | Developer machine | Build job |
|---|---|---|
| Who | Everyone, daily | One person, a few times ever |
| Does | Restores a physical backup | Parses 4,710 statutes + ~120k judgments |
| RAM | **16 GB comfortable**, 8 GB for client work | 16 GB enough, 32 faster |
| Disk | ~35 GB | ~120 GB |
| Where | Your laptop | **Rent it** — a box for a day is ~€2 |

Developers **never parse anything**. They restore a **physical** pgBackRest backup — indexes arrive already built, so no HNSW rebuild: statutes ~280 MB in under a minute; full corpus ~3.5 GB in ~6 minutes. `pg_restore` would rebuild indexes and take 4 and 50 minutes respectively.

Production parses **deltas only** — 20–50 gazette documents a week, one small worker.

## Sizing: memory and disk, not cores

At **50,000 MAU** the system needs **well under one core at peak** but ~10 GB of hot index. Source documents live in R2, not on the server, so production disk is ~47 GB, not 130.

Production requirement is **~14 GB RAM**. RAM buys **latency, not correctness** — at 16 GB, ~60% of the corpus stays hot and answer p95 is ~260 ms against a 4 s budget. Every RAM tier answers identically.

Capacity: **a single €21–40 VPS comfortably carries 50,000–100,000 MAU** and does not bind until past 250,000. At 250k the machine is ~€40 and the model calls are ~$2,400 — **you run out of money before you run out of server**, which makes deflection a capacity strategy, not an optimisation.

## The hosting ladder — moving rungs changes a connection string, not the schema

0. **Local Docker** — full corpus, every extension, `pg_search` for a real BM25 baseline. Do not develop against a 500 MB ceiling.
1. **Managed free tier** — federal statutes only (248 MB against 500 MB). Bind the `tsvector` implementation and **measure the ranking delta** against the local baseline; that number is a thesis result.
2. **Self-hosted node** — when case law lands. Restore from R2, widen published scope, rebind `pg_search`.
3. **Scale** — vertical first, then partition judgments by court and year.

**Managed Postgres hosts the database, not the system.** Inference workers, ingest workers, the LaTeX sandbox and the staging filesystem still need a host — so the managed path is two hosts and two bills, with the public internet between the API and every query.

## Prices change — these did, twice, during this project

Hetzner raised cloud prices ~2.1–2.75× in June 2026; Oracle halved Always Free to 2 OCPU / 12 GB with over-limit instances terminated from 18 Aug 2026. **Never quote a figure from memory.** Re-verify before ordering or before putting a number in a document.

## Postgres configuration is computed, not copied

Size `shared_buffers` to the **working set**, not to 25% of host RAM — that is an OLTP rule and this is a small hot index over a large cold corpus. Developer machine: 2 GB. Production: 6–8 GB.

Bulk-load profile is separate and reverted afterwards: `maintenance_work_mem` 8 GB, `max_wal_size` 16 GB, `synchronous_commit` off, autovacuum off on the four large tables. **Build indexes last** — building before the load turns a 45-minute HNSW build into most of a day.

## Parity is what makes the move a restore

Pinned image digest · extension versions asserted by a migration · identical `lc_collate` · identical Postgres major version (a physical restore cannot cross one) · golden set green on the target before traffic moves · **a completed restore drill**.

**pgAdmin is a viewer and a terrible source of truth.** Every schema object comes from a migration in git, or the move stops being a restore.

## Operations minimum

pgBackRest to R2 — weekly full, daily incremental, continuous WAL, 14-day window. This replaces the $100/month managed PITR add-on. **Monthly restore drill with the golden set run against the restored copy** — a backup nobody has restored is a hypothesis, and the drill doubles as the migration rehearsal.

Dedicated hardware has no snapshot and no live resize: the RAID pair and the off-box backup are load-bearing, not belt-and-braces.

## Verify online before you claim

- **Every price and free-tier limit**, every time. Hetzner, Contabo, Netcup, Supabase, Neon, Oracle, Cloudflare R2.
- **Extension availability on a candidate managed host** before assuming a migration is possible.
- **arm64 support** for `pg_search`, pgvector and ONNX Runtime before ordering an ARM instance — verify on the laptop first, not after.

Delegate to the `vendor-verifier` agent rather than quoting from memory.

## Common failures

- Sizing every laptop for a job that runs three times.
- `pgdata` on a Windows-mounted path under WSL2 — the 9p bridge makes HNSW builds 5–10× slower.
- Quoting a 2025 price in 2026.
- Buying cores when the constraint is RAM.
- Reaching for Kubernetes. One node, Docker Compose, pgBackRest.
