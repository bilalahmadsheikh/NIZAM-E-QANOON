# Local environment

> **Setting up a new machine? Start with [SETUP.md](../SETUP.md).** This file is
> the reference — what each piece does and why it is the way it is.

Everything here is driven by one command from the repository root:

```
./nz up          start the database, migrate, verify     (.\nz.ps1 up from PowerShell)
./nz status      what is running and what is in it
./nz extract     run L1 extraction over the corpus
./nz test        unit tests + the environment self test
./nz export      one portable dump + sha256 + manifest for a teammate
./nz restore     restore a snapshot or an export (checked)
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
The October–November recrawls and the ICT, AJK and GB landings went through
`tools/recrawl/` and `land_missing.py` instead. On 17 Nov 2026 the database holds
10,394 official observations over 10,188 distinct blobs, with 66 declared
acquisition exceptions. Failed, missing, recovered and repeated official
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
`SNAPSHOT_BUDGET_GB` total (25). The statutory corpus now dumps to ~0.62 GB, so
eight snapshots are ~5 GB. Retention prunes only `<db>-*.dump` at the top of
the folder. It never removes interrupted `.partial-*` dumps, and those have to be
cleared by hand.

**Retention once removed prune evidence.** The archive dumps of prune batches 3 and
4 (9 Sep) were ordinary snapshots and were rotated away. Any archive a
`revision_archive_batch` row names must live outside the snapshot rotation, as
`E:\nizam-data\archives\prune-2026-11-11\` does for batch 5.

At judgment scale, replace this with pgBackRest incrementals, which ship only
changed blocks — doc 09a §1.1 already specifies physical backup for that reason.
The `snapshot` / `restore` interface stays the same.

```bash
bash infra/scripts/snapshot.sh          # now, if anything changed
bash infra/scripts/snapshot.sh --force  # now, regardless
bash infra/scripts/export.sh            # a portable folder for a teammate (./nz export)
bash infra/scripts/export-physical.sh   # a byte-exact cluster copy (./nz export --physical)
bash infra/scripts/restore-physical.sh --verify exports/physical-<stamp>   # prove an exact copy
bash infra/scripts/restore.sh --list    # what is available
bash infra/scripts/restore.sh           # restore the newest snapshot of nizam_clean
bash infra/scripts/restore.sh exports/<name>/<name>.dump   # restore an export
```

A teammate who has the repo and Docker runs `./nz up`. They copy an export folder
into `snapshots/exports/` and run `./nz restore exports/<name>/<name>.dump`;
they never parse a PDF. `restore` checks the dump's sha256 and refuses a dump
made from a different database. A bare `restore` once picked `latest.dump`, the
retired `nizam` database's 6 Sep snapshot, and would have rolled `nizam_clean`
back two months. It then recomputes the corpus signature
(`scripts/corpus-signature.sql`) and compares it with the export's
`manifest.json`.

**Why snapshots and not a rebuilt Docker image.** Image layers are immutable and
content-addressed, so every database change would rewrite and re-push the whole
thing as a new layer: 4.8 GB today, more once judgments land, with no
incremental. Doc 09a §1.1 is explicit that the corpus ships as a backup someone
restores, not as an image they pull. This is that, automated. It is also the same
procedure that recovers the database after a mistake, which is why 09a wants it
exercised weekly rather than discovered during an incident.

---

## Everything on E:

| What | Where | Size |
|---|---|---|
| Ubuntu disk — Docker images, containers, **pgdata** (6.4 GB of it) | `E:\wsl\Ubuntu\ext4.vhdx` | grows with pgdata |
| Source blobs | `E:\nizam-data\raw\` | 23 GB |
| Snapshots | `E:\nizam-data\snapshots\` | 13.5 GB on 17 Nov, ~6 GB of it interrupted `.partial-*` dumps |
| Prune archives | `E:\nizam-data\archives\` | 2.0 GB |
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
| `scripts/export.sh` | Portable dump + sha256 + manifest under `snapshots/exports/` |
| `scripts/export-physical.sh` | Byte-exact cluster copy (`pg_basebackup`) + checksums + manifest |
| `scripts/restore-physical.sh` | Restore an exact copy into the pgdata volume, or `--verify` it in a throwaway container |
| `scripts/restore.sh` | Restore a snapshot or export: sha256, source-database and signature checks |
| `scripts/corpus-signature.sql` | The one-line corpus signature export and restore compare |
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

Counts measured 17 November 2026. "Total" includes retired revisions, which
the prune workflow may archive.

| Table | Holds | Rows | Migration |
|---|---|---|---|
| `source_observation` | What a portal exposed, when — URL, status, hash | 10,394 | 0001 |
| `blob` | Bytes, identified by SHA-256 | 10,188 | 0002 |
| `document` | A blob read as text, in one language | 11,326 total / 10,188 active | 0002, 0012 |
| `page` | Per page: size, character count, extraction lane | 153,929 total / 134,983 active | 0002 |
| `text_block` | The raw text with `{page, bbox, reading_order, script}` | 2,843,446 total / 2,249,286 active | 0002 |
| `extraction_attempt` | Every extraction try, successful or not | 12,198 | 0003 |
| **`instrument`** | **The legal work: jurisdiction + kind + number + year + expression ordinal** | **13,685 total / 10,486 active; 10,339 released, 147 linked duplicates** | **0004, 0012, 0036, 0040** |
| **`provision`** | **THE CITABLE UNIT (INV-4) — a tree, not a list** | **1,803,643 total / 1,197,584 active; 1,172,566 released** | **0004, 0012** |
| **`provision_version`** | **That provision as at a date (INV-5)** | **1,720,412** | **0004** |
| `segmentation_run` | Every retained segmentation attempt | 66,597 | 0004 |
| `provision_ancestor` | Disposable closure of real active provision parentage | 3,242,502 | 0018, 0027 |
| `segmentation_structural_candidate` / `_adjudication` | Source-anchored S7 decisions and their append-only resolutions | 5,519 / 4,334; 0 pending in release | 0035, 0036 |
| `instrument_identity_resolution` | Full-tree SHA-256 proof for exact legal-expression identity | 632 | 0036 |
| `segmentation_boundary_candidate` | Source-evidenced internal-boundary history | 61; 0 pending | 0038 |
| `instrument_expression_manifest` | Versioned source spans for legal expressions in a PDF | 1,119 total / 476 active | 0040 |
| `instrument_revision_archive_manifest` | Recoverable proof for archived superseded derived revisions | 51,834 | 0034, prune workflow |
| `instrument_metadata_assertion` | Dated, sourced assertions: titles, dates, status, extent | ~56,000 | 0070, extended through 0095 |
| `statutory_repeal` / `territorial_repeal` | Repeals read from the repealing law's own text | 199 / 47 | 0066, 0095 |
| `consolidated_twin` | As-made Gazette text linked to its consolidated text | 51 | 0075 |
| `mv_instrument_serving` / `mv_provision_text_known_from` | The serving snapshot `operative_provision` reads | 10,288 / 1,156,469 | 0094, 0096–0099 |

Your own corpus is why the ladder exists. The Penal Code sits at **two paths** in
the federal archive under **one SHA-256** — one blob, two observations. Punjab
publishes **its own copy** with a **different SHA-256** — two blobs, two
documents, and (per doc 03b §3) *two legitimate instruments*, because a federal
Act and its provincial adaptation are different law.

### Views to work from

| View | For |
|---|---|
| **`operative_provision`** | **The only application read of law.** Requires `SET nzq.as_of`; optional `SET nzq.territory`. Serves each law where it runs, as at the date, with currency and `text_known_from` |
| `v_instrument_currency` | Per law: current / not current / historical, with the reason and territory exits |
| `v_document` | Curation/current-state documents by published title, year and URL — active, but not the application release boundary |
| `v_extract_queue` | What still needs extracting, and why the last attempt failed |
| `v_corpus_health` | Pages, characters and printable ratio per jurisdiction |
| **`v_provision`** | **Curation/current-state provisions with currently-operative text; production uses the release views below** |
| `v_segmentation_health` | Instruments, provisions and mean ToC agreement per jurisdiction |
| `v_instrument_duplicates` | Citations claimed by more than one document — the identity-resolution queue |
| `v_structural_adjudication_pending` | Exact source-anchored S7 review queue; corrective decisions block until replayed |
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

Acquisition is explicit rather than silently “finished”: 10,394 observations
over 10,188 distinct blobs, and 66 catalogue items are declared acquisition
exceptions with dated attempts and the observed error (C1). Failed, missing and
recovered attempts remain in their ledgers.

### Extraction lanes

Of the 10,188 active documents, 8,212 are born-digital (E2), 171 are mixed (E3)
and 1,805 are OCR (E4). New laws that would need OCR are not landed for now
(owner rule, 14 Nov 2026): 874 AJK and 151 Gilgit-Baltistan scans wait.
`SELECT * FROM v_extract_queue` is the work list.

### Segmentation, and how it is checked

Doc 02 §5 requires the law be parsed, not window-chunked, and names the
acceptance test: reconciliation against the document's own printed table of
contents. Of the active, non-duplicate laws, 3,881 have a contents list the
latest run compared against:

```
mean agreement   0.9974        median  1.0000
exact            3,799 / 3,881  (97.9%)
>= 0.95          3,834 / 3,881  (98.8%)
```

Every run is recorded in `segmentation_run` with its missing and extra labels.

## What exists now, and what does not

As of 17 Nov 2026: PostgreSQL 17.11 with pgvector 0.8 and pg_search 0.25.6, 101
migrations, and 10,339 released laws served through `operative_provision`. All
40 audit criteria pass. Retrieval indexing (the `chunk` table, BM25, then
embeddings) is the next engineering slice. It must read only released law
through `operative_provision`. See `docs/CORPUS-STATE-2026-11-17.md`.
