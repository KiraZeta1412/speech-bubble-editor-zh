"""
shapes.py — Balloon shapes authored as SVG paths.

Why SVG instead of code: a bubble outline is artwork, not geometry homework.
Hand-coding each silhouette out of ellipses and star polygons is what made the
old shapes look mechanical. Here a shape is path data drawn in any vector tool,
normalised to a 100x100 box, and scaled to whatever the bubble's body rect is.

添加ing a shape = adding one line to SHAPE_PATHS. No new drawing code, and the
inspector's preview tiles pick it up automatically because they render the very
same path.

The parser covers the subset the library uses: M L H V C S Q T Z, absolute and
relative. Arcs (A) are deliberately unsupported — every shape here is beziers.
"""

import re

from PyQt6.QtGui import QPainterPath
from PyQt6.QtCore import QRectF, QPointF

# Authored on a 100x100 grid. Slight asymmetries are intentional: perfectly
# symmetric curves read as clip-art, a little wobble reads as inked by hand.
SHAPE_PATHS = {
    # Classic comic balloon — an egg, not an ellipse.
    "oval": (
        "M 51 2 C 78 3 99 22 98 49 C 97 76 75 98 49 97 "
        "C 23 96 1 74 2 47 C 3 20 25 1 51 2 Z"
    ),
    # Fat round balloon with soft lobes, for single words / SFX.
    "round": (
        "M 50 2 C 74 2 90 12 95 30 C 99 44 98 61 92 73 "
        "C 85 89 68 98 50 98 C 32 98 15 89 8 73 "
        "C 2 61 1 44 5 30 C 10 12 26 2 50 2 Z"
    ),
    # Hand-drawn rounded box: edges bow very slightly, corners are uneven.
    "softbox": (
        "M 12 5 C 38 2 62 2 88 5 C 95 6 98 12 97 24 "
        "C 96 44 96 58 97 76 C 98 89 94 96 86 96 "
        "C 60 99 38 99 14 96 C 6 95 2 89 3 77 "
        "C 4 58 4 44 3 24 C 2 12 5 6 12 5 Z"
    ),
    # Puffy cumulus burst — the big cloud balloon from the reference sheet.
    "puffy": (
        "M 26 34 C 20 20 30 8 44 10 C 50 2 64 2 70 10 "
        "C 84 6 95 16 92 29 C 100 36 99 51 90 56 "
        "C 92 70 80 79 68 74 C 60 84 44 84 36 74 "
        "C 22 78 12 66 16 54 C 6 48 8 36 26 34 Z"
    ),
    # Jagged explosion — sharp irregular spikes, the SFX balloon.
    "explode": (
        "M 50 1 L 60 14 L 74 6 L 74 21 L 90 17 L 82 30 "
        "L 99 34 L 86 44 L 98 55 L 82 58 L 90 72 L 74 69 "
        "L 74 85 L 61 76 L 52 99 L 43 76 L 29 86 L 27 69 "
        "L 11 73 L 19 58 L 2 54 L 15 44 L 1 33 L 18 30 "
        "L 10 16 L 27 21 L 27 5 L 40 14 Z"
    ),
    # Rounded panel with a squared shoulder — the boxed dialogue balloon.
    "panel": (
        "M 9 10 C 34 6 66 6 91 10 C 96 11 98 16 97 26 "
        "C 96 44 96 60 97 76 C 98 86 94 91 87 91 "
        "C 62 95 38 95 13 91 C 6 90 2 86 3 76 "
        "C 4 60 4 44 3 26 C 2 16 4 11 9 10 Z"
    ),
    # Irregular hand-inked blob — the "drawn in a hurry" manga balloon.
    "blob": (
        "M 44 3 C 66 1 86 9 94 25 C 100 39 96 56 88 68 "
        "C 79 81 62 92 46 95 C 30 98 12 90 6 74 "
        "C 1 58 3 38 12 24 C 20 12 30 5 44 3 Z"
    ),
    # Wobbly "shaky voice" balloon: scalloped left and right flanks.
    "wobble": (
        "M 50 3 C 70 3 88 8 94 18 C 98 25 90 30 94 37 "
        "C 98 44 90 49 94 56 C 98 63 90 68 93 76 "
        "C 88 89 70 97 50 97 C 30 97 12 89 7 76 "
        "C 10 68 2 63 6 56 C 10 49 2 44 6 37 "
        "C 10 30 2 25 6 18 C 12 8 30 3 50 3 Z"
    ),
}

# Safe text areas per lobe, in the same 0-100 space as the paths above.
# A lobed balloon holds one text block per lobe (x, y, w, h).
LOBE_RECTS = {
    "twin": [(10, 14, 48, 30), (34, 56, 52, 30)],
    "triple": [(9, 10, 44, 22), (41, 40, 48, 24), (9, 68, 50, 22)],
}


