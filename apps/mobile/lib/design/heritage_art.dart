import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../domain/heritage.dart';
import 'theme.dart';

/// Pakistan's landmarks and craft motifs as original vector art (D-077), drawn in the stamp-paper palette.
///
/// Ornament here does semantic work (docs/12): a landmark names a region, a motif band carries its craft. Cost is
/// kept near zero by construction: no image assets and no network; every path is built once per landmark (static
/// cache) in a 100 x 100 box and only scaled at paint; each piece sits behind its own RepaintBoundary and never
/// animates, so a scrolling list rasterises it once.

// -------------------------------------------------------------------------------------------- landmark geometry

enum _Role { body, shade, dark, open, accent }

typedef _Shape = (_Role, Path);

Path _rect(double l, double t, double r, double b) => Path()..addRect(Rect.fromLTRB(l, t, r, b));

Path _poly(List<double> xy) {
  final p = Path()..moveTo(xy[0], xy[1]);
  for (var i = 2; i < xy.length; i += 2) {
    p.lineTo(xy[i], xy[i + 1]);
  }
  return p..close();
}

/// An onion dome standing on (cx, base), w wide and h tall.
Path _onion(double cx, double base, double w, double h) => Path()
  ..moveTo(cx - w / 2, base)
  ..cubicTo(cx - w * .62, base - h * .45, cx - w * .22, base - h * .78, cx, base - h)
  ..cubicTo(cx + w * .22, base - h * .78, cx + w * .62, base - h * .45, cx + w / 2, base)
  ..close();

/// A pointed (Mughal) arch from l to r, apex at top, open to the bottom b.
Path _arch(double l, double r, double top, double b) {
  final spring = top + (r - l) * .55;
  return Path()
    ..moveTo(l, b)
    ..lineTo(l, spring)
    ..quadraticBezierTo(l, top + (r - l) * .12, (l + r) / 2, top)
    ..quadraticBezierTo(r, top + (r - l) * .12, r, spring)
    ..lineTo(r, b)
    ..close();
}

/// A low dome from (l, base) to (r, base), rising h.
Path _dome(double l, double r, double base, double h) => Path()
  ..moveTo(l, base)
  ..cubicTo(l, base - h * 1.05, r, base - h * 1.05, r, base)
  ..close();

