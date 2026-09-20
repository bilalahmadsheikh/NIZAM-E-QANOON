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

  Future<Map<String, dynamic>> _get(
    String path,
    Map<String, String> query,
  ) async {
    try {
      final response = await _client
          .get(Uri.parse('$baseUrl$path').replace(queryParameters: query))
          .timeout(const Duration(seconds: 18));
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
}
