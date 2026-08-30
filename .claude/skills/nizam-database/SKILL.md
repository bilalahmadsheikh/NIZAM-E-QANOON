---
name: nizam-database
description: Rules for the Nizam-e-Qanoon data and storage layer (L2) — Postgres schema, extensions, the bitemporal exclusion constraint, ltree provision paths, binary-quantised vectors and HNSW, BM25 versus tsvector, the publish transaction, partitioning, RLS, migrations and recovery, and the SQLite offline-pack projection. Load when writing DDL, migrations, indexes, queries, or anything touching the database or the mobile pack schema.
---

# Nizam-e-Qanoon — data and storage

**Reference:** `docs/03-data-and-storage.html` (schema, indexes, publish) · `docs/03a-capacity-plan.html` (sizing, hosting) · `docs/03b-legal-data-model.html` §6–7 (edges, facets, SQLite projection)
**Intent:** Make temporal and referential correctness properties of the schema, so a buggy ingest run fails loudly at commit rather than corrupting the corpus quietly.

## Extensions — each earns its place by making something impossible

`vector` (pgvector) · `pg_search` (ParadeDB BM25) · `ltree` · `btree_gist` · `pg_trgm`

A migration **asserts** extension versions, `server_version_num` and `lc_collate`, and raises on mismatch. A different collation silently changes index ordering and text comparison — genuinely nasty to diagnose after the fact.

## The four lines that carry INV-5

```sql
CONSTRAINT no_overlap EXCLUDE USING gist (
  provision_id WITH =,
  validity     WITH &&
)
```

Overlapping validity intervals for one provision become **impossible to insert**. This is why SQLite was rejected as a *server* engine despite matching the mobile pack — it has no `EXCLUDE`.

## Storage decisions that are already settled

- **Chunks store offsets** (`version_id, char_start, char_end`), never a second copy of the text. Saves ~158 MB at statutory scale, ~2 GB with judgments.
- **`bit(1024)` is a column, not an expression index.** pgvector's documented pattern keeps the full-precision vector in the table and only shrinks the index — the table still pays 4,104 bytes/row. We store the bits directly (136 B) and **do not retain full precision**, because rescoring happens at the cross-encoder over text, never in the database.
- **The tsvector column is not materialised.** Index the expression; halves the full-text cost, identical to query.
- **Re-embedding is a rebuild, never an update.** Two embedding generations in one index is silently wrong. `TRUNCATE chunk`, re-embed, rebuild HNSW.

## Reads go through a view, never a table

`operative_provision` filters repeal, commencement, judicial invalidation and territorial extent in one place. Retrieval is granted access to the view only — a provision that is repealed, uncommenced, struck down or out-of-extent **cannot appear in a result set**, not because the code remembered to filter but because the view already did.

## The publish transaction

One transaction per instrument. Upsert unpublished → replace provision tree → insert versions (the exclusion constraint fires here on a bad amendment resolution) → insert edges and chunks → **`DELETE stored_answer WHERE cited_provisions && changed`** → set `published = true` and bump `corpus_version` → commit.

There is **no second write path** into the live index. `REVOKE INSERT, UPDATE, DELETE` on corpus tables from the application role.

## Partition judgments; do not partition statutes

Partition when a table is large **and** queries filter on the partition key. Judgments (4.8M paragraph rows, date-bounded queries) meet both. Provisions (362k rows, filtered by validity and ltree path) meet neither, and partitioning them would complicate the exclusion constraint for nothing.

## Migrations discipline

- Every object comes from a migration in git. A schema created in pgAdmin is reproducible nowhere.
- `CREATE INDEX CONCURRENTLY` in production — a plain create takes `ACCESS EXCLUSIVE`.
- Backfills are separate from schema changes: add column → deploy → backfill in batches → add constraint.
- `FORCE ROW LEVEL SECURITY`, not just `ENABLE` — without it policies are bypassed for the table owner, which is the role a migration is likely to use.

## SQLite pack is a projection, not a parallel design

Same identities, fewer enforcement mechanisms, because the server enforced them before export. `ltree` → TEXT path + prefix index; `daterange` + EXCLUDE → two TEXT columns **verified at build time**; `bit(1024)` → sqlite-vec float[384] (different model, different space — label it); `pg_search` → FTS5 with `content=''`.

**Guard columns are the trick:** the server evaluates repeal, commencement, invalidation and extent at build time and writes two integers. The device does one indexed comparison instead of four correlated subqueries. They are as-at the pack build date — which is why every offline view is stamped with the pack version.

## Verify online before you claim

- **pgvector release notes** before relying on quantisation, `halfvec`, iterative scans or HNSW dimension ceilings.
- **ParadeDB `pg_search`** availability per host and architecture, and its licence, before assuming it is installable.
- **Managed-platform extension allow-lists** — no managed Postgres permits `pg_search`; confirm rather than assume for any new candidate host.

## Common failures

- Reading `provision` instead of `operative_provision`.
- A migration that rewrites millions of rows inside one transaction, holding locks for the duration.
- Assuming a physical restore can cross a Postgres major version. It cannot — that needs a dump.
- Sizing `shared_buffers` at 25% of host RAM. That is an OLTP rule; this is a small hot index over a large cold corpus.
