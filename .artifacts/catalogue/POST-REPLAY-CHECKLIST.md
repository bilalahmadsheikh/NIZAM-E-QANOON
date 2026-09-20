# What must run after a full replay, and why

*Written 20 Sep 2026, during the `--all --redo` replay that followed the
compound-label and heading-linker repairs.*

A replay is not finished when `segment` exits. It retires every instrument it
touches, and four separate kinds of record point at instruments by an identifier
the replay regenerates. Each needs its own repair, and three of them are easy to
forget because nothing fails loudly when they are skipped -- the corpus simply
starts double-counting, or silently loses reviewed judgements.

Run these in order.

## 1. Re-link exact duplicates

    uv run python tools/resolve_exact_instrument_duplicates.py          # dry run
    uv run python tools/resolve_exact_instrument_duplicates.py --apply

**Symptom when skipped:** a document carries two active canonical instruments at
the same `expression_ordinal`, so one citation resolves to two provisions and
every corpus-wide count of that document is doubled. Measured after the 19 Sep
replay: documents 2605, 3677, 4139 and 4501, eight instruments between them.
It is easy to mistake for a segmentation defect -- a naive before/after query
that sums across expressions on one side and takes a single revision on the
other will report a document "doubling its sections", which is the query's bug,
not the corpus's.

Distinct source observations are provenance and are never removed. The tool only
links a redundant *revision* to the best-attributed copy, after hashing every
structural field and provision text. It already handles the case where a replay
corrects a tree that a duplicate was previously linked to, by advancing the
pointer to the active successor.

## 2. Re-attach orphaned S7 readings

    ./nz reattach

Keyed on `(document_id, source_block_id)`, which survives a regeneration;
`candidate_id` does not. Emits readings back through
`adjudicate_s7_from_source.py` so every guard re-fires rather than trusting the
stored verdict.

## 3. Re-attach orphaned contents-gap decisions

**No tool existed for this as of 20 Sep**; one is being built. After the 19 Sep
replay, 496 of 497 TOC gap adjudications pointed at a retired instrument and
zero pending gaps bound to one, while 176 pending gaps carried an unbound prior
decision -- real page readings doing nothing.

**Do not rebind blind.** Of 93 `absent_in_source` claims, 29 must not be carried
forward as they stand: doc 3149's four are contradicted by its own pages 6-7,
which print `1[14 * * *]` under the footnote "Section-14 deleted by Khyber
Pakhtunkhwa Adaptation of Laws Order, 1975", and doc 4427's 25 rest on a
contested reading of a collapsed range. Re-anchoring repairs a pointer; it is
not a licence to re-assert a judgement later evidence contradicted.

## 4. Adjudicate S7 -- last, never first

    ./nz s7-adjudicate      # the machine-decidable, citation-preserving batch
    ./nz s7-source          # source-read the remainder

**The ordering law, learned by doing it backwards:** parser fix -> replay ->
adjudicate. A replay orphans every S7 adjudication in the documents it touches
(838 accepts across 63 documents, measured). Of 430 corrective decisions written
before a replay, 242 candidates retired and **118 -- 49% -- came back as the
same collision.** Half that work was done twice for nothing.

## 5. Re-measure, do not re-quote

    ./nz mislabelled-headings
    ./nz gap-causes
    ./nz audit
    ./nz test

Every figure in `PATTERNS.md` and in the docs that was measured before the replay
is now suspect. Re-derive before quoting. Two readers once took the same census
an hour apart and got different numbers because the *detector* was being
tightened between the runs -- a measurement is only stable once the thing
measuring it is.

## Documents that will fail the replay, and why

These are not transient and will still be failing after it:

- **4441, 3581, 4608** -- `stale TOC disposition assertion`. `segment()` refuses
  to materialise a tree while an assertion it cannot match is outstanding, which
  is correct: silently dropping a repeal assertion would let repealed text become
  citable again. The disposition model has no append-only repair for ordinal
  drift, because a superseding row must carry the same ordinal as the row it
  supersedes. That is a schema question, not a patch. See the finding at the head
  of `tools/evidence/reanchor-shifted-toc-dispositions.sql`.
