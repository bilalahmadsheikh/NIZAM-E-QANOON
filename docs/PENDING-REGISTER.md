# What is not added yet — laws and judgments

Generated 2026-11-26 by `tools/pending_register.py` from the database and the staging lists; never
edited by hand (D-130). Every row, with its file, URL and reason, is in `docs/pending/laws.csv` and
`docs/pending/judgments.csv`. Rerun the tool after any landing.

## Laws: 1,639 items to work on (815 more set aside by rule)

What each needs:

| category | needs | items |
|---|---|---:|
| not a PDF | open the file (a .docx or web page) and read it by hand | 23 |
| not acquired | find another source, or retry the portal | 66 |
| partial copy | a complete copy of the law | 48 |
| scan | OCR (D-114: Document AI + Tesseract, page agreement) | 1,164 |
| text, not structurable yet | a per-document reading (repeated labels, contents, mastheads) | 338 |

By source:

| source | category | items |
|---|---|---:|
| ajk | scan | 906 |
| ajk | text, not structurable yet | 168 |
| fbr_code | text, not structurable yet | 11 |
| fbr_code | scan | 7 |
| fbr_sro | text, not structurable yet | 26 |
| fbr_sro | scan | 9 |
| pk-balochistan | partial copy | 5 |
| pk-balochistan | not acquired | 1 |
| pk-federal | partial copy | 16 |
| pk-federal | not acquired | 5 |
| pk-gb | not acquired | 26 |
| pk-kp | not acquired | 4 |
| pk-kp | partial copy | 2 |
| pk-punjab | not acquired | 8 |
| pk-punjab | partial copy | 6 |
| pk-sindh | not acquired | 22 |
| pk-sindh | partial copy | 19 |
| psx | not a PDF | 9 |
| psx | text, not structurable yet | 1 |
| secp | scan | 242 |
| secp | text, not structurable yet | 132 |
| secp | not a PDF | 14 |

Set aside by rule (listed for review, nothing to do unless a rule changes):

| category | items |
|---|---:|
| set aside: a copy or compilation | 55 |
| set aside: already held | 279 |
| set aside: draft | 172 |
| set aside: not law | 309 |

## Judgments

| source | category | items |
|---|---|---:|
| AJK | court not held | 1 |
| AJKHC | scan | 30 |
| AJKHC | held by a gate | 28 |
| AJKHC | released, date not printed | 5 |
| AJKSC | released, date not printed | 220 |
| AJKSC | scan | 147 |
| AJKSC | held by a gate | 73 |
| BHC | law-report reprint | 1,936 |
| BHC | scan | 32 |
| BHC | released, date not printed | 7 |
| BHC | held by a gate | 2 |
| BHC | court not held | 1 |
| FCC | held by a gate | 6 |
| FCC | released, date not printed | 6 |
| FCC | court not held | 1 |
| FSC | court not held | 1 |
| GB | court not held | 1 |
| GBCC | scan | 124 |
| GBCC | held by a gate | 7 |
| GBCC | released, date not printed | 5 |
| GBSAC | released, date not printed | 417 |
| GBSAC | held by a gate | 83 |
| GBSAC | scan | 21 |
| IHC | released, date not printed | 1,243 |
| IHC | held by a gate | 370 |
| IHC | scan | 291 |
| IHC | law-report reprint | 18 |
| IHC | court not held | 1 |
| LHC | released, date not printed | 4,971 |
| LHC | held by a gate | 877 |
| LHC | law-report reprint | 477 |
| LHC | scan | 267 |
| PHC | scan | 1,832 |
| PHC | released, date not printed | 699 |
| PHC | held by a gate | 681 |
| PHC | law-report reprint | 655 |
| SC | scan | 444 |
| SC | released, date not printed | 324 |
| SC | held by a gate | 199 |
| SC | released, text layer below J9 | 1 |
| SHC | released, date not printed | 6,267 |
| SHC | scan | 5,223 |
| SHC | held by a gate | 2,024 |
| SHC | law-report reprint | 2 |
| SHC | source to recrawl | 1 |

What each needs:

| category | needs | items |
|---|---|---:|
| court not held | acquire the court's judgments | 6 |
| held by a gate | a parser rule or a person's reading (see reason) | 4,350 |
| law-report reprint | the court's own copy (portal recrawl); D-120 | 3,088 |
| released, date not printed | the court's decision date (portal recrawl with metadata) | 14,164 |
| released, text layer below J9 | an OCR re-read (D-114); released before the gate | 1 |
| scan | OCR (D-114) | 8,411 |
| source to recrawl | recrawl the Sindh High Court portal | 1 |

## Order of work (recommended)

1. **OCR**: law scans and judgment scans share one route (D-114). It needs the owner's choice: Google billing for
   Document AI, or the card-free Kaggle GPU route.
2. **Texts not structurable yet**: per-document readings, the established repair batches.
3. **Judgments held by a gate**: read the reasons; most are one parser rule each.
4. **Recrawls**: the Sindh High Court portal; the court's own copy for each law-report reprint; decision dates for
   judgments released undated.
5. **Not acquired / partial copies**: another source for each, or a dated retry.
6. **Courts not held**: acquire, then the same pipeline.