List<_Shape> _build(Landmark m) {
  final s = <_Shape>[];
  void add(_Role role, Path p) => s.add((role, p));
  switch (m) {
    case Landmark.minar:
      add(_Role.shade, _rect(16, 88, 84, 93));
      add(_Role.body, _rect(24, 84, 76, 88));
      for (final x in [30.0, 42.0, 54.0]) {
        add(_Role.body, _poly([x, 84, x + 8, 64, x + 16, 84]));
      }
      add(_Role.body, _poly([44.5, 72, 55.5, 72, 53, 24, 47, 24]));
      add(_Role.shade, _poly([50, 72, 55.5, 72, 53, 24, 50, 24]));
      for (final (l, t) in [(43.0, 50.0), (45.0, 37.0), (46.2, 25.0)]) {
        add(_Role.dark, _rect(l, t, 100 - l, t + 2.4));
      }
      add(_Role.body, _onion(50, 25, 9, 10));
      add(_Role.accent, _rect(49.4, 8.5, 50.6, 15.5));
      add(_Role.accent, Path()..addOval(Rect.fromCircle(center: const Offset(50, 8), radius: 1.4)));
    case Landmark.badshahi:
      for (final x in [6.0, 89.0]) {
        add(_Role.body, _rect(x, 28, x + 5, 92));
        add(_Role.dark, _rect(x - 1, 27, x + 6, 29.5));
        add(_Role.shade, _onion(x + 2.5, 27, 7, 8));
      }
      add(_Role.body, _onion(27, 58, 16, 15));
      add(_Role.body, _onion(73, 58, 16, 15));
      add(_Role.body, _onion(50, 46, 27, 25));
      add(_Role.shade, _onion(57, 46, 13, 22));
      add(_Role.body, _rect(13, 58, 87, 92));
      add(_Role.shade, _rect(13, 56, 87, 58.5));
      add(_Role.body, _rect(36, 44, 64, 92));
      add(_Role.shade, _rect(36, 44, 64, 46.5));
      add(_Role.open, _arch(41.5, 58.5, 54, 92));
      add(_Role.open, _arch(18, 30, 69, 88));
      add(_Role.open, _arch(70, 82, 69, 88));
      for (final (x, top) in [(50.0, 16.0), (27.0, 38.0), (73.0, 38.0)]) {
        add(_Role.accent, _rect(x - .6, top, x + .6, top + 6));
      }
    case Landmark.mohenjodaro:
      add(_Role.shade, _poly([2, 92, 16, 74, 84, 74, 98, 92]));
      add(_Role.body, _rect(20, 62, 80, 74));
      add(_Role.body, _rect(29, 52, 71, 62));
      for (final (l, r, y) in [(20.0, 80.0, 67.0), (29.0, 71.0, 56.5), (16.0, 84.0, 79.0), (10.0, 90.0, 85.0)]) {
        add(_Role.dark, _rect(l, y, r, y + .9));
      }
      add(_Role.body, _dome(35, 65, 52, 16));
      add(_Role.shade, _dome(51, 65, 52, 14));
      add(_Role.shade, _rect(8, 84, 20, 92));
      add(_Role.shade, _rect(80, 82, 92, 92));
    case Landmark.takhtibahi:
      add(_Role.shade, _poly([0, 92, 0, 70, 18, 60, 40, 52, 62, 46, 84, 54, 100, 66, 100, 92]));
      add(_Role.body, _rect(14, 72, 86, 80));
      add(_Role.body, _rect(20, 54, 46, 66));
      add(_Role.body, _rect(48, 46, 74, 60));
      for (final x in [23.0, 29.0, 35.0, 41.0]) {
        add(_Role.open, _rect(x, 58, x + 3, 64));
      }
      for (final x in [51.0, 57.0, 63.0, 69.0]) {
        add(_Role.open, _rect(x, 50, x + 3, 57));
      }
      for (final x in [20.0, 32.0, 44.0, 56.0, 68.0, 78.0]) {
        add(_Role.open, _rect(x, 74.5, x + 4, 79));
      }
      add(_Role.body, _rect(76, 49, 88, 55));
      add(_Role.body, _dome(77, 87, 49, 7));
      add(_Role.accent, _rect(81.4, 37, 82.6, 43));
    case Landmark.ziarat:
      add(_Role.dark, _poly([4, 92, 11, 60, 18, 92]));
      add(_Role.dark, _poly([82, 92, 89, 56, 96, 92]));
      add(_Role.shade, _poly([21, 58, 35, 45, 49, 58]));
      add(_Role.shade, _poly([51, 58, 65, 45, 79, 58]));
      add(_Role.dark, _rect(43, 42, 47, 52));
      add(_Role.dark, _rect(19, 56, 81, 59));
      add(_Role.body, _rect(23, 59, 77, 90));
      add(_Role.shade, _rect(23, 75, 77, 90));
      for (final x in [27.0, 35.0, 43.0, 51.0, 59.0, 67.0, 75.0]) {
        add(_Role.dark, _rect(x - .6, 75, x + .6, 90));
      }
      for (final x in [29.0, 39.0, 56.0, 66.0]) {
        add(_Role.open, _rect(x, 63, x + 5, 70));
      }
      add(_Role.shade, _rect(19, 90, 81, 93));
    case Landmark.faisal:
      add(_Role.shade, _rect(12, 86, 88, 92));
      add(_Role.body, _poly([25, 86, 50, 32, 75, 86]));
      add(_Role.shade, _poly([50, 32, 75, 86, 57, 86]));
      add(_Role.dark, _poly([50, 32, 43.5, 86, 45.5, 86]));
      add(_Role.open, _poly([46, 86, 50, 76, 54, 86]));
      for (final (x, top, role) in [(10.0, 14.0, _Role.body), (86.4, 14.0, _Role.body),
                                    (20.8, 26.0, _Role.shade), (77.2, 26.0, _Role.shade)]) {
        add(role, _rect(x, top, x + 2.6, 88));
        add(role, _poly([x, top, x + 1.3, top - 8, x + 2.6, top]));
        add(_Role.dark, _rect(x - .8, top + 24, x + 3.4, top + 25.6));
      }
    case Landmark.redfort:
      add(_Role.shade, _rect(0, 80, 100, 88));
      add(_Role.dark, _rect(0, 89, 100, 90.4));
      add(_Role.dark, _rect(8, 92, 92, 93));
      add(_Role.body, _rect(8, 56, 80, 80));
      for (var x = 8.0; x < 78; x += 6) {
        add(_Role.body, _rect(x, 51.5, x + 3.5, 56));
      }
      add(_Role.body, _rect(78, 46, 94, 80));
      for (final x in [78.0, 83.5, 89.5]) {
        add(_Role.body, _rect(x, 41.5, x + 3.5, 46));
      }
      add(_Role.shade, _rect(78, 46, 80, 80));
      add(_Role.open, _arch(37, 49, 60, 80));
      for (final (x, y) in [(17.0, 63.0), (66.0, 63.0), (84.5, 55.0)]) {
        add(_Role.open, _rect(x, y, x + 3, y + 6));
      }
    case Landmark.baltit:
      add(_Role.shade, _poly([0, 92, 0, 60, 16, 40, 30, 58, 46, 30, 64, 56, 80, 36, 100, 58, 100, 92]));
      add(_Role.body, _poly([40.5, 39, 46, 30, 51.5, 39, 48.5, 37, 46, 40, 43.5, 37.5]));
      add(_Role.body, _poly([75, 43, 80, 36, 85, 43, 82, 41.5, 79, 43.5]));
      add(_Role.dark, _poly([8, 92, 24, 77, 76, 73, 94, 92]));
      add(_Role.body, _rect(32, 47, 68, 76));
      add(_Role.body, _rect(36, 37, 64, 47));
      add(_Role.body, _rect(55, 28, 64, 37));
      add(_Role.shade, _rect(30, 45.5, 70, 47.5));
      add(_Role.shade, _rect(34, 35.5, 66, 37.5));
      add(_Role.shade, _rect(53, 26.5, 66, 28.5));
      for (final (x, y) in [(38.0, 52.0), (46.0, 52.0), (54.0, 52.0), (62.0, 52.0), (40.0, 62.0), (58.0, 62.0),
                            (40.0, 40.0), (49.0, 40.0), (58.0, 30.5)]) {
        add(_Role.open, _rect(x, y, x + 3, y + 4));
      }
    case Landmark.mazar:
      add(_Role.shade, _rect(14, 84, 86, 92));
      add(_Role.body, _rect(22, 78, 78, 84));
      add(_Role.body, Path()
        ..moveTo(31, 50)
        ..cubicTo(29, 26, 45, 18, 50, 16)
        ..cubicTo(55, 18, 71, 26, 69, 50)
        ..close());
      add(_Role.body, _rect(28, 48, 72, 78));
      add(_Role.shade, _rect(62, 48, 72, 78));
      add(_Role.open, _arch(43, 57, 56, 78));
      add(_Role.accent, _rect(49.4, 8, 50.6, 16));
  }
  return s;
}

