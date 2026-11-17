# Mobile library: implemented preview slice

## 17 November 2026 (later): section lists, popular laws, reading modes, scope bar, measured performance

**A law page lists every section.** `GET /v1/law/instruments/{id}/sections?as_of=&territory=&limit=&after=`
returns the law's served sections in printed order, 40 to a page (at most 100). Each entry carries:
- its label and heading;
- the first 300 characters of its own words;
- its Part or Chapter;
- the first PDF page;
- `survives_repeal` (0103);
- a citation rendered on the server from the records (`render_citation`: "Pakistan Penal Code, 1860, s. 302";
  INV-1).

The index is built from `operative_provision` at the requested date and territory (INV-5). It is cached per (law,
date, territory) for 10 minutes, and the server warms it for the popular laws at startup. A warm page takes about
5 ms. The cursor is the last ordinal, bound to its scope.

**Each section is a card** (`presentation/sections.dart`):
- its name is a button to the full text;
- two lines of its wording follow, with amendment and omission markers raised (`²[…]`, `⁴* * *`);
- a "Read more" button leads to the same page.

The list is a lazy sliver. It asks for the next page 15 rows before the end of what is loaded, so on a fling the
rows are in memory before the finger gets there. The law page keeps a Sections / Structure switch; Structure is the
earlier tree.

**Popular laws on the home page.** `GET /v1/law/collections/popular` returns 18 laws:
- Constitution, PPC, CrPC, CPC, Qanun-e-Shahadat and Contract Act;
- Specific Relief, Limitation, Transfer of Property, Muslim Family Laws, Family Courts and Guardians & Wards;
- Anti-Terrorism, Narcotics, Income Tax, Companies, Registration and Stamp.

The list (`nizam/api/collections.py`) names each law by document id and also states the title it must carry. A
document whose title has changed is dropped rather than shown under a wrong name. The carousel
(`presentation/popular.dart`) is a horizontal lazy list headed "A starting shelf, not a ranking in law".

**Reading modes** (`domain/reading_mode.dart`), chosen from the scope bar: Everyday, Student, Lawyer and Judge. Doc
13 §02 sets the limit: a mode models circumstances, not a persona; it uses progressive disclosure, not deletion; and
a professional view adds evidence density, not certainty. So a mode changes density and tools only. It never
changes which law is served, a status, or a qualification, and choosing "Judge" verifies nothing.

| Mode | Changes |
|---|---|
| Everyday | Reader text +2 pt; no Part/Chapter headers in section lists; no citations |
| Student | Part/Chapter headers; citation shown with each section |
| Lawyer | Denser cards, reader −1 pt, one-tap citation copy, PDF page beside each section |
| Judge | As Lawyer, plus a record panel above the text: as-at date, territory, currency and its basis code, enacted, commenced and repealed dates, reach and how the reach was read, and the not-served code |

The mode is held in memory only. It is not yet kept across app restarts, because no persistence package is added:
`shared_preferences` pulls in a newer Android toolchain, and the URL-launcher pin already holds that back.

**The scope bar** is one horizontally scrollable row: preview tag, reading mode, territory and date. Territory
covers all seven territories plus "All". With AJK chosen, the federal PPC is refused with "This law does not apply in
Azad Jammu and Kashmir" (code `law_does_not_run_in_territory`), because its recorded reach is the four provinces
and ICT.

**Catalogue.** The catalogue searches `mv_instrument_serving` behind a trigram index (0105; 0104's index on the
base table was dropped). It sorts by title with numbers, punctuation and a leading "The" ignored. Title-prefix
matches come first, and amending laws come after the laws they amend. Search went from 0.9 s to 6–8 ms. Urdu titles
are no longer sorted first.

**Back on a tab root** now returns to Discover; the app no longer exits.

**Verified:**
- 15 Flutter tests. A new one opens the reader in Judge mode and checks that the record panel shows the served
  record, the text is identical, and there is still exactly one provision request. Everyday shows no panel.
