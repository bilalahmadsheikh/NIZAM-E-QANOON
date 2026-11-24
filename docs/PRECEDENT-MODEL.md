# Precedent model — judgments, courts, authority and links

Decided 22 Nov 2026 (DECISION-LOG D-116 to D-122). This is the contract for the judgment pipeline. It corrects the
judgment sketches in docs/03 §1.1 and §2.5, docs/06 §5 and docs/04 §6.1, and those documents point here. Nothing in
it is built yet. Each section says what the first migration or tool must enforce.

Every fact about the courts below is read from the served corpus, with version ids, never from memory (CLAUDE.md:
never assert an external fact). Where the corpus lacks the source, the rule is **not recorded**, and the system says
so rather than guess.

## As built, 22 Nov 2026 (D-123): the Supreme Court, end to end

| Step (§7) | State | Where |
|---|---|---|
| 1. Court registry and authority rules | **built**: 8 courts, 7 rules; each source's words checked (A24) | 0118, `nizam/storage/authority.py` |
| 2. Judgment tables | **built**, partitioned by decision date | 0119, 0121 |
| 3. SC ingest | **built**: 3,105 of 3,744 distinct files released, 314 of them marked undated (D-124, 23 Nov); 193 held with their gate; 438 waiting for OCR; 8 duplicates | `nizam/corpus/judgment.py` (`nizam.judgment/2`, `/3` for the J1 re-read), `nizam/workers/judgments.py` |
| 4. Judgment → statute links | **built**: one grammar (`nizam/storage/citations.py`), the law inherited from the judgment's last naming (0121), the version read through `operative_provision` at the decision date | `nizam/workers/judgment_links.py` (A26) |
| 5. Chunks, embeddings, precedent search | **built** for the CPU generation and BM25; the 8B GPU space for judgments is not built | 0120, `nizam/workers/judgment_chunk.py` (A27), `nizam/retrieval/precedent.py`, `nizam/api/precedent.py` |
| 5a. One record per case (D-125, 23 Nov) | **built**: 3,031 of 3,105 judgments placed in a case (6,935 cases with the appeals decided together); 326 reasons statements, 18 of them matched to a short order held as its own file; 1 second copy | 0123, `nizam/corpus/judgment_case.py`, `nizam/workers/judgment_cases.py` (A28), `/v1/precedent/cases/…` |
| 6. Other courts | **Lahore HC landed (D-128, 23 Nov):** 3,996 of 4,550 distinct files released, 2,518 of them undated (a hearing date and nothing else printed); 239 held; 197 reprints not landed; 117 waiting for OCR. Case types observed (0124); order sheets dated by their date of order; links read Punjab law first. **Peshawar HC landed (D-130, 23 Nov):** 2,593 of 5,704 distinct files released (693 undated); 1,818 to OCR (1,598 no text, 193 not readable by gate J9); 653 reprints; 639 held; links read KP law first. Sindh needs its recrawl | 0124–0127, `nizam.judgment/4` (LHC), `/5` (PHC, J9), `nizam.judgment_links/3` |
| 7. Treatments, lineage review, invalidation, citator | lineage rows are machine candidates; the rest is not started | |

Corrections to the sections below, as built:
- **§3.1:** judgments have their own ladder, not the statute ladder's tables. The statute criteria C1–C9 require every
  landed block to belong to a provision of a law.