final _cache = <Landmark, List<_Shape>>{};
List<_Shape> _shapes(Landmark m) => _cache[m] ??= _build(m);

/// The paints for one landmark: [mono] draws a single-colour silhouette (openings dropped) for small sizes and
/// light surfaces; otherwise the stamp-paper tones for the pine scene.
class _LandmarkPainter extends CustomPainter {
  final Landmark landmark;
  final Color? mono;
  final Color openings;
  _LandmarkPainter(this.landmark, this.mono, this.openings);

  static final _tones = {
    _Role.body: const Color(0xFFF1E6CF),
    _Role.shade: const Color(0xFFC9B48C),
    _Role.dark: const Color(0xFF8C7857),
    _Role.accent: Stamp.brass,
  };

  @override
  void paint(Canvas canvas, Size size) {
    final scale = math.min(size.width, size.height) / 100;
    canvas.save();
    canvas.translate((size.width - 100 * scale) / 2, (size.height - 100 * scale) / 2);
    canvas.scale(scale);
    final paint = Paint()..isAntiAlias = true;
    for (final (role, path) in _shapes(landmark)) {
      if (role == _Role.open) {
        if (mono != null) continue;
        paint.color = openings;
      } else {
        paint.color = mono ?? _tones[role]!;
      }
      canvas.drawPath(path, paint);
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(_LandmarkPainter old) =>
      old.landmark != landmark || old.mono != mono || old.openings != openings;
}

/// A region's landmark: a silhouette in one colour at icon sizes (excluded from semantics: the region's name sits
/// beside it), or in full tones for a scene.
class LandmarkArt extends StatelessWidget {
  final Landmark landmark;
  final double size;
  final Color? color;
  final Color openings;
  final String? semanticLabel;
  const LandmarkArt(this.landmark,
      {super.key, this.size = 24, this.color, this.openings = Stamp.pine, this.semanticLabel});

  @override
  Widget build(BuildContext context) {
    final art = RepaintBoundary(
      child: CustomPaint(
        size: Size.square(size),
        painter: _LandmarkPainter(landmark, color, openings),
        isComplex: true,
      ),
    );
    return semanticLabel == null
        ? ExcludeSemantics(child: art)
        : Semantics(label: semanticLabel, image: true, child: art);
  }
}

/// The landmark of a jurisdiction as an icon; nothing where the jurisdiction has none.
class RegionGlyph extends StatelessWidget {
  final String jurisdiction;
  final double size;
  final Color? color;
  const RegionGlyph(this.jurisdiction, {super.key, this.size = 20, this.color});
  @override
  Widget build(BuildContext context) {
    final region = heritageRegion(jurisdiction);
    if (region == null) return SizedBox.square(dimension: size);
    return LandmarkArt(region.landmark, size: size, color: color ?? Theme.of(context).colorScheme.secondary);
  }
}

/// A region's landmark as a scene: the pine ground of the home card, a quiet sun, the landmark in tones, the
/// region's motif along the foot.
class LandmarkScene extends StatelessWidget {
  final HeritageRegion region;
  final double height;
  const LandmarkScene(this.region, {super.key, this.height = 220});
  @override
  Widget build(BuildContext context) => Semantics(
        label: 'Illustration of ${region.place}, ${region.location}',
        image: true,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(28),
          child: SizedBox(
            height: height,
            child: Column(
              children: [
                Expanded(
                  child: RepaintBoundary(
                    child: CustomPaint(
                      painter: _ScenePainter(),
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(24, 18, 24, 0),
                        child: Center(child: LandmarkArt(region.landmark, size: height - 40)),
                      ),
                    ),
                  ),
                ),
                MotifBand(region.motif, height: 14),
              ],
            ),
          ),
        ),
      );
}

