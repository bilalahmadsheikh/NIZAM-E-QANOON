import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:nizam_app/data/library_repository.dart';
import 'package:nizam_app/main.dart';
import 'package:nizam_app/state/library_state.dart';
import 'package:nizam_app/design/components.dart';

void main() {
  testWidgets(
    'expired continuation offers a fresh list, not an endless retry',
    (tester) async {
      var refreshed = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MoreButton(
              const Paged<int>(
                [1],
                'expired',
                moreError: LibraryFailure('Expired', refreshRequired: true),
              ),
              load: () => fail('Must not retry expired cursor'),
              refresh: () => refreshed = true,
            ),
          ),
        ),
      );
      await tester.tap(find.text('Refresh list'));
      expect(refreshed, isTrue);
    },
  );

  test('invalid cursor is a distinct client failure', () async {
    final repo = LibraryRepository(
      MockClient((_) async => http.Response('{}', 400)),
      'http://fixture.invalid',
    );
    await expectLater(
      repo.instruments(asOf: '2026-11-17', after: 'expired'),
      throwsA(
        isA<LibraryFailure>().having(
          (e) => e.refreshRequired,
          'refreshRequired',
          true,
        ),
      ),
    );
  });

  test(
    'recorded real corpus responses decode through generated DTOs',
    () async {
      final fixture =
          jsonDecode(
                File('test/fixtures/library-responses.json').readAsStringSync(),
              )
              as Map<String, dynamic>;
      final repo = LibraryRepository(
        MockClient((request) async {
          final matched = fixture.entries.firstWhere(
            (e) => Uri.parse(e.key).path == request.url.path,
          );
          return http.Response(
            jsonEncode(matched.value),
            200,
            headers: {'content-type': 'application/json; charset=utf-8'},
          );
        }),
        'http://fixture.invalid',
      );
      final page = await repo.instruments(asOf: '2026-11-17');
      expect(page.items, isNotEmpty);
      final instrument = await repo.instrument(
        page.items.first.id,
        '2026-11-17',
      );
      expect(instrument.item.source_hash.length, 64);
      // the leaf's own record and its served subtree (/text, 17 Nov 2026)
      final textPath = fixture.keys.lastWhere(
        (p) => Uri.parse(p).path.endsWith('/text'),
      );
      final id = Uri.parse(textPath).pathSegments[3];
      final unit = await repo.unitText(id, '2026-11-17');
      final recorded = fixture[textPath] as Map;
      expect(unit.nodes, isNotEmpty);
      expect(unit.nodes.first.text_en, (recorded['nodes'] as List)[0]['text_en']);
      expect(unit.item.instrument.source_hash.length, 64);
      expect(unit.law?.currency, (recorded['law'] as Map)['currency']);
      final source = await repo.provision(id, '2026-11-17');
      expect(source.item.id, id);
    },
  );
  test(
    'HTTP reads carry temporal scope and never substitute failed content',
    () async {
      final repo = LibraryRepository(
        MockClient((request) async {
          expect(request.url.queryParameters['as_of'], '2026-11-17');
          return http.Response('{}', 404);
        }),
        'http://fixture.invalid',
      );
      await expectLater(
        repo.provision('id', '2026-11-17'),
        throwsA(isA<LibraryFailure>()),
      );
    },
  );

  test(
    'paging is single-flight and preserves existing rows on failure',
    () async {
      var calls = 0;
      final second = Completer<(List<int>, String?)>();
      final pager = Pager<int>((after) async {
        calls++;
        return after == null ? ([1], 'next') : second.future;
      });
      await Future<void>.delayed(Duration.zero);
      final pending = pager.more();
      await pager.more();
      expect(calls, 2);
      second.completeError(const LibraryFailure('Fixture failure'));
      await pending;
      expect(pager.state.value!.items, [1]);
      expect(pager.state.value!.moreError, isA<LibraryFailure>());
      pager.dispose();
    },
  );

  Future<void> fonts() async {
    final icons = FontLoader('MaterialIcons')
      ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await icons.load();
    for (final font in [
      ('Spectral', 'Spectral-Regular.ttf'),
      ('Karla', 'Karla.ttf'),
    ]) {
      final loader = FontLoader(font.$1)
        ..addFont(rootBundle.load('assets/fonts/${font.$2}'));
      await loader.load();
    }
  }

  testWidgets(
    'discovery renders at phone size and opens real title-search route',
    (tester) async {
      await fonts();
      tester.view.physicalSize = const Size(430, 932);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final repo = LibraryRepository(
        MockClient(
          (request) async => http.Response(
            jsonEncode({
              'as_of': '2026-11-17',
              'mode': 'research_preview',
              'notice': 'Fixture',
              'items': [],
              'next_cursor': null,
              if (request.url.path.endsWith('/collections/popular')) 'name': 'Most consulted laws',
            }),
            200,
          ),
        ),
        'http://fixture.invalid',
      );
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            repositoryProvider.overrideWithValue(repo),
            asOfProvider.overrideWith((ref) => '2026-11-17'),
          ],
          child: const NizamApp(),
        ),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      await expectLater(
        find.byType(MaterialApp),
        matchesGoldenFile('goldens/discover.png'),
      );
      await tester.tap(find.text('Library'));
      await tester.pumpAndSettle();
      // the library: one box for a title or a subject, one-tap filters, and an honest empty state
      expect(find.text('A title or a subject — robbery, bail, rent…'), findsOneWidget);
      expect(find.text('Everywhere'), findsOneWidget);
      expect(find.textContaining('That is not proof none exists'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('large text, dark mode and reduced motion do not overflow', (
    tester,
  ) async {
    await fonts();
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    tester.platformDispatcher.accessibilityFeaturesTestValue =
        const FakeAccessibilityFeatures(disableAnimations: true);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [darkModeProvider.overrideWith((ref) => true)],
        child: const NizamApp(),
      ),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'real recorded hierarchy opens unchanged text and source evidence',
    (tester) async {
      await fonts();
      tester.view.physicalSize = const Size(430, 932);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final fixture =
          jsonDecode(
                File('test/fixtures/library-responses.json').readAsStringSync(),
              )
              as Map<String, dynamic>;
      final requested = <Uri>[];
      final repo = LibraryRepository(
        MockClient((request) async {
          requested.add(request.url);
          final matched = fixture.entries.firstWhere((entry) {
            final uri = Uri.parse(entry.key);
            return uri.path == request.url.path &&
                uri.queryParameters['parent'] ==
                    request.url.queryParameters['parent'];
          });
          return http.Response(
            jsonEncode(matched.value),
            200,
            headers: {'content-type': 'application/json; charset=utf-8'},
          );
        }),
        'http://fixture.invalid',
      );
      final container = ProviderContainer(
        overrides: [
          repositoryProvider.overrideWithValue(repo),
          asOfProvider.overrideWith((ref) => '2026-11-17'),
        ],
      );
      addTearDown(container.dispose);
      const instrument = '14968f5b-a03f-4bda-a904-031606c09592';
      const root = '05f26c6b-5ea0-419c-8da9-ad37bacf5a27';
      const leaf = 'c0a426c4-c42b-4d73-85b6-8f21d51b2750';
      container.read(routerProvider).go('/instrument/$instrument');
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const NizamApp(),
        ),
      );
      await tester.pumpAndSettle();
      // the law page lists its sections lazily (one /sections page); each card shows the section's first words
      final sectionsPage = fixture.entries
          .firstWhere((e) => Uri.parse(e.key).path == '/v1/law/instruments/$instrument/sections')
          .value as Map;
      final first = (sectionsPage['items'] as List).first as Map;
      expect(find.text(first['heading'] as String), findsOneWidget);
      expect(find.text(first['preview'] as String), findsOneWidget);
      expect(requested.where((u) => u.path.endsWith('/sections')).length, 1);
      // its name is the button to the full text; the section opens with its sub-sections inline
      final card = find.byKey(ValueKey('section/$root'));
      await tester.tap(find.descendant(of: card, matching: find.text(first['heading'] as String)));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      // the reader shows exactly the text operative_provision served for the leaf (INV-5), from one /text call
      final served =
          (fixture.entries
                      .firstWhere(
                        (e) =>
                            Uri.parse(e.key).path ==
                            '/v1/law/provisions/$leaf/text',
                      )
                      .value
                  as Map);
      final nodeText = ((served['nodes'] as List).first as Map)['text_en'] as String;
      expect(find.text(nodeText.trim()), findsOneWidget);
      expect(
        requested.any((uri) => uri.path == '/v1/law/provisions/$root/text'),
        isTrue,
      );
      // one request for the whole section: no per-sub-section reads (beside it, at most one for the units either
      // side, which never carries text)
      expect(requested.where((uri) => uri.path.endsWith('/text')).length, 1);
      expect(
        requested.where((uri) =>
            uri.path.startsWith('/v1/law/provisions/') && !uri.path.endsWith('/text') &&
            !uri.path.endsWith('/neighbours')),
        isEmpty,
      );
      expect(requested.where((uri) => uri.path.endsWith('/neighbours')).length, lessThanOrEqualTo(1));
      expect(
        requested.every((uri) => uri.queryParameters['as_of'] == '2026-11-17'),
        isTrue,
      );
      await expectLater(
        find.byType(MaterialApp),
        matchesGoldenFile('goldens/reader.png'),
      );
      await tester.ensureVisible(find.text('Source & edition'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Source & edition'));
      await tester.pumpAndSettle();
      expect(
        find.textContaining(
          (served['item'] as Map)['instrument']['source_hash'] as String,
        ),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
      // the default (everyday) reading mode carries no record panel
      expect(find.text('THE RECORD'), findsNothing);
      // closing the reader starts the five-minute cache countdown; let it run out
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump(const Duration(minutes: 6));
    },
  );

  testWidgets(
    'judge mode shows the served record above the text, same text, same requests',
    (tester) async {
      await fonts();
      tester.view.physicalSize = const Size(430, 932);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final fixture =
          jsonDecode(File('test/fixtures/library-responses.json').readAsStringSync()) as Map<String, dynamic>;
      final requested = <Uri>[];
      final repo = LibraryRepository(
        MockClient((request) async {
          requested.add(request.url);
          final matched = fixture.entries.firstWhere((entry) {
            final uri = Uri.parse(entry.key);
            return uri.path == request.url.path &&
                uri.queryParameters['parent'] == request.url.queryParameters['parent'];
          });
          return http.Response(jsonEncode(matched.value), 200,
              headers: {'content-type': 'application/json; charset=utf-8'});
        }),
        'http://fixture.invalid',
      );
      final container = ProviderContainer(
        overrides: [
          repositoryProvider.overrideWithValue(repo),
          asOfProvider.overrideWith((ref) => '2026-11-17'),
        ],
      );
      addTearDown(container.dispose);
      container.read(readingModeProvider.notifier).state = ReadingMode.judge;
      const root = '05f26c6b-5ea0-419c-8da9-ad37bacf5a27';
      const leaf = 'c0a426c4-c42b-4d73-85b6-8f21d51b2750';
      container.read(routerProvider).go('/provision/$root');
      await tester.pumpWidget(UncontrolledProviderScope(container: container, child: const NizamApp()));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      final served = fixture.entries
          .firstWhere((e) => Uri.parse(e.key).path == '/v1/law/provisions/$leaf/text')
          .value as Map;
      final lawRecord = served['law'] as Map?;
      expect(find.text('THE RECORD'), findsOneWidget);
      expect(find.text('Read as at'), findsOneWidget);
      // the panel shows the record's own values, not client-derived ones
      expect(find.text('2026-11-17'), findsWidgets);
      if (lawRecord != null) {
        expect(find.textContaining(lawRecord['currency'] as String), findsWidgets);
      } else {
        expect(find.text('Serving record'), findsOneWidget);
      }
      // a reading mode changes presentation only: the same text, from the same single request
      final nodeText = ((served['nodes'] as List).first as Map)['text_en'] as String;
      expect(find.text(nodeText.trim()), findsOneWidget);
      expect(requested.where((u) => u.path.endsWith('/text')).length, 1);
      expect(
          requested.where((u) =>
              u.path.startsWith('/v1/law/provisions/') && !u.path.endsWith('/text') && !u.path.endsWith('/neighbours')),
          isEmpty);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump(const Duration(minutes: 6));
    },
  );
}
