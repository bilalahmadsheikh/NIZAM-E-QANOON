import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import '../contracts/library_models.g.dart';
import '../data/library_repository.dart';
import '../platform/source_actions.dart';
export '../data/library_repository.dart' show LibraryFailure;

String pakistanDate() => DateTime.now()
    .toUtc()
    .add(const Duration(hours: 5))
    .toIso8601String()
    .substring(0, 10);
final asOfProvider = StateProvider<String>((ref) => pakistanDate());
final darkModeProvider = StateProvider<bool>((ref) => false);
final readerSizeProvider = StateProvider<double>((ref) => 19);
final urduContentProvider = StateProvider<bool>((ref) => false);
final sourceActionsProvider = Provider<SourceActions>((ref) => SourceActions());
final repositoryProvider = Provider<LibraryRepository>((ref) {
  final client = http.Client();
  ref.onDispose(client.close);
  return LibraryRepository(
    client,
    const String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://10.0.2.2:8080',
    ),
  );
});

typedef CatalogueQuery = ({String q, String jurisdiction, String kind});
typedef ChildQuery = ({String instrument, String? parent});

class Paged<T> {
  final List<T> items;
  final String? next;
  final bool loadingMore;
  final Object? moreError;
  const Paged(
    this.items,
    this.next, {
    this.loadingMore = false,
    this.moreError,
  });
}

/// One request in flight; dispose prevents stale searches updating a new screen.
class Pager<T> extends StateNotifier<AsyncValue<Paged<T>>> {
  final Future<(List<T>, String?)> Function(String?) fetch;
  bool _closed = false;
  Pager(this.fetch) : super(const AsyncLoading()) {
    reload();
  }
  Future<void> reload() async {
    state = const AsyncLoading();
    try {
      final (items, next) = await fetch(null);
      if (!_closed) state = AsyncData(Paged(items, next));
    } catch (e, s) {
      if (!_closed) state = AsyncError(e, s);
    }
  }

  Future<void> more() async {
    final previous = state.valueOrNull;
    if (previous == null || previous.next == null || previous.loadingMore) {
      return;
    }
    state = AsyncData(Paged(previous.items, previous.next, loadingMore: true));
    try {
      final (items, next) = await fetch(previous.next);
      if (!_closed) {
        state = AsyncData(Paged([...previous.items, ...items], next));
      }
    } catch (e) {
      if (!_closed) {
        state = AsyncData(Paged(previous.items, previous.next, moreError: e));
      }
    }
  }

  @override
  void dispose() {
    _closed = true;
    super.dispose();
  }
}

final catalogueProvider = StateNotifierProvider.autoDispose
    .family<Pager<Instrument>, AsyncValue<Paged<Instrument>>, CatalogueQuery>((
      ref,
      query,
    ) {
      final repo = ref.watch(repositoryProvider);
      final day = ref.watch(asOfProvider);
      return Pager((after) async {
        final page = await repo.instruments(
          asOf: day,
          q: query.q,
          jurisdiction: query.jurisdiction,
          kind: query.kind,
          after: after,
        );
        return (page.items, page.next_cursor);
      });
    });
final childrenProvider = StateNotifierProvider.autoDispose
    .family<Pager<Node>, AsyncValue<Paged<Node>>, ChildQuery>((ref, query) {
      final repo = ref.watch(repositoryProvider);
      final day = ref.watch(asOfProvider);
      return Pager((after) async {
        final page = await repo.children(
          query.instrument,
          day,
          parent: query.parent,
          after: after,
        );
        return (page.items, page.next_cursor);
      });
    });
final instrumentProvider = FutureProvider.autoDispose
    .family<InstrumentResult, String>(
      (ref, id) =>
          ref.watch(repositoryProvider).instrument(id, ref.watch(asOfProvider)),
    );
final provisionProvider = FutureProvider.autoDispose
    .family<ProvisionResult, String>(
      (ref, id) =>
          ref.watch(repositoryProvider).provision(id, ref.watch(asOfProvider)),
    );
