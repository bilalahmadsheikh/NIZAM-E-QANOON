import 'dart:math' as math;
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import '../domain/heritage.dart';

/// Embroidery (D-082, D-084): crafts stitched -- patches set into the layout, hems, rules, and the seam between pages.
/// under-shadow, its colour and a highlight, satin fills as parallel threads, outlines as running or back stitch, mirrors
/// ringed with buttonhole stitch -- and the page's cards, buttons and text lie on top of it.
///
/// Cost: one tile is stitched once into an image (cached per stitchwork, palette and pixel ratio) and the page is
/// filled from it with a repeating image shader: one draw per frame, behind a RepaintBoundary, never animated.

/// The three ways the app embroiders a craft.
enum Stitchwork {
  /// Truck art's phool patti: satin-stitched five-petal flowers on chain-stitched vines.
  phool,

  /// Multani and Hala blue pottery: kashi eight-point stars in back stitch round turquoise rosettes.
  kashi,

  /// Balochi, Sindhi and northern mirror embroidery: a mirror ringed with buttonhole stitch in a satin diamond.
  shisha,
}

/// The stitchwork that embroiders a craft's motif.
Stitchwork stitchworkFor(Motif m) => switch (m) {
      Motif.truckArt || Motif.folkVessels || Motif.football || Motif.chinar => Stitchwork.phool,
      Motif.kashi || Motif.halaTile || Motif.faisalFolds => Stitchwork.kashi,
      _ => Stitchwork.shisha,
    };

/// Thread colours for a stitchwork: a main thread, a second, an accent, and a light thread.
class _Threads {
  final Color a, b, accent, light;
  const _Threads(this.a, this.b, this.accent, this.light);
}

const _threads = {
  Stitchwork.phool: _Threads(Color(0xFFC0533F), Color(0xFFD9A033), Color(0xFF4C7A4A), Color(0xFFF4EEE0)),
  Stitchwork.kashi: _Threads(Color(0xFF1F4E8C), Color(0xFF3FA7B5), Color(0xFF1F4E8C), Color(0xFFF4EEE0)),
  Stitchwork.shisha: _Threads(Color(0xFF9B2335), Color(0xFFE07A3F), Color(0xFF233A6E), Color(0xFFD9DEE3)),
};

// ------------------------------------------------------------------------------------------------ thread drawing

Path _dashed(Path source, double dash, double gap) {
  final out = Path();
  for (final m in source.computeMetrics()) {
    var d = 0.0;
    while (d < m.length) {
      out.addPath(m.extractPath(d, math.min(d + dash, m.length)), Offset.zero);
      d += dash + gap;
    }
  }
  return out;
}

/// A thread along [path]: shadow below, the thread, a highlight along its top -- raised, as stitching is.
void _thread(Canvas c, Path path, Color color, double w) {
  Paint stroke(Color col, double width) => Paint()
    ..style = PaintingStyle.stroke
    ..strokeWidth = width
    ..strokeCap = StrokeCap.round
    ..strokeJoin = StrokeJoin.round
    ..color = col
    ..isAntiAlias = true;
  c.drawPath(path.shift(Offset(w * .3, w * .45)), stroke(const Color(0x33000000), w));
  c.drawPath(path, stroke(color, w));
  c.drawPath(path.shift(Offset(-w * .15, -w * .2)), stroke(Colors.white.withValues(alpha: .32), w * .32));
}

/// Running stitch: short threads with gaps, along [path].
void _running(Canvas c, Path path, Color color, double w) => _thread(c, _dashed(path, w * 3.4, w * 1.9), color, w);

/// Satin stitch: [shape] filled with close parallel threads at [angle].
void _satin(Canvas c, Path shape, Color color, double w, double angle) {
  final b = shape.getBounds();
  final r = b.longestSide;
  c.save();
  c.clipPath(shape);
  final dx = math.cos(angle), dy = math.sin(angle);
  final nx = -dy, ny = dx;
  final lines = Path();
  for (var t = -r; t <= r; t += w * 1.15) {
    final cx = b.center.dx + nx * t, cy = b.center.dy + ny * t;
    lines
      ..moveTo(cx - dx * r, cy - dy * r)
      ..lineTo(cx + dx * r, cy + dy * r);
  }
  _thread(c, lines, color, w);
  c.restore();
  // the satin's edge, as a split stitch outline
  _thread(c, shape, Color.lerp(color, Colors.black, .25)!, w * .55);
}

