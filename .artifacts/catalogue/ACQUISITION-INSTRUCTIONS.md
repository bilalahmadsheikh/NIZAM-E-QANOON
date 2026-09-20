# Acquisition lane instructions (re-check the declared exceptions)

Forty catalogued items never landed in the corpus. Each one carries a declared,
evidence-backed exception with its dated attempts and the observed error. Those
assertions were true when they were made; the question now is whether the item
can be obtained today from an official source.

**You research and report. You do not download into the corpus, do not write to
the database, and do not edit repository files** other than your own result
files. Nothing you find is "landed" until the acquisition pipeline fetches it
under its own provenance rules.

## What counts as an official source

In order of preference:

1. The portal that catalogued the item (`pakistancode.gov.pk`,
   `sindhlaws.gov.pk`, `kpcode.kp.gov.pk`, `punjabcode.punjab.gov.pk`,
   `balochistancode.gob.pk`) — a different URL on the same portal is the best
   possible answer, because the catalogue entry simply moved.
2. Another government portal of the same or a superior jurisdiction. Many
   pre-partition Acts that a provincial portal serves badly are also published
   federally on `pakistancode.gov.pk`.
3. The official Gazette copy published by the issuing government.

A commercial reproduction, a law-firm upload, a blog, a PDF aggregator, Scribd,
or an archive of a non-official copy is **not** acceptable. Say so plainly if
that is all that exists.

`web.archive.org` of the ORIGINAL official URL is acceptable as evidence that
the document existed and of what it contained, but record it as
`archived_official_copy`, not as a live source — it is a different decision for
the corpus owner to make.

## What to do for each item

1. Try the catalogued URL yourself and record what you actually get today
   (status, content type, what the page says). The error in the row is dated —
   confirm it or contradict it.
2. Search the portal for the title. Portals re-key their publication ids; the
   same Act often sits at a new `PUB-...` number. Check the portal's own index
   or search page rather than guessing ids.
3. If the portal is the problem rather than the document, look for the same
   instrument on another official portal by its exact short title and year.
4. Stop when you have either a working official URL or clear evidence that none
   exists. Do not spend more than a handful of fetches per item.

## Output

One JSON file per exception, written as soon as you finish it, to:

`E:\Nizam_e_Qanoon\.artifacts\catalogue\results\acquisition\<exception id>.json`

```json
{
  "exception_id": 13,
  "title": "ELECTRICITY ACT, 1910",
  "catalogued_url": "https://punjabcode.punjab.gov.pk/uploads/articles/ELECTRICITY%2BACT%252C%2B1910.doc.pdf",
  "recorded_reason": "served_content_is_not_a_pdf",
  "checked_at": "2026-09-17",
  "still_fails": true,
  "observed_today": "HTTP 200, Content-Type application/msword; the first bytes are a Word compound file, not %PDF",
  "outcome": "found_official_alternative",
  "candidate_url": "https://pakistancode.gov.pk/pdffiles/....pdf",
  "candidate_source": "pakistancode.gov.pk",
  "candidate_evidence": "the page titled 'Electricity Act, 1910' on the federal code portal links this PDF; the first page prints 'THE ELECTRICITY ACT, 1910 (IX of 1910)'",
  "same_instrument_confidence": "high",
  "notes": ""
}
```

`outcome` is one of:

- `resolved_same_portal` — a working URL on the portal that catalogued it
- `found_official_alternative` — a working URL on another official portal
- `archived_official_copy` — only `web.archive.org` of the official URL works
- `confirmed_unavailable` — the exception stands; say what you checked
- `needs_second_look` — you could not settle it; say exactly what is missing

Never record a `candidate_url` you have not actually fetched and confirmed is
the right instrument. If the title matches but the year or jurisdiction differs,
that is `needs_second_look`, not a resolution.

When your batch is done, reply with a count by `outcome` and name any item you
could not settle.
