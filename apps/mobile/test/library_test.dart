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
      repo.instruments(asOf: '2026-09-14', after: 'expired'),
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
      final page = await repo.instruments(asOf: '2026-09-14');
      expect(page.items, isNotEmpty);
      final instrument = await repo.instrument(
        page.items.first.id,
        '2026-09-14',
      );
      expect(instrument.item.source_hash.length, 64);
      final provisionPath = fixture.keys.lastWhere(
        (p) => p.startsWith('/v1/law/provisions/'),
      );
      final id = Uri.parse(provisionPath).pathSegments.last;
      final source = await repo.provision(id, '2026-09-14');
      expect(
        source.item.text_en,
        (fixture[provisionPath] as Map)['item']['text_en'],
      );
      expect(source.item.text_en, isNotEmpty);
    },
  );
  test(
    'HTTP reads carry temporal scope and never substitute failed content',
    () async {
      final repo = LibraryRepository(
        MockClient((request) async {
          expect(request.url.queryParameters['as_of'], '2026-09-14');
          return http.Response('{}', 404);
        }),
        'http://fixture.invalid',
      );
      await expectLater(
        repo.provision('id', '2026-09-14'),
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
              'as_of': '2026-09-14',
              'mode': 'research_preview',
              'notice': 'Fixture',
              'items': [],
              'next_cursor': null,
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
            asOfProvider.overrideWith((ref) => '2026-09-14'),
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
      expect(find.text('Search instrument titles'), findsOneWidget);
      expect(find.textContaining('No matching instrument'), findsOneWidget);
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
          asOfProvider.overrideWith((ref) => '2026-09-14'),
        ],
      );
      addTearDown(container.dispose);
      const instrument = '3f5e7f4e-2ec2-4517-bd10-634b9cc3681b';
      const root = '4392e379-d1c2-4cc7-9ff3-cf103f806d2d';
      const leaf = '12fc8042-a0c0-4320-850b-58469f8fcbef';
      container.read(routerProvider).go('/instrument/$instrument');
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const NizamApp(),
        ),
      );
      await tester.pumpAndSettle();
      for (final node in [root, leaf]) {
        final target = find.byKey(ValueKey('node/$node'));
        await tester.scrollUntilVisible(
          target,
          240,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.tap(target);
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      }
      final raw =
          (fixture.entries
                      .firstWhere(
                        (e) =>
                            Uri.parse(e.key).path == '/v1/law/provisions/$leaf',
                      )
                      .value
                  as Map)['item']
              as Map;
      expect(
        tester.widget<SelectableText>(find.byType(SelectableText)).data,
        raw['text_en'],
      );
      expect(
        requested.every((uri) => uri.queryParameters['as_of'] == '2026-09-14'),
        isTrue,
      );
      await expectLater(
        find.byType(MaterialApp),
        matchesGoldenFile('goldens/reader.png'),
      );
      await tester.ensureVisible(find.byTooltip('Source and edition'));
      await tester.tap(find.byTooltip('Source and edition'));
      await tester.pumpAndSettle();
      expect(
        find.textContaining(raw['instrument']['source_hash'] as String),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    },
  );
}
