# The law register

Every law released in the corpus, **10,342 laws**, generated 2026-11-19 by `tools/law_register.py` from the database. Do not edit these files by hand: change the database (through its recorders and migrations) and regenerate.

- [laws.csv](laws.csv): every law, every column below (UTF-8 with BOM; opens in Excel with Urdu intact)
- [Federal (incl. Islamabad Capital Territory)](federal.md)
- [Punjab](punjab.md)
- [Sindh](sindh.md)
- [Khyber Pakhtunkhwa](khyber-pakhtunkhwa.md)
- [Balochistan](balochistan.md)
- [Azad Jammu & Kashmir](azad-jammu-kashmir.md)
- [Gilgit-Baltistan](gilgit-baltistan.md)

## By place and currency

| Place | Laws | Current | Not current | Historical | Provisions | Urdu/Sindhi text |
|---|---:|---:|---:|---:|---:|---:|
| Federal (incl. Islamabad Capital Territory) | 3,562 | 2,452 | 439 | 671 | 513,129 | 0 |
| Punjab | 1,366 | 1,346 | 16 | 4 | 194,573 | 2 |
| Sindh | 2,004 | 1,713 | 291 | 0 | 180,308 | 0 |
| Khyber Pakhtunkhwa | 911 | 903 | 8 | 0 | 97,396 | 1 |
| Balochistan | 1,030 | 1,020 | 9 | 1 | 110,972 | 10 |
| Azad Jammu & Kashmir | 1,442 | 808 | 634 | 0 | 73,762 | 0 |
| Gilgit-Baltistan | 27 | 27 | 0 | 0 | 2,383 | 0 |
| **All** | **10,342** | **8,269** | **1,397** | **676** | **1,172,523** | **13** |

Currency counts every released law. 51 of them are as-made Gazette texts served through their consolidated twin and carry the twin's currency, so the laws served directly are 10,291.

## By kind

| Kind | Laws |
|---|---:|
| act | 5,115 |
| ordinance | 2,622 |
| rules | 1,655 |
| regulation | 521 |
| order | 353 |
| notification | 72 |
| constitution | 4 |

## By decade of the law

| Decade | Laws |
|---|---:|
| 1810s | 3 |
| 1820s | 3 |
| 1830s | 2 |
| 1840s | 2 |
| 1850s | 19 |
| 1860s | 76 |
| 1870s | 171 |
| 1880s | 133 |
| 1890s | 95 |
| 1900s | 90 |
| 1910s | 116 |
| 1920s | 146 |
| 1930s | 201 |
| 1940s | 287 |
| 1950s | 764 |
| 1960s | 744 |
| 1970s | 1,512 |
| 1980s | 901 |
| 1990s | 824 |
| 2000s | 1,137 |
| 2010s | 1,918 |
| 2020s | 1,192 |
| undated | 6 |

## Why laws are not current

| Reason | Laws |
|---|---:|
| ordinance_lapsed | 1,063 |
| pre_1947_text_not_in_official_consolidation | 549 |
| replaced_by_later_act | 144 |
| law_of_a_place_outside_pakistan | 117 |
| repealed | 98 |
| repealed_date_not_established | 67 |
| official_portal_marks_repealed | 23 |
| subordinate_rules_enabling_law_historical | 7 |
| subordinate_notification_enabling_law_historical | 2 |
| repealed_in_each_territory | 1 |
| superseded_by_later_instrument | 1 |
| subordinate_regulation_enabling_law_historical | 1 |

## Where each title comes from

| Title basis | Laws |
|---|---:|
| verified_in_printed_text | 6,776 |
| near_match_in_printed_text | 1,437 |
| verified_by_short_title_clause | 1,197 |
| reviewed_printed_name | 485 |
| catalogue title (no assertion) | 341 |
| reviewed_corrected_name | 64 |
| printed_short_title_clause | 42 |

## Columns of laws.csv

| Column | Meaning |
|---|---|
| `instrument_id` | the law's identity in the corpus (changes when the law is re-segmented) |
| `jurisdiction` | fed (federal and ICT) · punjab · sindh · kp · balochistan · ajk · gb |
| `kind` | constitution · act · ordinance · order · regulation · rules · sro · notification |
| `number` | the instrument's number as printed (Act No. …), where read |
| `year` | the year, corrected from the law's own text where the catalogue was wrong (0101) |
| `title` | the name rendered to a reader: display_title, else the catalogue short title (INV-1) |
| `catalogue_title` | the short title as the source catalogue gave it (never changed: identity keys on it) |
| `long_title` | the printed long title, where read |
| `title_basis` | the evidence for the title (verified_in_printed_text, near_match_in_printed_text, verified_by_short_title_clause, reviewed_printed_name, reviewed_corrected_name, printed_short_title_clause); empty = catalogue title |
| `text_language` | en · ur · sd, measured from the released text |
| `status` | lifecycle status: in_force · repealed · spent · lapsed · not_yet_commenced |
| `status_basis` | why that status (e.g. commenced_on_established, statutory_repeal_stands, owner_presumption_in_force) |
| `enacted_on, enacted_basis` | assent / promulgation / notification date, and where on the page it was read |
| `commenced_on, commenced_basis` | commencement date, and its basis |
| `repealed_on, repealed_by` | whole-law repeal date and the repealing law |
| `currency` | what is served today: current · not_current (repealed, lapsed, replaced, superseded) · historical (pre-1947 archive texts, places outside Pakistan) |
| `currency_reason, not_current_from` | the reason, and the date the law stopped being served |
| `territory_reach` | where the law runs (from its extent clause or its title) |
| `extent_basis` | extent_clause or the title reading |
| `territory_exits` | territories a later law repealed it in, with dates (JSON) |
| `superseded_by` | a later law of the same name that replaced it |
| `served` | direct · via_consolidated_twin (an as-made Gazette text served through its consolidated text) |
| `served_through` | the consolidated text that serves an as-made one |
| `text_known_from` | the earliest date the held text is known to be the law; before it, questions abstain |
| `provisions` | released provisions (every section, sub-section, clause, schedule item) |
| `units_repealed` | provisions repealed by a later law while the rest of the law stands (0102) |
| `document_id, document_pages` | the source document and its released page count |
| `expression_ordinal` | which law inside that document (a PDF can hold several) |
| `source_url, source_sha256` | where the text came from, and the fingerprint of the bytes |

## Limits

- `current` includes laws presumed in force by owner decision (16 Nov 2026) where no text proved their status; `status_basis = owner_presumption_in_force` marks them. The presumption never covers a pre-1947 archive text.
- Titles marked `verified_in_printed_text` were matched against the law's printed pages by machine, not read by a person; the `reviewed_*` bases were.
- `instrument_id` changes when a law is re-segmented; cite a law by its title, number and year.
- Laws that need OCR (874 AJK and 151 GB scans) are not landed and are not in this register (owner rule); see docs/CORPUS-STATE-2026-11-17.md.

Regenerate: `.venv/bin/python tools/law_register.py` (WSL), after any release or recorder run.
