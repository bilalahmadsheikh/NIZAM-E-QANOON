# Setting up Nizam-e-Qanoon

From a clean Windows machine to a working legal corpus database. Two paths —
pick the one that matches what you need.

| | You want | Time | You need |
|---|---|---|---|
| **A** | The database, to build against | ~30 min | An export folder from a teammate (624 MB dump, or 1.3 GB exact copy) |
| **B** | To build the corpus from source | many hours | The source archives and recrawl captures |

Almost everyone wants **A**. Doc 09a §1.1 is explicit that the corpus travels as
a restorable backup, not as something each person parses. As built it travels
as either a logical `pg_dump` or a byte-exact cluster copy (09a §1.1, as-built
note). Only the person rebuilding the corpus needs the PDFs.

---

## Prerequisites (both paths)

- **Windows 11**, virtualisation enabled in BIOS
- **~20 GB free** on a drive that is not `C:` if you can manage it (this guide
  uses `E:`)
- **16 GB RAM** is comfortable; 8 GB works for client-side work

### 1. WSL2 with Ubuntu 24.04

```powershell
wsl --install -d Ubuntu
```

`-d Ubuntu` (not `Ubuntu-24.04`) installs the current LTS **and registers it
under the name `Ubuntu`**, which is what every command below and `nz.ps1` expect.
If you already have it under another name, either use that name in place of
`Ubuntu` or set `NIZAM_WSL_DISTRO` before running `nz.ps1`.

Reboot if asked, then open Ubuntu once and create your user. Check it:

```powershell
wsl -l -v          # Ubuntu, VERSION 2, and it should say 24.04 inside
wsl --version      # WSL version 2.x
wsl -d Ubuntu -e lsb_release -d
```

### 2. Put WSL where the space is

The Ubuntu disk holds Docker's images and the database, and it defaults to `C:`.

```powershell
wsl --shutdown
mkdir E:\wsl
wsl --manage Ubuntu --move E:\wsl\Ubuntu
```

### 3. `C:\Users\<you>\.wslconfig`

```ini
[wsl2]
memory=10GB
processors=6
vmIdleTimeout=604800000

[experimental]
autoMemoryReclaim=gradual
sparseVhd=true
```

`vmIdleTimeout` is the one that matters. WSL shuts the VM down after 60 seconds
with no attached session and **does not count running containers as activity** —
without this, your database dies whenever you close the terminal.

Then `wsl --shutdown` once more so it takes effect.

### 4. Clone

```powershell
cd E:\
git clone <repo-url> Nizam_e_Qanoon
```

Put it on the same drive as the WSL disk. `E:\Nizam_e_Qanoon` is `/mnt/e/Nizam_e_Qanoon`
inside WSL.

---

## Path A — I just want the database

```powershell
wsl -d Ubuntu
```
```bash
cd /mnt/e/Nizam_e_Qanoon
./nz bootstrap
```

`bootstrap` installs Docker Engine, installs `uv`, generates `infra/.env` with
fresh passwords, starts Postgres + pgAdmin + MinIO, verifies the cluster against
doc 03 §1, and applies the migrations.

It will stop once, after installing Docker, and tell you to run `wsl --shutdown`
from PowerShell. That is not an error — Linux group membership needs a new
session. Reopen WSL and run `./nz bootstrap` again.

There are two ways to get the database from a teammate. Both carry everything:
every table and row (old revisions and evidence included), every view and
materialized view, every function, trigger, foreign key and index, the
extensions and the migration history. Both were tested on 17 Nov 2026 by
restoring into a scratch copy, comparing the corpus signature and passing all
39 audit criteria.

| | **Dump** (`./nz export`) — recommended | **Exact copy** (`./nz export --physical`) |
|---|---|---|
| What it is | A logical `pg_dump` of the `nizam_clean` database | A byte-for-byte copy of the whole PostgreSQL cluster (`pg_basebackup`) |
| Size | **624 MB** | **1.3 GB** |
| Restore time | ~6 min (indexes and statistics rebuilt) | **~1 min** (nothing rebuilt) |
| Indexes | rebuilt on arrival, identical definitions | arrive as built |
| Exactness | every row and object identical; physical layout fresh | identical down to the disk pages, planner statistics included |
| Receiver needs | the repo + `./nz up` | the repo + `./nz up`, the **same image digest** and CPU type (x86-64) |
| Replaces | only the `nizam_clean` database | the **whole cluster**; their old database is gone |

Use the **dump** normally: it is half the size, works on any machine with the
repo, and cannot clobber anything but `nizam_clean`. Use the **exact copy** when
you want the receiving machine to be literally the same database, for example
before moving to the production server.

**Dump.** Your teammate runs:

```bash
./nz export
# -> E:\nizam-data\snapshots\exports\nizam_clean-<stamp>\
#      nizam_clean-<stamp>.dump          the whole database, compressed
#      nizam_clean-<stamp>.dump.sha256   checksum
#      manifest.json                     git commit, image digest, corpus signature
```