/// A mirror (shisha): a silvered disc held by a ring of buttonhole stitches.
void _mirror(Canvas c, Offset o, double r, Color thread, double w) {
  c.drawCircle(
    o,
    r,
    Paint()
      ..shader = RadialGradient(colors: const [Color(0xFFF7F8FA), Color(0xFFAEB6BF)], center: const Alignment(-.3, -.4))
          .createShader(Rect.fromCircle(center: o, radius: r)),
  );
  final ring = Path();
  final n = math.max(10, (2 * math.pi * r / (w * 1.6)).floor());
  for (var k = 0; k < n; k++) {
    final a = k * 2 * math.pi / n;
    ring
      ..moveTo(o.dx + math.cos(a) * r * .82, o.dy + math.sin(a) * r * .82)
      ..lineTo(o.dx + math.cos(a) * (r + w * 1.6), o.dy + math.sin(a) * (r + w * 1.6));
  }
  _thread(c, ring, thread, w * .8);
}

Path _star8(Offset o, double r) {
  final p = Path();
  for (var k = 0; k < 16; k++) {
    final a = -math.pi / 2 + k * math.pi / 8;
    final rr = k.isEven ? r : r * .62;
    final pt = Offset(o.dx + math.cos(a) * rr, o.dy + math.sin(a) * rr);
    k == 0 ? p.moveTo(pt.dx, pt.dy) : p.lineTo(pt.dx, pt.dy);
  }
  return p..close();
}

Path _petal(Offset o, double len, double wid, double angle) {
  final tip = Offset(o.dx + math.cos(angle) * len, o.dy + math.sin(angle) * len);
  final nx = -math.sin(angle) * wid, ny = math.cos(angle) * wid;
  final mid = Offset(o.dx + math.cos(angle) * len * .5, o.dy + math.sin(angle) * len * .5);
  return Path()
    ..moveTo(o.dx, o.dy)
    ..quadraticBezierTo(mid.dx + nx, mid.dy + ny, tip.dx, tip.dy)
    ..quadraticBezierTo(mid.dx - nx, mid.dy - ny, o.dx, o.dy)
    ..close();
}

Path _diamond(Offset o, double rx, double ry) => Path()
  ..moveTo(o.dx, o.dy - ry)
  ..lineTo(o.dx + rx, o.dy)
  ..lineTo(o.dx, o.dy + ry)
  ..lineTo(o.dx - rx, o.dy)
  ..close();

// ------------------------------------------------------------------------------------------ embroidered patches

/// An embroidered patch (D-084): a round of cloth stitched onto the page -- woven ground, a merrow edge of dense
/// satin, a ring of tacking stitches, and inside it the craft's design worked in several stitches -- set into a
/// margin of the layout (never behind text) and scrolling with it. Stitched once into an image, cached.
class EmbroideredPatch extends StatelessWidget {
  final Motif motif;
  final double size;
  /// Turned a little, as a patch is sewn on by hand.
  final double angle;
  const EmbroideredPatch(this.motif, {super.key, this.size = 140, this.angle = .1});
  @override
  Widget build(BuildContext context) {
    final dpr = MediaQuery.devicePixelRatioOf(context);
    return IgnorePointer(
      child: ExcludeSemantics(
        child: RepaintBoundary(
          child: Transform.rotate(
            angle: angle,
            child: CustomPaint(size: Size.square(size), painter: _PatchPainter(stitchworkFor(motif), size, dpr)),
          ),
        ),
      ),
    );
  }
}

final _patches = <String, ui.Image>{};

ui.Image _patchImage(Stitchwork s, double size, double dpr) {
  final key = '${s.name}@$size@$dpr';
  return _patches[key] ??= () {
    final rec = ui.PictureRecorder();
    final c = Canvas(rec)..scale(dpr);
    _stitchPatch(c, s, size);
    final px = (size * dpr).ceil();
    return rec.endRecording().toImageSync(px, px);
  }();
}

class _PatchPainter extends CustomPainter {
  final Stitchwork s;
  final double size, dpr;
  _PatchPainter(this.s, this.size, this.dpr);
  @override
  void paint(Canvas canvas, Size box) {
    final img = _patchImage(s, size, dpr);
    canvas.drawImageRect(img, Rect.fromLTWH(0, 0, img.width.toDouble(), img.height.toDouble()),
        Offset.zero & box, Paint()..filterQuality = FilterQuality.medium);
  }

  @override
  bool shouldRepaint(_PatchPainter old) => old.s != s || old.size != size || old.dpr != dpr;
}

