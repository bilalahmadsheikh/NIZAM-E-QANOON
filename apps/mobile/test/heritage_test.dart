import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:nizam_app/data/library_repository.dart';
import 'package:nizam_app/design/heritage_art.dart';
import 'package:nizam_app/domain/heritage.dart';
import 'package:nizam_app/main.dart';
import 'package:nizam_app/state/library_state.dart';

const _jurisdictions = ['fed', 'punjab', 'sindh', 'kp', 'balochistan', 'ict', 'ajk', 'gb'];

Future<void> _fonts() async {
  final icons = FontLoader('MaterialIcons')..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
  await icons.load();
  for (final font in [('Spectral', 'Spectral-Regular.ttf'), ('Karla', 'Karla.ttf')]) {
    await (FontLoader(font.$1)..addFont(rootBundle.load('assets/fonts/${font.$2}'))).load();
  }
}

Map<String, dynamic> _instrument(int doc, String title, String jurisdiction, int year) => {
      'id': '00000000-0000-0000-0000-${doc.toString().padLeft(12, '0')}',
      'title': title, 'kind': 'act', 'year': year, 'jurisdiction': jurisdiction, 'status': 'in_force',
      'source_url': null, 'document_id': doc, 'source_hash': 'a' * 64, 'currency': 'current',
      'currency_reason': 'commences_at_once', 'year_display': '$year',
    };

/// The page the server sends (nizam/api/collections.py heritage_page), as recorded on 18 Nov 2026, trimmed.
Map<String, dynamic> _page() {
  final federal = [
    {'short_name': 'Antiquities Act', 'instrument': _instrument(3468, 'Antiquities Act, 1975', 'fed', 1975)},
  ];
  return {
    'as_of': '2026-11-18', 'mode': 'research_preview', 'notice': 'Fixture',
    'regions': [
      for (final j in _jurisdictions)
        {
          'jurisdiction': j,
          'laws_from': j == 'ict' ? 'fed' : j,
          'laws': j == 'fed' || j == 'ict'
              ? federal
              : j == 'gb'
                  ? []
                  : [
                      {'short_name': 'Antiquities Act', 'instrument': _instrument(5000, 'Antiquities Act, 1975', j, 1975)},
                    ],
        },
    ],
    'questions': [
      {
        'key': 'found_object',
        'instrument': _instrument(3468, 'Antiquities Act, 1975', 'fed', 1975),
        'units': [
          {'id': '00000000-0000-0000-0000-000000000051', 'kind': 'section', 'label': '5A',
           'heading': 'Accidental discovery of antiquity to be reported, to Director-General',
           'citation': 'Antiquities Act, 1975, s. 5A'},
        ],
      },
      {
        'key': 'culture_right',
        'instrument': _instrument(4419, 'Constitution of the Islamic Republic of Pakistan', 'fed', 1973),
        'units': [
          {'id': '00000000-0000-0000-0000-000000000028', 'kind': 'section', 'label': '28',
           'heading': 'Preservation of language, script and culture',
           'citation': 'Constitution of the Islamic Republic of Pakistan, 1973, Art. 28'},
        ],
      },
    ],
  };
}

LibraryRepository _repo() => LibraryRepository(
      MockClient((request) async => http.Response(
            jsonEncode(request.url.path.endsWith('/collections/heritage')
                ? _page()
                : {
                    'as_of': '2026-11-18', 'mode': 'research_preview', 'notice': 'Fixture', 'items': [],
                    'next_cursor': null, 'name': 'Most consulted laws',
                  }),
            200,
          )),
      'http://fixture.invalid',
    );

Future<void> _openHeritage(WidgetTester tester) async {
  await tester.pumpWidget(ProviderScope(
    overrides: [
      repositoryProvider.overrideWithValue(_repo()),
      asOfProvider.overrideWith((ref) => '2026-11-18'),
    ],
    child: const NizamApp(),
  ));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Heritage'));
  await tester.pumpAndSettle();
}

