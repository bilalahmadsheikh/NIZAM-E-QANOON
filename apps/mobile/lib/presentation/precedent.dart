import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../contracts/library_models.g.dart';
import '../design/components.dart';
import '../state/library_state.dart';

/// Precedent in the app (D-184): judgments as the courts published them, beside the law they read.
///
/// Network-required content (docs/08): there is no offline substitute, so offline is the quiet waiting state, never
/// an error. Every list says what it was drawn from (`coverage_note`), because a judgment not held must never read as
/// "no precedent". Citations, dates and party lines are the server's, rendered from records (INV-1); withheld names
/// arrive already replaced (D-131). Ordering is the reader's choice: newest first, or those construing the law first.

/// How a judgment cites the law it is listed for, in a reader's words.
String roleWording(String role) => const {
      'interpreted': 'Interprets it',
      'challenged': 'Challenges it',
      'quoted': 'Quotes it',
      'cited': 'Cites it',
      'charge': 'Charge under it',
    }[role] ??
    _human(role);

String _human(String code) => code.isEmpty ? code : (code[0].toUpperCase() + code.substring(1)).replaceAll('_', ' ');

/// The decision date as the record holds it: a date, or why there is none (D-124) -- never a guessed day.
String decidedWording({String? decidedOn, required bool undated, String? noLaterThan}) {
  if (decidedOn != null) return 'Decided $decidedOn';
  if (undated && noLaterThan != null) return 'Date of decision not printed · held by $noLaterThan';
  return 'Date of decision not printed';
}

String count(int n) {
  final s = n.toString();
  final out = StringBuffer();
  for (var i = 0; i < s.length; i++) {
    if (i > 0 && (s.length - i) % 3 == 0) out.write(',');
    out.write(s[i]);
  }
  return out.toString();
}

/// One judgment in a list. Its title is the parties as published (names withheld where the law requires), else the
/// case as printed; the citation and date below it are the record's.
class JudgmentTile extends StatelessWidget {
  final JudgmentCard item;
  final bool showRoles;
  const JudgmentTile({super.key, required this.item, this.showRoles = true});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final title = item.parties_display ?? item.case_type ?? 'Judgment';
    final when = decidedWording(
        decidedOn: item.decided_on, undated: item.undated, noLaterThan: item.decided_no_later_than);
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Semantics(
        button: true,
        label: '$title. ${item.citation}. $when',
        excludeSemantics: true,
        child: PaperCard(
          onTap: () => context.push('/judgment/${item.judgment_id}'),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Eyebrow(item.court),
              const SizedBox(height: 10),
              Text('\u2068$title\u2069',
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontFamily: 'Spectral', fontSize: 19, height: 1.3)),
              const SizedBox(height: 8),
              Text('\u2068${item.citation}\u2069', style: TextStyle(fontSize: 13, height: 1.4, color: scheme.secondary)),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  _Tag(when, icon: Icons.event_outlined),
                  if (item.disposition case final d?) _Tag(_human(d)),
                  if (item.reported == true) const _Tag('Reported'),
                  if (showRoles)
                    for (final r in item.roles) _Tag(roleWording(r), strong: r != 'charge' && r != 'cited'),
                  for (final t in item.treatments) _Tag(_human(t), strong: true),
                  if (item.names_withheld) const _Tag('Names withheld', icon: Icons.visibility_off_outlined),
                ],
              ),
              if (item.treatments_awaiting_review > 0) ...[
                const SizedBox(height: 10),
                Text(
                  item.treatments_awaiting_review == 1
                      ? 'One reading of how it treats this case awaits a lawyer’s review and is not shown.'
                      : '${item.treatments_awaiting_review} readings of how it treats this case await a lawyer’s review and are not shown.',
                  style: const TextStyle(fontSize: 12, height: 1.4),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  final String text;
  final IconData? icon;
  final bool strong;
  const _Tag(this.text, {this.icon, this.strong = false});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: strong ? solidTint(context, .12) : null,
        border: Border.all(color: scheme.outline),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        if (icon != null) ...[Icon(icon, size: 14), const SizedBox(width: 6)],
        Text(text, style: TextStyle(fontSize: 12, fontWeight: strong ? FontWeight.w700 : FontWeight.w500)),
      ]),
    );
  }
}

/// Newest first, or those that construe the law first.
class OrderSwitch extends StatelessWidget {
  final String order;
  final ValueChanged<String> onChanged;
  const OrderSwitch({super.key, required this.order, required this.onChanged});
  @override
  Widget build(BuildContext context) => SegmentedButton<String>(
        segments: const [
          ButtonSegment(value: 'recent', icon: Icon(Icons.schedule), label: Text('Newest')),
          ButtonSegment(value: 'relevant', icon: Icon(Icons.balance), label: Text('Most relevant')),
        ],
        selected: {order},
        onSelectionChanged: (s) => onChanged(s.first),
      );
}