class _ScenePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(Offset.zero & size, Paint()..color = Stamp.pine);
    final sun = Offset(size.width * .78, size.height * .3);
    canvas.drawCircle(sun, size.height * .16, Paint()..color = Stamp.brass.withValues(alpha: .16));
    canvas.drawCircle(sun, size.height * .09, Paint()..color = Stamp.brass.withValues(alpha: .22));
    final ring = Paint()
      ..color = Stamp.parchment.withValues(alpha: .1)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    canvas.drawOval(Rect.fromCenter(center: Offset(size.width / 2, size.height * .72), width: size.width * .86,
        height: size.height * .5), ring);
    canvas.drawRect(Rect.fromLTWH(0, size.height - 3, size.width, 3), Paint()..color = Colors.black12);
  }

  @override
  bool shouldRepaint(_ScenePainter old) => false;
}

// -------------------------------------------------------------------------------------------- motif bands

/// A band of a region's craft motif: a repeat unit drawn across the width, height-tall. Static; one raster.
class MotifBand extends StatelessWidget {
  final Motif motif;
  final double height;
  const MotifBand(this.motif, {super.key, this.height = 8});
  @override
  Widget build(BuildContext context) => ExcludeSemantics(
        child: RepaintBoundary(
          child: CustomPaint(size: Size(double.infinity, height), painter: _MotifPainter(motif)),
        ),
      );
}