/// The cloth each patch is stitched on: a ground colour and the weave's two thread shades.
const _cloth = {
  Stitchwork.phool: (Color(0xFF1E3B33), Color(0xFF26473E)), // a truck's deep green panel
  Stitchwork.kashi: (Color(0xFFF2EEE4), Color(0xFFE4DDCD)), // a white glazed tile ground
  Stitchwork.shisha: (Color(0xFF5E1A2A), Color(0xFF6E2434)), // maroon, as Balochi and Sindhi work is
};

void _stitchPatch(Canvas c, Stitchwork s, double size) {
  final t = _threads[s]!;
  final (ground, weave) = _cloth[s]!;
  final o = Offset(size / 2, size / 2);
  final r = size / 2 - size * .06;            // room for the shadow
  final w = size / 150 * 1.4;                 // the thread's weight at this size
  // the shadow it casts, sewn on
  c.drawCircle(o.translate(size * .012, size * .02), r,
      Paint()..color = const Color(0x40000000)..maskFilter = MaskFilter.blur(BlurStyle.normal, size * .025));
  // woven ground: the cloth, then warp and weft
  c.save();
  c.clipPath(Path()..addOval(Rect.fromCircle(center: o, radius: r)));
  c.drawCircle(o, r, Paint()..color = ground);
  final weft = Paint()..color = weave..strokeWidth = w * .55;
  for (var y = o.dy - r; y < o.dy + r; y += w * 1.6) {
    c.drawLine(Offset(o.dx - r, y), Offset(o.dx + r, y), weft);
  }
  final warp = Paint()..color = weave.withValues(alpha: .5)..strokeWidth = w * .45;
  for (var x = o.dx - r; x < o.dx + r; x += w * 1.6) {
    c.drawLine(Offset(x, o.dy - r), Offset(x, o.dy + r), warp);
  }
  c.restore();
  final inner = r * .8;
  switch (s) {
    case Stitchwork.phool:
      // chain-stitched vine ring with leaves, twelve small flowers on it, an eight-petal phool at the heart
      _running(c, Path()..addOval(Rect.fromCircle(center: o, radius: inner * .72)), t.accent, w);
      for (var k = 0; k < 12; k++) {
        final a = k * math.pi / 6;
        final p = o + Offset(math.cos(a), math.sin(a)) * inner * .72;
        _satin(c, _petal(p, inner * .16, inner * .05, a + math.pi / 2 + .5), t.accent, w * .7, a);
        for (var j = 0; j < 5; j++) {
          final b = a + j * 2 * math.pi / 5;
          _satin(c, _petal(p, inner * .1, inner * .045, b), k.isEven ? t.a : t.b, w * .6, b + math.pi / 2);
        }
        c.drawCircle(p, inner * .025, Paint()..color = t.light);
      }
      for (var k = 0; k < 8; k++) {
        final a = -math.pi / 2 + k * math.pi / 4;
        _satin(c, _petal(o, inner * .46, inner * .16, a), k.isEven ? t.a : t.b, w, a + math.pi / 2);
        _satin(c, _petal(o, inner * .26, inner * .08, a + math.pi / 8), t.b, w * .7, a);
      }
      _mirror(c, o, inner * .1, t.b, w);
      // French knots between the flowers
      for (var k = 0; k < 24; k++) {
        final a = (k + .5) * math.pi / 12;
        _knot(c, o + Offset(math.cos(a), math.sin(a)) * inner * .9, w * 1.1, t.light);
      }
    case Stitchwork.kashi:
      // interlaced strapwork rings, a sixteen-point rosette, the eight-point star, petals and a centre
      _thread(c, Path()..addOval(Rect.fromCircle(center: o, radius: inner * .92)), t.a, w * 1.2);
      _running(c, Path()..addOval(Rect.fromCircle(center: o, radius: inner * .84)), t.b, w);
      final rosette = Path();
      for (var k = 0; k < 32; k++) {
        final a = -math.pi / 2 + k * math.pi / 16;
        final rr = k.isEven ? inner * .78 : inner * .6;
        final p = o + Offset(math.cos(a), math.sin(a)) * rr;
        k == 0 ? rosette.moveTo(p.dx, p.dy) : rosette.lineTo(p.dx, p.dy);
      }
      _thread(c, rosette..close(), t.b, w);
      _satin(c, _star8(o, inner * .58), t.a, w, .4);
      _satin(c, _star8(o, inner * .4), t.light, w * .8, -.4);
      for (var k = 0; k < 8; k++) {
        final a = -math.pi / 2 + k * math.pi / 4;
        _satin(c, _petal(o, inner * .3, inner * .09, a), k.isEven ? t.b : t.a, w * .75, a + math.pi / 2);
        _knot(c, o + Offset(math.cos(a + math.pi / 8), math.sin(a + math.pi / 8)) * inner * .68, w * 1.2, t.b);
      }
      c.drawCircle(o, inner * .07, Paint()..color = t.b);
      c.drawCircle(o, inner * .035, Paint()..color = t.light);
    case Stitchwork.shisha:
      // six mirrors round a large one, each in a satin diamond, a herringbone ring, cross-stitched spokes
      final ring = Path();
      for (var k = 0; k < 36; k++) {
        final a = k * math.pi / 18;
        final p1 = o + Offset(math.cos(a), math.sin(a)) * inner * .86;
        final p2 = o + Offset(math.cos(a + math.pi / 18), math.sin(a + math.pi / 18)) * inner * .74;
        ring..moveTo(p1.dx, p1.dy)..lineTo(p2.dx, p2.dy);
        final p3 = o + Offset(math.cos(a), math.sin(a)) * inner * .74;
        final p4 = o + Offset(math.cos(a + math.pi / 18), math.sin(a + math.pi / 18)) * inner * .86;
        ring..moveTo(p3.dx, p3.dy)..lineTo(p4.dx, p4.dy);
      }
      _thread(c, ring, t.b, w * .8);
      for (var k = 0; k < 6; k++) {
        final a = -math.pi / 2 + k * math.pi / 3;
        final p = o + Offset(math.cos(a), math.sin(a)) * inner * .5;
        _satin(c, _diamond(p, inner * .17, inner * .2), k.isEven ? t.b : t.light, w * .75, a);
        _mirror(c, p, inner * .085, t.accent, w * .8);
        final q = o + Offset(math.cos(a + math.pi / 6), math.sin(a + math.pi / 6)) * inner * .55;
        _thread(c, Path()..moveTo(q.dx - w * 2.4, q.dy - w * 2.4)..lineTo(q.dx + w * 2.4, q.dy + w * 2.4), t.b, w * .8);
        _thread(c, Path()..moveTo(q.dx + w * 2.4, q.dy - w * 2.4)..lineTo(q.dx - w * 2.4, q.dy + w * 2.4), t.b, w * .8);
      }
      _satin(c, _diamond(o, inner * .3, inner * .3), t.a, w, .78);
      _mirror(c, o, inner * .15, t.light, w);
  }
  // tacking stitches inside the edge, then the merrow edge: dense satin over the rim, with its highlight
  _running(c, Path()..addOval(Rect.fromCircle(center: o, radius: r * .9)), t.light.withValues(alpha: .8), w * .7);
  final edge = Path();
  final n = (2 * math.pi * r / (w * .95)).floor();
  for (var k = 0; k < n; k++) {
    final a = k * 2 * math.pi / n;
    final dir = Offset(math.cos(a), math.sin(a));
    final p1 = o + dir * (r - w * 3.2), p2 = o + dir * (r + w * .2);
    edge..moveTo(p1.dx, p1.dy)..lineTo(p2.dx, p2.dy);
  }
  _thread(c, edge, s == Stitchwork.kashi ? t.a : t.b, w * .9);
}

