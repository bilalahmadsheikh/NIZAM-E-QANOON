---
name: nizam-ux
description: Interaction and content rules for Nizam-e-Qanoon — who the users are and how the product can harm them, information architecture and journeys, question intake, answer anatomy, showing sources and status, communicating uncertainty, plain language and voice, trust and privacy signals, and the UX research programme. Load when designing a flow, writing user-facing copy, deciding what a screen says, or reviewing how uncertainty and status are communicated.
---

# Nizam-e-Qanoon — UX and interaction

**Reference:** `docs/13-ux-and-interaction-architecture.html` · `docs/12-design-system.html` (visual vocabulary) · `docs/08-client-architecture.html` (client mechanics)
**Intent:** The people using this are frequently frightened, often unable to read fluently, and rarely able to tell a good legal answer from a plausible one. Every interaction decision is a decision about how much they can safely rely on us.

## The people, and the harms

National literacy is around 60% and legal literacy far below it. The realistic user is on a mid-tier Android phone, on a metered connection, with a deadline they do not know exists.

**The harms are specific and asymmetric:**

- Acting on law that has been repealed or struck down
- Missing a limitation period because the deadline was below the fold
- Mistaking information for advice and not consulting anyone
- Filing in the wrong forum and losing time that cannot be recovered
- Being surveilled for asking about a sensitive matter

Design against these, in this order. A pretty screen that lets someone miss a limitation period is a failure.

## Answer anatomy

**Deadline before doctrine.** Where a matter is time-sensitive, the limitation period is surfaced *above* the substantive right. A correct explanation of a remedy that is already time-barred is not a useful answer.

Every claim ends in a citation chip; every chip reaches the source in **two taps**. The provenance sheet shows authoritative text verbatim with the matched span highlighted — the reader is being invited to check us, and the interaction should feel like that.

## Uncertainty is communicated, never smoothed

- **Abstention is a destination**, with its own route, layout and three actions: rephrase, browse, find an advocate. It states **what was searched** — jurisdiction, date, corpus size — so a refusal becomes information rather than a dead end.
- Nearest-but-unconfirmed results are **visually demarcated** and never styled as results.
- A partially-supported claim shows a visible qualifier. Silently dropping it and silently keeping it are both wrong.
- Coverage is stated wherever absence could be misread: "from 3,412 SC judgments indexed, 2009–2026" rather than an empty list.

## Status is chrome, not a detail

Repealed, not-yet-commenced and superseded-at-`as_of` banners sit **above** the text they qualify and cannot be collapsed. The scope bar — jurisdiction and `as_of` — is permanent, because an answer is only true within them.

Offline views carry the pack version and build date **inline**, not in settings. A reader must never have to wonder whether what they are reading predates an amendment.

## Language and voice

Three independent axes: UI language, content language, input script. **Roman Urdu is a primary input path**, not a fallback — most people type Urdu in Latin script.

**Urdu voice in and out is the largest single reach gain in the product** — the difference between serving the top decile of the target population and serving the target population. Treat it as a primary affordance in the search field, not an accessory in a menu.

Plain speech and professional register render **the same grounded payload** — a reading-level control, never a second retrieval.

## Copy rules

- Register is "the law provides X", never "you should do X". Never recommend an action in the user's own matter.
- Name things as a person recognises them: *what happened to you*, not the statutory concept. "Locked out by a landlord", not "wrongful dispossession".
- Errors say what went wrong and what to do. No apologies, no vagueness.
- The disclaimer is quiet enough to live with and present enough to mean something. It is structural and non-dismissible.
- Never fabricate a fact to fill a slot — a missing rate or date is a visible placeholder, not an invention.

## Research programme

Journeys are validated with real people, stratified by legal literacy and language preference, including participants who cannot read fluently. Task completion and *comprehension of uncertainty* are both measured — a user who confidently misreads an abstention is a failure the SUS score will not show.

## Verify online before you claim

- **Platform accessibility and interaction guidance** (iOS HIG, Material, WCAG 2.2) rather than a remembered threshold.
- **Urdu STT/TTS availability** per OEM and OS version before designing around on-device voice.
- Any statistic about literacy, connectivity or device mix that appears in user-facing or thesis copy.

## Common failures

- Burying the deadline below the substantive explanation.
- Rendering an abstention as an error, a toast, or an empty state.
- A dismissible disclaimer.
- Icon-only primary navigation.
- Copy written from the statute's point of view rather than the person's.
- Treating voice as an accessibility checkbox instead of the main road in.
