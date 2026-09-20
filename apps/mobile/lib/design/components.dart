import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../state/library_state.dart';

class GlassPanel extends StatelessWidget {
  final Widget child;
  const GlassPanel({super.key, required this.child});
  @override
  Widget build(BuildContext context) => ClipRRect(
    borderRadius: BorderRadius.circular(24),
    child: BackdropFilter(
      filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
      child: Container(
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface.withValues(alpha: .91),
          borderRadius: BorderRadius.circular(24),
          border: Border.all(
            color: Theme.of(context).colorScheme.outline.withValues(alpha: .7),
          ),
        ),
        child: child,
      ),
    ),
  );
}

class LibraryScaffold extends ConsumerWidget {
  final Widget body;
  final String title;
  final int selected;
  final List<Widget> actions;
  const LibraryScaffold({
    super.key,
    required this.body,
    required this.title,
    this.selected = 1,
    this.actions = const [],
  });
  @override
  Widget build(BuildContext context, WidgetRef ref) => Scaffold(
    appBar: AppBar(
      title: Text(
        title,
        style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
      ),
      actions: [
        ...actions,
        IconButton(
          tooltip: 'Switch light or dark theme',
          onPressed:
              () =>
                  ref.read(darkModeProvider.notifier).state =
                      !ref.read(darkModeProvider),
          icon: Icon(
            ref.watch(darkModeProvider)
                ? Icons.light_mode_outlined
                : Icons.dark_mode_outlined,
          ),
        ),
        const SizedBox(width: 12),
      ],
    ),
    body: SafeArea(
      bottom: false,
      child: Column(children: [const ScopeBand(), Expanded(child: body)]),
    ),
    bottomNavigationBar: SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
        child: GlassPanel(
          child: NavigationBar(
            backgroundColor: Colors.transparent,
            elevation: 0,
            height: 72,
            selectedIndex: selected,
            onDestinationSelected:
                (index) => context.go(['/', '/library', '/heritage'][index]),
            destinations: const [
              NavigationDestination(
                icon: Icon(Icons.home_outlined),
                selectedIcon: Icon(Icons.home),
                label: 'Discover',
              ),
              NavigationDestination(
                icon: Icon(Icons.auto_stories_outlined),
                selectedIcon: Icon(Icons.auto_stories),
                label: 'Library',
              ),
              NavigationDestination(
                icon: Icon(Icons.account_balance_outlined),
                selectedIcon: Icon(Icons.account_balance),
                label: 'Heritage',
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

class ScopeBand extends ConsumerWidget {
  const ScopeBand({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) => Container(
    width: double.infinity,
    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 5),
    decoration: BoxDecoration(
      border: Border(
        bottom: BorderSide(color: Theme.of(context).colorScheme.outline),
      ),
    ),
    child: Wrap(
      crossAxisAlignment: WrapCrossAlignment.center,
      alignment: WrapAlignment.spaceBetween,
      children: [
        const Text(
          'RESEARCH PREVIEW',
          style: TextStyle(
            fontSize: 10,
            letterSpacing: 1.8,
            fontWeight: FontWeight.w700,
          ),
        ),
        TextButton.icon(
          icon: const Icon(Icons.calendar_today_outlined, size: 14),
          label: Text(
            'As of ${ref.watch(asOfProvider)}',
            style: const TextStyle(fontSize: 12),
          ),
          onPressed: () async {
            final day = await showDatePicker(
              context: context,
              initialDate: DateTime.parse(ref.read(asOfProvider)),
              firstDate: DateTime(1800),
              lastDate: DateTime.now().add(const Duration(days: 365)),
            );
            if (day != null) {
              ref.read(asOfProvider.notifier).state = day
                  .toIso8601String()
                  .substring(0, 10);
            }
          },
        ),
      ],
    ),
  );
}

class Eyebrow extends StatelessWidget {
  final String text;
  const Eyebrow(this.text, {super.key});
  @override
  Widget build(BuildContext context) => Text(
    text.toUpperCase(),
    style: TextStyle(
      fontSize: 11,
      letterSpacing: 2.1,
      fontWeight: FontWeight.w700,
      color: Theme.of(context).colorScheme.secondary,
    ),
  );
}

class PaperCard extends StatelessWidget {
  final Widget child;
  final VoidCallback? onTap;
  const PaperCard({super.key, required this.child, this.onTap});
  @override
  Widget build(BuildContext context) => Material(
    color: Theme.of(context).colorScheme.surface,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(20),
      side: BorderSide(color: Theme.of(context).colorScheme.outline),
    ),
    clipBehavior: Clip.antiAlias,
    child: InkWell(
      onTap: onTap,
      child: Padding(padding: const EdgeInsets.all(24), child: child),
    ),
  );
}

class Notice extends StatelessWidget {
  final String text;
  final IconData icon;
  const Notice(this.text, {super.key, this.icon = Icons.info_outline});
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.secondary.withValues(alpha: .08),
      borderRadius: BorderRadius.circular(14),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 19),
        const SizedBox(width: 12),
        Expanded(
          child: Text(text, style: const TextStyle(fontSize: 13, height: 1.5)),
        ),
      ],
    ),
  );
}

class LoadingStructure extends StatelessWidget {
  const LoadingStructure({super.key});
  @override
  Widget build(BuildContext context) => Semantics(
    label: 'Loading library content',
    liveRegion: true,
    child: Column(
      children: List.generate(
        3,
        (i) => Padding(
          padding: const EdgeInsets.only(bottom: 16),
          child: PaperCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _line(context, 72, 12),
                const SizedBox(height: 20),
                _line(context, double.infinity, 20),
                const SizedBox(height: 10),
                _line(context, 170, 16),
              ],
            ),
          ),
        ),
      ),
    ),
  );
  Widget _line(BuildContext context, double width, double height) => Container(
    width: width,
    height: height,
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.outline.withValues(alpha: .4),
      borderRadius: BorderRadius.circular(6),
    ),
  );
}

