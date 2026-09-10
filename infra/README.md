# Local environment

> **Setting up a new machine? Start with [SETUP.md](../SETUP.md).** This file is
> the reference — what each piece does and why it is the way it is.

Everything here is driven by one command from the repository root:

```
./nz up          start the database, migrate, verify     (.\nz.ps1 up from PowerShell)
./nz status      what is running and what is in it
./nz extract     run L1 extraction over the corpus
./nz test        unit tests + the 30-check self test
./nz bootstrap   a fresh machine, from nothing
```

Implements Document 09a. One command gets you a PostgreSQL identical to the one
the VPS will run, the corpus loaded, a browser to inspect it, and automatic
snapshots your teammates can restore.

Everything lives on **E:** — the Ubuntu disk, Docker's images and volumes, the
corpus, and the snapshots.

```
                  Windows                        WSL2 Ubuntu 24.04
                                                 (E:\wsl\Ubuntu\ext4.vhdx)
  browser  ──►  localhost:5050  ──────────────►  nizam-pgadmin
  psql     ──►  localhost:5433  ──────────────►  nizam-postgres  ─► pgdata (ext4)
  browser  ──►  localhost:9001  ──────────────►  nizam-minio
                                                       │
  E:\nizam-data\raw        ── /corpus (ro) ────────────┤   immutable source blobs
  E:\nizam-data\snapshots  ── /snapshots ──────────────┘   auto, every 15 min
```

---

## First-time setup

`./nz bootstrap` — it installs Docker Engine and `uv`, generates `infra/.env`,
lands the corpus from `data/`, starts everything and verifies it. The full
walkthrough, including WSL and where to put things, is in
[SETUP.md](../SETUP.md); it is not repeated here so the two cannot drift.

The one step `bootstrap` cannot do for you, because Linux group membership needs
a new session:

```powershell
wsl --shutdown          # after it installs Docker, then run bootstrap again
```

And the one worth doing once, so the database survives closing your terminal:

```powershell
powershell -ExecutionPolicy Bypass -File infra\wsl\keepalive.ps1 -Install
```

### The landing step, for reference

`tools/corpus-land/land.py` reads the five archives in `data/` without modifying
them and promotes the bytes to a content-addressed store. The original 28 August
landing contained 4,710 PDFs and 4,592 unique blobs with zero hash mismatches.
Recovery remained append-only; the current clean database contains 4,716 landed
official observations over 4,595 distinct hashes, while 41 catalogue items
remain unresolved. Failed, missing, recovered and repeated official
observations remain first-class rows as doc 02 §3.1 requires.

---

## Seeing the database

