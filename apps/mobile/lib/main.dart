import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'design/theme.dart';
import 'presentation/discover.dart';
import 'presentation/library.dart';
import 'presentation/reader.dart';
import 'state/library_state.dart';

void main() => runApp(const ProviderScope(child: NizamApp()));

final routerProvider = Provider<GoRouter>((ref) {
  final router = GoRouter(
    routes: [
      GoRoute(path: '/', builder: (context, state) => const DiscoverScreen()),
      GoRoute(
        path: '/library',
        builder:
            (context, state) => CatalogueScreen(
              key: ValueKey(state.uri.toString()),
              initialQuery: state.uri.queryParameters['q'] ?? '',
              initialJurisdiction:
                  const [
                        'fed',
                        'punjab',
                        'sindh',
                        'kp',
                        'balochistan',
                        'ict',
                        'ajk',
                        'gb',
                      ].contains(state.uri.queryParameters['jurisdiction'])
                      ? state.uri.queryParameters['jurisdiction']!
                      : '',
            ),
      ),
      GoRoute(
        path: '/instrument/:id',
        builder:
            (context, state) =>
                InstrumentScreen(id: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '/provision/:id',
        builder:
            (context, state) =>
                ProvisionScreen(id: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '/heritage',
        builder: (context, state) => const HeritageScreen(),
      ),
    ],
  );
  ref.onDispose(router.dispose);
  return router;
});

class NizamApp extends ConsumerWidget {
  const NizamApp({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) => MaterialApp.router(
    title: 'Nizam-e-Qanoon',
    debugShowCheckedModeBanner: false,
    theme: Stamp.theme(false),
    darkTheme: Stamp.theme(true),
    themeMode: ref.watch(darkModeProvider) ? ThemeMode.dark : ThemeMode.light,
    routerConfig: ref.watch(routerProvider),
  );
}
