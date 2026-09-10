# Setting up Nizam-e-Qanoon

From a clean Windows machine to a working legal corpus database. Two paths —
pick the one that matches what you need.

| | You want | Time | You need |
|---|---|---|---|
| **A** | The database, to build against | ~20 min | A snapshot file from a teammate |
| **B** | To build the corpus from source | ~1 hr | The 1.6 GB of source archives |

Almost everyone wants **A**. Doc 09a §1.1 is explicit that the corpus travels as
a restorable backup, not as something each person parses: *"A physical restore is
a file copy... there is no HNSW rebuild on the receiving machine."* Only the
person rebuilding the corpus needs the PDFs.

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

Then drop your teammate's snapshot into `E:\nizam-data\snapshots\` and:

```bash
./nz restore
```

Done. You have the corpus without parsing a single PDF.

---

## Path B — build the corpus from source

Same bootstrap, but you need `data/*.zip` first (the five scraper archives,
~1.6 GB — they are deliberately not in git). Put them in `E:\Nizam_e_Qanoon\data\`.

```bash
cd /mnt/e/Nizam_e_Qanoon
./nz bootstrap        # also lands the PDFs into E:\nizam-data\raw
./nz extract --all    # ~4,600 documents
```

`bootstrap` runs the landing tool, which reads the archives without modifying
them and promotes the bytes to a content-addressed store, verifying every hash
against what the scrapers recorded.

Then take a snapshot so nobody else has to repeat it:

```bash
./nz snapshot --force
```

Hand them the file from `E:\nizam-data\snapshots\`.

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
./nz snapshot      snapshot now
./nz restore       restore the newest snapshot
./nz logs          follow container logs
./nz down          stop (your data is kept)
./nz bootstrap     a fresh machine, from nothing
```

Day to day it is `./nz up` in the morning and nothing else.

`nizam_clean` is currently a rebuild candidate, not the default database. Its
release gates and remaining review queues are recorded in
`docs/CLEAN-REBUILD-REPORT.md`; do not switch or delete `nizam` merely because
the candidate is smaller.

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
`Nizam` → `nizam` → `Schemas` → `public` → `Tables`.

**Your own pgAdmin, DBeaver or psql:** host `localhost`, port **5433**, database
`nizam`, user `nizam`, password from `infra/.env`.

> Port 5433, not 5432 — Windows often already runs a PostgreSQL service on 5432.

Some queries worth knowing:

```sql
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
| `E:\nizam-data\raw\` | Source PDF blobs, content-addressed |
| `E:\nizam-data\snapshots\` | Database snapshots, taken automatically |
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

## What exists today

- **PostgreSQL 17** with pgvector, pg_search, ltree, btree_gist, pg_trgm — the
  same stack the VPS will run, so deployment is a restore, not a rebuild
- **4,595 distinct source PDFs** landed and hash-verified from 4,716 official
  observations; 41 catalog items remain genuinely unresolved
- **4,595/4,595 active documents extracted** — 63,047 pages, 128,636,469
  characters and 955,153 active text blocks with page coordinates
- **4,788 active legal expressions** — 512,094 active provisions and 488,518
  active versions; 4,668 observations are segmented and another 48 are
  explicitly `unstructured`
- **1,764,095,667-byte `nizam_clean` database** after restore-tested archival
  pruning; nine retired identity-proof endpoints remain
- **Automatic snapshots** that fire only after a real change settles

Extraction and block/character accounting close exactly for acquired blobs.
Base segmentation is populated and citation labels are unambiguous, but corpus
qualification is not complete: S7 has 2,312 pending structural decisions across
406 observations and 1,988 canonical contents/body gaps affect 607 expressions
(2,120 gaps when redundant provenance trees are also counted).
The reviewed multi-instrument set is materialised and S10 is zero. The
fail-closed legal views currently release 3,720 instruments, 300,137 provisions
and 285,156 versions. Run `./nz audit` and `./nz state` for measured truth; the
next build step is release-view-only retrieval segmentation while S7/contents
curation continues—not first-time PDF extraction.
