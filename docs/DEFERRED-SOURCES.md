# Deferred sources: decide when retrieval is finished

## Taken up 21 Nov 2026 (DECISION-LOG D-113): what landed, what is left

**Landed and released: 230 laws.** 251 landed. 21 were then found not to be law (19 drafts, a circular, a press
release) and are recorded in `source_not_law` (0116).

| Source | Released | Left: scans (OCR) | Left: text, not yet structurable | Not landed by rule |
|---|---:|---:|---:|---|
| FBR codes | 9 | 7 | 9 | 142 versions of held laws, incl. six 2026 consolidations |
| FBR Customs SROs | 21 | 11 | 46 | 2 drafts, 9 held |
| SECP | 198 | 248 (+2 Urdu) | 354 | 214 guidance, 170 drafts, 148 held, 47 older copies, 14 .docx |
| PSX | 0 | — | 1 (the Rule Book: S7 = 20) | 62 notices, forms and policies |
| GB drop | 2 | 16 (the 2020–24 Acts and Rules) | — | the PEC Act (held as federal) |

The released counts are after the 21 not-law files came out: 6 FBR SROs, 15 SECP.

**Left, in the order of value per effort:**
1. **The six FBR 2026 consolidations of laws held** (Customs Act, Sales Tax Act, Federal Excise Act, the Income Tax
   Ordinance twice, the Finance Act 2026). They carry the Finance Act 2026 amendments. They need a newer-consolidation
   rule, a sibling of the 0075 twin link that serves the newer text, plus a golden-set re-point for the tax cases.
2. ~~About 290 unnumbered notifications~~ **Done 22 Nov 2026 (D-115):** a new provision kind `notification` and
   profile `notification-v1` serve each as one unit, "Notification". 238 landed; two more drafts found and recorded
   `source_not_law`; **236 released (10,572 → 10,808)**. About 55 notification-shaped texts the rule does not fire on
   remain with item 3.
3. **About 120 other blocked text files:** repeated labels (S7), evidence failures, and Gazette mastheads read as
   Parts. These are per-document readings.
4. **29 released new laws flagged by leakscan:** notes, heads, page furniture. These are the established repair
   batches. The GB Civil Servants Act carries a Gazette price line as a false sub-section.
5. **Scans: 282 here** (FBR 7, Customs 11, SECP 248, GB 16), plus the 874 AJK and 151 GB scans of item 6. That is
   1,307 laws. **Route since 22 Nov 2026 (D-114):** Google Document AI reads them, with Tesseract as an independent
   second reader (done: 1,179 scans read locally, 0 failures, `E:/nizam-data/ocr/second-read/`). Release needs the
   two readings to agree page by page. **Blocked on the owner's Google credentials**
   (`gcloud auth application-default login`). The "151 GB scans" figure does not reproduce from disk: the GB
   government sites list 15 PDFs today (13 scans staged in `E:/nizam-data/acquire/gb-2026-11-22/`), and the
   Assembly's 28 links are dead.
6. **Judgments (item 7)** and the **acquisition exceptions (item 8)** are untouched.

The per-file lists are in `E:/nizam-data/acquire/drops-2026-11-21/<drop>/` (staged.csv, excluded.csv, preflight.csv,
select-excluded.csv).

---

**Owner ruling, 19 Nov 2026 (D-100):** everything below is held, not landed, until L3 retrieval is finished:
- the reranker, the calibrated gate and context assembly (docs/04);
- the golden-set evaluation on the frozen test split.

Then each item is decided in turn. The reason is the build order (CLAUDE.md, the `nizam-workflow` skill). New laws and
new kinds of material would move the golden-set numbers while retrieval is still being tuned against them.
Judgments also need a pipeline that does not exist yet.

Nothing here has been landed or changed. Every count was measured on 19 Nov 2026:
- each file's SHA-256 against `blob`, and its title and year against the 10,342 released laws;
- each PDF's text layer: characters on its first three pages (TEXT above 300, else SCAN).

The per-file evidence is in `tools/evidence/source-drops-2026-11-19/`:
- `drops-compare.csv`: verdict, matched law, score, fingerprint;
- `tl-*.txt`: the text-layer results;
- `compare_drops.py` and `textlayer.py`: the scripts that made them.

The source zips are in `E:\nizam-data`.

