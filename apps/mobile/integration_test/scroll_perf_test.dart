// Device benchmark (client skill: "no frame > 16.7 ms"). Runs the real app against the API named by
// --dart-define=API_BASE_URL, opens the Pakistan Penal Code's section list and flings through it while pages load
// ahead of the scroll, then opens a section in the reader and flings through that. Frame build and raster times are
// written by test_driver/perf_driver.dart to build/<name>.timeline_summary.json.
//
//   flutter drive --profile --driver=test_driver/perf_driver.dart \
//     --target=integration_test/scroll_perf_test.dart --dart-define=API_BASE_URL=http://<host>:8080
import 'dart:ui' show FrameTiming;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:nizam_app/main.dart';

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('section list and reader scroll within the frame budget', (tester) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    await tester.pumpWidget(UncontrolledProviderScope(container: container, child: const NizamApp()));
    await tester.pumpAndSettle();

    // Open the PPC from the popular shelf, as a reader would
    final ppc = find.text('PPC');
    await tester.scrollUntilVisible(find.text('Most consulted laws'), 300, scrollable: _vertical());
    await _waitFor(tester, ppc);
    await tester.ensureVisible(ppc);
    await tester.pumpAndSettle();
    await tester.tap(ppc);
    await _waitFor(tester, find.textContaining('sections served on'));
    await _settle(tester);

    final list = _vertical();
    await _frames(binding, () async {
      for (var i = 0; i < 12; i++) {
        await tester.fling(list, const Offset(0, -1400), 3000);
        await tester.pump(const Duration(milliseconds: 600));
      }
      // back up through what is already loaded
      for (var i = 0; i < 4; i++) {
        await tester.fling(list, const Offset(0, 1400), 3000);
        await tester.pump(const Duration(milliseconds: 600));
      }
    }, 'sections_scroll');

    // Open the first visible section and read down through it
    final names = find.byWidgetPredicate((w) => w is InkWell && w.onTap != null && w.child is Padding);
    await tester.tap(names.first);
    await _settle(tester);
    final reader = _vertical();
    await _frames(binding, () async {
      for (var i = 0; i < 6; i++) {
        await tester.fling(reader, const Offset(0, -1200), 2500);
        await tester.pump(const Duration(milliseconds: 600));
      }
    }, 'reader_scroll');
  });
}

/// Network reads finish on their own time; pump until the frame tree stops changing or 10 s pass.
Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 50; i++) {
    await tester.pump(const Duration(milliseconds: 200));
    if (!tester.binding.hasScheduledFrame) return;
  }
}

/// The page's vertical scroll view (the scope band above it scrolls sideways).
Finder _vertical() => find.byWidgetPredicate((w) => w is Scrollable && w.axisDirection == AxisDirection.down).first;

/// Pump until [finder] matches (live network), failing after 15 s.
Future<void> _waitFor(WidgetTester tester, Finder finder) async {
  for (var i = 0; i < 75; i++) {
    if (finder.evaluate().isNotEmpty) return;
    await tester.pump(const Duration(milliseconds: 200));
  }
  fail('timed out waiting for $finder');
}

/// Frame build and raster times from the engine's FrameTiming reports (what watchPerformance summarises, without its
/// VM-service garbage-collection count, which cannot connect on an emulator).
Future<void> _frames(IntegrationTestWidgetsFlutterBinding binding, Future<void> Function() action, String key) async {
  await Future<void>.delayed(const Duration(seconds: 2)); // flush earlier timings
  final timings = <FrameTiming>[];
  binding.addTimingsCallback(timings.addAll);
  await action();
  await Future<void>.delayed(const Duration(seconds: 2)); // the engine batches reports about once a second
  binding.removeTimingsCallback(timings.addAll);
  double ms(Duration d) => d.inMicroseconds / 1000;
  Map<String, num> stats(List<double> v) {
    v.sort();
    double at(double q) => v.isEmpty ? 0 : v[((v.length - 1) * q).round()];
    return {'p50': at(.5), 'p90': at(.9), 'p99': at(.99), 'max': v.isEmpty ? 0 : v.last};
  }
  final build = timings.map((t) => ms(t.buildDuration)).toList();
  final raster = timings.map((t) => ms(t.rasterDuration)).toList();
  final total = timings.map((t) => ms(t.totalSpan)).toList();
  binding.reportData ??= <String, dynamic>{};
  binding.reportData![key] = {
    'frames': timings.length,
    'build_ms': stats(build),
    'raster_ms': stats(raster),
    'over_16_7ms_build': build.where((v) => v > 16.7).length,
    'over_16_7ms_raster': raster.where((v) => v > 16.7).length,
    'total_span_ms': stats(total),
  };
}