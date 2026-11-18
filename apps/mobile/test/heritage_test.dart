import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:nizam_app/data/library_repository.dart';
import 'package:nizam_app/design/embroidery.dart';
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

/// The page the server sends (nizam/api/collections.py heritage_page), as recorded on 18 Nov 2026, trimmed: each
/// region carries the questions its own law answers (D-078).
Map<String, dynamic> _page() {
  final federal = [
    {'short_name': 'Antiquities Act', 'instrument': _instrument(3468, 'Antiquities Act, 1975', 'fed', 1975)},
  ];
  final culture = {
    'key': 'culture_right',
    'instrument': _instrument(4419, 'Constitution of the Islamic Republic of Pakistan', 'fed', 1973),
    'units': [
      {'id': '00000000-0000-0000-0000-000000000028', 'kind': 'section', 'label': '28',
       'heading': 'Preservation of language, script and culture',
       'citation': 'Constitution of the Islamic Republic of Pakistan, 1973, Art. 28', 'preview': null},
    ],
  };
  Map<String, dynamic> found(int doc, String title, String j, String label, String? heading, String? preview) => {
        'key': 'found_object',
        'instrument': _instrument(doc, title, j, 1975),
        'units': [
          {'id': '00000000-0000-0000-0000-0000000000${doc % 100}', 'kind': 'section', 'label': label,
           'heading': heading, 'citation': '$title, s. $label', 'preview': preview},
        ],
      };
  List<Map<String, dynamic>> questions(String j) => switch (j) {
        'fed' || 'ict' => [
            found(3468, 'Antiquities Act, 1975', 'fed', '5A',
                'Accidental discovery of antiquity to be reported, to Director-General', null),
            culture,
          ],
        'punjab' => [
            found(3157, 'Antiquities Act, 1975', 'punjab', '5-A',
                'Accidental discovery of antiquity to be reported to Director-General', null),
            culture,
          ],
        // the Balochistan Act prints no headings: the card quotes the section's opening words
        'balochistan' => [
            found(4986, 'The Balochistan Antiquities Act, 2014', 'balochistan', '6', null,
                '(1) Whoever discovers, or finds accidentally any movable antiquity shall inform the Director'),
            culture,
          ],
        'gb' => [],
        // AJK: its own law answers; the Constitution is not served there
        'ajk' => [found(10935, 'Antiquites Act, 1986', 'ajk', '6', null, 'Accidental discovery of antiquity')],
        _ => [culture],
      };
  return {
    'as_of': '2026-11-18', 'mode': 'research_preview', 'notice': 'Fixture',
    // D-079: the federal laws a maker relies on, and a question answered by its sections
    'makers': {
      'laws': [
        {'short_name': 'Geographical indications',
         'instrument': _instrument(3433, 'Geographical Indications (Registration and Protection) Act, 2020', 'fed', 2020)},
      ],
      'questions': [
        {
          'key': 'gi_logo',
          'instrument': _instrument(3433, 'Geographical Indications (Registration and Protection) Act, 2020', 'fed', 2020),
          'units': [
            {'id': '00000000-0000-0000-0000-000000003428', 'kind': 'section', 'label': '28',
             'heading': 'National logo for certifying geographical indication products.',
             'citation': 'Geographical Indications (Registration and Protection) Act, 2020, s. 28', 'preview': null},
          ],
        },
      ],
    },
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
          'questions': questions(j),
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
      // every region names at least one craft, maker or keeper of crafts (D-079)
      expect(r.crafts, isNotEmpty, reason: r.jurisdiction);
      for (final url in [...r.sources, for (final c in r.crafts) c.source, giFirst.source]) {
        expect(Uri.parse(url).scheme, 'https', reason: url);
      }
    }
    // every craft has a motif of its own: no two crafts share one, and every motif drawn is some craft's or a landmark's
    final motifs = [for (final (_, c) in allCrafts) c.motif];
    expect(motifs.toSet().length, motifs.length);
    expect({...motifs, Motif.faisalFolds}, Motif.values.toSet());
    // the craft of the day turns through every craft, one a day, the same all day
    expect({for (var d = 0; d < allCrafts.length; d++) craftOfDay(DateTime(2026, 3, 1).add(Duration(days: d))
        .toIso8601String().substring(0, 10)).$2.name}.length, allCrafts.length);
    expect(craftOfDay('2026-11-18'), craftOfDay('2026-11-18'));
    // every code the server sends is worded; an unknown code is shown as itself, never as a guessed question
    for (final key in ['found_object', 'build_near', 'repair', 'declared_protected', 'damage_signs', 'export',
        'visit', 'culture_right', 'gi_place', 'gi_logo', 'gi_fake', 'brand', 'design', 'copyright']) {
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

  testWidgets('embroidery: each stitchwork at full strength and as a page ground under a card (review sheet)',
      (tester) async {
    await _fonts();
    tester.view.physicalSize = const Size(1900, 1500);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    Widget panel(Motif m, double opacity) => SizedBox(
          width: 200,
          height: 200,
          child: Stack(children: [
            Positioned.fill(child: EmbroideredGround(m, opacity: opacity)),
            if (opacity < 1)
              const Center(
                child: Card(
                  child: Padding(padding: EdgeInsets.all(10), child: Text('A card on the cloth')),
                ),
              ),
          ]),
        );
    await tester.pumpWidget(MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ThemeData(scaffoldBackgroundColor: const Color(0xFFF3EFE6)),
      home: Scaffold(
        body: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(children: [
            Row(children: [for (final m in [Motif.truckArt, Motif.kashi, Motif.mirrorwork]) panel(m, 1)]),
            Row(children: [for (final m in [Motif.truckArt, Motif.kashi, Motif.mirrorwork]) panel(m, .24)]),
            const SizedBox(height: 8),
            const SizedBox(width: 400, child: EmbroideredBorder(Motif.truckArt, height: 16)),
            const SizedBox(height: 8),
            const SizedBox(width: 400, child: StitchRule()),
          ]),
        ),
      ),
    ));
    expect(tester.takeException(), isNull);
    await expectLater(find.byType(MaterialApp), matchesGoldenFile('goldens/embroidery.png'));
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
    // Punjab's own copy of the Act answers in Punjab (D-078), named once
    expect(find.text('Accidental discovery of antiquity to be reported to Director-General'), findsOneWidget);
    expect(find.textContaining('in the Antiquities Act, 1975.'), findsOneWidget);
    expect(find.text('The Constitution on culture'), findsOneWidget);
    // Punjab's crafts, each with its town; then what protects them
    expect(find.text('Crafts and makers'), findsOneWidget);
    for (final name in ['Multani blue pottery', 'Footballs', 'Carved furniture']) {
      expect(find.text(name), findsOneWidget);
    }
    expect(find.text('SIALKOT'), findsOneWidget);
    expect(find.text('Protecting what Pakistan makes'), findsOneWidget);
    expect(find.text('How is a registered regional product marked?'), findsOneWidget);
    expect(find.textContaining('Basmati rice was registered'), findsOneWidget);
    await expectLater(find.byType(MaterialApp), matchesGoldenFile('goldens/heritage.png'));

    final picker = find.byType(ListView).at(1);
    // Balochistan: its 2014 Act answers; no heading is printed, so the section's opening words are quoted
    await tester.dragUntilVisible(find.text('Balochistan'), picker, const Offset(-80, 0));
    await tester.tap(find.text('Balochistan'));
    await tester.pumpAndSettle();
    expect(find.textContaining('in the Balochistan Antiquities Act, 2014.'), findsOneWidget); // never 'the The'
    expect(find.textContaining('“(1) Whoever discovers'), findsOneWidget);

    await tester.dragUntilVisible(find.text('Gilgit-Baltistan'), picker, const Offset(-160, 0));
    await tester.tap(find.text('Gilgit-Baltistan'));
    await tester.pumpAndSettle();
    expect(find.text('Baltit Fort'), findsOneWidget);
    expect(find.textContaining('does not yet hold a heritage law of Gilgit-Baltistan'), findsOneWidget);
    expect(find.text('Questions people ask'), findsNothing); // no law, no questions -- never another region's
    expect(find.text('The Constitution on culture'), findsNothing);

    await tester.dragUntilVisible(find.text('AJK'), picker, const Offset(80, 0));
    await tester.tap(find.text('AJK'));
    await tester.pumpAndSettle();
    expect(find.text('Questions people ask'), findsOneWidget);
    expect(find.text('The Constitution on culture'), findsNothing); // not served in AJK

    await tester.dragUntilVisible(find.text('Islamabad'), picker, const Offset(80, 0));
    await tester.tap(find.text('Islamabad'));
    await tester.pumpAndSettle();
    expect(find.textContaining('is served federal law'), findsOneWidget);
    expect(find.textContaining('the federal law that runs here'), findsOneWidget);
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
    // the craft of the day, keyed to the reader's date
    final (region, craft) = craftOfDay('2026-11-18');
    expect(find.text(craft.name), findsOneWidget);
    await expectLater(find.byType(MaterialApp), matchesGoldenFile('goldens/discover_tall.png'));
    // ...opens its own region on the Heritage tab
    await tester.tap(find.text(craft.name));
    await tester.pumpAndSettle();
    expect(find.text(region.place), findsOneWidget);
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
