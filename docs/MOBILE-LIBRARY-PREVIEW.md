# Mobile library: implemented preview slice

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
