import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import '../contracts/library_models.g.dart';
import '../data/library_repository.dart';
import '../domain/reading_mode.dart';
import '../platform/source_actions.dart';
export '../domain/reading_mode.dart';
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

/// The reading mode (domain/reading_mode.dart): density and tools, never a different law or status.
final readingModeProvider = StateProvider<ReadingMode>((ref) => ReadingMode.everyday);

/// A law's served sections, paged ahead of the reader's scroll. The served count and the law's serving record
/// arrive with the first page and are kept beside the list.
final sectionsHeadProvider = StateProvider.family<SectionPage?, String>((ref, id) => null);
final sectionsProvider = StateNotifierProvider.autoDispose
    .family<Pager<SectionItem>, AsyncValue<Paged<SectionItem>>, String>((ref, id) {
  final repo = ref.watch(repositoryProvider);
  final day = ref.watch(asOfProvider);
  final territory = ref.watch(territoryProvider);
  final link = ref.keepAlive();
  Timer? timer;
  ref.onCancel(() => timer = Timer(const Duration(minutes: 5), link.close));
  ref.onResume(() => timer?.cancel());
  ref.onDispose(() => timer?.cancel());
  return Pager((after) async {
    final page = await repo.sections(id, day, territory: territory, after: after);
    if (after == null) {
      Future.microtask(() => ref.read(sectionsHeadProvider(id).notifier).state = page);
    }
    return (page.items, page.next_cursor);
  });
});

/// The home carousel: one small request, kept for the session.
final popularProvider = FutureProvider<CollectionPage>(
  (ref) => ref.watch(repositoryProvider).popular(ref.watch(asOfProvider)),
);

/// Laws dealing with a subject, with the units that say it; only for a query of two letters or more.
final subjectProvider = FutureProvider.autoDispose.family<SubjectPage, CatalogueQuery>((ref, query) =>
    ref.watch(repositoryProvider).subjectSearch(query.q, ref.watch(asOfProvider),
        jurisdiction: query.jurisdiction, kind: query.kind));

/// The reader's previous / next units, fetched beside the text (never in its way).
final neighboursProvider = FutureProvider.autoDispose.family<Neighbours, String>((ref, id) =>
    ref.watch(repositoryProvider).neighbours(id, ref.watch(asOfProvider), territory: ref.watch(territoryProvider)));

/// The Constitution's page: the Constitution, its amendments and the texts around it, as at the chosen date.
final constitutionProvider = FutureProvider<ConstitutionPage>(
  (ref) => ref.watch(repositoryProvider).constitution(ref.watch(asOfProvider)),
);

/// The reader's territory ('' = none chosen: every law is returned, each with its own reach). Part of the scope,
/// like the date: a Punjab reader must not be served a law that does not run in Punjab (docs/04 §6).
final territoryProvider = StateProvider<String>((ref) => '');

/// A unit and its served subtree. Kept for five minutes after the screen closes, so going back to a section and
/// forward again costs no request; the date and territory are part of the key through ref.watch.
final unitTextProvider = FutureProvider.autoDispose.family<UnitText, String>((ref, id) async {
  // the countdown starts only when the last screen showing this unit closes, and stops if one comes back
  final link = ref.keepAlive();
  Timer? timer;
  ref.onCancel(() => timer = Timer(const Duration(minutes: 5), link.close));
  ref.onResume(() => timer?.cancel());
  ref.onDispose(() => timer?.cancel());
  return ref.watch(repositoryProvider).unitText(
        id,
        ref.watch(asOfProvider),
        territory: ref.watch(territoryProvider),
      );
});
