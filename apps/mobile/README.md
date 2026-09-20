# Nizam-e-Qanoon · Flutter library preview

Open **this directory**, not `android/`, in Android Studio. This is a read-only,
real-data library slice, not a production legal-advice application.

Verified: Flutter analysis, eight Flutter tests, ten API tests, generated-contract
check and web compilation. **No APK yet:** Android compilation reached annotation
extraction but eight Google/Maven dependency JARs could not be downloaded/cached.
See the [exact build blocker](../../docs/MOBILE-LIBRARY-PREVIEW.md).

## Start the API

In WSL, from the repository root:

```bash
uv sync --extra api
uv run --extra api uvicorn nizam.api.library:create_app --factory --host 0.0.0.0 --port 8080
hostname -I
```

Use the first WSL address for Windows/Android development if localhost forwarding
is unavailable. This binds to the development network: **do not expose it to the
internet**. DB credentials remain server-side in `infra/.env`. The API does not
write to the corpus, change release gates, or generate legal text.

## Android Studio

1. Open `E:/Nizam_e_Qanoon/apps/mobile`.
2. Enable the Flutter and Dart IDE plugins if needed; use the installed Flutter
   SDK (`D:/downloads/flutter` on this machine).
3. Run `flutter pub get` and select an emulator or connected Android device.
4. Add `--dart-define=API_BASE_URL=http://<WSL-IP>:8080` to the Flutter run
   configuration's **Additional run args**, then Run.

From this directory, the equivalent is:

```powershell
flutter run --dart-define=API_BASE_URL=http://<WSL-IP>:8080
```

For an API running directly on Windows, the Android emulator normally uses
`http://10.0.2.2:8080` (the app default). A physical phone needs a reachable
development-server address; the WSL private address may not be reachable from it.
Never put a database password in a Dart define.

The checked SDK is Flutter 3.29.2 / Dart 3.7.2, with Android Studio 2024.3 and
Android SDK 35 installed. This work does not upgrade the global SDK. Doctor
reported some unaccepted Android licences; review them yourself with
`flutter doctor --android-licenses` if requested by the build.

If the Flutter launcher stalls fetching SDK tags, invoke its installed tool
without a version check:

```powershell
& D:/downloads/flutter/bin/cache/dart-sdk/bin/dart.exe D:/downloads/flutter/bin/cache/flutter_tools.snapshot --no-version-check run --dart-define=API_BASE_URL=http://<WSL-IP>:8080
```

For web development: `flutter run -d chrome --web-port=5173` with the same Dart
define. API development CORS allows `http://localhost:5173`. Android debug builds
permit HTTP; release builds do not. HTTPS and production signing are required
before distribution; release builds are intentionally unsigned, not debug-signed.
The Android URL-launcher implementation is pinned to 6.3.16 to stay on the
installed Gradle toolchain. Upgrade it together with Flutter/Android build tools.

## Implemented

- Discover, Library and Heritage; stamp-paper light/dark themes and bundled fonts.
- Glass navigation, skeleton loading and reduced-motion-aware spring entrance.
- Original dimensional Minar-e-Pakistan and Mazar-e-Quaid illustrations: stylised
  **2.5D artwork**, not interactive 3D meshes or photogrammetry.
- Real title search, jurisdiction/type filters, cursor-paged instruments, lazy
  child-unit lists, breadcrumbs, selected-date source text and source details.
- Reader size controls and held Urdu text; no automatic substitute translation.
- Explicit preview, unknown-status, missing-version, offline and retired-record states.

CPEC currently means disclosed title discovery, not an invented curated collection.
Unavailable Constitution editions remain unavailable; the UI does not bypass gates.
Test-only recorded API responses are in `test/fixtures/`, never bundled as runtime law.

## Verify

```powershell
flutter analyze
flutter test
flutter build web --dart-define=API_BASE_URL=http://<WSL-IP>:8080
```

From WSL at the repository root:

```bash
uv run --extra api pytest tests/test_library_api.py
uv run --extra api python tools/generate_library_contract.py --check
uv run --extra api python tools/smoke_library_api.py
```

Regenerate the OpenAPI/Dart DTOs with `tools/generate_library_contract.py` after
intentional schema changes. Do not hand-edit generated contract files.
See [architecture, evidence and remaining work](../../docs/MOBILE-LIBRARY-PREVIEW.md).
