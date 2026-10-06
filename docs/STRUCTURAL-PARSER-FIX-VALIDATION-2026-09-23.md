# Source-verified structural parser fix and replay assessment — 23 September 2026

## Decision

The parser now fixes the four source-verified findings in documents 118 and 956 in a read-only dry run. **Do not perform a corpus-wide production replay or release any instrument on this result.** The pre-fix parser already differs from stored trees, and the new grammar has additional released-tree effects that have not all been checked against their PDFs. No production rows, adjudications, or release states were changed during this work.

## Exact corrections

The patch in `nizam/corpus/segment.py`:

1. Recognizes an amendment-marker prefix only when it is immediately followed by a literal bracketed `Provided`, as in `3[Provided` and `10[Provided`. The immutable source block retains the printed marker; it is not made into a section label. Generic bracketed amendment text is not promoted.
2. Keeps Document 118's independent Section 2. Under Section 3's newly recognized third proviso it nests dotted items 1–3 only when the proviso explicitly introduces “the following provisions ... shall be read as”, the items are indented and consecutive, and their wording refers to the earlier Act. Item 2's romanettes remain beneath item 2. Parent inference therefore precedes the unchanged repeated-section collision pass.
3. Gives Document 118 block 3429 a footnote role and removes its enactment-history text from the second proviso's operative version, while keeping the source block. The guard uses the verified 1985 Punjab wording and bottom-of-page position; a broad “This Act was passed by” trial changed hundreds of released trees and was rejected.
4. Ends Document 956's bracketed proviso at its closing bracket. The following separate paragraph, block 45049, remains Section 3 text rather than becoming proviso text.

## Before and proposed after (not written to the database)

| Document | Stored | Dry-run proposal |
| --- | --- | --- |
| 118 | 20 nodes. Section 2 is independent; the third proviso (block 3431) is missing; its items 1–3 are root clauses, and item 2 (block 3433) collides with Section 2. Block 3429 is `body` in the second proviso. Three S7 candidates. | 21 nodes. Section 2 remains `...s_2`; block 3431 opens `...s_3.prov_Provided_n2_1`; items 1–3 are its `cl_1`, `cl_2`, `cl_3`; romanettes (i)–(v) are under `cl_2`. Block 3429 is `footnote`. No S7 candidates; TOC unchanged. |
| 956 | 20 nodes. Section 3 contains the `10[Provided` paragraph (block 45048) with no proviso node. | 21 nodes. New `...s_3.prov_Provided` opens at block 45048. Section 3 retains the subsequent paragraph in block 45049. S7 and TOC unchanged. |

The exact path, parent, first-block, text, ordinal, role, S7 and TOC before/after records for both are in [`verified-target-detail.jsonl`](../.artifacts/structural-parser-fix-2026-09-23/verified-target-detail.jsonl). The original PDFs for documents 118 and 956 were rendered and inspected; their source SHA-256 values match the active source files listed in [`source-verified.json`](../.artifacts/structural-audit-2026-09-23/source-verified.json).

## Tests and corpus method

`uv run pytest tests/test_segment.py tests/test_structural_review.py tests/test_doc118_third_proviso.py -rA`: **144 passed, 0 failed, 0 xfailed**. The three formerly expected-failure source tests now pass normally. New tests cover the Document 956 closed-proviso boundary, negative bracket/ordinary-amendment cases, the narrow footnote guard, and a source-verified proviso in released Document 247.

The read-only dry run builds active canonical expressions through the same segment worker/materializer and curation inputs as the writer, then compares provision rows, candidate S7 rows and TOC links with stored rows. A reconstructed pre-fix parser was run on the same target set, so new effects are separated from existing drift. The final code SHA-256 prefix is `387b0129`; the pre-fix control prefix is `17839a7b`. The run targets 4,687 canonical active expressions across 4,598 observations (4,596 distinct documents). Five build errors leave 38 expressions unmeasured. It never calls the production writer.

| Read-only comparison | Instruments different from stored | Previously released among them |
| --- | ---: | ---: |
| Pre-fix parser versus stored | 27 | 24 |
| Final parser versus stored | 352 | 277 |
| Final versus pre-fix, isolating this patch | 326 | 254 |
| Rejected broad-footnote trial versus pre-fix | 566 | 486 |