/// A square swatch of a motif, for naming a craft beside it.
class MotifSwatch extends StatelessWidget {
  final Motif motif;
  final double size;
  const MotifSwatch(this.motif, {super.key, this.size = 36});
  @override
  Widget build(BuildContext context) => ExcludeSemantics(
        child: ClipRRect(
          borderRadius: BorderRadius.circular(size * .28),
          child: RepaintBoundary(
            child: CustomPaint(size: Size.square(size), painter: _MotifPainter(motif, rows: 2)),
          ),
        ),
      );
}

class _MotifPainter extends CustomPainter {
  final Motif motif;
  final int rows;
  _MotifPainter(this.motif, {this.rows = 1});

  static const _ground = {
    Motif.truckArt: Stamp.pine,
    Motif.kashi: Color(0xFF1F4E8C),
    Motif.ajrak: Color(0xFF8B1E1E),
    Motif.lacquer: Color(0xFF6B4226),
    Motif.mirrorwork: Color(0xFF5E1A2A),
    Motif.faisalFolds: Color(0xFF2E4B44),
    Motif.chainStitch: Color(0xFFEADFC8),
    Motif.crossStitch: Color(0xFF2A2A2A),
    Motif.football: Color(0xFF2F6B3A), // the pitch
    Motif.jaali: Color(0xFF5A3A22), // sheesham
    Motif.halaTile: Color(0xFFF1EEE6), // the white tile ground
    Motif.chappal: Color(0xFF8A5A2B), // tanned leather
    Motif.rug: Color(0xFF6E1F1F), // madder red
    Motif.folkVessels: Color(0xFFE2C48A), // sun on a courtyard wall
    Motif.chinar: Color(0xFF4A3222), // walnut
    Motif.woolCap: Color(0xFF3B4A57), // mountain slate
  };

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(Offset.zero & size, Paint()..color = _ground[motif]!);
    final u = size.height / rows; // a square unit per row
    if (u <= 0) return;
    final n = (size.width / u).ceil();
    final p = Paint()..isAntiAlias = true;
    for (var row = 0; row < rows; row++) {
      for (var i = 0; i < n; i++) {
        _unit(canvas, Rect.fromLTWH(i * u, row * u, u, u), i + row, p);
      }
    }
  }

  void _unit(Canvas c, Rect r, int i, Paint p) {
    final cx = r.center.dx, cy = r.center.dy, h = r.height;
    Path diamond(double rx, double ry) =>
        _poly([cx, cy - ry, cx + rx, cy, cx, cy + ry, cx - rx, cy]);
    switch (motif) {
      case Motif.kashi: // Multani tile: an eight-pointed star of two squares, turquoise heart
        p.color = const Color(0xFFF4EEE0);
        c.drawRect(Rect.fromCenter(center: r.center, width: h * .5, height: h * .5), p);
        c.drawPath(diamond(h * .35, h * .35), p);
        p.color = const Color(0xFF3FA7B5);
        c.drawCircle(r.center, h * .12, p);
      case Motif.ajrak: // ajrak: indigo medallions on madder red, white dots between
        p.color = const Color(0xFF1F2552);
        c.drawCircle(r.center, h * .3, p);
        p.color = const Color(0xFFF4EEE0);
        c.drawCircle(r.center, h * .09, p);
        c.drawCircle(Offset(r.left, r.top + h * .15), h * .06, p);
        c.drawCircle(Offset(r.left, r.bottom - h * .15), h * .06, p);
      case Motif.lacquer: // lacquer and carved wood: a brass lattice
        p
          ..color = const Color(0xFFC99A4A)
          ..style = PaintingStyle.stroke
          ..strokeWidth = math.max(.8, h * .08);
        c.drawPath(diamond(h * .45, h * .4), p);
        p.style = PaintingStyle.fill;
        c.drawCircle(r.center, h * .08, p);
      case Motif.mirrorwork: // Balochi embroidery: stitched diamonds round a mirror
        p.color = const Color(0xFFE07A3F);
        c.drawPath(diamond(h * .42, h * .42), p);
        p.color = const Color(0xFF5E1A2A);
        c.drawPath(diamond(h * .26, h * .26), p);
        p.color = const Color(0xFFD9DEE3);
        c.drawCircle(r.center, h * .13, p);
      case Motif.crossStitch: // Hunza stitching: alternating triangles
        p.color = i.isEven ? const Color(0xFFB8322A) : const Color(0xFFF1E6CF);
        c.drawPath(_poly([r.left, r.bottom - h * .12, cx, r.top + h * .12, r.right, r.bottom - h * .12]), p);
      case Motif.chainStitch: // chain-stitch: a vine with red flowers on felted wool
        p
          ..color = const Color(0xFF4C7A4A)
          ..style = PaintingStyle.stroke
          ..strokeWidth = math.max(.8, h * .08);
        c.drawArc(Rect.fromCenter(center: r.center, width: r.width, height: h * .7), i.isEven ? 0 : math.pi,
            math.pi, false, p);
        p.style = PaintingStyle.fill;
        p.color = const Color(0xFFB03A2E);
        c.drawCircle(Offset(cx, i.isEven ? cy + h * .35 : cy - h * .35), h * .11, p);
      case Motif.truckArt: // phool patti: four-petal flowers, brass and oxide
        p.color = i.isEven ? Stamp.brass : const Color(0xFFC0533F);
        for (var k = 0; k < 4; k++) {
          final a = k * math.pi / 2;
          c.drawCircle(Offset(cx + math.cos(a) * h * .2, cy + math.sin(a) * h * .2), h * .14, p);
        }
        p.color = Stamp.parchment;
        c.drawCircle(r.center, h * .1, p);
      case Motif.faisalFolds: // the Faisal Mosque's folded shell
        p.color = const Color(0xFFE6E1D4);
        c.drawPath(_poly([r.left + h * .1, r.bottom - h * .1, cx, r.top + h * .1, cx, r.bottom - h * .1]), p);
        p.color = const Color(0xFFB9B3A3);
        c.drawPath(_poly([cx, r.top + h * .1, r.right - h * .1, r.bottom - h * .1, cx, r.bottom - h * .1]), p);
      case Motif.football: // Sialkot: a ball, its black pentagon and the seams running from it
        p.color = const Color(0xFFF4F1EA);
        c.drawCircle(r.center, h * .38, p);
        p.color = const Color(0xFF1E1E1E);
        c.drawPath(_ngon(cx, cy, h * .13, 5, -math.pi / 2), p);
        p
          ..style = PaintingStyle.stroke
          ..strokeWidth = math.max(.6, h * .04);
        for (var k = 0; k < 5; k++) {
          final a = -math.pi / 2 + k * 2 * math.pi / 5;
          c.drawLine(Offset(cx + math.cos(a) * h * .13, cy + math.sin(a) * h * .13),
              Offset(cx + math.cos(a) * h * .36, cy + math.sin(a) * h * .36), p);
        }
        p.style = PaintingStyle.fill;
      case Motif.jaali: // Chiniot carving: a pierced lattice of a ring through a lozenge, brass-light on sheesham
        p
          ..color = const Color(0xFFD9B27A)
          ..style = PaintingStyle.stroke
          ..strokeWidth = math.max(.8, h * .07);
        c.drawCircle(r.center, h * .3, p);
        c.drawPath(diamond(h * .5, h * .5), p);
        p.style = PaintingStyle.fill;
        c.drawCircle(r.center, h * .07, p);
      case Motif.halaTile: // Hala kashi: a six-petal cobalt flower with a turquoise heart on white
        p.color = const Color(0xFF1F4E8C);
        for (var k = 0; k < 6; k++) {
          final a = k * math.pi / 3;
          c.drawCircle(Offset(cx + math.cos(a) * h * .2, cy + math.sin(a) * h * .2), h * .12, p);
        }
        p.color = const Color(0xFF3FA7B5);
        c.drawCircle(r.center, h * .1, p);
      case Motif.chappal: // the chappal's braided strap: cream chevrons with stitch dots between
        p
          ..color = const Color(0xFFF0DDB8)
          ..style = PaintingStyle.stroke
          ..strokeWidth = math.max(.8, h * .1)
          ..strokeCap = StrokeCap.round;
        c.drawPath(
            Path()
              ..moveTo(r.left + h * .15, r.top + h * .25)
              ..lineTo(cx, cy + h * .1)
              ..lineTo(r.right - h * .15, r.top + h * .25),
            p);
        p
          ..style = PaintingStyle.fill
          ..strokeCap = StrokeCap.butt;
        for (final dx in [-.25, 0.0, .25]) {
          c.drawCircle(Offset(cx + dx * h, r.bottom - h * .2), h * .045, p);
        }
      case Motif.rug: // Balochi rug: a stepped navy lozenge with a cream heart, on madder
        p.color = const Color(0xFF1F2A4F);
        c.drawPath(
            _poly([cx, cy - h * .4, cx + h * .14, cy - h * .26, cx + h * .4, cy, cx + h * .14, cy + h * .26, cx,
              cy + h * .4, cx - h * .14, cy + h * .26, cx - h * .4, cy, cx - h * .14, cy - h * .26]),
            p);
        p.color = const Color(0xFFEBDDC2);
        c.drawPath(diamond(h * .1, h * .1), p);
      case Motif.folkVessels: // Lok Virsa: a terracotta pot with a painted band, alternating with a small one
        final big = i.isEven;
        final rr = h * (big ? .27 : .19);
        final body = Offset(cx, r.bottom - rr - h * .08);
        p.color = const Color(0xFFA0482A);
        c.drawCircle(body, rr, p);
        c.drawRect(Rect.fromCenter(center: Offset(cx, body.dy - rr * .95), width: rr * .7, height: rr * .5), p);
        p.color = const Color(0xFFF4EEE0);
        c.drawRect(Rect.fromCenter(center: body, width: rr * 1.9, height: math.max(.6, h * .045)), p);
      case Motif.chinar: // walnut carving: a five-lobed chinar leaf and its stem
        p.color = const Color(0xFFC79A66);
        c.drawPath(
            _poly([cx, r.top + h * .1, cx + h * .1, cy - h * .12, cx + h * .36, cy - h * .2, cx + h * .2, cy + h * .02,
              cx + h * .3, cy + h * .22, cx, cy + h * .14, cx - h * .3, cy + h * .22, cx - h * .2, cy + h * .02,
              cx - h * .36, cy - h * .2, cx - h * .1, cy - h * .12]),
            p);
        p
          ..style = PaintingStyle.stroke
          ..strokeWidth = math.max(.6, h * .04);
        c.drawLine(Offset(cx, cy + h * .1), Offset(cx, r.bottom - h * .08), p);
        p.style = PaintingStyle.fill;
      case Motif.woolCap: // the Gilgiti cap: a rolled brim under a soft crown, in undyed wool
        p.color = const Color(0xFFEDE6D6);
        c.drawRRect(
            RRect.fromRectAndRadius(
                Rect.fromLTWH(r.left + h * .14, cy, h * .72, h * .22), Radius.circular(h * .11)),
            p);
        c.drawArc(Rect.fromLTWH(r.left + h * .2, cy - h * .28, h * .6, h * .5), math.pi, math.pi, true, p);
        p.color = const Color(0xFFBFB4A0);
        c.drawRect(Rect.fromLTWH(r.left + h * .18, cy + h * .1, h * .64, math.max(.6, h * .03)), p);
    }
  }

  /// A regular n-gon of radius [rad] centred at (cx, cy), its first vertex at angle [start].
  static Path _ngon(double cx, double cy, double rad, int n, double start) => _poly([
        for (var k = 0; k < n; k++) ...[
          cx + math.cos(start + k * 2 * math.pi / n) * rad,
          cy + math.sin(start + k * 2 * math.pi / n) * rad,
        ],
      ]);

  @override
  bool shouldRepaint(_MotifPainter old) => old.motif != motif || old.rows != rows;
}

