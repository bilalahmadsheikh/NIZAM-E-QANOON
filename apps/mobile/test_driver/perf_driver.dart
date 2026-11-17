// Writes each watchPerformance report (frame build/raster percentiles, missed frames) to build/<key>.json.
import 'dart:convert';
import 'dart:io';
import 'package:integration_test/integration_test_driver.dart';

Future<void> main() => integrationDriver(
      responseDataCallback: (data) async {
        if (data == null) return;
        Directory('build').createSync(recursive: true);
        for (final entry in data.entries) {
          File('build/${entry.key}.json').writeAsStringSync(const JsonEncoder.withIndent('  ').convert(entry.value));
          stdout.writeln('${entry.key}: ${jsonEncode(entry.value)}');
        }
      },
    );