class LoadFailure extends StatelessWidget {
  final Object error;
  final VoidCallback onRetry;
  const LoadFailure(this.error, {super.key, required this.onRetry});
  @override
  Widget build(BuildContext context) {
    final offline =
        error is LibraryFailure && (error as LibraryFailure).offline;
    return PaperCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            offline ? Icons.cloud_off_outlined : Icons.info_outline,
            size: 32,
          ),
          const SizedBox(height: 20),
          Text(
            offline ? 'Not connected' : 'Unable to load this page',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 12),
          Text(
            error is LibraryFailure
                ? error.toString()
                : 'The library is temporarily unavailable.',
            style: const TextStyle(height: 1.5),
          ),
          const SizedBox(height: 20),
          if (offline)
            const Text(
              'Reconnect, then reopen this page. No offline pack is installed.',
            )
          else
            OutlinedButton(onPressed: onRetry, child: const Text('Try again')),
        ],
      ),
    );
  }
}

class MoreButton<T> extends StatelessWidget {
  final Paged<T> page;
  final VoidCallback load;
  final VoidCallback refresh;
  const MoreButton(
    this.page, {
    super.key,
    required this.load,
    required this.refresh,
  });
  bool get expired =>
      page.moreError is LibraryFailure &&
      (page.moreError as LibraryFailure).refreshRequired;
  @override
  Widget build(BuildContext context) => Column(
    children: [
      if (page.moreError != null)
        const Padding(
          padding: EdgeInsets.all(12),
          child: Text(
            'The next page could not be loaded. Your current results are still here.',
          ),
        ),
      if (page.next != null)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: OutlinedButton.icon(
            onPressed: page.loadingMore ? null : (expired ? refresh : load),
            icon: const Icon(Icons.expand_more),
            label: Text(
              page.loadingMore
                  ? 'Loading next page…'
                  : expired
                  ? 'Refresh list'
                  : 'Load more',
            ),
          ),
        ),
    ],
  );
}

class ReadingWidth extends StatelessWidget {
  final Widget child;
  const ReadingWidth({super.key, required this.child});
  @override
  Widget build(BuildContext context) => Align(
    alignment: Alignment.topCenter,
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 960),
      child: child,
    ),
  );
}

String jurisdictionName(String key) =>
    const {
      'fed': 'Federal',
      'punjab': 'Punjab',
      'sindh': 'Sindh',
      'kp': 'Khyber Pakhtunkhwa',
      'balochistan': 'Balochistan',
      'ict': 'Islamabad',
      'ajk': 'AJK',
      'gb': 'Gilgit-Baltistan',
    }[key] ??
    key;
String statusName(String key) =>
    const {
      'unknown': 'Legal status unverified',
      'in_force': 'Recorded as in force',
      'repealed': 'Recorded as repealed',
      'spent': 'Recorded as spent',
      'lapsed': 'Recorded as lapsed',
      'not_yet_commenced': 'Not yet commenced',
    }[key] ??
    'Legal status unverified';

class StatusNote extends StatelessWidget {
  final String status;
  const StatusNote(this.status, {super.key});
  @override
  Widget build(BuildContext context) => Notice(
    '${statusName(status)}. The selected date filters stored text versions; it is not proof that amendment history is complete.',
    icon: status == 'repealed' ? Icons.block : Icons.policy_outlined,
  );
}