**pgAdmin at [http://localhost:5050](http://localhost:5050)** — the "browse the
whole database" surface. The Nizam server is pre-registered, so it is already in
the tree on first open: schemas, tables, row counts, a SQL editor, query plans,
index sizes.

Doc 09a §2 is deliberate about its role — *"Inspection only — never the source of
schema truth."* Do not create tables or indexes in it. An index made by hand in a
GUI is invisible to git and will not exist on the server, and 09a §7 calls that
"the most common and most damaging drift". Schema changes go in
`infra/postgres/migrations/` and nowhere else.

Also available: **MinIO console at [http://localhost:9001](http://localhost:9001)**
(the local stand-in for Cloudflare R2), and Postgres on **localhost:5433** for
`psql`, DBeaver, or any client — from Windows or WSL, since WSL2 forwards
localhost.

> **Why 5433.** Windows already runs a PostgreSQL 17 service on 5432. It is
> unrelated to this project and cannot host the corpus — `pg_search` has no
> Windows build at all, and `pgvector` needs a Visual Studio toolchain. Leave it
> alone; the container sits on 5433 so the two never collide.

---

## Snapshots: how the corpus travels

A systemd timer ticks every 15 minutes, but **a tick is not a snapshot**. Two
gates have to open first:

| Gate | Test | Why |
|---|---|---|
| **Changed** | at least `SNAPSHOT_MIN_WAL_MB` (default 1 MB) of write-ahead log since the last snapshot | An idle PostgreSQL still nudges the WAL by a few KB — autovacuum, the stats collector, `pg_dump` itself. Comparing positions for *equality* would treat that noise as a change and dump forever. Distance in bytes separates real writes (MBs) from housekeeping (KBs). |
| **Settled** | less than `SNAPSHOT_SETTLE_KB` (default 64 KB) of movement since the *previous tick* | A full corpus ingest writes for hours. Without this, a 15-minute timer would dump the whole database twelve times during that ingest, each dump bigger than the last and every one obsolete before it finished. |

So a three-hour ingest produces **exactly one** snapshot, taken one tick after
the writes stop — not twelve taken during it. An idle laptop produces none.

Retention prunes on whichever limit bites first: `SNAPSHOT_KEEP` files (8) or
`SNAPSHOT_BUDGET_GB` total (25). The budget is the one that matters as the
corpus grows: the statutory corpus dumps to 55 MB, so eight is under half a
gigabyte — but eight snapshots of the judgment corpus would be tens.

At judgment scale, replace this with pgBackRest incrementals, which ship only
changed blocks — doc 09a §1.1 already specifies physical backup for that reason.
The `snapshot` / `restore` interface stays the same.

```bash
bash infra/scripts/snapshot.sh          # now, if anything changed
bash infra/scripts/snapshot.sh --force  # now, regardless
bash infra/scripts/restore.sh --list    # what is available
bash infra/scripts/restore.sh           # restore the newest
```

A teammate who has the repo and Docker runs `up.sh`, drops a `.dump` into
`snapshots/`, and runs `restore.sh`. They never parse a PDF.

**Why snapshots and not a rebuilt Docker image.** Image layers are immutable and
content-addressed, so every database change would rewrite and re-push the whole
thing as a new layer — 744 MB today, ~10 GB once judgments land, with no
incremental. Doc 09a §1.1 is explicit that the corpus ships as a backup someone
restores, not as an image they pull. This is that, automated. It is also the same
procedure that recovers the database after a mistake, which is why 09a wants it
exercised weekly rather than discovered during an incident.

---

## Everything on E:

| What | Where | Size |
|---|---|---|
| Ubuntu disk — Docker images, containers, **pgdata** | `E:\wsl\Ubuntu\ext4.vhdx` | 7.5 GB |
| Source blobs | `E:\nizam-data\raw\` | 1.66 GB |
| Snapshots | `E:\nizam-data\snapshots\` | 473 MB for the current restore-tested build |
| Original archives | `E:\Nizam_e_Qanoon\data\` | 1.57 GB |

Docker's data-root is `/var/lib/docker` *inside* the Ubuntu disk, so images,
volumes and the database are on E: without a single bind mount to a Windows path.
That matters: doc 09a §1.2 is emphatic that `pgdata` must be on ext4 and never on
`/mnt/c` or `/mnt/e`, because the 9p bridge is roughly ten times slower for many
small files and every index operation is random I/O. Source PDFs are fine on
NTFS — they are read sequentially, once.

`D:\DockerData` (5.5 GB) is the old Docker Desktop store and is no longer used.
Safe to delete once you are happy the stack works.

---

## Troubleshooting

**The database stops when I close my terminal.** WSL terminates a distribution
once its last attached session exits, and it does not count running containers as
a reason to stay up. That is what `keepalive.ps1 -Install` fixes — it holds one
session open at logon and starts the stack. `.wslconfig` also sets
`vmIdleTimeout`, but the keepalive is what actually does the work.

**Docker Desktop.** Not used, and on this machine it does not work: 4.41.2
crashes at startup with `running com.docker.build: exit status 1` against WSL
2.6.3. Docker Engine inside Ubuntu is what the VPS will run anyway, so local and
production stop being two different stories. You can leave Desktop installed or
remove it.

**`docker: command not found`, or it talks about WSL integration.** WSL appends
the Windows PATH, so a bare `docker` can resolve to Docker Desktop's CLI at
`/mnt/c/Program Files/...`, which cannot reach anything here. `which docker`
should say `/usr/bin/docker`.

**`permission denied` on the docker socket.** Group membership needs a fresh
session: `wsl --shutdown` from PowerShell, then reopen.

**pgAdmin restarts in a loop.** Check `PGADMIN_EMAIL` — pgAdmin validates it and
refuses reserved TLDs like `.local` outright.

---

## Verify it yourself

```bash
bash infra/scripts/selftest.sh
```

24 checks: containers running; PostgreSQL ≥ 17; collation `en_US.UTF-8`; all five
extensions present *and working* — including that `btree_gist` actually rejects an
overlapping validity interval and pgvector really can binary-quantise and Hamming-
compare; the blob store and `source_observation` populated and internally
consistent; all three ports reachable; pgAdmin answering; the snapshot mechanism
skipping when idle and firing on a write; and Docker's data-root on ext4.

Last run: **24 passed, 0 failed.**

---

## Files

| | |
|---|---|
| `compose.yaml` | Postgres (ParadeDB), pgAdmin, MinIO — all pinned by digest |
| `up.sh` | Start, verify, migrate, load, snapshot |
| `.env.example` | Copy to `.env`, set three passwords |
| `postgres/postgresql.dev.conf` | Developer profile, computed in 09a §4 for 16 GB / 6 cores |
| `postgres/postgresql.bulk.conf` | Ingest profile, 09a §4.1 — not safe to leave on |
| `postgres/verify.sql` | Environment assertions from doc 03 §1 |
| `postgres/migrations/` | Schema. The only place it may come from |
| `pgadmin/servers.json` | Pre-registers the server in the pgAdmin tree |
| `scripts/migrate.sh` | Applies migrations once, refuses a changed one |
| `scripts/snapshot.sh` | WAL-gated dump to E: |
| `scripts/restore.sh` | Restore a snapshot |
| `scripts/selftest.sh` | The 24 checks above |
| `wsl/setup-docker.sh` | Docker Engine + the snapshot timer |
| `wsl/keepalive.ps1` | Keeps WSL and the stack alive at logon |
| `../nz` | The single entry point. `up`, `status`, `extract`, `test`, `bootstrap` |
| `../nz.ps1` | PowerShell wrapper that forwards into WSL |
| `scripts/load-observations.sh` | Loads the landing tool's CSV into `source_observation` |
| `wsl/bootstrap.sh` | **Alternative, not needed.** Installs Postgres natively in WSL without Docker. Do not run it alongside the containers — it creates a second cluster |

---

## What is actually in the database

The identity ladder from doc 02 §7, built one rung at a time. Each rung is a
different thing, and conflating them is the mistake that cannot be undone later.

| Table | Holds | Rows | Migration |
|---|---|---|---|
| `source_observation` | What a portal exposed, when — URL, status, hash | 4,763 | 0001 |
| `blob` | Bytes, identified by SHA-256 | 4,595 | 0002 |
| `document` | A blob read as text, in one language | 4,631 total / 4,595 active | 0002, 0012 |
| `page` | Per page: size, character count, extraction lane | 63,868 total / 63,047 active | 0002 |
| `text_block` | The raw text with `{page, bbox, reading_order, script}` | 968,951 total / 955,153 active | 0002 |
| `extraction_attempt` | Every extraction try, successful or not | 4,724 | 0003 |
| **`instrument`** | **The legal work: jurisdiction + kind + number + year + expression ordinal** | **4,797 total / 4,788 active; 4,679 canonical** | **0004, 0012, 0036, 0040** |
| **`provision`** | **THE CITABLE UNIT (INV-4) — a tree, not a list** | **528,132 total / 512,094 active** | **0004, 0012** |
| **`provision_version`** | **That provision as at a date (INV-5)** | **504,368 total / 488,518 current-active** | **0004** |
| `segmentation_run` | Every retained segmentation attempt | 20,941 | 0004 |
| `provision_ancestor` | Disposable closure of real active provision parentage | 1,208,678 | 0018, 0027 |
| `segmentation_structural_candidate` | Immutable source/page-anchored S7 decisions for retained trees | 7,239 total / 6,684 current canonical-expression items | 0035, 0036 |
| `segmentation_structural_adjudication` | Append-only machine/source/human decisions retained live | 4,498 total / 4,372 current candidates adjudicated | 0035, 0036 |
| `instrument_identity_resolution` | Full-tree SHA-256 proof for exact legal-expression identity | 110 resolutions; 109 active redundant trees | 0036 |
| `segmentation_boundary_candidate` / `segmentation_boundary_adjudication` | Retained source-evidenced internal-boundary history | 42 / 0; 0 current pending | 0038 |
| `instrument_expression_manifest` | Versioned source spans for materialised legal expressions in a PDF | 131 active / 11 retired | 0040 |
| `instrument_revision_archive_manifest` | Recoverable proof for compacted superseded derived revisions | 15,989 | 0034, prune workflow |

Your own corpus is why the ladder exists. The Penal Code sits at **two paths** in
the federal archive under **one SHA-256** — one blob, two observations. Punjab
publishes **its own copy** with a **different SHA-256** — two blobs, two
documents, and (per doc 03b §3) *two legitimate instruments*, because a federal
Act and its provincial adaptation are different law.

### Views to work from

| View | For |
|---|---|
| `v_document` | Curation/current-state documents by published title, year and URL — active, but not the application release boundary |
| `v_extract_queue` | What still needs extracting, and why the last attempt failed |
| `v_corpus_health` | Pages, characters and printable ratio per jurisdiction |
| **`v_provision`** | **Curation/current-state provisions with currently-operative text; production uses the release views below** |
| `v_segmentation_health` | Instruments, provisions and mean ToC agreement per jurisdiction |
| `v_instrument_duplicates` | Citations claimed by more than one document — the identity-resolution queue |
| `v_structural_adjudication_pending` | Exact source-anchored S7 review queue; currently 2,312 items across 406 observations; corrective decisions block until replayed |
| `v_release_document`, `v_release_text_block` | Quality-passed source evidence for application reads |
| `v_release_instrument`, `v_release_provision`, `v_release_provision_version` | Fail-closed legal release; excludes pending S7, incomplete printed contents and unresolved multi-instrument boundaries |

### Structural-review workflow

```bash
# show the exact current queue and application-safe legal scope
./nz state-clean

# append only decisions supported by independent layout/form/table evidence
uv run python tools/adjudicate_structural_candidates.py --apply

# S7 remains red until every candidate is adjudicated and itemization is exact
./nz audit-clean
```

Review remaining rows directly from `v_structural_adjudication_pending` beside
their source PDF pages and append source/human decisions; do not replay them just
to change the counter. Use `--pending-s7` only after a parser improvement that is
intended to change those trees. Use `--documents id,id` for bounded regression
work and `--boundary-changed-from VERSION` to audit body-boundary changes. The
`--include-review` flag is diagnostic only; it is required to replay a
quality-quarantined document and does not promote that document into release.

```sql
-- section 302 of the Penal Code, with its clauses. Canonical paths remain
-- ltree; the active real-provision ancestor closure uses stable B-tree equality
-- instead of duplicate-heavy incremental GiST page splits. Synthetic path
-- identity prefixes are deliberately absent (migration 0027, audit S9).
WITH root AS (
  SELECT p.path FROM v_release_provision p
  JOIN v_release_instrument i ON i.id=p.instrument_id
   WHERE i.short_title ILIKE 'Pakistan Penal Code%'
     AND p.kind='section' AND p.label='302' LIMIT 1)
SELECT p.path::text,p.kind,p.label,p.heading,p.first_page,left(v.text_normalised,70)
  FROM provision_ancestor a
  JOIN v_release_provision p ON p.id=a.provision_id
  LEFT JOIN LATERAL (
       SELECT pv.text_normalised FROM v_release_provision_version pv
        WHERE pv.provision_id=p.id AND pv.validity @> current_date
        ORDER BY lower(pv.validity) DESC LIMIT 1) v ON true
 WHERE a.ancestor_path=(SELECT path FROM root)
 ORDER BY p.path;

SELECT document_id, title, year, page_count FROM v_document
 WHERE title ILIKE '%penal code%';

-- found by name, not a hard-coded id, and skipping the printed contents pages
SELECT b.page_no, left(b.text, 200)
  FROM text_block b JOIN v_document v ON v.document_id = b.document_id
 WHERE v.title ILIKE 'Pakistan Penal Code%' AND b.page_no >= 30
   AND b.text LIKE '302.%' ORDER BY b.reading_order;
```

Acquisition is explicit rather than silently “finished”: 4,716 observations are
landed over 4,595 distinct hashes, with **zero hash mismatches**, and 41 current
catalogue items remain an evidenced recovery queue. Historical failed, missing
and recovered attempts remain in their ledgers.

### The OCR backlog is a query, not a memory

The active corpus contains 4,397 E2 born-digital documents, 99 mixed E3
documents and 99 E4 OCR documents. OCR remains a bounded fallback, but its
review queue is release-blocking rather than hidden by the corpus-wide rate.

| Why it was rejected | Count | Goes to |
|---|---|---|
| No text layer at all — a scan | 93 | lane E4 |
| Some pages blank | 46 | lane E3 |
| Printable ratio below 0.95 | 31 | review |

Concentrated in Balochistan (64) and Sindh (60), where scanned publication is
still common. `SELECT * FROM v_extract_queue` is the work list.

### Segmentation, and how it is checked

Doc 02 §5 requires the law be parsed, not window-chunked, and names the
acceptance test: reconciliation against the document's own printed table of
contents. The latest observation runs detect one in 3,117 observations.

```
mean agreement   0.9771        median  1.0000
exact            2,494 / 3,117  (80.0%)
>= 0.95          2,741 / 3,117  (87.9%)
below 0.50           8 / 3,117  (0.3%)
```

Every run is recorded in `segmentation_run` with its missing and extra labels.
`v_toc_gap` reports 2,120 entries across 623 active provenance trees. After
exact-duplicate exclusion, the canonical fail-closed queue is 1,988 entries
across 607 expressions.

## What exists now, and what does not

The database is real: PostgreSQL 17.11 with pgvector 0.8.4 and pg_search 0.25.6,
the right collation, and 4,763 immutable source-observation ledger rows.
The `nizam/` package implements extraction, verification, segmentation and
append-only legal writing through migration 0041. Multi-expression source spans
are materialised, and S10 is clear. Retrieval indexing is the next engineering
slice, but it must consume only `v_release_provision_version`; S7 and canonical
contents gaps continue as a separate curation queue.
