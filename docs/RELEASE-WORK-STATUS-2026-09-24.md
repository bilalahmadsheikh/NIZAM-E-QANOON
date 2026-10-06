# Controlled release checkpoint — 24 September 2026

## Later bounded correction (07:48:47 UTC)

Document 974 was released through an append-only, source-verified S7
adjudication with an exact-block parent override and a one-document versioned
replay. Its quoted replacement section 3 now sits under this Ordinance's
section 3; both printed occurrences and operative text are preserved. The
official PDF SHA matched the source observation, the source page was inspected,
the response passed schema/image validation, two focused regression tests
passed, and a subsequent dry-run still produced zero S7 candidates. The
signed comparison found no removed or changed previously released trees.

**Current authoritative DB snapshot:** 4,130 / 4,687 released; 557 blocked;
1,024 pending TOC rows; 738 pending S7 units. The detailed case and
instrument ledger is under
`.artifacts/release-work-2026-09-24/direct-s7-974-progress/`; the correction
record is `.artifacts/release-work-2026-09-24/direct-s7-974-result.json`.

## Earlier checkpoint (07:09:18 UTC)

Authoritative database snapshot: 2026-09-24 07:09:18 UTC (`nizam_clean`).

| Measure | Current |
|---|---:|
| Active canonical instruments | 4,687 |
| Released | 4,129 |
| Blocked | 558 |
| Pending TOC rows | 1,024 |
| Pending S7 units | 739 |
| Pending boundary units | 0 |
| Confirmed defective previously released instruments | 8 |

This run increased the released count from 4,122 to 4,129. The seven added
documents were 118, 527, 523, 559, 1051, 1079 and 362. Each was handled as a
bounded document replay after source inspection and parser tests. Signed
baseline verification showed no previously released instrument removed or
changed by any successful batch. Document 362 was immediately replayed a
second time after an independently observed two-block publication footnote was
found inside Section 3; the final released revision separates that footnote.

The blocked-review pack contains 1,769 original cases. Sixteen response JSONs
have non-template answers that pass the strict schema and supplied-image hash
checks. Seven original cases now belong to released instruments; one more
original case has its exact TOC blocker cleared while its instrument remains
blocked for two newly exposed S7 candidates. Eight validated response cases
still concern blocked instruments. Two live S7 candidates in Document 2373
were generated after the signed pack and are separately listed in
`live-unpacked-cases.jsonl`; they must not be silently covered by old machine
demotions. A validated response is not an accepted adjudication.

The corpus audit remains 32/33: only S7 fails (739 pending units, no
itemization mismatches). A11 has zero different-name headings; C5 reports no
character reachability difference. The full parser regression suite passed
after the final code correction. The final signed release baseline is
`.artifacts/second-parser/release-after-362-2026-09-24` and verifies `safe`.

Highest-priority unresolved corrections:

1. Document 128: the active tree starts with schedule rows as top-level
   sections and omits the actual Sections 1 and 2. The eight source-reviewed
   answers are validated, but a source-body-start-only dry-run still misorders
   schedule table cells. It was not released.
2. Document 2373: its false 1980 title-year TOC gap is corrected, but a
   bounded replay exposed two S7 candidates. The old machine-only demotion of
   the genuine Section 2 is unsafe; Section 1(2) had been mistaken for the
   canonical Section 2. It remains blocked.
3. The eight previously released instruments with confirmed source defects
   (Documents 3, 17, 19, 120, 157, 220, 247, 671) still require separate
   source-backed correction and release-status decisions. No broad replay or
   release-status withdrawal was performed.
4. The released-corpus audit's 277 changed trees and 29 failed reparses,
   including Document 252's Section 20 loss, still prohibit broad replacement
   of previously released trees. This is separate from bounded blocked releases.

A read-only dry-run of all 180 then-current one-TOC-gap blocked documents
returned no additional TOC-improving replay under the current parser. Further
release gains therefore require source-backed parser/corpus fixes rather than
re-running that same group unchanged. No machine-only or ambiguous review
answer was promoted to a release.

Detailed machine-readable records:

- `.artifacts/release-work-2026-09-24/summary.json`
- `.artifacts/release-work-2026-09-24/cases.jsonl`
- `.artifacts/release-work-2026-09-24/instruments.jsonl`
- `.artifacts/release-work-2026-09-24/live-unpacked-cases.jsonl`
- `.artifacts/release-work-2026-09-24/unresolved-blockers.jsonl`
- `.artifacts/release-work-2026-09-24/checkpoints.jsonl`
- `.artifacts/blocked-review-pack-2026-09-23/response-validation-2026-09-24.json`
- `.artifacts/release-work-2026-09-24/batch-001-doc118-result.json` through
  `batch-008-doc362-result.json` (batch 003 was a dry-run probe, batch 005 did
  not release Document 2373).

The response validator used offline pack validation after the original signed
blocked-target snapshot became stale from bounded releases. The progress
worker independently matched every original case to its current stable
document, source observation, expression ordinal and source hash; stale
blocker identities are explicitly recorded rather than treated as accepted.
No full-instrument source-verification certificate is claimed for the seven
newly released instruments or the previously released corpus.
