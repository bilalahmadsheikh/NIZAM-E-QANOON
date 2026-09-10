# Corpus browser

Read the corpus the way a lawyer would: the **source PDF on the left, the text we
extracted on the right**, on the same page, jumping to the same page number.

pgAdmin is the right tool for inspecting a schema and the wrong one for reading a
statute. It shows only the first line of a multi-line cell — so `text_block`
rows look empty when they are not — it has no idea that page 106 of a PDF is the
thing you want to compare against, and it cannot show you both at once.

```bash
./nz browse            # then open http://localhost:5055
```

From PowerShell: `.\nz.ps1 browse`. Add a port if 5055 is taken: `./nz browse 5060`.

---

## What it serves

| Route | What you get |
|---|---|
| `/` | Every document. Search titles, filter by jurisdiction and lane. Pages, characters, quality, OCR flags. |
| `/doc/<id>` | **PDF beside extracted text.** Type a page number and both panes jump there. |
| `/doc/<id>.txt` | The whole document as plain text with `[page N]` markers — for diffing, printing, or piping anywhere. |
| `/schema` | Every table, column, key, index, view and enum, read live from the catalog. |
| `/blob/<sha256>` | The source PDF itself, inline. |

## It reads the database, not a cache

This was checked rather than assumed. Change one row in Postgres and reload:

```
before:   302.
UPDATE:   PROOF-THIS-CAME-FROM-POSTGRES
browser:  PROOF-THIS-CAME-FROM-POSTGRES     ← same URL, no restart
```

Every request runs a fresh `SELECT`. There is no cache, no file fallback, and no
post-extraction copy — what you see is what is stored.

## It cannot change anything

Read-only by construction, not by convention:

- every query is a `SELECT`; there is no `INSERT`, `UPDATE` or `DELETE` anywhere
- the pages contain no form that posts back, and the server implements only `do_GET`
- it imports nothing from `nizam` — it is a tool under `tools/`, not product code

Doc 09a §2's rule about pgAdmin applies here just as much: **inspection only**.
Schema changes come from a migration in `infra/postgres/migrations/` and nowhere
else, or your laptop and the server stop being the same thing (09a §7).

---

## Reading a document

Open the Pakistan Penal Code from the index (search `penal code`) and the layout is:

```
┌───────────────────────────┬───────────────────────────┐
│   source PDF              │   extracted text          │
│   (the scan/original)     │   (what is in the db)     │
│                           │   page markers, and for   │
│                           │   OCR, per-block          │
│                           │   confidence              │
└───────────────────────────┴───────────────────────────┘
```

Things worth knowing when you compare:

- **The contents pages are not the law.** The PPC prints its own table of
  contents on pages 1–29; the enacting words are on page 30 and section 302 is on
  page 106. A section number appears twice — once in the contents, once as the
  provision.
- **OCR blocks show a confidence.** Below 0.70 it turns red. Lane E2 blocks show
  none, because a text layer is not a guess.
- **Urdu blocks render right-to-left** in Nastaliq. Most sit around 0.35
  confidence — Tesseract's Urdu model is trained on Naskh, and Pakistani legal
  publishing uses Nastaliq. Those documents are flagged, and the same instruments
  are in the corpus in clean English.

## Reading the schema

`/schema` draws the identity ladder from doc 02 §7 and then lists, for every
table and view: row count, size, comment, every column with type and nullability,
primary keys, **foreign keys as `FK → table.column`**, and every index.

It is generated from `pg_catalog` and `information_schema` on each request, so it
cannot drift from the database the way a hand-drawn diagram does.

---

## Setup

Nothing to install if you have already run `./nz bootstrap` — it uses `psycopg`,
which is already a project dependency, and Python's standard library for the
server. Connection settings come from `infra/.env`, so it always points at the
same database as everything else.

Standalone, without `nz`:

```bash
uv run python tools/corpus-browser/serve.py --port 5055
```

It binds to `127.0.0.1` only. WSL forwards localhost, so open it in a Windows
browser exactly as printed.

| Problem | Fix |
|---|---|
| `connection refused` | The stack is not up: `./nz up` |
| `Address already in use` | Something else has 5055: `./nz browse 5060` |
| The PDF pane is blank | The blob is missing from `E:\nizam-data\raw\`. Re-run the landing tool. |
| Page shows a Python error | It is caught and printed rather than killing the server; the message names the cause. |
