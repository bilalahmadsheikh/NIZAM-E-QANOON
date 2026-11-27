import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../contracts/library_models.g.dart';

class LibraryFailure implements Exception {
  final String message;
  final bool offline;
  final bool refreshRequired;
  const LibraryFailure(
    this.message, {
    this.offline = false,
    this.refreshRequired = false,
  });
  @override
  String toString() => message;
}

/// Network-only preview. No unsigned cache masquerades as the future offline pack.
class LibraryRepository {
  final http.Client _client;
  final String baseUrl;
  LibraryRepository(this._client, this.baseUrl);

  /// A read that meets a dropped or refused connection is tried again twice, after 0.4 s and 1.2 s, before the
  /// reader is told the library cannot be reached: a server restart or a network blip should not end a reading
  /// (18 Nov 2026). Only connection failures are retried -- a 4xx/5xx answer or a timeout is reported at once.
  Future<Map<String, dynamic>> _get(String path, Map<String, String> query) async {
    const waits = [Duration(milliseconds: 400), Duration(milliseconds: 1200)];
    for (var attempt = 0;; attempt++) {
      try {
        return await _getOnce(path, query);
      } on LibraryFailure catch (e) {
        if (!e.offline || attempt >= waits.length) rethrow;
        await Future<void>.delayed(waits[attempt]);
      }
    }
  }

  Future<Map<String, dynamic>> _getOnce(
    String path,
    Map<String, String> query,
  ) async {
    try {
      final response = await _client
          .get(Uri.parse('$baseUrl$path').replace(queryParameters: query))
          .timeout(const Duration(seconds: 18));
      if (response.statusCode == 404 && path.startsWith('/v1/precedent/judgments/')) {
        // a judgment decided after the research date did not exist on that day (D-184)
        throw const LibraryFailure(
          'This judgment was not decided on or before the chosen date, or is no longer held. Change the date or return to the list.',
        );
      }
      if (response.statusCode == 404) {
        throw const LibraryFailure(
          'This revision is no longer available. Return to the library to find the current record.',
        );
      }
      if (response.statusCode == 400 && query.containsKey('after')) {
        throw const LibraryFailure(
          'This list has expired. Refresh to continue.',
          refreshRequired: true,
        );
      }
      if (response.statusCode != 200) {
        throw const LibraryFailure(
          'The library could not complete this request. Please try again.',
        );
      }
      return jsonDecode(utf8.decode(response.bodyBytes))
          as Map<String, dynamic>;
    } on TimeoutException {
      throw const LibraryFailure(
        'The library is taking longer than expected. Please try again.',
      );
    } on http.ClientException {
      throw const LibraryFailure(
        'The server cannot be reached. An offline law pack is not installed.',
        offline: true,
      );
    } on FormatException {
      throw const LibraryFailure('The server returned an unreadable response.');
    }
  }

  Future<InstrumentPage> instruments({
    required String asOf,
    String q = '',
    String jurisdiction = '',
    String kind = '',
    String? after,
  }) async => InstrumentPage.fromJson(
    await _get('/v1/law/instruments', {
      'as_of': asOf,
      'q': q,
      'jurisdiction': jurisdiction,
      'kind': kind,
      if (after != null) 'after': after,
    }),
  );
  Future<InstrumentResult> instrument(String id, String asOf) async =>
      InstrumentResult.fromJson(
        await _get('/v1/law/instruments/$id', {'as_of': asOf}),
      );
  Future<NodePage> children(
    String id,
    String asOf, {
    String? parent,
    String? after,
  }) async => NodePage.fromJson(
    await _get('/v1/law/instruments/$id/children', {
      'as_of': asOf,
      if (parent != null) 'parent': parent,
      if (after != null) 'after': after,
    }),
  );
  Future<ProvisionResult> provision(String id, String asOf) async =>
      ProvisionResult.fromJson(
        await _get('/v1/law/provisions/$id', {'as_of': asOf}),
      );

  /// A page of a law's served sections, in printed order (the law page's lazy list).
  Future<SectionPage> sections(String id, String asOf, {String territory = '', String? after}) async =>
      SectionPage.fromJson(
        await _get('/v1/law/instruments/$id/sections', {
          'as_of': asOf,
          'limit': '40',
          if (territory.isNotEmpty) 'territory': territory,
          if (after != null) 'after': after,
        }),
      );

  /// The home page's editorial collection of most-consulted laws.
  Future<CollectionPage> popular(String asOf) async =>
      CollectionPage.fromJson(await _get('/v1/law/collections/popular', {'as_of': asOf}));