- **§4.1:** the shared grammar lives in `nizam/storage/`, not `nizam/shared/` (`.importlinter` contract 3).
- **§3.3 (D-125, 23 Nov):** a short order and its detailed reasons stay two judgments, one per file, each with its
  own date. They are not merged into one judgment with two opinions: what joins them is **the case**.
  - `judicial_case` is keyed by the case as printed, `<court>/<type>/<number>/<year>` ('SC/CA/1507/2024'), so a
    rebuild never changes a key and a stored reference to a case never breaks.
  - `judgment_case` gives the case a judgment decides (`lead`) and the cases of the same type and year printed
    beside it (`joined`: 'Civil Appeals No. 1507 and 1508 of 2024', 'Nos. 545 to 550').
  - `judgment_relation` `reasons_for`: the court's own statement, "the above are the reasons for our short order
    dated …", with the short order's printed date. The short order is linked when the case holds it as a separate
    file that its own record marks as a short order. `copy_of`: a second file of one decision, never shown beside
    the copy kept.
  - The case line is read by its own grammar. Where the header parser's number or year differs (44 judgments, every
    one read and the grammar right), the case line is the record and the difference is kept.
  - A case citation in a judgment ("Civil Appeal No. 984 of 2018") resolves to the case, however many decisions it
    has (§4.2).
- **§6.3 (D-131, 24 Nov):** built. Four categories with their basis read from the corpus: sexual offences (statute:
  PPC s.376A(1), whose exemption covers law journals only; Anti-Rape Act 2021 s.26(1)); minors (follows the Juvenile
  Justice System Act 2018 s.13(1), which exempts superior-court judgments); family and medical (product policy).
  Marked by the laws a judgment cites, header words, and for sexual offences the body's words. The parties line
  withholds any side naming a person; victims, "Mst." names and minors named in the body are withheld too; readers
  replace them in every paragraph and hit, and a search naming a withheld person never returns the judgment (A29).
- **§6.1:** `judgment_chunk` is one table, not partitioned, until a second court lands. (The second court, Lahore,
  landed on 23 Nov; the table stays one table, because judgment search filters by court through the judgment row and
  the chunk count is still under 200k.)
- **§3.2 / §3.7 for the High Courts (D-128):** an order sheet's decision date is its printed date of order
  (`decided_on_basis = 'date_of_order'`). A judgment sheet whose "Announced … on" line is left blank is released
  undated (D-124), bounded by its hearing date.