/// A French knot: a raised dot of thread with its shine.
void _knot(Canvas c, Offset p, double r, Color color) {
  c.drawCircle(p.translate(r * .3, r * .4), r, Paint()..color = const Color(0x33000000));
  c.drawCircle(p, r, Paint()..color = color);
  c.drawCircle(p.translate(-r * .3, -r * .35), r * .38, Paint()..color = Colors.white.withValues(alpha: .45));
}

/// The page transition (D-084): as a page comes in, a thread is stitched across its top -- a running stitch drawn
/// behind a moving needle -- while the page fades up; when the seam is done the thread fades. Off under reduced motion.
class StitchTransition extends StatelessWidget {
  final Animation<double> animation;
  final Widget child;
  const StitchTransition({super.key, required this.animation, required this.child});
  @override
  Widget build(BuildContext context) {
    if (MediaQuery.disableAnimationsOf(context)) return child;
    final scheme = Theme.of(context).colorScheme;
    final fade = CurvedAnimation(parent: animation, curve: const Interval(0, .7, curve: Curves.easeOut));
    return Stack(
      children: [
        FadeTransition(
          opacity: fade,
          child: SlideTransition(
            position: Tween(begin: const Offset(0, .015), end: Offset.zero).animate(fade),
            child: child,
          ),
        ),
        Positioned(
          left: 0,
          right: 0,
          top: MediaQuery.paddingOf(context).top + kToolbarHeight + 2,
          height: 12,
          child: IgnorePointer(
            child: AnimatedBuilder(
              animation: animation,
              builder: (context, _) => animation.isCompleted || animation.value == 0
                  ? const SizedBox.shrink()
                  : CustomPaint(painter: _SeamPainter(animation.value, scheme.secondary)),
            ),
          ),
        ),
      ],
    );
  }
}