  /// Laws dealing with a subject ('robbery', 'bail'), from section headings, with the units that say it (D-075).
  Future<SubjectPage> subjectSearch(String q, String asOf, {String jurisdiction = '', String kind = ''}) async =>
      SubjectPage.fromJson(await _get('/v1/law/search', {
        'q': q,
        'as_of': asOf,
        if (jurisdiction.isNotEmpty) 'jurisdiction': jurisdiction,
        if (kind.isNotEmpty) 'kind': kind,
      }));

  /// The units either side of [id] in its law's printed order, at [asOf] in [territory].
  Future<Neighbours> neighbours(String id, String asOf, {String territory = ''}) async => Neighbours.fromJson(
        await _get('/v1/law/provisions/$id/neighbours', {
          'as_of': asOf,
          if (territory.isNotEmpty) 'territory': territory,
        }),
      );

  /// The Constitution and the texts around it, grouped by how they relate (D-070).
  Future<ConstitutionPage> constitution(String asOf) async =>
      ConstitutionPage.fromJson(await _get('/v1/law/collections/constitution', {'as_of': asOf}));

  /// Pakistan's heritage law region by region, and questions answered by sections (D-077).
  Future<HeritagePage> heritage(String asOf) async =>
      HeritagePage.fromJson(await _get('/v1/law/collections/heritage', {'as_of': asOf}));

  // ------------------------------------------------------------------------------------------ precedent (D-184)
  // Network-required content (docs/08: precedent and judgments have no offline substitute). Every read carries the
  // research date: a judgment decided after it did not exist on that day and is never returned.

  /// Every recorded court, with how many of its judgments are held and the years they span.
  Future<CourtsPage> courts() async => CourtsPage.fromJson(await _get('/v1/precedent/courts', {}));

  /// A court's judgments, newest first, undated last; [after] is the previous page's cursor.
  Future<JudgmentList> courtJudgments(String court, String asOf, {String? after}) async =>
      JudgmentList.fromJson(await _get('/v1/precedent/courts/$court/judgments', {
        'as_of': asOf,
        'limit': '20',
        if (after != null) 'after': after,
      }));

  /// One judgment: its text with withheld names replaced, the laws it cites and the cases around it.
  Future<JudgmentPage> judgment(String id, String asOf) async =>
      JudgmentPage.fromJson(await _get('/v1/precedent/judgments/$id', {'as_of': asOf}));

  /// Later judgments that cite this one's case.
  Future<JudgmentList> citedBy(String id, String asOf) async =>
      JudgmentList.fromJson(await _get('/v1/precedent/judgments/$id/cited-by', {'as_of': asOf, 'limit': '20'}));

  /// What the courts above did with this judgment's case, as far as the corpus holds.
  Future<HistoryPage> history(String id, String asOf) async =>
      HistoryPage.fromJson(await _get('/v1/precedent/judgments/$id/history', {'as_of': asOf}));

  /// The decisions citing a section ([scope] 'provision') or a whole law ([scope] 'instrument'), [order] 'recent'
  /// (newest first) or 'relevant' (those construing it first, D-161), [offset] for the next page.
  Future<CitingPage> citing(String scope, String id, String asOf,
          {String order = 'recent', int offset = 0, int limit = 20}) async =>
      CitingPage.fromJson(await _get(
        scope == 'instrument' ? '/v1/law/instruments/$id/judgments' : '/v1/law/provisions/$id/judgments',
        {'as_of': asOf, 'order': order, 'limit': '$limit', if (offset > 0) 'offset': '$offset'},
      ));

  /// Judgments bearing on a question (discovery, not an answer: no gate is passed).
  Future<PrecedentSearchPage> precedentSearch(String q, String asOf, {String court = ''}) async =>
      PrecedentSearchPage.fromJson(await _get('/v1/precedent/search', {
        'q': q,
        'as_of': asOf,
        'limit': '10',
        if (court.isNotEmpty) 'court': court,
      }));

  /// A unit with everything under it, as operative_provision serves it at [asOf] in [territory] (INV-5): one
  /// request for a whole section instead of one per sub-section.
  Future<UnitText> unitText(String id, String asOf, {String territory = ''}) async => UnitText.fromJson(
        await _get('/v1/law/provisions/$id/text', {
          'as_of': asOf,
          if (territory.isNotEmpty) 'territory': territory,
        }),
      );
}
