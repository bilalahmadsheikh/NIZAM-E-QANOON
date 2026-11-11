# Expression source variants

7November2026. Decision: the9361 compilation contains seven reproductions of
already released amending instruments, alongside two unique notifications and
an older legal version of the1957 Order. Existing0036 exact-tree and0062
whole-file same-text contracts do not cover this mixed compilation. The new
manifest method `nizam.expression_source_variant/1` records **same issued
identity with retained print variants**, not word equality or legal-version
history. This is L2 identity curation under `docs/02` and `docs/03`; INV-4 and
INV-5 forbid using this decision as an automatic citation/text substitution.

Initial scope is closed:9361/13533 ordinals3–9 point, respectively, to released
documents712,518,727,9391,985,933,3591, ordinal0. The original Order(e0) and the
two unique notifications(e1/e2) are excluded. The former needs genuine legal
validity evidence, not an invented publication-only historical interval.

Each matrix pair binds live stable source-observation/ordinal keys, reviewed
revision and manifest IDs, source PDF hashes/object keys, complete source span
ledgers, raw block digests, and every inspected page image. Readable title,
jurisdiction, kind, year, number, Gazette issuance and numbered-unit extent
must establish issued identity. Known printing differences and unreadable loci
remain explicit; not every faint word has been adjudicated. The decision does
not certify word equality, present legal status or a current-version interval.
An actual amended/consolidated version, different commencement, partial copy,
or ambiguous issuance/extent is refused. The only reviewed number-metadata
exception is9391's null DB number: both paired Gazette images printIof1983.
Neither canonical metadata nor text is corrected by this route.

The owner's standing delegation is recorded as9361/q5 via
`tools/recrawl/deleg_answer.py`, binding the full seven-pair directional digest.
`tools/expression_source_variants.py` defaults to read-only validation. `--trial`
performs the exact write then rolls back. `--apply --approval FILE` additionally
requires independent hash-bound implementation/matrix approval and checks all
released UUIDs/full fingerprints before and after in one consistent snapshot.

The transaction locks/rechecks source identities and manifests, requires every
target to be active, released, canonical and nonhistorical, and every copy to
be unreleased with zero active provisions. It appends a manifest superseding
the old one while copying its exact spans, retaining prior source evidence,
and setting `source_body_review_state=identity-resolved/raw-variant-retained`.
Only the approved held copy's `duplicate_of` may change. Raw blocks, curations,
assignment ledger, prior manifests, canonical text/UUIDs and9361/e1/e2 remain.
No new law release is counted; canonical/held counts fall by resolved copies.

Replay is deliberately fail-closed. `legal_write.save_many()` refuses an
observation with any active standing variant disposition before its first
write. Single-tree/unstructured writers already refuse multi-expression
observations; the source-observation lock serializes the new decision with
ordinary writers. The whole-plan CLI also refuses a plan carrying the variant
field even if all ordinals are marked qualified. No post-replay helper window
is allowed. A later changed source, target lineage, or explicit withdrawal
needs a separately reviewed atomic variant-aware writer. No such general
writer or automatic target UUID advancement is claimed here.

The immutable matrix and approval are retained with the9361 release evidence;
the source plan receives the same standing disposition after application.
CLI reruns on exactly the same active source/target revision and proof are
idempotent. It refuses changed reviewed metadata, hashes, spans, or targets.

## As built, 10 November 2026 -- releasing one held expression of a variant-carrying observation

`tools/publish_held_expression.py` is the "separately reviewed atomic variant-aware writer" this document called for, for the
narrow case of a HELD, EMPTY expression (document 9361, e0). It writes that one expression's tree and leaves every other
expression, manifest and variant disposition untouched: the old e0 instrument, manifest and the observation's block-assignment set are
retired and superseded (append-only); the manifest evidence (including `source_access_release`) is carried forward and a
`held_expression_release` record is added; every other block keeps its assignment; a `segmented` run is recorded; the release gate and
every release fingerprint are checked in the same transaction. Default is a rehearsal that rolls back (rehearsed 10 Nov: 779 provisions
from a trial build, released 8,819 -> 8,820, no other fingerprint, manifest, variant flag or block assignment changed); `--apply`
needs `--owner-decision` (>= 80 characters). It writes no dates (versions open at the observation's `as_at`, status `unknown`).
It was run for 9361 e0 on 11 Nov 2026 (770 provisions, released 8,842 -> 8,843, no other fingerprint, manifest, variant flag or block
assignment changed) from the owner's proofread readings of scans 1-56 (scans 3, 5, 10, 49 duplicates set aside; scans 28 and 37, which have no
text-layer blocks, are carried by the readings of scans 27 and 36 with `additional_render`; scan 56 restricted to the Order's own text). The two
printed articles numbered 73 are both kept citable by a reviewed order-suffix group (decision 9361/q7, 'keep-both'). The source-access notice
stays in force; no validity dates were written.
