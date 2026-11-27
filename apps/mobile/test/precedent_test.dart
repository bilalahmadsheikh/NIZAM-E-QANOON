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
import 'package:nizam_app/presentation/precedent.dart';
import 'package:nizam_app/state/library_state.dart';

/// D-184: precedent in the app, against responses recorded from the real API (test/fixtures/precedent-responses.json:
/// a Lahore High Court judgment, cut to six paragraphs).
void main() {
  final fixture =
      jsonDecode(File('test/fixtures/precedent-responses.json').readAsStringSync()) as Map<String, dynamic>;
  final judgmentId = fixture['_judgment'] as String;
  final provisionId = fixture['_provision'] as String;
  final instrumentId = fixture['_instrument'] as String;

  /// A repository answering from the fixture by path; [asked] records every request; [edit] may change a response.
  LibraryRepository repo(List<Uri> asked, {Map<String, dynamic> Function(String path, Map<String, dynamic> body)? edit,
      bool offline = false}) =>
      LibraryRepository(
        MockClient((request) async {
          asked.add(request.url);
          if (offline) throw http.ClientException('no route to host');
          final body = fixture[request.url.path];
          if (body == null) return http.Response('{"detail": "not found"}', 404);
          final out = edit == null ? body as Map<String, dynamic> : edit(request.url.path, jsonDecode(jsonEncode(body)));
          return http.Response(jsonEncode(out), 200, headers: {'content-type': 'application/json; charset=utf-8'});
        }),
        'http://fixture.invalid',
      );

  Future<void> fonts() async {
    final icons = FontLoader('MaterialIcons')..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await icons.load();
    for (final font in [('Spectral', 'Spectral-Regular.ttf'), ('Karla', 'Karla.ttf')]) {
      final loader = FontLoader(font.$1)..addFont(rootBundle.load('assets/fonts/${font.$2}'));
      await loader.load();
    }
  }

  test('every recorded precedent response decodes through the generated contract', () async {
    final r = repo([]);
    final courts = await r.courts();
    expect(courts.total_judgments, greaterThan(60000));
    expect(courts.coverage_note, contains('not proof that nothing else was decided'));
    final list = await r.courtJudgments('LHC', '2026-11-27');
    expect(list.items, isNotEmpty);
    final page = await r.judgment(judgmentId, '2026-11-27');
    expect(page.statutes_cited, isNotEmpty);
    expect(page.paragraphs, isNotEmpty);
    expect((await r.citing('provision', provisionId, '2026-11-27')).total, greaterThan(0));
    expect((await r.citing('instrument', instrumentId, '2026-11-27')).scope, 'instrument');
    await r.citedBy(judgmentId, '2026-11-27');
    await r.history(judgmentId, '2026-11-27');
    expect((await r.precedentSearch('eviction of a tenant', '2026-11-27')).kind, 'precedent_discovery');
  });

  test('a judgment not decided by the chosen date says so, not "revision unavailable"', () async {
    final r = repo([]);
    await expectLater(
      r.judgment('00000000-0000-0000-0000-000000000000', '1990-01-01'),
      throwsA(isA<LibraryFailure>().having((e) => e.message, 'message', contains('not decided on or before'))),
    );
  });

  Future<(ProviderContainer, List<Uri>)> app(WidgetTester tester, String location,
      {Map<String, dynamic> Function(String, Map<String, dynamic>)? edit, Size size = const Size(430, 932)}) async {
    await fonts();
    tester.view.physicalSize = size;
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final asked = <Uri>[];
    final container = ProviderContainer(overrides: [
      repositoryProvider.overrideWithValue(repo(asked, edit: edit)),
      asOfProvider.overrideWith((ref) => '2026-11-27'),
    ]);
    addTearDown(container.dispose);
    await tester.pumpWidget(UncontrolledProviderScope(container: container, child: const NizamApp()));
    container.read(routerProvider).go(location);
    await tester.pumpAndSettle();
    return (container, asked);
  }

  /// closing a screen starts the five-minute cache countdown (as the reader's tests do); let it run out
  Future<void> close(WidgetTester tester) async {
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(minutes: 6));
  }

  Finder scroller(Type t) => find.descendant(of: find.byType(t), matching: find.byType(Scrollable)).first;

  /// brings [f] to the upper third of its list, clear of the navigation bar, before it is tapped
  Future<void> raise(WidgetTester tester, Finder f) async {
    await Scrollable.ensureVisible(tester.element(f), alignment: .3);
    await tester.pumpAndSettle();
  }

  String here(ProviderContainer c) => c.read(routerProvider).routerDelegate.currentConfiguration.last.matchedLocation;

  testWidgets('a judgment reads whole and a law it cites opens the law', (tester) async {
    final (c, asked) = await app(tester, '/judgment/$judgmentId');
    expect(tester.takeException(), isNull);
    final page = fixture['/v1/precedent/judgments/$judgmentId'] as Map<String, dynamic>;
    expect(find.text(page['judgment']['parties_display'] as String, findRichText: true), findsNothing); // isolated
    expect(find.textContaining(page['judgment']['parties_display'] as String), findsOneWidget);
    expect(find.text('LAWS THIS JUDGMENT CITES'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('THE JUDGMENT'), 300, scrollable: scroller(CustomScrollView));
    expect(find.text('THE JUDGMENT'), findsOneWidget);
    await tester.scrollUntilVisible(find.byType(ActionChip).first, -300, scrollable: scroller(CustomScrollView));
    expect(asked.every((u) => u.queryParameters['as_of'] == '2026-11-27'), isTrue);   // every read carries the date
    // a cited unit opens the law at that unit
    final first = (page['statutes_cited'] as List).first as Map<String, dynamic>;
    await raise(tester, find.byType(ActionChip).first);
    await tester.tap(find.byType(ActionChip).first);
    await tester.pumpAndSettle();
    expect(here(c), '/provision/${first['provision_id']}');
    await close(tester);
  });

  testWidgets('a machine-read outcome is never shown as a fact', (tester) async {
    await app(tester, '/judgment/$judgmentId', edit: (path, body) {
      if (path.endsWith(judgmentId)) {
        body['appeal_from'] = [
          {'relation': 'appeal_from', 'court_below': 'Civil Judge', 'case_below': 'Suit 4 of 2020',
           'decided_below': '2021-01-01', 'outcome': null, 'outcome_withheld': true}
        ];
      }
      if (path.endsWith('/history')) {
        body['items'] = [
          {'source': 'upper_judgment', 'judgment_id': judgmentId, 'court': 'Supreme Court of Pakistan',
           'relation': 'appeal', 'outcome': null, 'outcome_withheld': true, 'outcome_printed': null,
           'decided_on': '2026-11-20', 'citation': 'Supreme Court of Pakistan, C.P. 1 of 2026, decided 20 Nov 2026',
           'upper_file_url': null}
        ];
      }
      return body;
    });
    await tester.scrollUntilVisible(find.text('WHAT THE COURTS ABOVE DID'), 400,
        scrollable: scroller(CustomScrollView));
    await tester.pumpAndSettle();
    expect(find.textContaining('awaits a lawyer’s review'), findsWidgets);
    expect(find.textContaining('Set aside'), findsNothing);
    expect(find.textContaining('Reversed'), findsNothing);
    await close(tester);
  });

  testWidgets('decisions citing a section are newest first, and the reader may ask for the most relevant',
      (tester) async {
    await fonts();
    final asked = <Uri>[];
    await tester.pumpWidget(ProviderScope(
      overrides: [
        repositoryProvider.overrideWithValue(repo(asked)),
        asOfProvider.overrideWith((ref) => '2026-11-27'),
      ],
      child: MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(child: CitingSection(scope: 'provision', id: provisionId, noun: 'section')),
        ),
      ),
    ));
    await tester.pumpAndSettle();
    final total = (fixture['/v1/law/provisions/$provisionId/judgments'] as Map<String, dynamic>)['total'] as int;
    expect(find.text('${count(total)} decisions held cite this section'), findsOneWidget);
    expect(asked.last.queryParameters['order'], 'recent');
    await tester.tap(find.text('Most relevant'));
    await tester.pumpAndSettle();
    expect(asked.last.queryParameters['order'], 'relevant');
    expect(find.textContaining('A judgment not held is not shown'), findsOneWidget);   // coverage, always stated
    await close(tester);
  });

  testWidgets('offline, the decisions wait quietly and the law is unaffected', (tester) async {
    await tester.pumpWidget(ProviderScope(
      overrides: [
        repositoryProvider.overrideWithValue(repo([], offline: true)),
        asOfProvider.overrideWith((ref) => '2026-11-27'),
      ],
      child: MaterialApp(home: Scaffold(body: CitingSection(scope: 'provision', id: provisionId, noun: 'section'))),
    ));
    await tester.pump(const Duration(seconds: 3));
    await tester.pumpAndSettle();
    expect(find.text('Decisions need the library connection. The law above is unaffected.'), findsOneWidget);
    expect(find.text('Try again'), findsNothing);                                      // offline is not an error
    await close(tester);
  });

  testWidgets('the Judgments tab lists every court with what is held, and a court opens newest first',
      (tester) async {
    final (c, _) = await app(tester, '/judgments');
    expect(find.text('Judgments'), findsWidgets);
    expect(find.textContaining('judgments held'), findsWidgets);
    await tester.scrollUntilVisible(find.text('Lahore High Court'), 200, scrollable: scroller(ListView));
    expect(find.text('Lahore High Court'), findsOneWidget);
    await raise(tester, find.text('Lahore High Court'));
    await tester.tap(find.text('Lahore High Court'));
    await tester.pumpAndSettle();
    expect(here(c), '/court/LHC');
    expect(find.text('NEWEST FIRST'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await close(tester);
  });

  testWidgets('a judgment at phone width with large text does not overflow', (tester) async {
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await app(tester, '/judgment/$judgmentId', size: const Size(360, 800));
    expect(tester.takeException(), isNull);
    await tester.drag(find.byType(CustomScrollView), const Offset(0, -3000));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    await close(tester);
  });
}