// ------------------------------------------------------------------------------------------- craft backdrops

/// A craft medallion (D-081): a disc of the craft's ground with two rings of its motif turned around a centre unit,
/// as a kashi tile rosette, a truck's painted wheel-boss or an embroidered roundel is laid out. Faint, behind content,
/// decorative to a screen reader and untouchable; one raster, cached behind its RepaintBoundary.
class CraftCorner extends StatelessWidget {
  final Motif motif;
  final double size;
  final double opacity;
  const CraftCorner(this.motif, {super.key, this.size = 220, this.opacity = .1});
  @override
  Widget build(BuildContext context) => IgnorePointer(
        child: ExcludeSemantics(
          child: RepaintBoundary(
            child: Opacity(
              opacity: opacity,
              child: CustomPaint(size: Size.square(size), painter: _MedallionPainter(motif)),
            ),
          ),
        ),
      );
}

class _MedallionPainter extends CustomPainter {
  final Motif motif;
  _MedallionPainter(this.motif);

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    final r = size.shortestSide / 2;
    final unit = _MotifPainter(motif);
    canvas.drawCircle(c, r, Paint()..color = _MotifPainter._ground[motif]!);
    final rule = Paint()
      ..color = Stamp.brass
      ..style = PaintingStyle.stroke
      ..strokeWidth = math.max(1, r * .018);
    // two rings of the motif, each unit turned to face the centre, the outer one larger
    for (final (radius, u) in [(r * .78, r * .3), (r * .47, r * .24)]) {
      final n = math.max(6, (2 * math.pi * radius / (u * 1.15)).floor());
      for (var j = 0; j < n; j++) {
        final a = j * 2 * math.pi / n;
        canvas.save();
        canvas.translate(c.dx + math.cos(a) * radius, c.dy + math.sin(a) * radius);
        canvas.rotate(a + math.pi / 2);
        unit._unit(canvas, Rect.fromCenter(center: Offset.zero, width: u, height: u), j, Paint()..isAntiAlias = true);
        canvas.restore();
      }
      canvas.drawCircle(c, radius + u * .62, rule);
    }
    unit._unit(canvas, Rect.fromCenter(center: c, width: r * .4, height: r * .4), 0, Paint()..isAntiAlias = true);
    canvas.drawCircle(c, r * .24, rule);
  }

  @override
  bool shouldRepaint(_MedallionPainter old) => old.motif != motif;
}