/// What lawyer-verified reviews say of a section's validity, and how many machine readings await review (D-161).
class _JudicialStatusNote extends StatelessWidget {
  final JudicialStatus status;
  const _JudicialStatusNote({required this.status});
  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final v in status.verified) ...[
            Notice(
              'A court has held this ${v.extent == 'whole' ? 'provision' : 'provision in part'} invalid'
              '${v.effective_on == null ? '' : ' from ${v.effective_on}'} (verified by a lawyer)'
              '${v.extent_note == null ? '' : ': ${v.extent_note}'}.',
              icon: Icons.gavel_outlined,
            ),
            const SizedBox(height: 12),
          ],
          if (status.candidates_awaiting_review > 0) ...[
            Notice(
              '${status.candidates_awaiting_review == 1 ? 'One reading' : '${status.candidates_awaiting_review} readings'} '
              'of whether a court struck this down ${status.candidates_awaiting_review == 1 ? 'awaits' : 'await'} a lawyer’s review. '
              'None is stated until it is verified.',
              icon: Icons.hourglass_empty,
            ),
            const SizedBox(height: 12),
          ],
        ],
      );
}

/// "Decisions citing this section" (or this law): the five newest -- or most relevant -- with the number held and a
/// way to all of them. Fetched beside the text and never in its way: while it loads, a quiet placeholder; offline,
/// one line saying the decisions need the connection while the law above is unaffected.
class CitingSection extends ConsumerStatefulWidget {
  final String scope;   // 'provision' | 'instrument'
  final String id;
  final String noun;    // 'section', 'Article', 'Part', 'law'
  final bool compact;   // the law page: the two newest and a way to all
  const CitingSection({super.key, required this.scope, required this.id, required this.noun, this.compact = false});
  @override
  ConsumerState<CitingSection> createState() => _CitingSectionState();
}

class _CitingSectionState extends ConsumerState<CitingSection> {
  String order = 'recent';
  @override
  Widget build(BuildContext context) {
    final q = (scope: widget.scope, id: widget.id, order: order);
    final page = ref.watch(citingPreviewProvider(q));
    final noun = widget.noun;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Eyebrow('Decisions citing this $noun'),
        const SizedBox(height: 12),
        page.when(
          loading: () => const _Placeholder(),
          error: (e, s) => e is LibraryFailure && e.offline
              ? const Notice('Decisions need the library connection. The law above is unaffected.',
                  icon: Icons.cloud_off_outlined)
              : Row(children: [
                  const Expanded(child: Text('The decisions could not be loaded.', style: TextStyle(fontSize: 13))),
                  TextButton(onPressed: () => ref.invalidate(citingPreviewProvider(q)), child: const Text('Try again')),
                ]),
          data: (p) {
            if (p.total == 0) {
              return Notice('No judgment held cites this $noun. ${p.coverage_note}', icon: Icons.search_off);
            }
            final shown = widget.compact ? p.items.take(2).toList() : p.items;
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${count(p.total)} ${p.total == 1 ? 'decision' : 'decisions'} held cite this $noun',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                if (!widget.compact) ...[
                  OrderSwitch(order: order, onChanged: (o) => setState(() => order = o)),
                  const SizedBox(height: 16),
                ],
                if (p.judicial_status case final s?) _JudicialStatusNote(status: s),
                for (final item in shown) JudgmentTile(item: item),
                if (p.total > shown.length)
                  OutlinedButton.icon(
                    onPressed: () => context.push(
                        '/citing/${widget.scope}/${widget.id}?order=$order&noun=${Uri.encodeQueryComponent(noun)}'),
                    icon: const Icon(Icons.format_list_bulleted),
                    label: Text('See all ${count(p.total)} decisions'),
                  ),
                const SizedBox(height: 12),
                Text(p.coverage_note, style: TextStyle(fontSize: 12, height: 1.45, color: Theme.of(context).colorScheme.secondary)),
              ],
            );
          },
        ),
      ],
    );
  }
}

class _Placeholder extends StatelessWidget {
  const _Placeholder();
  @override
  Widget build(BuildContext context) => Semantics(
        label: 'Loading decisions',
        liveRegion: true,
        child: Container(
          height: 120,
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.outline.withValues(alpha: .25),
            borderRadius: BorderRadius.circular(20),
          ),
        ),
      );
}