| # | Source | What it is | Files (distinct) | Text / scan | Against the corpus | Decision needed |
|---|---|---|---:|---|---|---|
| 1 | FBR codes (`fbr_code.zip`) | Federal tax Acts, Ordinances and Rules, many in several dated consolidations | 178 | 153 / 25 | 8 same file; 132 files are other versions of 39 laws we hold; 34 new | Land the dated versions? |
| 2 | FBR Customs SROs (`fbr_Customs.zip`) | Customs SROs and notifications, 2023–2026 | 89 | 78 / 11 | 80 new, 3 same law, 6 unsure | Land SROs? |
| 3 | SECP (`secp_code.zip`) | Acts, Ordinances, Rules, Regulations, SRO notifications, and guidance | 1,322 | 925 / 383 | 1 same file; 105 files of 53 laws we hold; 1,177 new; 171 unsure | Which categories count as law? |
| 4 | PSX (`psx_legal_framework.zip`) | Exchange rule books (current and archive) and notices | 150 | 115 / 26 | all new | Do exchange rules belong? |
| 5 | GB code (`GB_code.zip`, 12 Sep) | The 26 GB Assembly Acts whose official links 404 | 19 | 3 / 16 | 2 new laws with text; 1 federal law we hold; 16 scans | OCR the scans? |
| 6 | AJK and GB scans (catalogued earlier) | Laws with no text layer | 874 AJK + 151 GB | 0 / 1,025 | not landed (owner rule, 14 Nov) | OCR them? |
| 7 | Judgments | Supreme Court, Lahore, Peshawar and Sindh High Courts | about 69,000 | per court, below | none held: no judgment table exists | When to build the judgment pipeline? |
| 8 | Acquisition exceptions | Catalogue items whose source could not be fetched | 66 | — | declared, with dated attempts | Retry, or find another source? |

## 1. FBR codes: dated versions of the federal tax laws

**What is in it.** FBR publishes every "as amended up to" consolidation of its laws. The zip holds:

| Law | Versions |
|---|---:|
| Customs Act, 1969 | 24 |
| The Sales Tax Act, 1990 | 18 |
| The Federal Excise Act, 2005 | 18 |
| Income Tax Ordinance, 2001 | 17 |
| Sales Tax Rules, 2006 | 9 |
| ICT (Tax on Services) Ordinance, 2001 | 9 |
| Income Tax Rules, 2002 (not held) | 9 |
| Finance Acts 2011–2026 | one each |

It also holds the AML, Benami, Single Window and FBR Acts and Rules, which we hold in other copies.

**Why it matters.**
- **Newer text, probably.** Two consolidations, the Customs Act and the Sales Tax Act, are "as amended up to
  30 June 2026". Our copies were captured on 19 June 2026. So the FBR text is likely to carry the Finance Act 2026
  amendments that ours lacks. A diff will confirm it.
- **History.** The older versions let these laws be answered as at past dates. For 3,856 laws, the text can now be
  served only from its capture date (0096–0099).
- **New laws.** The Income Tax Rules, 2002, the Sales Tax Special Procedures Rules, 2007, and about 15 amendment Acts
  and Ordinances: Tax Laws (Amendment) 2019–2025, Income Tax (Amendment) 2016–2022, Finance Supplementary. Their
  absence from the corpus was confirmed directly in the database.
- **Every dated consolidation has a text layer.** The 25 scans are older single laws: Finance Acts 2011–2018, the 2016
  Income Tax amendment Acts, a few amendment Ordinances, the Benami Act and Rules, the reward Rules and the FBR Rules
  2007. A text copy of most of them is already held.

**Open design question.** The schema serves one text per law, with versions dated by amendment footnotes. A dated
consolidation is a whole-law snapshot. Landing them needs a rule:
- which snapshot is the served text;
- how snapshots become `provision_version` ranges without breaking stored citations (INV-4, INV-5).

docs/03 does not cover this yet.

**Recommended:** land the 30 June 2026 consolidations as the current text, and the new Rules and amendment laws. Take
the older snapshots as dated versions once the snapshot-to-version rule is written and logged.

## 2. FBR Customs SROs

89 SROs and notifications (78 text, 11 scan). Examples: off-dock terminal declarations, Customs Rules 2001 amendments,
auction rules, the Overstayed Cargo Management Rules 2026. 80 of them are new.

The `fbr_sro_orders_code/` folder inside `judgments_peshawar_high_court.zip` holds the same 89 files byte for byte,
so only one copy is needed.

**Recommended:** land them with item 1. An amending SRO should become an `amends` edge to the Customs Rules.

## 3. SECP

| Category | Files | Note |
|---|---:|---|
| Notifications (SROs) | 934 | mostly new; 24 are amendments of regulations we hold |
| Regulations | 211 | 53 already held in another copy |
| Circulars | 111 | regulator guidance, not statute |
| Rules | 71 | 15 held |
| Guidelines | 52 | regulator guidance |
| Directives | 51 | regulator directions |
| Acts / Ordinances | 24 | 14 held (Companies Act 2017, Securities Act 2015, and others) |

383 of the 1,322 distinct files (29%) are scans, mostly older notifications.

**Decision needed:** do circulars, guidelines and directives belong in the corpus? They are not legislation. Serving
them as law would blur what is binding.