- API tests for paging, the scope-bound cursor, `render_citation`, and the popular list dropping a retitled
  document.
- On the emulator:
  - the carousel, then the PPC with 645 sections served on 2026-11-17;
  - the Judge panel;
  - the AJK refusal;
  - Back from the Library root.

**Measured on the emulator** (Android 16 x86-64, GLES translated to the host's AMD GPU; a phone is needed for
budget figures):

| | Result | Budget (client skill) |
|---|---|---|
| APK, release, one ABI (x86-64) | 8.2 MB | ≤ 25 MB |
| Cold start, release, after first launch | 1.8–2.2 s | ≤ 1.5 s p95 |
| Cold start, profile | 2.7–2.9 s | — |
| Section list fling, frame build | p50 1.8–2.0 ms, p90 6–7 ms, 8–13 of ~790 frames over 16.7 ms | no frame > 16.7 ms |
| Reader fling, frame build | p50 1.5 ms, p99 6.4–7.6 ms, none over | no frame > 16.7 ms |
| Raster, both screens | p90 17–19 ms | — |

The emulator's raster figures are an upper bound, because every draw call crosses the GL translator. The benchmark
is `integration_test/scroll_perf_test.dart`, run with `flutter drive --profile` (command in its header). It collects
the engine's FrameTiming reports directly: `watchPerformance` also asks the VM service for garbage-collection counts,
and that connection fails on this emulator.

**Open:**
- the section list's build tail (8–13 frames over budget, worst 95–185 ms). It needs a timeline on a phone; the
  likely suspects are page arrival rebuilding every built card, and fast flings laying out many cards in one frame;
- cold start against the budget, on a phone;
- reading-mode persistence;
- corpus defects seen while reading (both fixed later the same day: DECISION-LOG D-060, D-062, D-063):
  - the federal PPC has footnote numbers segmented as false sections ("499" and "70" between s.4 and s.5; the known
    label-run defect);
  - "__" print artefacts survive in some texts.

## 17 November 2026: first emulator run, crash fix, and the section reader

**First Android build and device run.** A debug APK was built from `apps/mobile` and run on an Android 16 x86-64
emulator. The API ran in WSL, so the app was built with `API_BASE_URL=http://<WSL-IP>:8080`: Windows `localhost`
did not forward to WSL on this host, and the emulator's `10.0.2.2` default reaches Windows only.

**Crash, found and fixed.** Opening a law aborted the Flutter engine's raster thread:
`impeller/renderer/backend/gles/render_pass_gles.cc: Must be able to encode GL commands without error`. The trigger
was the navigation bar's `BackdropFilter(blur 12)`; with it replaced by a solid panel, the same journey runs
without a crash. Impeller's OpenGL ES path is also what phones without Vulkan use. The blur sat over a 91 %
opaque surface, so it was barely visible, yet it cost an offscreen pass on every frame behind every screen.

**Law text is read through `operative_provision` (INV-5).** The September adapter read `provision_version` and the
release views directly. It therefore ignored currency, territory, partial repeals (0102), surviving units (0103) and
`text_known_from`. A repealed section would have been shown as current text.

New endpoint `GET /v1/law/provisions/{id}/text?as_of=&territory=` returns:
- the unit and its whole served subtree, in printed order with depth, capped at 400 nodes with a `truncated` flag;
- the law's serving record (`LawStatus`: currency and reason);
- for an empty subtree, a `not_served` code saying which record decides it.

The codes are `unit_repealed`, `law_repealed`, `law_not_current`, `law_historical`, `law_not_yet_in_force`,
`law_does_not_run_in_territory`, `law_repealed_in_territory`, `served_through_consolidated_text` and
`no_text_for_date`.

