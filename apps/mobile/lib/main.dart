import 'dart:ui' show PointerDeviceKind;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'design/embroidery.dart';
import 'design/theme.dart';
import 'presentation/catalogue.dart';
import 'presentation/constitution.dart';
import 'presentation/discover.dart';
import 'presentation/heritage.dart';
import 'presentation/library.dart';
import 'presentation/reader.dart';
import 'state/library_state.dart';

void main() => runApp(const ProviderScope(child: NizamApp()));

const _jurisdictions = ['fed', 'punjab', 'sindh', 'kp', 'balochistan', 'ict', 'ajk', 'gb'];
const _kinds = ['act', 'ordinance', 'constitution', 'rules', 'regulation', 'order', 'sro', 'notification'];

/// Every page comes in through a stitched seam (D-084): the page fades up while a thread is run across its top.
Page<void> _stitched(GoRouterState state, Widget child) => CustomTransitionPage<void>(
      key: state.pageKey,
      child: child,
      transitionDuration: const Duration(milliseconds: 380),
      reverseTransitionDuration: const Duration(milliseconds: 200),
      transitionsBuilder: (context, animation, secondary, child) => StitchTransition(animation: animation, child: child),
    );

final routerProvider = Provider<GoRouter>((ref) {
  final router = GoRouter(
    routes: [
      GoRoute(path: '/', pageBuilder: (context, state) => _stitched(state, const DiscoverScreen())),
      GoRoute(
        path: '/library',
        pageBuilder: (context, state) {
          final p = state.uri.queryParameters;
          return _stitched(
            state,
            CatalogueScreen(
              key: ValueKey(state.uri.toString()),
              initialQuery: p['q'] ?? '',
              initialJurisdiction: _jurisdictions.contains(p['jurisdiction']) ? p['jurisdiction']! : '',
              initialKind: _kinds.contains(p['kind']) ? p['kind']! : '',
            ),
          );
        },
      ),
      GoRoute(path: '/constitution', pageBuilder: (context, state) => _stitched(state, const ConstitutionScreen())),
      GoRoute(
        path: '/instrument/:id',
        pageBuilder: (context, state) => _stitched(state, InstrumentScreen(id: state.pathParameters['id']!)),
      ),
      GoRoute(
        path: '/provision/:id',
        pageBuilder: (context, state) => _stitched(state, ProvisionScreen(id: state.pathParameters['id']!)),
      ),
      // ?region= opens a region's panel (the home page's craft of the day, D-079)
      GoRoute(
        path: '/heritage',
        pageBuilder: (context, state) => _stitched(
            state,
            HeritageScreen(
                key: ValueKey(state.uri.queryParameters['region']), region: state.uri.queryParameters['region'])),
      ),
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