They send you the whole folder (USB drive, Google Drive, anything). Check out the
commit named in `manifest.json` (`git checkout <git_commit>`) so the migrations
and tools match the data, run `./nz up`, copy the folder into
`E:\nizam-data\snapshots\exports\` and:

```bash
./nz restore exports/nizam_clean-<stamp>/nizam_clean-<stamp>.dump
```

`restore` checks the sha256 and refuses a dump taken from another database. It
restores in one transaction, gathering statistics before it rebuilds the serving
views, and then recomputes the corpus signature, which must equal the one in
`manifest.json`.

**Exact copy.** Your teammate runs:

```bash
./nz export --physical
# -> E:\nizam-data\snapshots\exports\physical-<stamp>\
#      base.tar.gz  pg_wal.tar.gz  backup_manifest  SHA256SUMS  manifest.json
```

You check out the commit from `manifest.json`, run `./nz up` once (this creates
the container and its volume), copy the folder into
`E:\nizam-data\snapshots\exports\`, and:

```bash
./nz restore --physical --verify exports/physical-<stamp>   # optional: prove it in a throwaway container first
./nz restore --physical exports/physical-<stamp>            # replace your cluster with it
```

The restore checks every checksum, the image digest and the CPU architecture
before touching anything. It then stops Postgres and pgAdmin, swaps in the copy,
starts them, and sets the login password back to the one in *your*
`infra/.env` (the copy carries the sender's). Last, it compares the signature.

Either way, `./nz audit` afterwards should report all 40 criteria passing.

Done. You have the corpus without parsing a single PDF. The source PDFs (23 GB
under `E:\nizam-data\raw`) are only needed for re-extraction and for the page
images in `./nz browse`; copy that folder too if you want either.

---

## Path B — build the corpus from source

Same bootstrap, but you need `data/*.zip` first (the five scraper archives,
~1.6 GB — they are deliberately not in git). Put them in `E:\Nizam_e_Qanoon\data\`.

```bash
cd /mnt/e/Nizam_e_Qanoon
./nz bootstrap        # also lands the PDFs into E:\nizam-data\raw
./nz extract --all    # the ~4,600 documents of the original five archives
```

That rebuilds only the August baseline. More than half of today's 10,339 laws
came later. They came from the October–November portal recrawls and the ICT,
AJK and GB landings (`tools/recrawl/`, `tools/acquire/`, `land_missing.py`),
followed by the recorders in `tools/post_replay_sequence.sh`. Replaying all of
that is not a one-command job, so use path A unless you are changing the parser.

`bootstrap` runs the landing tool, which reads the archives without modifying
them and promotes the bytes to a content-addressed store, verifying every hash
against what the scrapers recorded.

Then export it so nobody else has to repeat it:

```bash
./nz export
```

Hand them the folder it prints.

---

## The one command

Everything runs through `./nz` from WSL, or `.\nz.ps1` from PowerShell.

```
./nz up            start the database, migrate, verify
./nz status        what is running and what is in the database
./nz psql          a SQL prompt
./nz extract       run L1 extraction  (--all, --source pk-federal, --limit N)
./nz browse        read the corpus: PDF beside extracted text
./nz verify        cross-check the database against the source PDFs
./nz verify-clean  run all four verifier families against the nizam_clean candidate
./nz audit-clean   run every corpus release criterion against nizam_clean
./nz state-clean   report nizam_clean completeness and quality percentages
./nz test          unit tests + the environment self test
./nz test-clean    the same environment self test against nizam_clean
./nz snapshot      snapshot now (automatic every 15 min after a change)
./nz export        one portable dump + sha256 + manifest for a teammate
./nz export --physical         byte-exact copy of the whole cluster
./nz restore       restore the newest snapshot of nizam_clean, or a named one/export
./nz restore --physical [--verify] exports/physical-<stamp>   restore (or prove) an exact copy
./nz logs          follow container logs
./nz down          stop (your data is kept)
./nz bootstrap     a fresh machine, from nothing
```

Day to day it is `./nz up` in the morning and nothing else.

`nizam_clean` is the only corpus database (`POSTGRES_DB=nizam_clean` in
`infra/.env`). The old `nizam` database no longer exists; dumps named
`nizam-2026…` in the snapshot folder are its September copies, and `restore`
refuses them.

### Keep it running after you close the terminal

```powershell
powershell -ExecutionPolicy Bypass -File infra\wsl\keepalive.ps1 -Install
```

Registers a logon task that holds a WSL session open and starts the stack. Remove
it with `-Uninstall`.

---

## Seeing the database

**The corpus browser — `./nz browse`, then http://localhost:5055.** Purpose-built
for reading law: the source PDF on the left, the extracted text on the right, both
jumping to the same page. `/schema` shows every table, key and index live from the
catalog. Read-only. See [tools/corpus-browser/README.md](tools/corpus-browser/README.md).

**pgAdmin — http://localhost:5050.** The server is pre-registered; expand
`Nizam` → `nizam_clean` → `Schemas` → `public` → `Tables`.

**Your own pgAdmin, DBeaver or psql:** host `localhost`, port **5433**, database
`nizam_clean`, user `nizam`, password from `infra/.env`.

> Port 5433, not 5432 — Windows often already runs a PostgreSQL service on 5432.

Some queries worth knowing:

```sql
-- the law as it reads today in Punjab: the only way application code reads law.
-- as_of is required (INV-5); territory is optional (punjab sindh kp balochistan ict ajk gb)
SET nzq.as_of = '2026-11-17';
SET nzq.territory = 'punjab';
SELECT jurisdiction, instrument_title, label, heading, currency, left(text_en, 80)
  FROM operative_provision
 WHERE instrument_title ILIKE 'Pakistan Penal Code%'
   AND provision_kind = 'section' AND label = '302';
-- two rows: Punjab's own copy of the Code and the federal text, both in force there

-- find a statute by name
SELECT document_id, title, year, page_count FROM v_document
WHERE title ILIKE '%penal code%';

-- the law itself, as extracted, with page coordinates
-- section 302 of the Penal Code, found by name rather than a hard-coded id
SELECT b.page_no, left(b.text, 200)
  FROM text_block b
  JOIN v_document v ON v.document_id = b.document_id
 WHERE v.title ILIKE 'Pakistan Penal Code%'
   AND b.page_no >= 30            -- pages 1-29 are the printed contents list
   AND b.text LIKE '302.%'
 ORDER BY b.reading_order;

-- what still needs extracting, and why the last attempt failed
SELECT source_id, title, last_outcome, left(last_reason, 80) FROM v_extract_queue LIMIT 20;

-- corpus health per jurisdiction
SELECT * FROM v_corpus_health;
```

**pgAdmin is for inspection only** (doc 09a §2). Never create a table or index in
it — schema comes from `infra/postgres/migrations/` and nothing else, or the
server and your laptop stop being the same thing.

---

## What is where

| | |
|---|---|
| `E:\wsl\Ubuntu\ext4.vhdx` | Ubuntu, Docker images, **the database** |
| `E:\nizam-data\raw\` | Source PDF blobs, content-addressed (23 GB) |
| `E:\nizam-data\snapshots\` | Database snapshots, taken automatically |
| `E:\nizam-data\snapshots\exports\` | `./nz export` folders, kept outside snapshot retention |
| `E:\Nizam_e_Qanoon\` | This repository |

The database lives in a Docker named volume inside the Ubuntu ext4 disk, never on
a Windows path. Doc 09a §1.2: the 9p bridge is roughly ten times slower for many
small files, and every index operation is random I/O.

---

## When something is wrong

| Symptom | Fix |
|---|---|
| `cannot reach the docker daemon` | `sudo systemctl start docker`. If `groups` lacks `docker`, `wsl --shutdown` and reopen. |
| Database gone after closing the terminal | Install the keepalive task, above. |
| `docker` found but nothing works | WSL puts the Windows PATH on yours, so a bare `docker` can hit Docker Desktop's CLI. `which docker` must say `/usr/bin/docker`. |
| Port 5432 already in use | Expected — we use 5433. Leave the Windows PostgreSQL service alone. |
| pgAdmin restarting | Check `PGADMIN_EMAIL`; pgAdmin rejects reserved TLDs like `.local`. |
| Docker Desktop errors | We don't use it. Docker Engine runs inside WSL, which is what the server runs too. |

Full reference and the reasoning behind each choice: [infra/README.md](infra/README.md).

---

## What exists today (17 Nov 2026)

- **PostgreSQL 17.11** (ParadeDB image, digest-pinned) with pgvector, pg_search,
  ltree, btree_gist, pg_trgm and pgcrypto: the same stack the VPS will run
- **10,339 laws released, none held**: federal, the four provinces, ICT, AJK and
  Gilgit-Baltistan. 1,172,566 released provisions over 134,982 pages
- **Every law answered as at a date and in a territory** through
  `operative_provision` (`SET nzq.as_of`, optionally `SET nzq.territory`), with
  in-force status, dates, extent and repeals recorded
- **40 audit criteria, all passing**; 103 migrations
- **A 4.8 GB database that exports to a 624 MB dump or a 1.3 GB exact copy**, plus automatic snapshots
  that fire only after a real change settles
- **Golden sets 1–4**: 200 evaluation cases with text-checked answers

Not built yet: the retrieval layer (chunks, embeddings, search indexes) and
everything above it. The current state and the next step are in
[docs/CORPUS-STATE-2026-11-17.md](docs/CORPUS-STATE-2026-11-17.md); run
`./nz audit` and `./nz state` for measured truth.