/// Every decision citing a section or a law, a page at a time, in the chosen order.
class CitingScreen extends ConsumerStatefulWidget {
  final String scope;
  final String id;
  final String order;
  final String noun;
  const CitingScreen({super.key, required this.scope, required this.id, this.order = 'recent', this.noun = 'law'});
  @override
  ConsumerState<CitingScreen> createState() => _CitingScreenState();
}

class _CitingScreenState extends ConsumerState<CitingScreen> {
  late String order = widget.order == 'relevant' ? 'relevant' : 'recent';
  @override
  Widget build(BuildContext context) {
    final q = (scope: widget.scope, id: widget.id, order: order);
    final list = ref.watch(citingProvider(q));
    final head = ref.watch(citingHeadProvider(q));
    return LibraryScaffold(
      title: 'Decisions',
      body: ReadingWidth(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 24, 24, 120),
          children: [
            Eyebrow('Decisions citing this ${widget.noun}'),
            const SizedBox(height: 12),
            Text(head == null ? 'Decisions' : '${count(head.total)} decisions held',
                style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 16),
            OrderSwitch(order: order, onChanged: (o) => setState(() => order = o)),
            const SizedBox(height: 20),
            ...list.when(
              loading: () => [const LoadingStructure()],
              error: (e, s) => [LoadFailure(e, onRetry: () => ref.invalidate(citingProvider(q)))],
              data: (page) => [
                for (final item in page.items) JudgmentTile(item: item),
                MoreButton(page,
                    load: () => ref.read(citingProvider(q).notifier).more(),
                    refresh: () => ref.read(citingProvider(q).notifier).reload()),
              ],
            ),
            if (head != null) ...[
              const SizedBox(height: 12),
              Text(head.coverage_note, style: const TextStyle(fontSize: 12, height: 1.45)),
            ],
          ],
        ),
      ),
    );
  }
}

/// The Judgments tab: search the judgments, or open a court and read its decisions newest first. Each court says
/// how many of its judgments are held and the years they span; a court with none held says so.
class PrecedentScreen extends ConsumerStatefulWidget {
  const PrecedentScreen({super.key});
  @override
  ConsumerState<PrecedentScreen> createState() => _PrecedentScreenState();
}

class _PrecedentScreenState extends ConsumerState<PrecedentScreen> {
  final controller = TextEditingController();
  String query = '';

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final courts = ref.watch(courtsProvider);
    return LibraryScaffold(
      title: 'Judgments',
      selected: 2,
      body: ReadingWidth(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 24, 24, 120),
          children: [
            const Eyebrow('Judgments of Pakistan’s courts'),
            const SizedBox(height: 14),
            Text('What the courts decided.', style: Theme.of(context).textTheme.displaySmall),
            const SizedBox(height: 12),
            const Text('Read a judgment whole, and the law it cites. Or open a law and see the decisions citing it.',
                style: TextStyle(fontSize: 15, height: 1.5)),
            const SizedBox(height: 24),
            TextField(
              controller: controller,
              textInputAction: TextInputAction.search,
              decoration: InputDecoration(
                labelText: 'Describe a dispute or a point of law',
                hintText: 'bail in a murder case, khula, eviction of a tenant…',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: query.isEmpty
                    ? null
                    : IconButton(
                        tooltip: 'Clear',
                        icon: const Icon(Icons.close),
                        onPressed: () => setState(() {
                          controller.clear();
                          query = '';
                        }),
                      ),
              ),
              onSubmitted: (v) => setState(() => query = v.trim()),
            ),
            const SizedBox(height: 20),
            if (query.length >= 2) _SearchResults(query: query) else ...[
              Text('Courts', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 12),
              ...courts.when(
                loading: () => [const LoadingStructure()],
                error: (e, s) => [LoadFailure(e, onRetry: () => ref.invalidate(courtsProvider))],
                data: (page) => [
                  for (final c in page.items) _CourtRow(court: c),
                  const SizedBox(height: 8),
                  Text(page.coverage_note, style: const TextStyle(fontSize: 12, height: 1.45)),
                ],
              ),
            ],
            const SizedBox(height: 24),
            const Notice('Judgments are legal information, not advice. Read the judgment and its official source before '
                'relying on it, and ask an advocate about your own matter.'),
          ],
        ),
      ),
    );
  }
}

