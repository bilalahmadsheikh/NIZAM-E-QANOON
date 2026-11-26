# Sources not yet held: judgments and the laws judgments cite (26 Nov 2026)

Research by the `legal-source-scout` agent on 26 Nov 2026. These are leads, not acquisitions.

- **(V):** a page or PDF opened and read.
- **(S):** read through a fetch tool's summary, so column lists and links are second-hand.
- **Status:** nothing here is a ruling on a law's status. A status is quoted only with its source.

Before any crawl: confirm the site structure, read its robots.txt, and never pass a captcha or a login (D-139).

## Judgments

| Source | Official URL | What it serves | Barrier | Next step |
|---|---|---|---|---|
| **Islamabad High Court** | mis.ihc.gov.pk: `/frmJgmnt.aspx?jgs=1` (judgments), `/frmSrchOrdr.aspx` (case law) | ASP.NET (S). Text-layer PDFs at `attachments/judgements/<id>/<n>/<name>.pdf` (V: Customs Reference 112/2023, "uncertified" watermark). Filters: approved for reporting, important, year, judge, citation series | None seen. robots.txt 404 | **Landed 26 Nov (D-156):** 2,736 released from its public JSON listing (`ihc.asmx/srchDecisionClms`), case types 0140; Art. 201's high-court rule already reaches its subordinate courts. Left: 370 held, 291 for OCR, 78 the server would not serve |
| **Federal Shariat Court** | federalshariatcourt.gov.pk: `shariatjudgment2.2.php` (169 Shariat petitions, 1980–2025, with law challenged), plus criminal, suo motu and landmark pages | WordPress. The criminal and suo motu tables fill by AJAX (`admin-ajax.php`, which robots.txt allows) | None seen | **Landed 26 Nov (D-157):** 281 released (Shariat petitions, criminal appeals, suo motu), case types 0142; the law challenged kept in the listing for a later `invalidated_by` reading. Left: 137 held (mostly old OCR text layers), 98 for OCR, 29 the server answers 404 |
| Competition Appellate Tribunal | cc.gov.pk/home/decidedcatcases | 88 decided cases 2013–2026, PDFs | None | Small; a tribunal court record needed |
| NIRC (labour) | nirc.gov.pk | About 80 judgments (single and full bench), PDFs | None | Small |
| Appellate Tribunal, Punjab Revenue Authority | atpra.punjab.gov.pk | Judgments table with PDFs (S) | None seen | Candidate |
| Sindh Revenue Board | srb.gos.pk/srb/judgements/ | Not opened (TLS error) | — | Retry |
| ATIR (Inland Revenue) | No own site. fbr.gov.pk/categ/appellate-tribunal/665 has 7 curated PDFs | — | — | Not a bulk source |
| Federal Service Tribunal | fst.gov.pk | **Hosting account suspended** (26 Nov) | Site down | Write to the Registrar |
| Punjab / Sindh / KP Service Tribunals | pst.punjab.gov.pk; sstsindh.gov.pk/judgements.php (empty table); kpst.gov.pk | Unverified whether judgments are public | Unknown | A browser look first |
| **Family courts** (all provinces) | No official publication found. Punjab dsj.punjab.gov.pk and Sindh cases.districtcourtssindh.gos.pk are case-management systems (cause lists, status) with a math captcha or login | Not judgments | Captcha / login | Not available officially. **Islamabad district courts**: a site launched Jan 2025 reportedly shows final judgments (The News, opened); its URL was not found. Ask IHC IT |
| District and sessions courts, banking courts, environmental tribunals, Customs Appellate Tribunal, Wafaqi Mohtasib | None found | — | — | Not available officially |

Family-law **appeals and writs** are already held inside the High Court judgments (LHC, PHC, SHC, BHC). Family
courts themselves publish nothing officially that we could find.

## Laws judgments cite that the corpus lacks (D-151's "not held" rows)

| Law | Official source | Notes |
|---|---|---|
| Punjab Local Government Act 2013 (repealed) | punjablaws.gov.pk/lawspdf/111143.pdf (V, 110 pp, consolidated) | On the portal's repealed list. The 2019 and 2022 Acts are there too |
| Sindh Buildings Control Ordinance 1979 | sindhlaws.gov.pk PubID PUB-NEW-26-000131 (S, "updated till 23-Sep-2026") | **Already held** (document 9910); D-151 aliases SBCO/SBCA to it |
| Sindh Land Revenue Act 1967 | Not on sindhlaws.gov.pk; only amending Acts (V: Act III of 1976). A department HTML copy at sindhforests.gov.pk is unofficial | The Board of Revenue page was down. Owner question: no official text |
| Representation of the People Act 1976 | Pakistan Code (URL from search; **TLS chain error** on every fetch) | Repeal by the Elections Act 2017 is reported, not verified. Needed for judgments decided before 2017 |
| Cooperative Societies Act 1925 | punjablaws.gov.pk (Punjab copy, held); Sind copy on Pakistan Code (TLS error) | Sindh Act XXVIII of 2020 replaced it in Sindh (held) |
| Punjab Local Government Ordinance 2001 | Not on punjablaws.gov.pk; copies only on department hosts | Unofficial |
| Civil Service Regulations | No official page; a 2018 edition PDF on pasb.mod.gov.pk (not opened) | Ask the Finance or Establishment Division |
| Government of India Act 1935 | legislation.gov.uk (S, enacted text) | Historical, foreign-official |
| Sindh General Clauses Act | Not found (West Pakistan Act VI of 1956 as applied) | — |
| AJK and GB General Clauses Acts | AJK applies the federal 1897 Act as adapted (1959 adaptation list, law.gok.pk; not opened); GB not found | — |

`pakistancode.gov.pk` answered every fetch with a TLS certificate-chain error on 26 Nov. A copy of its intermediate
certificate fixes the chain without disabling verification.