- **3912, 4434, 4440, 4497 and the rest of their two lists** --
  `observation has multiple active legal expressions; use the source-reviewed
  multi-expression materializer`.

  **This one is not a failure. It is a guard working.** These documents were
  deliberately split into disjoint expression trees by a source-reviewed process,
  and `legal_write` refuses to let a plain single-tree segmentation overwrite
  that. The curated lists live at the top of
  `tools/materialize_multi_instrument.py`:

      PRIMARY_DOCUMENTS     = {1106, 3389, 3553, 3696, 3912, 4434, 4452}
          an independently citable outer instrument followed by appendices
      COMPILATION_DOCUMENTS = {3423, 3949, 4440, 4497}
          editorial compilations, not themselves legal instruments

  So **eleven documents will error on every full replay, by design**, and the
  repair is to re-run

      uv run python tools/materialize_multi_instrument.py            # report
      uv run python tools/materialize_multi_instrument.py --apply

  NOT to force the plain segmenter past the guard. Forcing it would collapse a
  reviewed multi-expression reading back into one tree and silently change what
  is citable -- which is precisely what the guard exists to prevent.

  4497 is ESTACODE, whose expression 1 spans a single block and yields no
  provisions; it is the reason that guard was written.

## 6. Refresh the documented figures from `./nz state`

`./nz state` re-derives everything CLAUDE.md's "Measured facts -- do not
re-derive" block asserts. That block is a promise to the next reader that the
numbers were measured rather than estimated; a replay breaks the promise
silently, because nothing in the build reads it.

Known stale after this replay (they were true when written):

- `CLAUDE.md:9-11` -- documents, pages, characters, active expressions, active
  provisions, and "30 criteria; 29 pass".
- `CLAUDE.md:108-109` -- pages, characters, text blocks; provisions from sections
  and the 4.99x tree expansion.
- `CLAUDE.md:119-120` -- released expressions and provisions, S7 units pending,
  contents gaps pending.
- `docs/RELEASING-THE-BLOCKED-INSTRUMENTS.md` -- the before/after tables at
  lines 422-514 and 658.

The house rule applies to the fix as much as to the original: **assert the rule,
report the number.** Where a figure is load-bearing for an argument, restate the
argument so it survives the number changing.

## 4a. Before trusting any S7 decision, re-run the exact harm check

    ./nz s7-citability

Under INV-4 the harm a demotion can do is precise and the database can answer it
exactly rather than by sample: after the demotion, is the printed label still
reachable as a section of that instrument? Where a sibling with the same label
remains a section, the demotion removed a duplicate and cost nothing. Where no
section carries the label any more, **the citation is gone.**

Two things to hold together here, because each alone is misleading:

- The exact check previously found **0 lost citations across all 6,522
  demotions** (4,190 adjudicated, 2,332 pending).
- That was true and **not sufficient.** Preserving the label does not preserve
  the provision. The surviving section can be a phantom anchored to a footnote or
  a wrapped continuation, holding no text, while the demoted unit holds the law.
  The Prevention of Corruption Act 1947 s.5 is the case, and the eligibility
  test's first branch ACCEPTS it, because the phantom's heading matches the
  printed contents perfectly while the real body has no heading at all.
  `tools/audit/accepted-demotions-burying-law.sql` is the check for that, and it
  reports two columns deliberately -- operative characters including the opener,
  and characters behind the opener -- because counting the opener block hides the
  defect.

So: citability is necessary, not sufficient. Run both.

## 4b. The rendered-source audit is a measurement, not a formality

`./nz s7-audit` draws a sample WEIGHTED BY SIBLING-GROUP SIZE, because large
groups are where a compendium was mistaken for one Act and where an error costs
most. The resulting rate therefore describes that weighted population and is
**not** a uniform per-decision error rate -- say so whenever quoting it.

At 86 of the required 200 verdicts it stood at 31 `correct`, 19 `wrong`,
36 `not_s7`: **19 wrong of the 50 genuine S7 rows.** If that survives to 200 it
means the automatic adjudicator cannot be trusted wholesale, and every one of its
accepts removes a provision from citation. The high `not_s7` share is itself
worth diagnosing -- it may indicate the sampler is drawing rows that are not
collisions at all.
