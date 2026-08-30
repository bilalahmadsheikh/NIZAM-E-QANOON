---
name: nizam-client
description: Rules for the Nizam-e-Qanoon client layer (L7) — Flutter app, web research surface, public SEO pages, curation console, the seven client sublayers, the signed offline pack and delta sync, offline grounded answers, navigation and routes, the invariant-bearing components, bidirectional Urdu typography, accessibility, and performance budgets. Load when working on Flutter, the web app, offline behaviour, screen states, RTL, or anything a user sees.
---

# Nizam-e-Qanoon — client

**Reference:** `docs/08-client-architecture.html` · `docs/12-design-system.html` (visual vocabulary)
**Intent:** L7 is terminal: it reads, never writes to the corpus, and holds no authority over legal content. Its job is to present grounded material truthfully, keep working when the network does not, and be usable by someone who cannot comfortably read.

## Seven sublayers, strictly ordered

`presentation → interaction state → client domain → data access → {local store ‖ remote access} → platform`

Local store and remote access are **siblings with no edge between them**. The source decision lives one level up in a repository, so airplane mode changes what data is available, never which code runs.

**A widget may not import a repository, a source, or a platform service.** Enforced in CI.

## Offline is a mode, not a cache

Content classes decide the read path — the **class**, not the network state:

- **Pack-authoritative** — statutory text, tree, cross-references, definitions, explainers, glossary, procedure guides, calculators. Local first, always, **never revalidated**: the pack is signed, so it is as trustworthy as the server.
- **Answer-pack-served** — grounded answers to the head of the query distribution. Local question index first, network only on a miss.
- **Network-required** — novel questions, precedent, judgments, drafting. INV-2 forbids a client-side substitute.

Sizes, measured: app 25 MB · core pack 17/51 · semantic tier 27/32 · answer tier 12/27 → **base experience 56 MB download, 135 MB on disk**.

**Offline answers ship as verified artefacts, not an on-device generator.** A 1B four-bit model is ~800 MB, slow to prefill, and reasons about Pakistani law worse than the server already did.

Every offline provision view is **stamped with the pack version and build date** — inline, not in settings. A reader must never wonder whether what they are reading predates an amendment.

## Screen states — eight, and four of them are not errors

`Loading · Ready · Empty · Abstained · Offline · Stale · Degraded · Error`

**Abstained, Offline, Stale and Degraded are outcomes.** None may borrow error styling, an error icon, or a retry affordance. Error framing invites the reader to interpret silence as absence of law rather than absence of confidence.

## The components that carry invariants

- **`CitationChip`** takes a resolved citation object, never strings to join. Cannot render without a real identity.
- **`ProvenanceSheet`** — authoritative text verbatim, matched span highlighted, validity stated, onward to amendment chain and citator. Two taps from any claim.
- **`AbstentionCard`** — its own route and layout, nearest results visually demarcated, referral off-ramp always offered.
- **`StatusBanner`** — above the text, not below; non-collapsible for repealed and not-yet-commenced; carries the savings clause.
- **`ScopeBar`** — jurisdiction and `as_of`, permanently visible.
- **Disclaimer** — structural, non-dismissible, on every generated surface.

A redesign may restyle these. It may not remove them.

## Bilingual — three independent axes

UI language · content language · **input script**. They move independently: a user reads Urdu chrome around English statutory text and types `talaq` on a Latin keyboard, routinely.

- **Bidi:** every foreign run wrapped in `U+2068 … U+2069` (first-strong isolates, **never** the deprecated LRE/RLE embeddings — those leak across adjacent runs). Neutrals — brackets, commas, the dash in `302–304` — otherwise migrate to the wrong end. **A citation whose parts reorder is a different citation.**
- **Two type scales chosen per run by script**, not by locale, because one sentence contains both.
- **Statutory identifiers always use Western digits**, in both scripts. A localised section number is a wrong citation.
- Nastaliq has no usable bold — emphasis by size and colour.
- Mirroring: layout mirrors; the **amendment timeline does not** — it is a chronological axis, not a reading order.

## Accessibility is reach, not compliance

Urdu voice in and out is the single largest gain — it is the difference between serving the top decile of the target population and serving the target population. STT runs on-device where available, and **the server fallback is disabled entirely in anonymous mode**: a voice query leaving the device is a recording of someone describing a legal problem aloud.

48 dp targets · 4.5:1 body contrast in both themes · no information by colour alone · reduced-motion honoured · icons never without text labels in primary navigation.

## Performance budgets, enforced in CI

APK ≤ 25 MB · cold start ≤ 1.5 s p95 · no frame > 16.7 ms · offline FTS ≤ 300 ms, vector ≤ 800 ms · public page ≤ 60 KB HTML with **zero required JS** — it is a legal reference people will cite and print.

## Verify online before you claim

- **Flutter, sqlite-vec and FTS5 capabilities** on the target platforms before designing around them.
- **Platform Urdu STT/TTS availability** — on-device model coverage varies by OEM and version.
- **iOS HIG and Material guidance** when a platform convention is in question rather than guessing.

## Common failures

- Rendering an abstention as a toast or an error state.
- Building a citation string in the client.
- A repository read that omits `as_of`.
- Choosing the type scale by locale instead of by run.
- Treating the offline pack as a cache and revalidating it.