void main() {
  test('every jurisdiction has a region, and every fact names where it was checked', () {
    expect(heritageRegions.map((r) => r.jurisdiction), _jurisdictions);
    for (final r in heritageRegions) {
      expect(r.sources, isNotEmpty, reason: r.place);
      for (final url in [...r.sources, if (r.craft != null) r.craft!.source]) {
        expect(Uri.parse(url).scheme, 'https', reason: url);
      }
    }
    // every code the server sends is worded; an unknown code is shown as itself, never as a guessed question
    for (final key in ['found_object', 'build_near', 'repair', 'declared_protected', 'damage_signs', 'export',
        'culture_right']) {
      expect(heritageQuestion(key), isNot(key));
    }
    expect(heritageQuestion('unheard_of'), 'unheard_of');
  });

  testWidgets('every landmark and motif paints, in tones and as a silhouette', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: Column(children: [
            Wrap(children: [
              for (final m in Landmark.values) ...[
                LandmarkArt(m, size: 64),
                LandmarkArt(m, size: 20, color: Colors.black54),
              ],
            ]),
            for (final m in Motif.values) ...[MotifBand(m, height: 10), MotifSwatch(m)],
          ]),
        ),
      ),
    ));
    expect(tester.takeException(), isNull);
    // a sheet of every drawing, for review: each landmark as its scene, each motif as a band
    tester.view.physicalSize = const Size(900, 1400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(
      debugShowCheckedModeBanner: false,
      home: Scaffold(
        backgroundColor: const Color(0xFFF3EFE6),
        body: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(children: [
            Wrap(spacing: 12, runSpacing: 12, children: [
              for (final r in heritageRegions) SizedBox(width: 280, child: LandmarkScene(r, height: 220)),
              SizedBox(width: 280, height: 220, child: Row(children: [
                for (final r in heritageRegions) Padding(padding: const EdgeInsets.all(3),
                    child: RegionGlyph(r.jurisdiction, size: 28, color: const Color(0xFF8A6216))),
              ])),
            ]),
            const SizedBox(height: 12),
            for (final m in Motif.values) Padding(padding: const EdgeInsets.only(bottom: 6), child: MotifBand(m, height: 16)),
          ]),
        ),
      ),
    ));
    await expectLater(find.byType(MaterialApp), matchesGoldenFile('goldens/heritage_art.png'));
  });

  testWidgets('heritage: region panel, laws, an honest empty region, questions answered by sections',
      (tester) async {
    await _fonts();
    tester.view.physicalSize = const Size(430, 2600);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await _openHeritage(tester);
    expect(find.text('Pakistan,\nregion by region.'), findsOneWidget);
    expect(find.text('Badshahi Mosque'), findsOneWidget); // Punjab first when no territory is chosen
    expect(find.text('Found an old object while digging or building?'), findsOneWidget);
    expect(find.text('Accidental discovery of antiquity to be reported, to Director-General'), findsOneWidget);
    expect(find.text('The Constitution on culture'), findsOneWidget);
    await expectLater(find.byType(MaterialApp), matchesGoldenFile('goldens/heritage.png'));

    final picker = find.byType(ListView).at(1);
    await tester.dragUntilVisible(find.text('Gilgit-Baltistan'), picker, const Offset(-160, 0));
    await tester.tap(find.text('Gilgit-Baltistan'));
    await tester.pumpAndSettle();
    expect(find.text('Baltit Fort'), findsOneWidget);
    expect(find.textContaining('does not yet hold a heritage law of Gilgit-Baltistan'), findsOneWidget);

    await tester.dragUntilVisible(find.text('Islamabad'), picker, const Offset(80, 0));
    await tester.tap(find.text('Islamabad'));
    await tester.pumpAndSettle();
    expect(find.textContaining('is served federal law'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('home: each jurisdiction tile carries its landmark and craft band', (tester) async {
    await _fonts();
    tester.view.physicalSize = const Size(430, 2300);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(ProviderScope(
      overrides: [repositoryProvider.overrideWithValue(_repo()), asOfProvider.overrideWith((ref) => '2026-11-18')],
      child: const NizamApp(),
    ));
    await tester.pumpAndSettle();
    expect(find.byType(RegionGlyph), findsNWidgets(8));
    expect(find.byType(MotifBand), findsAtLeastNWidgets(8));
    await expectLater(find.byType(MaterialApp), matchesGoldenFile('goldens/discover_tall.png'));
  });

  testWidgets('heritage at 360 dp with large text and reduced motion does not overflow', (tester) async {
    await _fonts();
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    tester.platformDispatcher.accessibilityFeaturesTestValue =
        const FakeAccessibilityFeatures(disableAnimations: true);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
    await _openHeritage(tester);
    await tester.drag(find.byType(ListView).first, const Offset(0, -1500));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
