import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../contracts/library_models.g.dart' as law;
import '../design/components.dart';
import '../domain/law_status.dart';
import '../state/library_state.dart';
import 'statute_text.dart' show markedSpans;

/// How many rows before the end of what is loaded the next page is requested. With 40-row pages and a warm server
/// index (~5 ms a page) the next rows are in memory well before the reader's finger gets there.
const _prefetchAhead = 15;

/// Every served section of a law, in printed order, as a lazy sliver: each row is its name (a button to the full
/// text), the first two lines of its own words and a "Read more" to the same page. Pages are fetched ahead of the
/// scroll, never all at once.
class SectionList extends ConsumerWidget {
  final String instrument;
  const SectionList({super.key, required this.instrument});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(sectionsProvider(instrument));
    final mode = ref.watch(readingModeProvider);
    return state.when(
      loading: () => const SliverToBoxAdapter(child: LoadingStructure()),
      error: (e, s) => SliverToBoxAdapter(
        child: LoadFailure(e, onRetry: () => ref.invalidate(sectionsProvider(instrument))),
      ),
      data: (page) {
        if (page.items.isEmpty) {
          return const SliverToBoxAdapter(
            child: Notice('No section of this law is served for the chosen date and territory.'),
          );
        }
        final count = page.items.length + (page.next != null || page.moreError != null ? 1 : 0);
        return SliverList.builder(
          itemCount: count,
          itemBuilder: (context, i) {
            if (i >= page.items.length) {
              return _Tail(page: page, onRetry: () => ref.read(sectionsProvider(instrument).notifier).more());
            }
            if (page.next != null && i >= page.items.length - _prefetchAhead && !page.loadingMore &&
                page.moreError == null) {
              // after this frame: never mutate provider state during build
              WidgetsBinding.instance.addPostFrameCallback(
                  (_) => ref.read(sectionsProvider(instrument).notifier).more());
            }
            final item = page.items[i];
            final previous = i == 0 ? null : page.items[i - 1];
            final newGroup = mode.showGroups && item.group != null && item.group != previous?.group;
            return Column(
              key: ValueKey('section/${item.id}'),
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (newGroup)
                  Padding(
                    padding: const EdgeInsets.only(top: 20, bottom: 10),
                    child: Eyebrow(item.group!),
                  ),
                Padding(
                  padding: EdgeInsets.only(bottom: mode.compact ? 8 : 12),
                  child: SectionCard(item: item),
                ),
              ],
            );
          },
        );
      },
    );
  }
}

class _Tail extends StatelessWidget {
  final Paged<law.SectionItem> page;
  final VoidCallback onRetry;
  const _Tail({required this.page, required this.onRetry});
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 20),
        child: Center(
          child: page.moreError != null
              ? OutlinedButton.icon(
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Load the next sections'),
                )
              : const SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
        ),
      );
}

class SectionCard extends ConsumerWidget {
  final law.SectionItem item;
  const SectionCard({super.key, required this.item});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mode = ref.watch(readingModeProvider);
    final scheme = Theme.of(context).colorScheme;
    void open() => context.push('/provision/${item.id}');
    final preamble = item.kind == 'preamble';
    final name = item.heading?.trim().isNotEmpty == true
        ? item.heading!.trim()
        : preamble
            ? 'Preamble'
            : 'Untitled ${item.kind}';
    final label = preamble ? '' : printedLabel(item.kind, item.label);
    return Container(
      padding: EdgeInsets.fromLTRB(16, mode.compact ? 6 : 10, 12, mode.compact ? 0 : 2),
      decoration: BoxDecoration(
        color: scheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: scheme.outline),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // the name is the button to the full text
          InkWell(
            onTap: open,
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (label.isNotEmpty)
                    SizedBox(
                      width: 52,
                      child: Text(
                        '\u2068$label\u2069',
                        style: TextStyle(
                          fontFamily: 'Spectral',
                          fontSize: mode.compact ? 17 : 20,
                          color: scheme.secondary,
                          height: 1.25,
                        ),
                      ),
                    ),
                  Expanded(
                    child: Text(
                      name,
                      style: TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: mode.compact ? 15 : 16.5,
                        height: 1.35,
                        color: scheme.primary,
                        decoration: TextDecoration.underline,
                        decorationColor: scheme.primary.withValues(alpha: .35),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          if (item.preview.isNotEmpty) ...[
            const SizedBox(height: 4),
            Builder(builder: (context) {
              final style = TextStyle(
                fontFamily: 'Spectral',
                fontSize: mode.compact ? 15 : 16,
                height: 1.5,
                color: Theme.of(context).colorScheme.onSurface,
              );
              return Text.rich(
                TextSpan(children: markedSpans(item.preview, style)),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: style,
              );
            }),
          ],
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 4,
            children: [
              TextButton(
                onPressed: open,
                // 48 dp tall target, no extra side padding: the card stays compact without a smaller tap area
                style: TextButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 0),
                  minimumSize: const Size(64, 48),
                ),
                child: const Text('Read more'),
              ),
              if (item.survives_repeal)
                const _Tag('Still law: excepted from a repeal'),
              if (mode.showPages && item.first_page != null) _Tag('PDF p. ${item.first_page}'),
              if (mode.showCitation && item.citation != null)
                mode.copyCitation
                    ? TextButton.icon(
                        onPressed: () async {
                          await Clipboard.setData(ClipboardData(text: item.citation!));
                          if (context.mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(content: Text('Copied: ${item.citation}')),
                            );
                          }
                        },
                        icon: const Icon(Icons.copy, size: 16),
                        label: Text(item.citation!, overflow: TextOverflow.ellipsis),
                      )
                    : _Tag(item.citation!),
            ],
          ),
        ],
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  final String text;
  const _Tag(this.text);
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Text(text, style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.secondary)),
      );
}