def lobe_rects(name: str, rect: QRectF) -> list:
    """Per-lobe safe text rects for `name`, mapped into `rect`."""
    spec = LOBE_RECTS.get(name)
    if not spec:
        return []
    sx = rect.width() / 100.0
    sy = rect.height() / 100.0
    return [QRectF(rect.left() + x * sx, rect.top() + y * sy, w * sx, h * sy)
            for (x, y, w, h) in spec]


def lobe_count(name: str) -> int:
    return len(LOBE_RECTS.get(name, ()))


_TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtZz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?")


def _parse(data: str) -> QPainterPath:
    """SVG path data -> QPainterPath (subset: M L H V C S Q T Z)."""
    tokens = _TOKEN.findall(data)
    path = QPainterPath()
    i = 0
    cmd = None
    cur = QPointF(0.0, 0.0)
    start = QPointF(0.0, 0.0)
    last_c2 = None      # reflection point for S
    last_q = None       # reflection point for T

    def num():
        nonlocal i
        value = float(tokens[i])
        i += 1
        return value

    while i < len(tokens):
        token = tokens[i]
        if token.isalpha():
            cmd = token
            i += 1
            if cmd in "Zz":
                path.closeSubpath()
                cur = QPointF(start)
                last_c2 = last_q = None
                continue
        elif cmd is None:
            break
        rel = cmd.islower()
        c = cmd.upper()

        if c == "M":
            x, y = num(), num()
            if rel:
                x += cur.x()
                y += cur.y()
            cur = QPointF(x, y)
            start = QPointF(cur)
            path.moveTo(cur)
            cmd = "l" if rel else "L"      # implicit lineto for extra pairs
            last_c2 = last_q = None
        elif c == "L":
            x, y = num(), num()
            if rel:
                x += cur.x()
                y += cur.y()
            cur = QPointF(x, y)
            path.lineTo(cur)
            last_c2 = last_q = None
        elif c == "H":
            x = num()
            if rel:
                x += cur.x()
            cur = QPointF(x, cur.y())
            path.lineTo(cur)
            last_c2 = last_q = None
        elif c == "V":
            y = num()
            if rel:
                y += cur.y()
            cur = QPointF(cur.x(), y)
            path.lineTo(cur)
            last_c2 = last_q = None
        elif c in ("C", "S"):
            if c == "C":
                x1, y1 = num(), num()
                if rel:
                    x1 += cur.x()
                    y1 += cur.y()
                c1 = QPointF(x1, y1)
            else:
                c1 = QPointF(2 * cur.x() - last_c2.x(), 2 * cur.y() - last_c2.y()) \
                    if last_c2 else QPointF(cur)
            x2, y2 = num(), num()
            x, y = num(), num()
            if rel:
                x2 += cur.x()
                y2 += cur.y()
                x += cur.x()
                y += cur.y()
            c2 = QPointF(x2, y2)
            cur = QPointF(x, y)
            path.cubicTo(c1, c2, cur)
            last_c2 = c2
            last_q = None
        elif c in ("Q", "T"):
            if c == "Q":
                x1, y1 = num(), num()
                if rel:
                    x1 += cur.x()
                    y1 += cur.y()
                q = QPointF(x1, y1)
            else:
                q = QPointF(2 * cur.x() - last_q.x(), 2 * cur.y() - last_q.y()) \
                    if last_q else QPointF(cur)
            x, y = num(), num()
            if rel:
                x += cur.x()
                y += cur.y()
            cur = QPointF(x, y)
            path.quadTo(q, cur)
            last_q = q
            last_c2 = None
        else:
            i += 1     # unknown command: skip rather than crash

    return path


_CACHE: dict[str, QPainterPath] = {}


def unit_path(name: str) -> QPainterPath | None:
    """Parsed path for `name` in its authored 100x100 space (cached)."""
    if name not in SHAPE_PATHS:
        return None
    if name not in _CACHE:
        _CACHE[name] = _parse(SHAPE_PATHS[name])
    return _CACHE[name]


def path_for(name: str, rect: QRectF) -> QPainterPath | None:
    """The named shape scaled to fill `rect`, or None if it isn't in the library."""
    from PyQt6.QtGui import QTransform
    base = unit_path(name)
    if base is None:
        return None
    box = base.boundingRect()
    if box.width() <= 0 or box.height() <= 0:
        return None
    transform = (QTransform()
                 .translate(rect.left(), rect.top())
                 .scale(rect.width() / box.width(), rect.height() / box.height())
                 .translate(-box.left(), -box.top()))
    return transform.map(base)


def has_shape(name: str) -> bool:
    return name in SHAPE_PATHS