The unit is resolved first, and the view is then queried with the instrument id and path as values. Joined from a
CTE, the planner evaluated the view over every law: 47 s for one section. With values it takes about 10 ms.
Measured: 35–260 ms per call.

**Instrument records carry `currency` and `currency_reason`.** Cards and banners no longer say "Recorded as in
force" for laws in force only by the owner's presumption. Those read "Treated as in force — not verified"; a
recorded commencement reads "In force since <date>".

**The reader** (`presentation/reader.dart`, `statute_text.dart`) shows a section the way the statute prints it:
- sub-sections, clauses and provisos inline, indented, with printed labels, in one request instead of one tap and
  one round trip per sub-unit;
- a non-collapsible `StatusBanner` above the text (`design/status_banner.dart`), with wording in
  `domain/law_status.dart`;
- not-law outcomes as notices, never error styling;
- amendment footnote markers kept and set as raised numerals (`²[Balochistan]`);
- Parts, Chapters, Schedules and truncated units also list their sub-units.

The reader caches each unit in memory for five minutes after its screen closes, so going back is free. A
`territoryProvider` carries the reader's territory in every request; the scope-bar control that sets it is not
built yet (built later the same day, see above).

**Verified:**
- 14 Flutter tests, including law-status wording and a recorded-response widget test that opens a section with
  exactly one provision request and checks the served text;
- fixtures re-recorded from the live API on 17 Nov, because the September IDs no longer exist after replays;
- API tests, including that the unit endpoint never reads `provision_version`;
- the contract regenerated;
- goldens regenerated and inspected.

**Seen on device, not yet fixed:**
- a debug cold start of 6.6–14 s on the emulator; release-build timing is not measured yet (measured later the
  same day: 1.8–2.2 s release, see above);
- the catalogue is ordered by UUID, and title search has no trigram index (fixed later the same day, 0105);
- Back on a tab root exits the app instead of returning to Discover (fixed later the same day);
- a corpus defect: doc 1421-family texts carry the next section's heading ("Definitions.") at the end of a
  sub-section. That is a segmentation leak to fix in the corpus, not in the display.

14 September 2026. User-directed client development alongside continuing L2
qualification. This is a **local research preview**, not a corpus or app
production-readiness declaration. No corpus rows or release gates were changed.

## Working path

`apps/mobile/` is Android-first Flutter, also compiling for web preview. It calls
the real FastAPI contract in `nizam/api/library.py`; the read-only adapter is
`nizam/storage/library_read.py`. Source text is never generated or bundled as demo law.

```text
Discover / Library → title and jurisdiction/type search → instrument edition
  → printed part/chapter/article/section/schedule → own text and child units
  → source page, PDF URL, source hash, stored validity and revision identity
```

The app preserves database parentage. A container with no separate text directs
the reader to child units. No held version for a date does not mean no law existed.
Status `unknown` is visibly unverified, never converted to “in force.”

Constitution discovery uses a specific title and federal scope rather than trusting
`kind=constitution`: testing exposed a prosecution-service Act misclassified under
that kind. The narrower federal title query returned no eligible record during
this test. The client shows the empty state rather than bypassing qualification.
CPEC is a topic, not a statutory parent: its card is explicitly an `Economic
Corridor` title search, not a complete collection of applicable law. Reviewed
membership and stable edition selection remain necessary.

## Visual implementation

Document 12 §§2–7 governs the parchment/pine/brass palette, Spectral/Karla/Nastaliq
fonts, spacious cards, light/dark modes and 48+ dp primary controls. Fonts and
their OFL licences are bundled; no runtime font network request is required.
Glass blur is clipped to navigation, not repeated behind law paragraphs. Source
cards stay solid. Skeleton loading mirrors list shape and is announced semantically.
URL-opening and clipboard effects are isolated in the platform adapter, invoked
through interaction-state providers rather than directly from widgets.