class _SeamPainter extends CustomPainter {
  final double t;
  final Color color;
  _SeamPainter(this.t, this.color);
  @override
  void paint(Canvas canvas, Size size) {
    // the seam runs in the first 80% and fades out in the last 20%
    final run = (t / .8).clamp(0.0, 1.0);
    final fade = t <= .8 ? 1.0 : 1 - (t - .8) / .2;
    final x = size.width * Curves.easeInOut.transform(run);
    final cy = size.height / 2;
    final c = color.withValues(alpha: .85 * fade);
    _running(canvas, Path()..moveTo(0, cy)..lineTo(x, cy), c, 1.8);
    if (run < 1) {
      // the needle, eye trailing the thread
      final needle = Paint()..color = const Color(0xFF8E959C).withValues(alpha: fade)..strokeWidth = 1.6
        ..strokeCap = StrokeCap.round;
      canvas.drawLine(Offset(x - 2, cy), Offset(x + 12, cy - 1), needle);
      canvas.drawCircle(Offset(x - 1, cy), 1.4, Paint()..color = Colors.white.withValues(alpha: fade));
    }
  }

  @override
  bool shouldRepaint(_SeamPainter old) => old.t != t || old.color != color;
}

/// An embroidered border: a satin zigzag in two threads with a mirror at every turn, as a dupatta's or a truck's edge is
/// finished (D-082).
class EmbroideredBorder extends StatelessWidget {
  final Motif motif;
  final double height;
  const EmbroideredBorder(this.motif, {super.key, this.height = 16});
  @override
  Widget build(BuildContext context) => ExcludeSemantics(
        child: RepaintBoundary(
          child: CustomPaint(size: Size(double.infinity, height), painter: _BorderPainter(stitchworkFor(motif))),
        ),
      );
}

class _BorderPainter extends CustomPainter {
  final Stitchwork s;
  _BorderPainter(this.s);
  @override
  void paint(Canvas c, Size size) {
    final t = _threads[s]!;
    final h = size.height;
    final step = h * 1.6;
    for (var i = 0, x = 0.0; x < size.width; i++, x += step) {
      final up = _poly3(Offset(x, h * .85), Offset(x + step / 2, h * .15), Offset(x + step, h * .85));
      _satin(c, up, i.isEven ? t.a : t.b, h * .09, .3);
      _mirror(c, Offset(x + step / 2, h * .62), h * .14, t.accent, h * .07);
    }
    _running(c, Path()..moveTo(0, h * .95)..lineTo(size.width, h * .95), t.light, h * .07);
  }

  @override
  bool shouldRepaint(_BorderPainter old) => old.s != s;
}

Path _poly3(Offset a, Offset b, Offset c) => Path()
  ..moveTo(a.dx, a.dy)
  ..lineTo(b.dx, b.dy)
  ..lineTo(c.dx, c.dy)
  ..close();

/// An embroidered rule between sections: a running stitch in two threads with a mirror every few stitches (D-082).
class StitchRule extends StatelessWidget {
  final Motif motif;
  final double height;
  const StitchRule({super.key, this.motif = Motif.mirrorwork, this.height = 14});
  @override
  Widget build(BuildContext context) => ExcludeSemantics(
        child: RepaintBoundary(
          child: CustomPaint(size: Size(double.infinity, height), painter: _RulePainter(stitchworkFor(motif))),
        ),
      );
}

class _RulePainter extends CustomPainter {
  final Stitchwork s;
  _RulePainter(this.s);
  @override
  void paint(Canvas c, Size size) {
    final t = _threads[s]!;
    final cy = size.height / 2;
    const w = 1.6;
    // two interlaced running stitches, offset by half a stitch, as a double running (Holbein) stitch
    _running(c, Path()..moveTo(4, cy - 1.6)..lineTo(size.width - 4, cy - 1.6), t.a, w);
    _running(c, Path()..moveTo(7, cy + 1.6)..lineTo(size.width - 4, cy + 1.6), t.b, w);
    for (var x = size.width / 2 - 96.0; x <= size.width / 2 + 96; x += 96) {
      _satin(c, _diamond(Offset(x, cy), size.height * .5, size.height * .5), t.accent, w * .8, .78);
      _mirror(c, Offset(x, cy), size.height * .17, t.a, w * .7);
    }
  }

  @override
  bool shouldRepaint(_RulePainter old) => old.s != s;
}