The complete control comparison covers 4,649 successfully built expressions, 4,093 of them released. The active canonical release view listed 4,122 released expressions at the check; the other 29 fall inside the 38 unbuilt expressions. The final patch changes S7 output only for blocked Document 118 (three candidates to zero). It changes a TOC link in blocked Document 4120 without changing that document's unlinked-entry count. No released instrument has a patch-attributable S7 or TOC output change, but 254 released trees do change and remain replay-blocking until their citation/text implications are checked. The five errors and all 27 pre-existing stored-tree differences also persist.

## Source checks and unresolved risk

The original PDFs for released documents 120, 247 and 671 were hash-checked and visually inspected. Each prints the amendment-prefixed proviso that the dry run adds; this verifies those particular openings, **not** the entire resulting tree. Document 671 page 14 also proves an unresolved parent error: the new Section 10 proviso at block 28225 introduces romanettes (i) and (ii) in blocks 28226–28227, but the proposed tree leaves those romanettes as direct Section 10 children.

Document 252 page 13 visibly prints an independent Section 20 (block 11130). The pre-fix control already loses it on reparse, appending its text to Section 19; that drift is not caused by this patch but makes an unrestricted replay unsafe. The five build errors are also inherited from the control: four stale TOC disposition assertions (documents 1351, 1366, 1609, 1846) and a missing multi-expression provision in document 4497. The latter observation contains 34 active expressions; together the five failures account for all 38 unmeasured expressions.

The source review is **not** corpus-wide. New or changed provisos outside the verified pages remain unresolved until checked against original PDF pages, including their continuation, nested lists, citations and TOC consequences. The 64,922 screening flags in the prior audit are heuristic leads, not confirmed defects.

## Artifacts and safe replay boundary

- [`control-comparison.jsonl`](../.artifacts/structural-parser-fix-2026-09-23/control-comparison.jsonl): machine-readable patch-attributable changed instruments, with pre-fix and final comparisons against stored trees; [summary](../.artifacts/structural-parser-fix-2026-09-23/control-comparison.summary.json) and [build errors](../.artifacts/structural-parser-fix-2026-09-23/control-comparison.errors.json).
- [`changed-detail.jsonl`](../.artifacts/structural-parser-fix-2026-09-23/changed-detail.jsonl): every final tree differing from stored, matched by source-block identity where possible, with old/new paths and parents, full text, roles, S7 and TOC; [summary](../.artifacts/structural-parser-fix-2026-09-23/changed-detail.summary.json).
- [`unresolved.json`](../.artifacts/structural-parser-fix-2026-09-23/unresolved.json): patch effects still needing source review, pre-existing drift, build errors and the Document 671 parentage issue.
- `baseline-s0..3.jsonl` and `verified-s0..3.jsonl` in the same artifact directory retain the resumable read-only runs and code hashes. A broader footnote trial (`final-s0..3.jsonl`) is retained as **rejected risk evidence**, not the proposed parser.

No rollback of production data is needed: none was written. The code change can be reverted with an ordinary reviewed code reversal; the pre-fix copy and dry-run artifacts preserve its comparison basis. Before any future replay, freeze a stable corpus snapshot, resolve the inherited 27 stored-tree differences and five build failures, source-review all changed released instruments, create a case for Document 956, and verify that every old released instrument's source-backed provision and citation identity survives. First test an allowlisted set in a non-production database; compare provision/block/TOC/S7 and release counts against immutable pre-replay instrument IDs. Promote only with an explicit authorization and a transactional, reversible generation swap. A count-only or S7-only gate is insufficient.

The detail ledger's `added`/`removed` arrays are unmatched rows under a best-effort source-block alignment, **not** confirmed legal additions or omissions. Multiple nodes can share a first block, so its aggregate unmatched-row counts (2,017/1,009) overstate substantive changes. The control comparison records the parser-level differences; any alleged lost operative text must still be checked on the original page. The detailed ledger completed for all 352 changed instruments without an enrichment error.
