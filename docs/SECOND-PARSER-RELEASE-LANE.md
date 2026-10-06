# Second-parser release lane

> **Current continuation point (23 September 2026):** the measured pilot below
> is historical. Its `current-pages` manifest predates a full replay and must not
> authorize another write. The live state is now 4,122 releases; use the
> verified continuation manifest at
> `.artifacts/second-parser/release-after-1887-2026-09-23/` for legal-tree
> regression checks and follow [the release-all handoff](RELEASE-ALL-HANDOFF-2026-09-23.md).
> The still-running proposal-only Surya queue retains its older staged
> `release-all-post-T2-repeal-2026-09-23` run; that is evidence, not the new
> baseline for further release writes.

The second parser is Surya-2, already present in the corpus as an independent
layout/OCR reading. It is a shadow parser: it may name a block as a heading,
footnote, table or body region, but it cannot publish that opinion directly.

The target set is always generated from the live database. It contains active,
canonical instruments absent from `v_release_instrument`; a stored list of old
document numbers is never used. A run records the exact instrument UUID,
source observation, source SHA-256 and complete TOC/S7 blocker signature. If
any of those move, the target is stale and is skipped until a new run is made.
A normal bounded replay retires the old UUID and creates a new one. Verification
accepts that replacement only when document, source observation, expression
ordinal and source hash all match exactly; ambiguity still fails closed.

## Run

```bash
uv run python tools/second_parser_release.py prepare \
  --out .artifacts/second-parser/current --stage --page-slices

tools/run_surya_ocr.sh \
  .artifacts/second-parser/current/input \
  .artifacts/second-parser/current/output

uv run python tools/second_parser_release.py import-results \
  --run .artifacts/second-parser/current

uv run python tools/second_parser_release.py verify \
  --run .artifacts/second-parser/current

uv run python tools/second_parser_release.py propose \
  --run .artifacts/second-parser/current
```

`prepare --page-slices` stages only pages that can settle a live blocker: S7's
candidate and canonical pages, TOC source pages, body pages found by printed
label or heading, and one neighboring context page. Already stored Surya pages
are not staged again. Without `--page-slices`, source PDFs are symlinked from
the immutable object store. The Surya runner is resumable and skips result
directories already containing `results.json`.

`verify` is the no-collateral-change proof. It requires:

- no snapshot-time released instrument was removed;
- no snapshot-time released tree fingerprint changed;
- every remaining target has the same active UUID, source observation, source
  hash and blocker signature;
- any new release is one of this run's targets.

Targets already released since the snapshot are reported under
`already_released_skip`. Replayed targets with a new UUID are reported under
`released_replacements`. Both are excluded from subsequent batches. The old
release baseline is still fingerprinted by UUID, so this exception cannot hide
a mutation or removal of an instrument that was already released at snapshot
time.

`propose` maps Surya regions back to immutable `text_block` geometry. It emits
`proposals.json` with `review_state: proposed`. For S7, an apparatus candidate
opposed to a body canonical print proposes `reject_candidate`; the inverse
proposes `restore_citable`. Anything ambiguous remains `review`. For TOC, only
a unique non-contents body label becomes `unique_body_candidate`.

The proposal file is evidence for the existing source/human review and bounded
replay workflow. It is intentionally not an automatic adjudicator. A model
label cannot by itself change citability, split an instrument or alter source
text.

When a source-reviewed page proves that a short printed contents page precedes
the operative body, the reading may carry the narrow
`structural_overrides.source_body_start_block` fact. The adjudication tool
validates that the block belongs to the same document. The segmenter consumes
the fact only from active source-reviewed evidence, treats the earlier numbered
rows as contents, and otherwise keeps the normal parser unchanged.

The same evidence may name exact `source_apparatus_blocks` when the rendered
page and the independent layout parser both identify an entire immutable source
block as footnote/date/separator apparatus. Those blocks remain in the ledger
with role `footnote` but cannot open or absorb a legal provision. The source
adjudicator requires a non-empty unique list and verifies every block belongs to
the reviewed document.

For a measured pilot or incremental production run, create a priority queue
from the same signed manifest. This selects whole document evidence sets, so a
document is never half-selected merely to meet the file limit:

```bash
uv run python tools/second_parser_release.py batch \
  --run .artifacts/second-parser/current \
  --out .artifacts/second-parser/current/pilot-input \
  --single-blocker --max-files 40
```

`batch` re-runs freshness verification, selects fresh unreleased expressions
only, and omits page results already completed by a previous batch. Run the
result with both pre- and post-inference safety checks:

```bash
bash tools/run_second_parser_batch.sh \
  .artifacts/second-parser/current \
  .artifacts/second-parser/current/pilot-input
```

The wrapper imports and proposes only if the post-inference manifest check is
still safe. It never adjudicates a proposal or writes a legal tree.

## Measured pilot (2026-09-21)

The frozen run contained 681 blocked expressions in 667 documents and a 4,005
instrument release baseline. Forty selected page inputs completed with 39 new
results, one resumable skip and zero failures. One source-readable result,
document 1000, proved that page 1's `12.1` was a contents link and page 2's
`12.1` was operative law. After source review and a one-observation replay, the
candidate tree contained exactly sections `12.1` and `12.2`, with zero TOC, S7
or boundary blockers. The release count became 4,006. Post-write verification
reported one exact released UUID replacement, no unexpected release addition,
and zero changed or removed baseline releases (`safe: true`).

Batch 002 added 40 new page readings. Three actionable proposals were checked
against six official page renders and then against exact in-memory candidate
trees. Documents 1678 and 2154 required both a one-row contents boundary and
explicit apparatus blocks; an S7-only replay was rejected because it would have
published fake sections `3` and `672` from footnotes. Document 1800's rendered
section `1.` was lowercase `l.` in the immutable text layer, so a source-verified
curation patch corrected only the derived parser input. Bounded replays released
all three with TOC/S7/boundary queues at zero. The live total became 4,009 and
the blocked count 677. The frozen 4,005-release baseline still had zero changed
or removed fingerprints and verification remained `safe: true`. Exact evidence,
old/new UUIDs and rollback pointers are in
`.artifacts/second-parser/current-pages/release-log-2026-09-21.json`.
