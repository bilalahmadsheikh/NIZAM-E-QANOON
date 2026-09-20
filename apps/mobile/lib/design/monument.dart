import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/physics.dart';
import 'theme.dart';

/// Original vector artwork: stylised dimensional landmarks, not survey models.
/// One settling animation, no perpetual scene loop or WebView/3D engine.
class MonumentScene extends StatefulWidget {
  final bool mausoleum;
  const MonumentScene({super.key, this.mausoleum = false});
  @override
  State<MonumentScene> createState() => _MonumentSceneState();
}

class _MonumentSceneState extends State<MonumentScene>
    with SingleTickerProviderStateMixin {
  late final AnimationController _motion = AnimationController.unbounded(
    vsync: this,
  );
  bool _started = false;
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context)) {
      _motion.stop();
      _motion.value = 1;
    } else if (!_started) {
      _motion.animateWith(
        SpringSimulation(
          const SpringDescription(mass: 1, stiffness: 90, damping: 19),
          0,
          1,
          0,
        ),
      );
    }
    _started = true;
  }

  @override
  void dispose() {
    _motion.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Semantics(
    label:
        widget.mausoleum
            ? 'Stylised Mazar-e-Quaid illustration'
            : 'Stylised Minar-e-Pakistan illustration',
    image: true,
    child: RepaintBoundary(
      child: AnimatedBuilder(
        animation: _motion,
        builder:
            (context, child) => Transform(
              alignment: Alignment.center,
              transform:
                  Matrix4.identity()
                    ..setEntry(3, 2, 0.001)
                    ..rotateY((1 - _motion.value) * 0.25)
                    ..translate(0.0, 18 * (1 - _motion.value)),
              child: child,
            ),
        child: CustomPaint(
          painter: _LandmarkPainter(widget.mausoleum),
          size: const Size(300, 280),
        ),
      ),
    ),
  );
}

class _LandmarkPainter extends CustomPainter {
  final bool mausoleum;
  _LandmarkPainter(this.mausoleum);
  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 300, size.height / 280);
    final glow =
        Paint()
          ..shader = RadialGradient(
            colors: [
              Stamp.brass.withValues(alpha: .23),
              Stamp.pine.withValues(alpha: 0),
            ],
          ).createShader(const Rect.fromLTWH(0, 0, 300, 280));
    canvas.drawOval(const Rect.fromLTWH(0, 0, 300, 280), glow);
    final orbit =
        Paint()
          ..color = Stamp.parchment.withValues(alpha: .13)
          ..style = PaintingStyle.stroke
          ..strokeWidth = .8;
    canvas.drawOval(const Rect.fromLTWH(25, 90, 250, 150), orbit);
    canvas.drawCircle(const Offset(146, 132), 109, orbit);
    canvas.drawOval(
      const Rect.fromLTWH(36, 228, 238, 28),
      Paint()..color = Colors.black.withValues(alpha: .15),
    );
    void polygon(List<Offset> pts, Color color) {
      final path = Path()..addPolygon(pts, true);
      canvas.drawPath(path, Paint()..color = color);
    }

    void plinth(double x, double y, double w, double h, double depth) {
      polygon([
        Offset(x, y),
        Offset(x + w, y),
        Offset(x + w + depth, y - depth * .55),
        Offset(x + depth, y - depth * .55),
      ], const Color(0xFFD8C7A5));
      polygon([
        Offset(x, y),
        Offset(x + w, y),
        Offset(x + w, y + h),
        Offset(x, y + h),
      ], const Color(0xFFAE9A76));
      polygon([
        Offset(x + w, y),
        Offset(x + w + depth, y - depth * .55),
        Offset(x + w + depth, y + h - depth * .55),
        Offset(x + w, y + h),
      ], const Color(0xFF78694F));
    }

    plinth(42, 234, 176, 10, 32);
    plinth(56, 222, 149, 12, 32);
    plinth(70, 210, 123, 12, 30);
    if (mausoleum) {
      plinth(85, 139, 110, 71, 30);
      canvas.drawRect(
        const Rect.fromLTWH(85, 130, 110, 78),
        Paint()..color = const Color(0xFFF3EAD8),
      );
      polygon([
        const Offset(195, 130),
        const Offset(225, 114),
        const Offset(225, 194),
        const Offset(195, 208),
      ], const Color(0xFFCAB998));
      polygon([
        const Offset(85, 130),
        const Offset(115, 114),
        const Offset(225, 114),
        const Offset(195, 130),
      ], const Color(0xFFFFF7E7));
      final arch =
          Path()
            ..moveTo(122, 208)
            ..lineTo(122, 166)
            ..quadraticBezierTo(140, 139, 158, 166)
            ..lineTo(158, 208)
            ..close();
      canvas.drawPath(arch, Paint()..color = Stamp.pine);
      final dome =
          Path()
            ..moveTo(110, 122)
            ..cubicTo(107, 92, 125, 77, 150, 72)
            ..cubicTo(175, 77, 193, 92, 190, 122)
            ..close();
      canvas.drawPath(
        dome,
        Paint()
          ..shader = const LinearGradient(
            colors: [Color(0xFFFFF7E7), Color(0xFFCAB998)],
          ).createShader(const Rect.fromLTWH(110, 72, 80, 50)),
      );
      canvas.drawLine(
        const Offset(150, 58),
        const Offset(150, 74),
        Paint()
          ..color = Stamp.brass
          ..strokeWidth = 2,
      );
    } else {
      final tower =
          Path()
            ..moveTo(109, 210)
            ..lineTo(126, 87)
            ..quadraticBezierTo(139, 71, 152, 87)
            ..lineTo(172, 210)
            ..close();
      canvas.drawPath(
        tower,
        Paint()
          ..shader = const LinearGradient(
            colors: [Color(0xFFF7EDD4), Color(0xFFAE9770), Color(0xFFE9DAB9)],
            stops: [0, .62, 1],
          ).createShader(const Rect.fromLTWH(109, 80, 63, 130)),
      );
      for (var i = 0; i < 8; i++) {
        final y = 103.0 + i * 13;
        final half = 14.0 + i * 1.6;
        canvas.drawOval(
          Rect.fromCenter(
            center: Offset(140, y),
            width: half * 2 + 6,
            height: 6,
          ),
          Paint()..color = const Color(0xFFEDE0C4),
        );
        canvas.drawArc(
          Rect.fromCenter(
            center: Offset(140, y + 1),
            width: half * 2 + 6,
            height: 6,
          ),
          0,
          math.pi,
          false,
          Paint()
            ..color = const Color(0xFF8C7857)
            ..strokeWidth = 1
            ..style = PaintingStyle.stroke,
        );
      }
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          const Rect.fromLTWH(133, 66, 14, 25),
          const Radius.circular(6),
        ),
        Paint()..color = const Color(0xFFF2E7CF),
      );
      canvas.drawLine(
        const Offset(140, 43),
        const Offset(140, 68),
        Paint()
          ..color = Stamp.brass
          ..strokeWidth = 2,
      );
      canvas.drawCircle(const Offset(140, 42), 3, Paint()..color = Stamp.brass);
    }
    for (final p in [
      const Offset(48, 74),
      const Offset(254, 122),
      const Offset(230, 48),
    ]) {
      canvas.drawCircle(
        p,
        2,
        Paint()..color = Stamp.brass.withValues(alpha: .6),
      );
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(_LandmarkPainter old) => old.mausoleum != mausoleum;
}