/// An embroidered rule (D-081): a running stitch in brass with a small mirror every few stitches, as Balochi and Sindhi
/// needlework edge a panel. Separates sections where a plain gap would; static, one raster.
class StitchRule extends StatelessWidget {
  final double height;
  const StitchRule({super.key, this.height = 12});
  @override
  Widget build(BuildContext context) => ExcludeSemantics(
        child: RepaintBoundary(
          child: CustomPaint(size: Size(double.infinity, height),
              painter: _StitchPainter(Theme.of(context).colorScheme.secondary)),
        ),
      );
}

class _StitchPainter extends CustomPainter {
  final Color color;
  _StitchPainter(this.color);
  @override
  void paint(Canvas canvas, Size size) {
    final cy = size.height / 2;
    final stitch = Paint()
      ..color = color.withValues(alpha: .55)
      ..strokeWidth = 1.6
      ..strokeCap = StrokeCap.round;
    final mirror = Paint()..color = color.withValues(alpha: .7);
    final glass = Paint()..color = const Color(0xFFD9DEE3);
    const step = 14.0;
    for (var i = 0, x = 4.0; x < size.width - 4; i++, x += step) {
      if (i % 6 == 3) {
        final d = size.height * .42;
        canvas.drawPath(_poly([x + step / 2, cy - d, x + step / 2 + d, cy, x + step / 2, cy + d, x + step / 2 - d, cy]),
            mirror);
        canvas.drawCircle(Offset(x + step / 2, cy), d * .42, glass);
      } else {
        canvas.drawLine(Offset(x + 2, cy), Offset(x + step - 4, cy), stitch);
      }
    }
  }

  @override
  bool shouldRepaint(_StitchPainter old) => old.color != color;
}

/// A landmark as an icon: it takes its colour and size from the surrounding IconTheme, so a navigation bar's selected
/// and unselected states colour it like any other icon.
class LandmarkIcon extends StatelessWidget {
  final Landmark landmark;
  const LandmarkIcon(this.landmark, {super.key});
  @override
  Widget build(BuildContext context) {
    final theme = IconTheme.of(context);
    return LandmarkArt(landmark, size: theme.size ?? 24, color: theme.color);
  }
}