- **§3.7 J1 (D-124, 23 Nov):** a judgment with no usable printed decision date is released **marked undated**, not
  held. `decided_on` then holds the latest possible day (the archive's first observation of the file). It is the
  research-date filter and is never shown: `decision_date` is NULL, and the reader prints "date of decision not
  printed" with the bounds. Its citations are linked with no version.

---

## 0. What we hold (measured 22 Nov 2026)

| Court | Archive (`/mnt/e/nizam-data/`) | Files | Years | Text layer | Reporter reprints | Source URL |
|---|---|---:|---|---:|---:|---|
| Supreme Court | `scp_judgments.zip` → `scp_judgments/<year>/` | 3,750 | 1993–2026 | ~90% | 0 of 150 | `manifest.csv` (5,616 ok, 20 errors) |
| Lahore HC | `lahore_HC_judgements.zip` → `downloads/<year>/` | 4,557 | 2011–2026 | ~97% | 12 of 150 | none |
| Peshawar HC | `judgments_peshawar_high_court.zip` → `judgments_peshawar_high_court/<year>/` | 5,713 | 2009–2026 | ~64% | 13 of 150 | none |
| Sindh HC | `judgments_sorted/<year>/*.html` | 55,075 | (1966–2026 in names) | **none** | — | — |

Notes:
- The Sindh files are empty search-result pages. Only the filename carries facts (case number, year, S.B./D.B.,
  seat), so Sindh needs a recrawl.
- There are byte-identical duplicates within archives: 6 (SC), 7 (LHC), 9 (PHC). The Peshawar bundle also repeats
  the whole SC set.
- The 41 SC files named "…UrduTranslation" are official Urdu translations (§3.4).
- Not held: the Federal Constitutional Court, Islamabad HC, Balochistan HC, the Federal Shariat Court, the AJK and GB
  courts, and the AJK and GB constitutional texts (needed for those courts' authority rules, §1.3).

*As built (25 Nov 2026, D-138, D-139):* released judgments 55,229 — Sindh HC 45,371 (a new archive of 56,227 PDFs and
4,279 official HTML pages, lane E1), Lahore 3,996, Supreme Court 3,105, Peshawar 2,593, Federal Constitutional Court
134 (crawled from its API), Balochistan 30 (1,936 of its 2,001 archived files are law-report reprints, not landed).
Every court's own site is being crawled (D-139): Lahore lists 9,716 approved-for-reporting judgments, Peshawar 5,888;
the AJK Supreme Court (960), AJK High Court (262), GB Supreme Appellate Court (752) and GB Chief Court (154) are
downloaded and wait for their courts to be recorded, which waits for the AJK Interim Constitution and the GB Order
2018 to be released. Still not held: Islamabad HC and the Federal Shariat Court.

---

## 1. Courts are data, with dated authority rules (D-116)

Replaces `CREATE TYPE court AS ENUM (...)` (docs/03 §1.1). The enum has no FCC, no AJK or GB courts and no
subordinate courts, and it cannot carry a date. docs/04 §6.1 already called it stale.

### 1.1 Tables

| Table | Holds | Key rules |
|---|---|---|
| `court` | `code` (PK text: `FCC`, `SC`, `FSC`, `LHC`, `SHC`, `PHC`, `BHC`, `IHC`, `AJK-SC`, `AJK-HC`, `GB-SAC`, `GB-CC`, and subordinate classes), `name`, `court_class`, `jurisdiction`, `established_on`, `abolished_on`, `established_by_version_id` | One row per court. `court_class` is `constitutional_apex`, `apex`, `shariat`, `high_court`, `subordinate`, `tribunal` or `special`. `jurisdiction` reuses the existing enum (fed, punjab, sindh, kp, balochistan, ict, ajk, gb) and is the court's territory |
| `court_seat` | principal seat, benches and circuit courts ("Rawalpindi Bench", "Circuit at Larkana") | A seat never changes authority; it is recorded because headers and filenames print it |
| `court_alias` | each printed form of a court's name → `court` | Added **only** from headers seen in landed judgments (`method = observed`, with the document). Never invented |
| `court_jurisdiction` | court × kind (`original`, `appellate`, `constitutional_writ`, `revisional`, `review`, `shariat`, `advisory`, `transfer`) × `validity` × `source_version_id` | Each row rests on a provision version: FCC original 175E, FCC appellate 175F, SC appellate 185, HC writ 199, FSC 203D, tribunals 212. It feeds the forum finder (docs/06) and records the jurisdiction a judgment invoked |
| `court_superintendence` | which courts are subordinate to which High Court, by territory | Art. 203: "Each High Court shall supervise and control all courts subordinate to it." Art. 201's "courts subordinate to it" is read through this table |
| `authority_rule` | deciding court (or class) → receiving court (or class), `effect`, `scope`, `subject`, `condition`, `validity`, source | See §1.2 |

### 1.2 `authority_rule`

```
deciding_court     text   → court.code, or a class
receiving_court    text   → court.code, or a class ('*' = all courts in Pakistan)
except_court       text   → e.g. FCC, for Art. 189(2)
effect             'binding'
scope              'question_of_law'   -- the constitutional formula: "to the extent that it decides a question of
                                          law or is based upon or enunciates a principle of law"
subject            NULL (all) | 'shariat_chapter_3A' (203GG)
condition          NULL | 'subordinate_to_deciding' (201) | 'same_court_smaller_bench' (case-law rules)
validity           daterange, EXCLUDE overlapping (deciding, receiving, subject) — the INV-5 pattern
source_version_id  → provision_version    } exactly one is NOT NULL: no rule without a source
source_paragraph   → judgment_paragraph   }
basis              'dated_text' | 'continuity_from_amendment_records' | 'case_law'
```

Only binding rules are stored. "Persuasive" is a doctrine, not a record. Where no binding rule applies, the resolver
says so; it never says "persuasive".

### 1.3 Seed rules, read from the corpus

| Rule | Source (served record) | Validity |
|---|---|---|
| SC binds all courts in Pakistan | Constitution copy `4510829f…`, Art. 189, version `016ce0e2…`: "Any decision of the Supreme Court shall … be binding on all other courts in Pakistan." | From the dated text [2016-06-08, 2017-01-07); to 2025-11-13 only under the continuity rule below |
| FCC binds all other courts, **including the SC** | Constitution (Twenty-seventh Amendment) Act 2025 s.34 (commenced 2025-11-13, recorded), substituting Art. 189; current Art. 189(1), version `1e2fab9c…` | [2025-11-13, ) |
| SC binds all other courts **except the FCC** | Art. 189(2), version `06875840…` | [2025-11-13, ) |
| A High Court binds the courts subordinate to it, "subject to Article 189" | Art. 201, versions `7d918c12…` (current) and `f81dda95…` (2016 copy); Art. 203 for "subordinate" | dated text, plus continuity |
| FSC (Chapter 3A jurisdiction) binds the High Courts and all courts subordinate to them, "subject to Articles 203D and 203F" | Art. 203GG, versions `a01bf855…` and `718665c5…` | dated text, plus continuity |

Rules for using the seeds:
- **Continuity rule.** The served Constitution is dated only from its capture (19 Jun 2026), and the older copy only
  for 2016. A gap between two dated texts is filled (`basis = continuity_from_amendment_records`) only when the
  amending Acts for the gap are held and `amendment_reference` shows none of them touches the article. Otherwise the
  gap answers **not recorded**.
- **Not recorded today:**
  - the AJK and GB courts, whose constitutional texts are not held;
  - the bench rules (a larger bench binds a smaller bench of the same court), which come from case law and are
    seeded only from the judgment paragraph that lays them down (`basis = case_law`).

### 1.4 The resolver

```
authority(deciding_court, receiving_court, subject, as_of)
  -> Binding(rule, source)              -- the rule that applies, and its record
   | NotBinding(rules_considered)       -- recorded rules exist, and none applies
   | NotRecorded(reason)                -- the rule cannot be read from the corpus
```

- `as_of` is the **research date** (docs/04 §6.1), not the decision date. A 2005 SC judgment asked about today is
  read under today's Art. 189(2).
- Precedent answers about whether a case binds pass the gate only on `Binding` or `NotBinding`. `NotRecorded`
  abstains on bindingness and may still show the judgment (docs/04 §6.4 `historical_discovery`).

---

## 2. Treatments: two vocabularies, and history kept apart from treatment (D-117)

docs/03 §1.1 lists 7 treatment values; docs/06 §5 lists 11 plus polarity and review status. docs/06 wins, because L5
owns treatment (docs/04 §6.5). It is corrected in three ways.

**2.1 A case treating a case's proposition** (`case_treatment`): `cited`, `applied`, `followed`, `approved`,
`explained`, `distinguished`, `doubted`, `disapproved`, `overruled`, `per_incuriam`.
- `per_incuriam` (decided in ignorance of a binding authority or a statute) is added because Pakistani judgments
  print it as a treatment.
- **Polarity is not stored.** It is a fixed map, so it can never contradict the treatment:
  - positive: applied, followed, approved;
  - neutral: cited, explained, distinguished;
  - negative: doubted, disapproved, overruled, per_incuriam.

**2.2 A judgment treating a provision** (`provision_treatment`): `cited`, `applied`, `interpreted`, `upheld`
(vires challenged and upheld), `read_down`, `struck_down`, `declared_repugnant` (FSC, Art. 203D). The last two
create `judicial_invalidation` evidence (§4.3).

**2.3 Subsequent history is not treatment.** "Affirmed" and "reversed" in docs/06 are what happened to *the same
case* on appeal. They live in `judgment_lineage` (§3.5), not in the citator's edges. A reversed High Court judgment
is flagged everywhere it is shown. That is a different fact from a later case doubting its reasoning.

Review rules:
- `review_status` is `machine_candidate`, `lawyer_verified`, `contested` or `rejected`.
- Negative treatments, `struck_down`, `declared_repugnant` and lineage reversals are displayed only when
  `lawyer_verified` (docs/06 §5.1).
- `method` is `grammar`, `model` or `human`, as in `legal_edge`.

---

## 3. Judgment identity: judgment, opinion, paragraph (D-118)

### 3.1 The ladder

Judgments enter by the statute ladder (docs/SCHEMA.md "The shape of it"):

```
source_observation → blob → document → page/text_block → judgment → judgment_opinion → judgment_paragraph
```

- Evidence is append-only, as for statutes. A re-extraction retires the earlier revision.
- Archives without source URLs (LHC, PHC) land with `source_id` = the archive. A later portal recrawl adds the
  official URL as a second observation of the same bytes.

### 3.2 `judgment` (partitioned by `decided_on`, docs/03 §7)

The docs/03 columns stay, with these corrections:
- `court` becomes `court_code` → `court`, plus `seat`.
- **Dates:**
  - `decided_on` NOT NULL is the date printed for the decision or announcement;
  - `decided_on_basis` records which printed phrase it came from ("Date of decision", "announced on",
    "decided on");
  - `hearing_on` and `uploaded_on` are kept separately.
  - A judgment with no printed decision date **does not land** (held with the reason). It is never dated from the
    upload date or the filename year.
- **Case:**
  - `case_no_printed`, plus `case_type` → the `case_type` table (§3.6), `case_number` and `case_year`;
  - `consolidated_cases` for a judgment that decides several cases;
  - `jurisdiction_invoked` → `court_jurisdiction` (writ under Art. 199, appeal, bail under ss.497/498 CrPC, and so
    on).
- **Bench:** `bench_size`, plus `bench_kind` (`single`, `division`, `full`, `larger`, `constitutional_bench`,
  `shariat_appellate_bench`).
- **Reporting:** `reported_flag` is set where the source marks it (Sindh's A.F.R. column). It is a ranking prior,
  never authority.
- **`neutral_citation`** is filled only when the judgment prints one.

### 3.3 `judgment_opinion`

- `kind`: `judgment_of_court`, `majority`, `concurring`, `dissenting`, `short_order`, `detailed_reasons`,
  `separate_note`, `order_sheet`.
- Plus `author_judge_id`, `joined_by[]`, `released_on`, `first_paragraph` and `last_paragraph`.
- The SC often announces a short order and releases reasons later, as two files. For example:
  - `H.R.C.No.19of1996DT19-10-2012.pdf`;
  - `H.R.C.19of1996[AsgharKhanCase]DetailedReasons.pdf`.

  That is **one judgment with two opinions**, each dated.
- Only `judgment_of_court`, `majority`, `short_order` and `detailed_reasons` paragraphs can carry a holding. A
  dissent's paragraphs are searchable and citable but never a treatment's evidence (docs/06 §5's opinion filter).

### 3.4 `judgment_paragraph` (partitioned by `decided_on`)

- **`printed_no`:** the number the judgment prints, else NULL.
  - `ordinal` is internal and never shown.
  - A citation renders "para 12" from `printed_no`, or "p. 4" from the PDF page when nothing is printed. A number
    the page does not print is a generated citation (INV-1, as D-115).
- **`role`:** facts, arguments, reasoning, holding or order (docs/03), set by method with review.
- **`text`:** the citable text, with `first_block` and `last_block` into `text_block` for provenance.
- **Official Urdu translations:** `judgment_translation` (`language`, `official`, document) links a translation to
  the same judgment and opinion. Translated paragraphs are searchable for Urdu queries (bilingual parity, docs/10).
  They are cited as the translation and never displace the English original as the authoritative text.

### 3.5 `judgment_lineage` — the same case up the hierarchy

- Columns: `lower_judgment_id` → `upper_judgment_id`, `relation`, `outcome`.
  - `relation`: appeal, leave petition, revision, review, intra-court appeal, remand.
  - `outcome`: affirmed, reversed, modified, set aside, remanded, leave refused, dismissed, withdrawn.
- It is read from "impugned judgment dated … passed by …" lines, and from case numbers that cite the case below.
- Used for:
  - subsequent-history flags;
  - the effective date of an FSC repugnancy decision, which waits for the appeal period or the appeal (Art. 203D(2)
    proviso, and Art. 203F's Shariat Appellate Bench).

### 3.6 `case_type`

The printed abbreviation maps to a kind, the jurisdiction invoked and the court, observed per court. For example:
- "Cr.M BA" → bail application;
- "W.P." / "Const. P." → constitutional writ, Art. 199;
- "C.P.L.A." → leave to appeal;
- "R.F.A.", "C.R." (civil revision), "I.C.A.", "H.C.A.", "Suit", "Crl.A".

This is what lets a user ask for "bail judgments under s.9(c) CNSA from Peshawar" (§4.2's `charge` role).

### 3.7 Gates before release (J1–J8, asserted as audit criteria when built)

| Gate | Requirement |
|---|---|
| J1 | A printed decision date; without one, released marked undated (D-124) |
| J2 | The court resolved by `court_alias` |
| J3 | A case number parsed into the `case_type` table, or held |
| J4 | Paragraph coverage ≥ 98% of the body characters (docs/02's coverage gate) |
| J5 | No reporter headnote (§5) |
| J6 | A duplicate check (same court, case and date, or the same bytes) |
| J7 | Every opinion has a kind |
| J8 | A text layer, or the D-114 two-reader OCR rule |

---

## 4. Links: which law a judgment quotes, and which cases it cites (D-119)

### 4.1 `judgment_statute_reference` — judgment → provision (derived, rebuilt from the release)

The same discipline as `provision_reference` (D-108): a named linker (`nizam.judgment_links/1`), a rebuild on a rule
change, and an audit criterion (A24: the table is exactly the release under one linker, and every destination is
released).

| Column | Holds |
|---|---|
| `paragraph_id`, `char_start`, `char_end` | where it is printed |
| `raw` | as printed: "S. 302(b) PPC", "u/s 497 Cr.P.C.", "section 9(c) of the Control of Narcotic Substances Act, 1997", "Article 199 of the Constitution", "Order XXXIX Rules 1 and 2 CPC" |
| `label`, `subs[]` | 302 and (b) |
| `law_printed`, `alias` | the law as written; the alias key |
| `dst_instrument_id`, `dst_provision_id` | the deepest unit that resolves (clause (b), not just s.302) |
| `dst_version_id`, `version_basis` | the version **in force on `decided_on`** in the court's territory (`dated`), or `not_dated` when the decision predates the law's `text_known_from` |
| `resolution` | `resolved`, `ambiguous` (alternates kept, as D-097), `law_not_held`, `unit_not_found`, `no_law_named` |
| `role` | see below |
| `amended_since`, `repealed_since` | computed against `operative_provision` at read time, never stored as truth |

`role` values:
- `charge`: "offence under section …", FIR and charge lines.
- `quoted`: a verbatim quotation matched against a version's text. The match also proves which version the court
  read.
- `challenged`: "ultra vires", "unconstitutional", "repugnant".
- `interpreted`: the paragraph construes the words.
- `cited`: everything else.

Rules:
- **One grammar.** The citation grammar and aliases in `nizam/retrieval/citations.py`, and the title resolver in
  `nizam/storage/linking.py`, move to `nizam/shared/` as pure functions. Retrieval (L3) and the judgment linker (an
  L1/L2 worker) import the same code, so the layer rule holds and two grammars cannot drift.
- **Territory.**
  - A title that names its province resolves there.
  - A bare title takes the **deciding court's territory** (a Lahore HC judgment citing "the Rented Premises Act" →
    Punjab), then federal.
  - Exactly one law must match, or the result is `ambiguous`.
- **Aliases grow from evidence.** A practitioner abbreviation seen in judgments (PPC, CrPC, CPC, QSO, CNSA, ATA,
  NAO, MFLO today) is added to the shared table only with the law it was resolved to by a person, from a sample of
  judgments.
  *As built (D-134, 24 Nov):* the table is `law_alias` (0130), filled from `docs/alias-review/` sheets by
  `tools/alias_review.py`. The first sheet read 172 printed names and made 81 aliases. An alias needs two judgments,
  or a year that makes the name unique. Act numbers, schedule Articles and names without their province stay
  unresolved. The grammar also changed: a title stops at its sentence's end or at the next citation, and trailing
  parentheses ("(V of 1908)") are dropped while any year inside them is kept.
  *As built (D-135, D-136):*
  - **Aliases and back-references.** 188 aliases; "of the Act." refers back by kind and year.
  - **Copies.** A High Court's citation of a federal law is also linked, in `alternates`, to its own province's copy
    where that unit is the same provision. Punjab's PPC s.489-F (a prize-bond offence) and ss.375/376 (repealed
    stubs) never are.
  - **Readers.** "Cases on this section" and the cited generator read every copy.
- **Time.** The version is the one valid on the decision date. When the law has since been amended or repealed, the
  reader and the answer say so: "This judgment read s.X before its substitution of <date>." The date comes from the
  version records.
- **Uses:**
  - `v_provision_judgments`: "cases on this section" in the reader, by court, with roles and dates;
  - assembly attaches leading judgments to a statute answer;
  - L3 graph expansion: a question about s.497 CrPC reaches bail judgments that apply it.

### 4.2 `judgment_case_reference` — judgment → judgment

- Printed reporter citations ("PLD 2016 SC 1", "2019 SCMR 1234") and case numbers ("Civil Appeal No. 123 of 2015").
- They resolve to a judgment by (court, case number, year), or by a `reporter_ref` alias already attached to that
  judgment.
- Unresolved rows are kept with the reason, as the statute links keep theirs.
- A `case_treatment` edge (§2.1) is classified on top of a resolved reference: the grammar for explicit verbs
  ("overruled", "distinguished", "followed", "per incuriam") first, then model candidates. Both are reviewed.

### 4.3 `judicial_invalidation` → `legal_edge` `invalidated_by`

- **Columns:** judgment, opinion, paragraph, provision, `extent` (as printed), `effective_on`, `appeal_state`,
  `review_status`.
- **Effective date:** read from the decision ("specify the day on which the decision shall take effect", Art.
  203D(2)(b)). For an FSC decision it is held back while an appeal lies or is pending (203D(2) proviso), read from
  `judgment_lineage`.
- **Effect on serving:**
  - Only lawyer-verified rows become `invalidated_by` edges.
  - `operative_provision` then serves the provision as struck down from `effective_on`: removed from operative
    evidence and kept for historical discovery.
  - `invalidation_coverage` changes from `not_tracked` to the courts and years held (§6).

---

## 5. Official text only: reporter reprints (D-120)

- **What a reprint is:** a file whose first page opens with a reporter citation and editorial headnote, e.g. "2014
  M L D 446 [Peshawar] … Penal Code (XLV of 1860)---S. 302(b)---Qatl-e-amd---".
- **What happens to it:**
  - It is recorded as a non-authoritative copy and **not landed**.
  - Its reporter citation is kept as a `reporter_ref` identifier (series, year, page, court tag) on the judgment, once
    the official copy is held. No reporter prose is stored (nizam-corpus copyright line; docs/04 §R0).
  - The official copy is recrawled from the court's portal.
- **Detection:** a reporter citation in the first lines plus at least four `---` headnote separators. A person reads
  the borderline cases.
- **Expected volume:** about 8–9% of Lahore and Peshawar files (sample), roughly 900.

---

## 6. Search storage, coverage, privacy (D-121, D-122)

### 6.1 Judgment chunks are their own tables (D-121)

- **Tables:** `judgment_chunk` holds offsets into `judgment_paragraph.text`, partitioned by `decided_on`. Its vectors
  are in two places:
  - its own `bit(1024)` bge-m3 column;
  - `judgment_chunk_embedding_gpu` (`bit(4096)`, Qwen3-8B).

  Both use the **same** embedding generations as statutes, so one query vector searches both. Each space has its own
  HNSW and BM25.
- **Why separate:**
  - `chunk` is defined against `provision_version`, and A20–A22 assert it is exactly the statute release.
  - A judgment span must never pass the statute gate.
  - Precedent mode needs its own calibrated gate (docs/04 §6), and the date partitions prune.
- **As built (D-132, 24 Nov):** the bge-m3 bits may come from the laptop's int8 encoder or from a Kaggle GPU run in
  fp16. Both are generation 1, as the statute chunks are. `judgment_chunk --export` / `--load` move the missing
  chunks through the GPU, and A27 asserts one generation and one chunker.
- **INV-4:** above L2, a precedent is cited by `judgment_paragraph`, never by a chunk.
- **Publishing and offline:** `publish_scope = 'judgments'` (docs/03) lets a small deployment leave judgments out.
  Judgments are network-only, not in the offline pack (docs/03b).

### 6.2 Coverage is a first-class fact (D-122)

- `v_judgment_coverage` gives, per court and year: documents held, source, last crawl and known gaps (the Sindh
  recrawl, the missing courts).
- Every precedent answer and every `AuthoritySignal` (docs/06 §5.1) carries it. "No adverse treatment found" is
  always "within this coverage".

### 6.3 People in judgments (D-122)

- **Party names:**
  - `parties_raw` is internal.
  - `parties_display` is redacted for categories the product treats as sensitive: family, sexual offences, minors,
    medical. Each category names its statutory basis from the corpus where one exists, or is marked as product
    policy. No basis is asserted from memory.
  - Party names are not a search key.
- **Judges** (`judge`, `judge_alias`, from printed benches) are recorded for bench composition and opinion
  authorship only. **No per-judge outcome statistics and no outcome prediction** (docs/06: L5 does not "predict a
  judge").

---

## 7. Build order

Each step is one slice, finished before the next:

1. **Migration: the court registry and authority rules** (§1), seeded from the records in §1.3. The tests cover the
   EXCLUDE on overlapping rules, the source CHECK and the resolver's three results.
2. **Migration: the judgment, opinion, paragraph, lineage and case-type tables** (§3), partitioned.
3. **Supreme Court ingest, text-layer files**: header parse, opinions, paragraphs, gates J1–J8.
4. **The shared citation grammar and the judgment → statute linker** (§4.1), with A24.
5. **Judgment chunks, embeddings and precedent search**, with a precedent stratum in the golden set (docs/10).
   *As built (D-133, 24 Nov):* the stratum is `golden-pk-v1-precedent1`: 58 cases, gold at judgment paragraphs,
   split by family, harness `evals/precedent_eval.py`. Provisional test figures: hit@10 .65, recall@50 .90, no
   leaks. It shows four gaps: no case-number fast path; provision questions rank low; Urdu queries miss; and no
   precedent gate for courts not held.
   *As built (D-137):* a printed case number ranks its case first (3/3 dev, 1/1 test). A court asked for narrows the
   search, and a court not held returns a typed `coverage_gap` with no hits (5/5 declined). The cited window counts
   judgments. Urdu is unchanged; its route is the 8B space.
6. **Lahore HC, Peshawar HC** (the OCR route, D-114), the reprint rule (§5), then the Sindh recrawl, then FCC, IHC,
   BHC, FSC and the AJK and GB texts and courts.
7. **Case references and treatments** (§2, §4.2), lineage (§3.5), invalidation (§4.3), then the citator (docs/06 §5).
