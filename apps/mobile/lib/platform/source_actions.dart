import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

/// Platform effects stay outside widgets (Document 08, client boundaries).
class SourceActions {
  Future<bool> open(String address, {int? page}) async {
    final uri = Uri.tryParse(address);
    if (uri == null ||
        !['https', 'http'].contains(uri.scheme) ||
        uri.host.isEmpty) {
      return false;
    }
    try {
      return await launchUrl(
        page == null ? uri : uri.replace(fragment: 'page=$page'),
        mode: LaunchMode.externalApplication,
      );
    } on PlatformException {
      return false;
    }
  }

  Future<bool> copy(String address) async {
    try {
      await Clipboard.setData(ClipboardData(text: address));
      return true;
    } on PlatformException {
      return false;
    }
  }
}
