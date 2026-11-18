import 'dart:math' as math;
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import '../domain/heritage.dart';

/// Embroidery (D-082): the page as embroidered cloth. A craft's pattern is stitched -- every thread drawn with an
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

// --------------------------------------------------------------------------------------------- the stitched tiles

const double _tile = 96;

/// One tile of [s]'s pattern, [_tile] logical pixels square; it repeats seamlessly (motifs on the edges are halves of
/// the neighbour's).
void _stitchTile(Canvas c, Stitchwork s) {
  final t = _threads[s]!;
  const w = 1.5;
  const o = Offset(_tile / 2, _tile / 2);
  const corners = [Offset(0, 0), Offset(_tile, 0), Offset(0, _tile), Offset(_tile, _tile)];
  switch (s) {
    case Stitchwork.phool:
      // vines from the flower to each corner, in running stitch
      for (final k in corners) {
        final mid = Offset((o.dx + k.dx) / 2 + (k.dy - o.dy) * .18, (o.dy + k.dy) / 2 - (k.dx - o.dx) * .18);
        _running(c, Path()..moveTo(o.dx, o.dy)..quadraticBezierTo(mid.dx, mid.dy, k.dx, k.dy), t.accent, w);
        // a leaf on each vine
        _satin(c, _petal(mid, 9, 3.6, math.atan2(k.dy - o.dy, k.dx - o.dx) + .9), t.accent, w * .8, .4);
      }
      // the five-petal phool, satin stitched, and a mirror at its heart
      for (var k = 0; k < 5; k++) {
        final a = -math.pi / 2 + k * 2 * math.pi / 5;
        _satin(c, _petal(o, 17, 7, a), k.isEven ? t.a : t.b, w, a + math.pi / 2);
      }
      _mirror(c, o, 4.2, t.b, w);
      // half-flowers at the corners join the neighbouring tiles into a field
      for (final k in corners) {
        for (var j = 0; j < 4; j++) {
          final a = math.pi / 4 + j * math.pi / 2;
          _satin(c, _petal(k, 9, 4, a), t.b, w * .8, a + math.pi / 2);
        }
      }
    case Stitchwork.kashi:
      // the star in back stitch (unbroken), a satin rosette inside
      _thread(c, _star8(o, 30), t.a, w * 1.1);
      _thread(c, _star8(o, 22), t.b, w * .8);
      for (var k = 0; k < 8; k++) {
        final a = -math.pi / 2 + k * math.pi / 4;
        _satin(c, _petal(o, 11, 4, a), k.isEven ? t.a : t.b, w * .75, a + math.pi / 2);
      }
      c.drawCircle(o, 3, Paint()..color = t.light);
      // lattice: diamonds on the tile's edges, halves of the neighbours'
      for (final m in const [Offset(_tile / 2, 0), Offset(0, _tile / 2), Offset(_tile, _tile / 2), Offset(_tile / 2, _tile)]) {
        _running(c, _diamond(m, 10, 10), t.a, w);
        c.drawCircle(m, 2.2, Paint()..color = t.b);
      }
      for (final k in corners) {
        _satin(c, _diamond(k, 7, 7), t.b, w * .8, .78);
      }
    case Stitchwork.shisha:
      // a satin diamond in two threads round a mirror, chain-stitch frame, cross stitch in the corners
      _satin(c, _diamond(o, 24, 30), t.a, w, .5);
      _satin(c, _diamond(o, 15, 19), t.b, w * .85, -.5);
      _mirror(c, o, 8, t.accent, w);
      _running(c, _diamond(o, 34, 42), t.accent, w);
      for (final k in corners) {
        _mirror(c, k, 5, t.a, w * .9);
        for (final d in const [Offset(14, 0), Offset(-14, 0), Offset(0, 14), Offset(0, -14)]) {
          final p = k + d;
          _thread(c, Path()..moveTo(p.dx - 3, p.dy - 3)..lineTo(p.dx + 3, p.dy + 3), t.b, w * .8);
          _thread(c, Path()..moveTo(p.dx + 3, p.dy - 3)..lineTo(p.dx - 3, p.dy + 3), t.b, w * .8);
        }
      }
  }
}

final _tiles = <String, ui.Image>{};

ui.Image _tileImage(Stitchwork s, double dpr) {
  final key = '${s.name}@$dpr';
  return _tiles[key] ??= () {
    final rec = ui.PictureRecorder();
    final c = Canvas(rec)..scale(dpr);
    _stitchTile(c, s);
    final px = (_tile * dpr).round();
    return rec.endRecording().toImageSync(px, px);
  }();
}

class _GroundPainter extends CustomPainter {
  final Stitchwork stitchwork;
  final double dpr;
  _GroundPainter(this.stitchwork, this.dpr);
  @override
  void paint(Canvas canvas, Size size) {
    final img = _tileImage(stitchwork, dpr);
    final scale = Matrix4.diagonal3Values(1 / dpr, 1 / dpr, 1).storage;
    canvas.drawRect(Offset.zero & size,
        Paint()..shader = ImageShader(img, TileMode.repeated, TileMode.repeated, scale)..filterQuality = FilterQuality.medium);
  }

  @override
  bool shouldRepaint(_GroundPainter old) => old.stitchwork != stitchwork || old.dpr != dpr;
}

/// A craft embroidered over the whole of its box, faint enough that what lies on it reads (D-082). Decorative to a
/// screen reader and never in the way of a tap.
class EmbroideredGround extends StatelessWidget {
  final Motif motif;
  final double opacity;
  const EmbroideredGround(this.motif, {super.key, this.opacity = .22});
  @override
  Widget build(BuildContext context) => IgnorePointer(
        child: ExcludeSemantics(
          child: RepaintBoundary(
            child: Opacity(
              opacity: opacity,
              child: CustomPaint(
                painter: _GroundPainter(stitchworkFor(motif), MediaQuery.devicePixelRatioOf(context)),
                isComplex: true,
                child: const SizedBox.expand(),
              ),
            ),
          ),
        ),
      );
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