class _CourtRow extends StatelessWidget {
  final CourtCoverage court;
  const _CourtRow({required this.court});
  @override
  Widget build(BuildContext context) {
    final held = court.judgments > 0;
    final span = court.first_decided == null || court.last_decided == null
        ? ''
        : ' · ${court.first_decided!.substring(0, 4)}–${court.last_decided!.substring(0, 4)}';
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: PaperCard(
        onTap: held ? () => context.push('/court/${court.code}') : null,
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(court.name, style: const TextStyle(fontFamily: 'Spectral', fontSize: 19, height: 1.3)),
                  const SizedBox(height: 6),
                  Text(held ? '${count(court.judgments)} judgments held$span' : 'None of its judgments is held yet',
                      style: const TextStyle(fontSize: 13)),
                ],
              ),
            ),
            if (held) const Icon(Icons.chevron_right),
          ],
        ),
      ),
    );
  }
}

class _SearchResults extends ConsumerWidget {
  final String query;
  const _SearchResults({required this.query});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final key = (q: query, court: '');
    return ref.watch(precedentSearchProvider(key)).when(
          loading: () => const LoadingStructure(),
          error: (e, s) => LoadFailure(e, onRetry: () => ref.invalidate(precedentSearchProvider(key))),
          data: (page) => Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // discovery, not an answer: the results passed no gate (INV-2), and the page says so
              Notice(page.note, icon: Icons.travel_explore),
              if (page.mode == 'lexical_only') ...[
                const SizedBox(height: 12),
                const Notice('Searched by words only: meaning-based search is unavailable on this server.',
                    icon: Icons.info_outline),
              ],
              if (page.coverage_gap case final gap?) ...[
                const SizedBox(height: 12),
                Notice(gap, icon: Icons.search_off),
              ],
              const SizedBox(height: 16),
              if (page.hits.isEmpty)
                Notice('No judgment held was found for this. ${page.coverage_note}', icon: Icons.search_off)
              else
                for (final h in page.hits) _HitTile(hit: h),
              const SizedBox(height: 8),
              Text(page.coverage_note, style: const TextStyle(fontSize: 12, height: 1.45)),
            ],
          ),
        );
  }
}

class _HitTile extends StatelessWidget {
  final PrecedentHitOut hit;
  const _HitTile({required this.hit});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final when = decidedWording(decidedOn: hit.decided_on, undated: hit.undated, noLaterThan: hit.decided_no_later_than);
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: PaperCard(
        onTap: () => context.push('/judgment/${hit.judgment_id}?paragraph=${hit.paragraph_id}'),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Eyebrow(hit.court),
            const SizedBox(height: 10),
            Text('\u2068${hit.parties_display ?? hit.case_type ?? 'Judgment'}\u2069',
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontFamily: 'Spectral', fontSize: 19, height: 1.3)),
            const SizedBox(height: 8),
            Text('\u2068${hit.citation}\u2069', style: TextStyle(fontSize: 13, height: 1.4, color: scheme.secondary)),
            const SizedBox(height: 12),
            // the passage that matched, as the court wrote it
            Container(
              padding: const EdgeInsets.only(left: 14),
              decoration: BoxDecoration(border: Border(left: BorderSide(color: scheme.secondary, width: 2))),
              child: Text(hit.text,
                  maxLines: 6,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontFamily: 'Spectral', fontSize: 16, height: 1.5)),
            ),
            const SizedBox(height: 10),
            Wrap(spacing: 8, runSpacing: 8, children: [
              _Tag(when, icon: Icons.event_outlined),
              if (hit.names_withheld) const _Tag('Names withheld', icon: Icons.visibility_off_outlined),
            ]),
          ],
        ),
      ),
    );
  }
}

/// A court's judgments, newest first, a page at a time.
class CourtScreen extends ConsumerWidget {
  final String code;
  const CourtScreen({super.key, required this.code});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final list = ref.watch(courtJudgmentsProvider(code));
    final court = ref.watch(courtsProvider).valueOrNull?.items.where((c) => c.code == code).firstOrNull;
    return LibraryScaffold(
      title: 'Court',
      selected: 2,
      body: ReadingWidth(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 24, 24, 120),
          children: [
            const Eyebrow('Newest first'),
            const SizedBox(height: 12),
            Text(court?.name ?? code, style: Theme.of(context).textTheme.headlineMedium),
            if (court != null) ...[
              const SizedBox(height: 8),
              Text('${count(court.judgments)} judgments held', style: const TextStyle(fontSize: 14)),
            ],
            const SizedBox(height: 20),
            ...list.when(
              loading: () => [const LoadingStructure()],
              error: (e, s) => [LoadFailure(e, onRetry: () => ref.invalidate(courtJudgmentsProvider(code)))],
              data: (page) => [
                for (final item in page.items) JudgmentTile(item: item, showRoles: false),
                MoreButton(page,
                    load: () => ref.read(courtJudgmentsProvider(code).notifier).more(),
                    refresh: () => ref.read(courtJudgmentsProvider(code).notifier).reload()),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
