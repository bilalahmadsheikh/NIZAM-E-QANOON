import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../domain/heritage.dart';
import '../state/library_state.dart';
import 'heritage_art.dart';

/// The navigation surface. A solid panel, not a live blur: on 17 Nov 2026 the
/// BackdropFilter(blur 12) that was here aborted the Impeller OpenGL ES raster
/// thread on an Android 16 emulator ("Must be able to encode GL commands
/// without error") on route changes. GLES is also the Impeller path on phones
/// without Vulkan. Over a 91 % opaque surface the blur was barely visible, yet
/// it cost an extra offscreen pass on every frame behind every screen.
class GlassPanel extends StatelessWidget {
  final Widget child;
  const GlassPanel({super.key, required this.child});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: scheme.surface.withValues(alpha: .97),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: scheme.outline.withValues(alpha: .7)),
        boxShadow: [
          BoxShadow(
            color: scheme.shadow.withValues(alpha: .08),
            blurRadius: 12,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: child,
    );
  }
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
  Widget build(BuildContext context, WidgetRef ref) {
    // Back on the Library or Heritage tab root returns to Discover instead of closing the app (seen on the
    // emulator 17 Nov 2026); on Discover, or on any pushed page, Back behaves as the platform expects.
    final tabRoot = selected != 0 && !GoRouter.of(context).canPop();
    return PopScope(
      canPop: !tabRoot,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop && tabRoot) context.go('/');
      },
      child: _scaffold(context, ref),
    );
  }

  Widget _scaffold(BuildContext context, WidgetRef ref) => Scaffold(
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
                // the Minar-e-Pakistan as the tab's mark (D-077), in the navigation's own icon colour
                icon: LandmarkIcon(Landmark.minar),
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
    padding: const EdgeInsets.symmetric(horizontal: 12),
    decoration: BoxDecoration(
      border: Border(
        bottom: BorderSide(color: Theme.of(context).colorScheme.outline),
      ),
    ),
    // one 48 dp row that scrolls sideways on a narrow phone, instead of wrapping to two rows on every screen
    child: SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
      children: [
        const Padding(
          padding: EdgeInsets.only(left: 12, right: 8),
          child: Text(
            'PREVIEW',
            style: TextStyle(
              fontSize: 10,
              letterSpacing: 1.8,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        // reading mode: density and tools only (domain/reading_mode.dart) -- labelled as a mode, not an identity
        PopupMenuButton<ReadingMode>(
          tooltip: 'Reading mode',
          initialValue: ref.watch(readingModeProvider),
          onSelected: (m) => ref.read(readingModeProvider.notifier).state = m,
          itemBuilder: (context) => [
            for (final m in ReadingMode.values)
              PopupMenuItem(
                value: m,
                child: ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(m.label),
                  subtitle: Text(m.description, style: const TextStyle(fontSize: 12)),
                ),
              ),
          ],
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 12),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              const Icon(Icons.chrome_reader_mode_outlined, size: 14),
              const SizedBox(width: 6),
              Text('Reading: ${ref.watch(readingModeProvider).label}', style: const TextStyle(fontSize: 12)),
              const Icon(Icons.arrow_drop_down, size: 18),
            ]),
          ),
        ),
        // territory: part of the scope, like the date (docs/04 §6); '' = all, each law with its own reach
        PopupMenuButton<String>(
          tooltip: 'Territory',
          initialValue: ref.watch(territoryProvider),
          onSelected: (t) => ref.read(territoryProvider.notifier).state = t,
          itemBuilder: (context) => [
            for (final t in const ['', 'punjab', 'sindh', 'kp', 'balochistan', 'ict', 'ajk', 'gb'])
              PopupMenuItem(value: t, child: Text(t.isEmpty ? 'All territories' : _territoryLabel(t))),
          ],
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 12),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              const Icon(Icons.place_outlined, size: 14),
              const SizedBox(width: 6),
              Text(
                ref.watch(territoryProvider).isEmpty ? 'All territories' : _territoryLabel(ref.watch(territoryProvider)),
                style: const TextStyle(fontSize: 12),
              ),
              const Icon(Icons.arrow_drop_down, size: 18),
            ]),
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
    ),
  );
}

String _territoryLabel(String key) =>
    const {
      'punjab': 'Punjab',
      'sindh': 'Sindh',
      'kp': 'Khyber Pakhtunkhwa',
      'balochistan': 'Balochistan',
      'ict': 'Islamabad',
      'ajk': 'AJK',
      'gb': 'Gilgit-Baltistan',
    }[key] ??
    key;

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

class LoadFailure extends StatefulWidget {
  final Object error;
  final VoidCallback onRetry;
  const LoadFailure(this.error, {super.key, required this.onRetry});
  @override
  State<LoadFailure> createState() => _LoadFailureState();
}

/// Offline is an outcome, not an error (client rules): no retry button. While it stands, the page quietly asks again
/// every few seconds and opens by itself when the library answers.
class _LoadFailureState extends State<LoadFailure> {
  Timer? _again;
  bool get _offline => widget.error is LibraryFailure && (widget.error as LibraryFailure).offline;

  @override
  void initState() {
    super.initState();
    if (_offline) _again = Timer.periodic(const Duration(seconds: 5), (_) => widget.onRetry());
  }

  @override
  void dispose() {
    _again?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final error = widget.error;
    final onRetry = widget.onRetry;
    final offline = _offline;
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
            offline ? 'Waiting for the library' : 'Unable to load this page',
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
            const Row(
              children: [
                SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
                SizedBox(width: 12),
                Expanded(child: Text('Checking again by itself; this page opens as soon as the library answers.')),
              ],
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
