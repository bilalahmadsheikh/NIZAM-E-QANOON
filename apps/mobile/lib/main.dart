import 'dart:ui' show PointerDeviceKind;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'design/theme.dart';
import 'presentation/constitution.dart';
import 'presentation/discover.dart';
import 'presentation/library.dart';
import 'presentation/reader.dart';
import 'state/library_state.dart';

void main() => runApp(const ProviderScope(child: NizamApp()));

const _jurisdictions = ['fed', 'punjab', 'sindh', 'kp', 'balochistan', 'ict', 'ajk', 'gb'];
const _kinds = ['act', 'ordinance', 'constitution', 'rules', 'regulation', 'order', 'sro', 'notification'];

final routerProvider = Provider<GoRouter>((ref) {
  final router = GoRouter(
    routes: [
      GoRoute(path: '/', builder: (context, state) => const DiscoverScreen()),
      GoRoute(
        path: '/library',
        builder: (context, state) {
          final p = state.uri.queryParameters;
          return CatalogueScreen(
            key: ValueKey(state.uri.toString()),
            initialQuery: p['q'] ?? '',
            initialJurisdiction: _jurisdictions.contains(p['jurisdiction']) ? p['jurisdiction']! : '',
            initialKind: _kinds.contains(p['kind']) ? p['kind']! : '',
          );
        },
      ),
      GoRoute(path: '/constitution', builder: (context, state) => const ConstitutionScreen()),
      GoRoute(
        path: '/instrument/:id',
        builder: (context, state) => InstrumentScreen(id: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '/provision/:id',
        builder: (context, state) => ProvisionScreen(id: state.pathParameters['id']!),
      ),
      GoRoute(path: '/heritage', builder: (context, state) => const HeritageScreen()),
    ],
  );
  ref.onDispose(router.dispose);
  return router;
});

/// Lists scroll by drag from any pointer. Flutter's default leaves mouse and trackpad out of the drag devices, so on
/// an emulator driven by a mouse, a desktop build or a laptop touchpad a sideways list (the home shelf) could not be
/// dragged at all -- a vertical wheel never scrolls a horizontal list.
class _AnyPointerScroll extends MaterialScrollBehavior {
  const _AnyPointerScroll();
  @override
  Set<PointerDeviceKind> get dragDevices => PointerDeviceKind.values.toSet();
}

class NizamApp extends ConsumerWidget {
  const NizamApp({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) => MaterialApp.router(
        title: 'Nizam-e-Qanoon',
        debugShowCheckedModeBanner: false,
        scrollBehavior: const _AnyPointerScroll(),
        theme: Stamp.theme(false),
        darkTheme: Stamp.theme(true),
        themeMode: ref.watch(darkModeProvider) ? ThemeMode.dark : ThemeMode.light,
        routerConfig: ref.watch(routerProvider),
      );
}