Original vector painters depict Minar-e-Pakistan and Mazar-e-Quaid with dimensional
shading and a short spring-settled perspective entrance. No perpetual animation,
WebView or remote model download is used. Reduced motion stops the entrance.
These are **stylised 2.5D illustrations, not interactive 3D meshes**. Further
licensed models and device GPU qualification remain future work.

Heritage is separate editorial context, citing the
[National Assembly's parliamentary history](https://na.gov.pk/en/content.php?id=75)
for the brief 1956/1962/1973 notes. Those notes never determine operative law.
Held Urdu text is supported; full Urdu chrome, voice, run-level bidi review and
native-reader typography qualification are not yet implemented.

## Load and correctness boundaries

| Concern | Implemented |
|---|---|
| Credentials | DB connection stays in Python, never Flutter |
| Concurrency | At most 3 pooled DB connections and 12 queued callers per API process |
| Query lifetime | Read-only repeatable-read transaction; 12-second statement timeout; 3-second pool wait |
| List size | Default 30, maximum 50 items, no per-page whole-corpus count |
| Paging | HMAC-signed keyset cursors bound to date/filter/parent; one-hour expiry and explicit refresh recovery |
| Hierarchy | Immediate children only, no whole-tree download on a tap |
| Rendering | Lazy slivers for catalogue and child rows; no accumulated eager child-card Column |
| Text | One opened provision's version, filtered with `validity @> as_of` |
| Gate | Exact instrument checked in `v_release_instrument` before exposing structure/text |
| Races | That release check and following reads share one repeatable-read snapshot |
| Failure | No silent redirect from a retired or unavailable identity to another law |
| Cache | `no-store`; no unsigned response cache represented as an authoritative offline pack |

After the mandatory instrument release check, direct structure/version queries
avoid duplicating the expensive release proof. This matches current released-view
membership (active provisions under a released instrument), verified in independent
review. Revisit the adapter if additional per-provision restrictions enter the
release view. Production needs a restricted application DB role; transaction
read-only mode does not make development credentials least-privilege credentials.

## Verification and observations

- API tests cover bounds, explicit scope/preview state, unavailable IDs, cursor
  signature/scope, rejected writes and no version read for an unreleased instrument.
- Eight Flutter tests cover request scope, failure handling, single-flight paging,
  expired-cursor recovery, generated DTO decoding of real recorded responses,
  home navigation and phone/dark/large-text/reduced-motion layout smoke checks.
  The recorded-data widget test follows an instrument through two hierarchy levels,
  checks unchanged stored text and opens its source-evidence sheet.
- Rendered phone home and real-data reader goldens were inspected, including bundled fonts/icons.
  This is not a WCAG certification or sustained device frame benchmark.
- Flutter analysis passes, all eight Flutter tests and ten API tests pass, and
  the final branded Flutter web release compilation succeeds. Contract drift check passes.
- **Android APK not produced.** The first online attempt failed resolving
  Google/Maven artifacts; the compatible-plugin retry stalled downloading them
  and was cancelled. The bounded offline build compiled Dart, Kotlin, Java and
  native resources, then failed at `:url_launcher_android:extractDebugAnnotations`
  because eight dependency JARs were not cached (listed below). No task was skipped
  to make the build appear successful. No emulator or physical-device run was done.
- The project now selects the already-installed NDK `27.0.12077973`, satisfying
  the plugin's requirement; Gradle workers are capped at two with a 2 GiB heap.
  Doctor also reported some unaccepted SDK licences; these were not accepted on
  the user's behalf. Release signing is intentionally unconfigured, not debug-signed.
- Live proof used document 1421, **The West Pakistan Usurious Loans Ordinance,
  1959**, instrument `3f5e7f4e-2ec2-4517-bd10-634b9cc3681b`. It traversed the root
  hierarchy to provision `12fc8042-a0c0-4320-850b-58469f8fcbef`; 102 returned
  characters matched the selected-date stored version exactly. This is API/DB
  equality, not independent PDF accuracy or whole-instrument verification.
- Local timings after removing a duplicate release-proof join: an earlier title lookup
  took 473 ms and detail/children 107–133 ms. The final concurrent-build rerun measured
  title lookup 2,358 ms, detail/children 160–258 ms and provision reads 193–220 ms.
  Earlier provision reads took 2.5–8.3 seconds.
  These are individual samples, **not p95 or load-test results**.

Evidence: `.review/mobile/library-smoke-final.json`,
`apps/mobile/test/fixtures/library-responses.json`, `openapi/library-preview.json`.
Test fixtures are not runtime application assets.

Android build resume: with Google Maven and Maven Central downloads working, run
`flutter build apk --debug --dart-define=API_BASE_URL=http://<WSL-IP>:8080` from
`apps/mobile`. The offline diagnostic identified these uncached JARs:
`lint-checks-31.7.0`, `intellij-core-31.7.0`, `kotlin-compiler-31.7.0`,
`uast-31.7.0`, `groovy-3.0.21`, `play-sdk-proto-31.7.0`,
`httpclient-4.5.6`, `commons-codec-1.10`. These are build dependencies, not
missing law data. Do not disable annotation/lint tasks as a substitute for resolving them.

## Explicit staging differences from Documents 07/08

1. No immutable published release snapshot across requests yet. Catalogue cursors
   traverse a changing live set. Production needs a published read model, release
   generation in cursors and representations, then safe public caching/invalidation.
2. No signed offline pack or sync yet. Network failure truthfully reports that no
   pack is installed. Transient caching is not a substitute for the specified pack.
3. DTOs and OpenAPI are generated together and drift-checked. The small HTTP
   adapter and Riverpod providers are explicit code; full operation/provider
   generation remains part of expanding the contract, not a completed claim.
4. No internet deployment, auth/tenancy, distributed quotas, audited generation,
   production signing, or public legal-advice workflow. Do not expose this local API.
5. No reviewed CPEC membership or selected canonical Constitution edition yet.
6. No full bilingual/voice/offline accessibility qualification, persistent reading
   preferences, sustained frame budget verification or true 3D model scene yet.

The workflow skill shaped this work into one complete browse/read slice rather
than placeholder Ask, account, drafting and judgment modules. It also required
independent review, which caught and led to fixes for expired cursors and eager
child rendering. The design/client skills preserved source/status visibility,
date scope and the existing palette while adding ornament only to discovery.

## Next slice

Implement a versioned, reviewed collection/read-model contract with a verified
Constitution edition and source-backed navigation fixtures. Qualify the corpus
separately; neither decoration nor HTTP transport fixes its existing gate blind
spots. Generated answers must wait for the documented retrieval/grounding gates.

## References

- [07 Backend/API](07-backend-api.html) §§2–3 and endpoint catalogue;
  [08 Client](08-client-architecture.html) §§2,4–7,9 and Appendix B;
  [12 Design](12-design-system.html) §§2–7;
  [13 UX](13-ux-and-interaction-architecture.html) §3 and source/uncertainty states.
- [Flutter architecture](https://docs.flutter.dev/app-architecture/recommendations),
  [BackdropFilter](https://api.flutter.dev/flutter/widgets/BackdropFilter-class.html),
  [device performance profiling](https://docs.flutter.dev/perf/ui-performance).
- [Psycopg pooling](https://www.psycopg.org/psycopg3/docs/advanced/pool.html),
  [FastAPI response models](https://fastapi.tiangolo.com/tutorial/response-model/).
- [Flutter-maintained Android URL-launcher changelog](https://pub.dev/packages/url_launcher_android/changelog):
  version 6.3.18 introduced AGP 8.12.1. This project's installed Flutter 3.29 /
  Gradle 8.10 toolchain uses implementation 6.3.16 explicitly; upgrade them together.

Run instructions: [Flutter README](../apps/mobile/README.md).