**Recommended:** land Acts, Ordinances, Rules, Regulations and SRO notifications. Hold circulars, guidelines and
directives, unless docs/03b is extended with a non-binding kind that is never presented as law.

## 4. PSX

The PSX Rule Book (current and an 82-file archive), regulations such as the Securities Broker (Licensing and
Operations) Regulations 2016, and notices. 115 text, 26 scan, and 7 zips not yet opened.

They are rules of a self-regulatory exchange, made under SECP approval, not an Act or SRO.

**Recommended:** hold, with the same rule as SECP guidance. A securities-regulation question needs them less than the
SECP regulations they sit under.

## 5. GB code: the 26 GB Assembly Acts whose links 404

The database records these 26 as acquisition exceptions, because the GB Assembly listing's PDF links return HTTP 404.
This zip, downloaded on 12 Sep, has 24 files (19 distinct):
- **16 scans:** the 2020–2024 Acts and Rules. Examples: Tobacco Control, Tourist Guide, Compulsory Education, PPRA 2021,
  Procurement Rules 2022, IT Board 2024, Finance Act 2024.
- **2 with text and new:** the Gilgit-Baltistan Civil Servants Act, 2011, and the Government of Gilgit-Baltistan
  Order, 2018. These may be the "2 text-layer Acts blocked at preflight" in docs/CORPUS-STATE-2026-11-17.md; check
  before landing.
- **1 with text and held:** the Pakistan Engineering Council Act, held as the federal 1975 law.

**Recommended:**
- Land the 2 text laws through the preflight path.
- OCR the 16 scans in the same lane as item 6.
- Record that the bytes came from this zip, since the official URL no longer resolves.

## 6. AJK and GB scans

874 AJK and 151 GB laws have no text layer and are not landed (owner rule, 14 Nov 2026;
docs/CORPUS-STATE-2026-11-17.md).

The one exception so far is the 25th–27th Amendment Acts. They were read page by page with a Kaggle GPU cross-check
(D-076).

**Recommended:** OCR on the Kaggle GPU route (`tools/kaggle/kg.sh`), with page-read verification for each law before
release, as D-076 did. Do it after retrieval, because about 1,000 new laws change the corpus the golden set measures.

## 7. Judgments

| Court | Files | Years | Form |
|---|---:|---|---|
| Supreme Court (`scp_judgments.zip`) | 3,750 | 1993–2026 | PDF |
| Lahore High Court (`lahore_HC_judgements.zip`) | 4,557 | 2000–2026 | PDF |
| Peshawar High Court (`judgments_peshawar_high_court.zip`) | 5,713 | 2000–2026 | PDF |
| Sindh High Court (`judgments_sorted/`) | 55,123 | 1966–2026 | HTML, sorted by year, with `mapping.csv` |

`judgments_peshawar_high_court.zip` (6 GB) is a bundle. Besides the Peshawar judgments, it holds byte-identical
copies of `GB_code`, `fbr_code`, `psx_legal_framework`, `scp_judgments` and `secp_code` (CRCs compared). Only its
Peshawar folder and the SRO folder of item 2 are unique.

**What it needs.** None of this can land today:
- docs/03 plans partitioned judgment tables;
- docs/06 plans the citator and treatment classification;
- docs/03b plans the `invalidated_by` edge, which only judgments can supply.

None is built. The copyright line in the `nizam-corpus` skill applies: official court text only, never reporter
headnotes.

**Recommended:** start the judgment pipeline after L4's first slice, unless precedent is needed earlier for the
`invalidated_by` coverage flag.

## 8. Acquisition exceptions (66)

Declared with dated attempts and the observed error (C1):

| Source | Reason | Count |
|---|---|---:|
| pk-gb | catalogued URL no longer resolves | 26 |
| pk-sindh | catalogued URL no longer resolves | 21 |
| pk-punjab | served content is not a PDF | 7 |
| pk-federal | catalogued URL no longer resolves | 5 |
| pk-kp | URL no longer resolves (2), no PDF catalogued (1), portal rejects (1) | 4 |
| pk-punjab | no PDF URL catalogued | 1 |
| pk-balochistan | served content is not a PDF | 1 |
| pk-sindh | no English PDF published | 1 |

Item 5 supplies files for the 26 GB entries. **Recommended:** re-check the other 40 against the new drops and
Internet Archive captures when this list is taken up.

## When this list is taken up

Take one item at a time: decide it, log the decision as a D-entry, land it, and re-run the audit and the golden set
(CLAUDE.md, "How to work here").

The suggested order is by value per effort:
1. Item 1 (FBR text laws, after the snapshot rule).
2. Item 2 (Customs SROs).
3. Item 5's two text laws.
4. Item 3, SECP's binding categories.
5. Items 5 and 6 (OCR).
6. Item 4 (PSX).
7. Item 7 (judgments).

Item 8 is checked alongside each.
