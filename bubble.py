"""
bubble.py — BubbleItem: draggable, resizable speech bubble QGraphicsItem.

Key design: tail + body are united into ONE QPainterPath so the border
traces the outer edge seamlessly — no seam, no black line cutting the tail.

Styles:  "oval" | "cloud" | "rect" | "spiky" | "scallop" | "burst" | "wobbly"
         | "text" | "scrim" | "caption"

Tail shapes ("wedge" | "curved" | "line" | "dots" | "none") and tail count
(0-3) are independent of the body style — Balloon+-style mix and match.
"""

import math
from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsEllipseItem, QGraphicsTextItem,
    QGraphicsRectItem, QGraphicsSceneMouseEvent,
    QGraphicsSceneContextMenuEvent, QMenu, QStyleOptionGraphicsItem,
    QWidget, QApplication, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import (
    QPainter, QPainterPath, QColor, QPen, QBrush, QFont, QCursor,
    QFontDatabase, QFontMetricsF
)
from PyQt6.QtCore import Qt, QRectF, QPointF

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HANDLE_SIZE   = 15          # visual size of a resize handle (drawn)
HANDLE_HIT    = 26          # clickable hit area — much larger than the visual
                            # so handles are easy to grab without pixel-hunting
TAIL_DOT_R    = 9
DEFAULT_W     = 220
DEFAULT_H     = 130
DEFAULT_STYLE = "oval"
# Fraction of an oval's full width the text column may span. An ellipse is
# widest at its vertical centre (where the text sits), so a single line can
# safely use most of the width — this keeps short text from floating in a sea
# of empty margin while staying clear of the curved edges.
OVAL_TEXT_FRAC = 0.72
ANCHORS = ["TL", "TC", "TR", "ML", "MR", "BL", "BC", "BR"]

# Styles that have a bubble body a tail can attach to.
TAILED_STYLES = ("oval", "cloud", "rect", "spiky", "scallop", "burst", "wobbly",
                 "round", "softbox", "puffy", "explode", "panel", "blob", "wobble",
                 
                 "twin", "triple")
# Tail render variants (Balloon+-style).
TAIL_SHAPES = ("wedge", "curved", "line", "dots", "none")
# Expression accents inked AROUND the balloon (comic emphasis marks).
# Accents are a SET, not a single choice — in the reference art a balloon
# routinely carries a halftone shadow AND ticks AND a star at once.
ACCENTS = ("halftone", "ticks", "impact", "puffs", "bolt")

# Premade *looks* for the "text" style — applied from the right-click menu and
# the inspector. A preset changes the appearance (font family, weight, colour,
# background frame, halo, alignment) but deliberately NEVER changes the font
# size or box dimensions, so switching presets keeps the size the user dialled
# in with the corner handles. Alignment is an int Qt.AlignmentFlag.
# "frame" is RGBA; alpha 0 = no background panel.
_AL = int(Qt.AlignmentFlag.AlignCenter)
_AL_LEFT = int(Qt.AlignmentFlag.AlignLeft)
# "halo" = thin outline, "bars" = Instagram-style per-line background bars,
# "frame" = RGBA of the background panel / bar colour (alpha 0 = none).
TEXT_PRESETS = [
    {"name": "Instagram",  "family": "Inter",      "bold": True,
     "color": (255, 255, 255), "frame": (0, 0, 0, 205), "bars": True, "align": _AL_LEFT},
    {"name": "简洁",      "family": "Inter",      "bold": True,
     "color": (255, 255, 255), "frame": (0, 0, 0, 0),   "align": _AL},
    {"name": "标题",   "family": "Anton",      "bold": False,
     "color": (255, 255, 255), "frame": (0, 0, 0, 0),   "align": _AL},
    {"name": "黄色醒目", "family": "Anton",      "bold": False,
     "color": (255, 214, 0),   "frame": (0, 0, 0, 0),   "halo": True, "align": _AL},
    {"name": "描边",    "family": "Inter",      "bold": True,
     "color": (255, 255, 255), "frame": (0, 0, 0, 0),   "halo": True, "align": _AL},
    {"name": "旁白条","family": "Inter",      "bold": True,
     "color": (255, 255, 255), "frame": (0, 0, 0, 165), "align": _AL},
]


# ---------------------------------------------------------------------------
# TailHandle — manual-drag red dot
# ---------------------------------------------------------------------------

class TailHandle(QGraphicsEllipseItem):
    """
    Red dot the user drags to repoint the tail.
    Manual drag (no ItemIsMovable) so it doesn't fight parent item movement.
    """

    def __init__(self, parent_bubble: "BubbleItem"):
        r = TAIL_DOT_R
        super().__init__(-r, -r, r * 2, r * 2, parent_bubble)
        self._bubble   = parent_bubble
        self._dragging = False

        self.setBrush(QBrush(QColor("#f87171")))
        self.setPen(QPen(QColor("#121212"), 2.0))
        self.setZValue(10)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        # Editing affordances are UI, not artwork. Keep the tail target the
        # same physical size when a small image is fitted above 100% zoom.
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.setToolTip("拖动以重新指向尾巴")

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._dragging:
            new_pos = self._bubble.mapFromScene(event.scenePos())
            self.setPos(new_pos)
            self._bubble.prepareGeometryChange()
            self._bubble.update()
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            event.accept()
        else:
            event.ignore()


# ---------------------------------------------------------------------------
# ResizeHandle
# ---------------------------------------------------------------------------

class ResizeHandle(QGraphicsRectItem):
    CURSORS = {
        "TL": Qt.CursorShape.SizeFDiagCursor, "TR": Qt.CursorShape.SizeBDiagCursor,
        "BL": Qt.CursorShape.SizeBDiagCursor, "BR": Qt.CursorShape.SizeFDiagCursor,
        "TC": Qt.CursorShape.SizeVerCursor,   "BC": Qt.CursorShape.SizeVerCursor,
        "ML": Qt.CursorShape.SizeHorCursor,   "MR": Qt.CursorShape.SizeHorCursor,
    }

    def __init__(self, anchor: str, parent_bubble: "BubbleItem"):
        s = HANDLE_SIZE
        super().__init__(-s / 2, -s / 2, s, s, parent_bubble)
        self._anchor      = anchor
        self._bubble      = parent_bubble
        self._dragging    = False
        self._hovered     = False
        self._start_mouse = QPointF()
        self._start_rect  = QRectF()
        self._start_font_pt = 0   # text-style font size at drag start (for scaling)

        self.setZValue(11)
        self.setCursor(QCursor(self.CURSORS[anchor]))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        # Handles remain a predictable screen size at every canvas zoom.
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setAcceptHoverEvents(True)

    # --- geometry: hit area is much larger than the drawn handle -------------

    def boundingRect(self) -> QRectF:
        h = HANDLE_HIT / 2
        return QRectF(-h, -h, HANDLE_HIT, HANDLE_HIT)

    def shape(self) -> QPainterPath:
        p = QPainterPath()
        p.addRect(self.boundingRect())
        return p

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Clean circular handle (Camtasia-style): white dot with a cyan ring,
        # growing/brightening on hover or drag for tactile feedback.
        active = self._hovered or self._dragging
        s = (HANDLE_SIZE + 4) if active else HANDLE_SIZE
        r = QRectF(-s / 2, -s / 2, s, s)
        # Soft dark halo so the dot reads on light backgrounds.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(15, 19, 25, 80))
        painter.drawEllipse(r.adjusted(-1.5, -1.5, 1.5, 1.5))
        painter.setBrush(QBrush(QColor("#fff2e8") if active else QColor("#ffffff")))
        painter.setPen(QPen(QColor("#ff8a3d"), 1.6))
        painter.drawEllipse(r)

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging    = True
            self._start_mouse = event.scenePos()
            self._start_rect  = QRectF(self._bubble.body_rect)
            self._start_font_pt = self._bubble.get_font().pointSize()
            self._bubble._resizing = True
            self.update()
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if not self._dragging:
            return
        delta = event.scenePos() - self._start_mouse
        r, a, MIN = QRectF(self._start_rect), self._anchor, 60

        if "L" in a:
            nl = r.left() + delta.x()
            if r.right() - nl >= MIN: r.setLeft(nl)
        if "R" in a:
            nr = r.right() + delta.x()
            if nr - r.left() >= MIN: r.setRight(nr)
        if "T" in a:
            nt = r.top() + delta.y()
            if r.bottom() - nt >= MIN: r.setTop(nt)
        if "B" in a:
            nb = r.bottom() + delta.y()
            if nb - r.top() >= MIN: r.setBottom(nb)

        # Text object: every handle resizes the FRAME freely (corners + edges),
        # like a normal selection box. The text wraps to the width and is
        # centred; use "文字适应框" to scale the text into the frame.
        if self._bubble.get_style() == "text":
            self._bubble._text_manual_h = True   # stop auto-hugging the height
            self._bubble.clear_fit()             # box changed → fit is stale
            self._bubble.set_body_rect(r)
        elif hasattr(self._bubble, "apply_resize"):
            # Speech bubbles: size the text to FILL the new bubble (fit-to-width),
            # so the text always catches up with the box — no empty margins.
            self._bubble.apply_resize(r)
        else:
            # Redaction boxes and other duck-typed items: plain frame resize.
            self._bubble.set_body_rect(r)
        event.accept()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._bubble._resizing = False
            self.update()
            stack = self._bubble._undo_stack()
            old_rect = self._start_rect
            new_rect = self._bubble.body_rect
            new_font_pt = self._bubble.get_font().pointSize()
            if old_rect != new_rect and stack:
                from undo_commands import ResizeBubbleCommand
                # Carry the font sizes so undo/redo restore the scaled text too.
                # Only real speech bubbles scale (text object + redaction don't).
                scales = (self._bubble.get_style() != "text"
                          and hasattr(self._bubble, "apply_resize"))
                old_pt = self._start_font_pt if scales else None
                new_pt = new_font_pt if scales else None
                stack.push(ResizeBubbleCommand(
                    self._bubble, old_rect, new_rect,
                    old_font_pt=old_pt, new_font_pt=new_pt))
        event.accept()


# ---------------------------------------------------------------------------
# BubbleItem
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Procedural shape builders (module level so the inspector's preview tiles
# can render the exact same silhouette the canvas draws)
# ---------------------------------------------------------------------------

def _scallop_path(r: QRectF) -> QPainterPath:
    """Scalloped 'flower' bubble: soft petal arcs around an ellipse."""
    cx, cy = r.center().x(), r.center().y()
    rx, ry = r.width() / 2, r.height() / 2
    n = 12
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n - math.pi / 2
        pts.append(QPointF(cx + math.cos(a) * rx * 0.86,
                           cy + math.sin(a) * ry * 0.86))
    path = QPainterPath(pts[0])
    for i in range(n):
        nxt = pts[(i + 1) % n]
        mid_a = 2 * math.pi * (i + 0.5) / n - math.pi / 2
        ctrl = QPointF(cx + math.cos(mid_a) * rx * 1.24,
                       cy + math.sin(mid_a) * ry * 1.24)
        path.quadTo(ctrl, nxt)
    path.closeSubpath()
    return path


def _burst_path(r: QRectF) -> QPainterPath:
    """Fine starburst: many short spikes — the 'zap' variant of spiky."""
    cx, cy = r.center().x(), r.center().y()
    rx, ry = r.width() / 2, r.height() / 2
    spikes = 26
    path = QPainterPath()
    for i in range(spikes * 2):
        angle = math.pi * i / spikes - math.pi / 2
        if i % 2 == 0:
            variation = 1.0 + 0.05 * math.sin(i * 2.3 + 0.6)
            px = cx + math.cos(angle) * rx * variation
            py = cy + math.sin(angle) * ry * variation
        else:
            px = cx + math.cos(angle) * rx * 0.80
            py = cy + math.sin(angle) * ry * 0.80
        if i == 0:
            path.moveTo(px, py)
        else:
            path.lineTo(px, py)
    path.closeSubpath()
    return path


def _wobbly_path(r: QRectF) -> QPainterPath:
    """Hand-drawn wobbly rectangle: each edge waves gently in and out."""
    amp = max(2.5, min(7.0, min(r.width(), r.height()) * 0.045))
    corners = [
        QPointF(r.left(), r.top()), QPointF(r.right(), r.top()),
        QPointF(r.right(), r.bottom()), QPointF(r.left(), r.bottom()),
    ]
    # Outward normals per edge (top, right, bottom, left)
    normals = [(0, -1), (1, 0), (0, 1), (-1, 0)]
    path = QPainterPath(corners[0])
    for e in range(4):
        p0 = corners[e]
        p1 = corners[(e + 1) % 4]
        ex, ey = p1.x() - p0.x(), p1.y() - p0.y()
        length = math.hypot(ex, ey) or 1
        segs = max(2, int(length / 60))
        nx, ny = normals[e]
        for s in range(segs):
            t0 = s / segs
            t1 = (s + 1) / segs
            mid_t = (t0 + t1) / 2
            sway = amp if s % 2 == 0 else -amp
            ctrl = QPointF(p0.x() + ex * mid_t + nx * sway,
                           p0.y() + ey * mid_t + ny * sway)
            path.quadTo(ctrl, QPointF(p0.x() + ex * t1, p0.y() + ey * t1))
    path.closeSubpath()
    return path


def _organic_oval_path(r: QRectF) -> QPainterPath:
    """
    Asymmetric comic oval using cubic bezier curves.
    It avoids the perfectly mechanical addEllipse() look.
    """
    cx, cy = r.center().x(), r.center().y()
    w2, h2 = r.width() / 2, r.height() / 2

    path = QPainterPath()
    path.moveTo(cx - w2 * 0.14, cy - h2 * 0.92)
    path.cubicTo(cx + w2 * 0.30, cy - h2 * 1.03,
                 cx + w2 * 0.88, cy - h2 * 0.76,
                 cx + w2 * 0.98, cy - h2 * 0.10)
    path.cubicTo(cx + w2 * 1.07, cy + h2 * 0.34,
                 cx + w2 * 0.64, cy + h2 * 0.87,
                 cx + w2 * 0.04, cy + h2 * 0.91)
    path.cubicTo(cx - w2 * 0.50, cy + h2 * 0.98,
                 cx - w2 * 1.02, cy + h2 * 0.58,
                 cx - w2 * 0.97, cy + h2 * 0.02)
    path.cubicTo(cx - w2 * 1.02, cy - h2 * 0.45,
                 cx - w2 * 0.64, cy - h2 * 0.86,
                 cx - w2 * 0.14, cy - h2 * 0.92)
    path.closeSubpath()
    return path


def _cloud_path(r: QRectF) -> QPainterPath:
    """
    Thought-cloud: 9 circles united into ONE path so the border traces the
    outer silhouette only — no internal rings (Audi logo effect).
    """
    w, h = r.width(), r.height()
    # (fraction-x, fraction-y, radius-fraction-of-min-dimension)
    bumps = [
        (0.14, 0.62, 0.22),
        (0.28, 0.42, 0.28),
        (0.48, 0.34, 0.31),
        (0.68, 0.42, 0.28),
        (0.84, 0.62, 0.22),
        (0.80, 0.78, 0.23),
        (0.62, 0.84, 0.26),
        (0.38, 0.84, 0.26),
        (0.18, 0.78, 0.21),
    ]
    # Seed with a core ellipse: the bumps sit in a RING, and on a wide or
    # short bubble that ring doesn't quite close over the middle, leaving a
    # literal hole in the cloud. The core guarantees a solid interior.
    path = QPainterPath()
    core = QPainterPath()
    core.addEllipse(r.center(), w * 0.34, h * 0.30)
    path = path.united(core)
    for fx, fy, fr in bumps:
        bx   = r.left() + fx * w
        by   = r.top()  + fy * h
        brad = fr * min(w, h)
        bump = QPainterPath()
        bump.addEllipse(QPointF(bx, by), brad, brad)
        path = path.united(bump)
    return path


def _spiky_path(r: QRectF) -> QPainterPath:
    """
    Dramatic starburst / shout bubble with 18 spikes of varying height.
    """
    cx, cy = r.center().x(), r.center().y()
    rx, ry = r.width() / 2, r.height() / 2
    spikes = 18
    path   = QPainterPath()

    for i in range(spikes * 2):
        angle = math.pi * i / spikes - math.pi / 2
        if i % 2 == 0:
            # Spike tip — vary outer radius for an organic, energetic look
            variation = 1.0 + 0.22 * math.sin(i * 1.9 + 0.8)
            px = cx + math.cos(angle) * rx * variation
            py = cy + math.sin(angle) * ry * variation
        else:
            # Valley between spikes
            px = cx + math.cos(angle) * rx * 0.64
            py = cy + math.sin(angle) * ry * 0.64
        if i == 0:
            path.moveTo(px, py)
        else:
            path.lineTo(px, py)
    path.closeSubpath()
    return path


def humanize(path: QPainterPath, amount: float = 1.0,
             seed: float = 0.0) -> QPainterPath:
    """Nudge a path off its perfect curve so it reads as drawn by hand.

    Authored beziers are mathematically smooth, and smooth is what makes a
    balloon look like clip-art. Resampling the outline and displacing each
    point by low-frequency noise gives the small wanders a pen makes, without
    turning the silhouette into mush.
    """
    if path.isEmpty() or amount <= 0:
        return path
    out = QPainterPath()
    for poly in path.toSubpathPolygons():
        pts = [poly.at(i) for i in range(poly.count())]
        if len(pts) < 8:
            continue
        if abs(pts[0].x() - pts[-1].x()) < 1e-6 and abs(pts[0].y() - pts[-1].y()) < 1e-6:
            pts = pts[:-1]
        n = len(pts)
        box = poly.boundingRect()
        scale = min(box.width(), box.height()) * 0.030 * amount
        moved = []
        for i, p in enumerate(pts):
            prv, nxt = pts[(i - 1) % n], pts[(i + 1) % n]
            dx, dy = nxt.x() - prv.x(), nxt.y() - prv.y()
            d = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / d, dx / d
            t = i / n
            # Three slow harmonics: a long lean, a medium bow, a light tremor.
            k = (math.sin(t * 2 * math.pi + seed) * 1.00
                 + math.sin(t * 2 * math.pi * 2.0 + seed * 1.7) * 0.55
                 + math.sin(t * 2 * math.pi * 3.0 + seed * 2.3) * 0.30)
            off = k * scale
            moved.append(QPointF(p.x() + nx * off, p.y() + ny * off))
        # Rebuild through quadratics so the wander stays smooth, not faceted.
        sub = QPainterPath(moved[0])
        for i in range(1, n + 1):
            a = moved[i % n]
            b = moved[(i + 1) % n]
            sub.quadTo(a, QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2))
        sub.closeSubpath()
        out = out.united(sub) if not out.isEmpty() else sub
    return out if not out.isEmpty() else path


def ink_stroke(path: QPainterPath, base_w: float, seed: float = 0.0) -> QPainterPath:
    """A filled ring that traces `path` with a VARYING width.

    Pen strokes from a real nib swell and thin as the hand moves. Drawing the
    outline with a constant-width QPen is what made every balloon look like
    clip-art; walking the path and modulating the offset gives an inked line.

    Each subpath is inked separately — traversing the whole path by percentage
    drew a stray line hopping from one closed loop to the next.
    """
    if base_w <= 0 or path.isEmpty():
        return QPainterPath()
    result = QPainterPath()
    for poly in path.toSubpathPolygons():
        pts = [poly.at(i) for i in range(poly.count())]
        if len(pts) > 1 and abs(pts[0].x() - pts[-1].x()) < 1e-6 \
                and abs(pts[0].y() - pts[-1].y()) < 1e-6:
            pts = pts[:-1]
        n = len(pts)
        if n < 6:
            continue
        outer, inner = [], []
        for i, p in enumerate(pts):
            prv = pts[(i - 1) % n]
            nxt = pts[(i + 1) % n]
            dx, dy = nxt.x() - prv.x(), nxt.y() - prv.y()
            d = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / d, dx / d
            t = i / n
            # Two slow swells plus a faster ripple: thick on the "pull" strokes,
            # thin where the nib lifts. Clamped so the line never breaks up.
            m = 0.72 + 0.42 * math.sin(t * 2 * math.pi * 2.0 + seed)
            m += 0.16 * math.sin(t * 2 * math.pi * 5.0 + seed * 1.7)
            m = max(0.52, min(1.40, m))
            half = base_w * m * 0.5
            outer.append(QPointF(p.x() + nx * half, p.y() + ny * half))
            inner.append(QPointF(p.x() - nx * half, p.y() - ny * half))
        ring = QPainterPath(outer[0])
        for q in outer[1:]:
            ring.lineTo(q)
        ring.lineTo(outer[0])
        ring.lineTo(inner[0])
        for q in reversed(inner[1:]):
            ring.lineTo(q)
        ring.closeSubpath()
        result = result.united(ring)
    return result


def _lobed_path(rect: QRectF, lobes) -> QPainterPath:
    """Union of organic lobes — the multi-balloon shapes.

    Built by uniting real blobs rather than hand-authoring one long bezier: the
    lobes come out genuinely round, differently sized, and the junction pinches
    naturally the way an inked balloon does.
    """
    path = QPainterPath()
    for (fx, fy, fw, fh) in lobes:
        sub = QRectF(rect.left() + rect.width() * (fx - fw / 2),
                     rect.top() + rect.height() * (fy - fh / 2),
                     rect.width() * fw, rect.height() * fh)
        path = path.united(_organic_oval_path(sub))
    return path


# Lobe layouts: deliberately different sizes per lobe, like the reference art.
TWIN_LOBES = ((0.34, 0.30, 0.68, 0.60), (0.63, 0.70, 0.74, 0.62))
TRIPLE_LOBES = ((0.31, 0.22, 0.58, 0.44), (0.67, 0.52, 0.64, 0.46),
                (0.35, 0.79, 0.64, 0.42))


# Per-shape wobble strength. Spiky/geometric shapes need less or they mush.
HAND_WOBBLE = {
    # Spiked silhouettes get none: displacing their points rounds the spikes
    # into waves and destroys the shape.
    "explode": 0.0, "spiky": 0.0, "burst": 0.0,
    "panel": 0.7, "softbox": 0.75, "puffy": 0.5, "scallop": 0.0,
    "wobble": 0.45, "round": 1.0, "oval": 1.0, "blob": 0.95, "cloud": 0.35,
}


def build_body_path(style: str, rect: QRectF, seed: float = 0.0) -> QPainterPath:
    """The silhouette for `style` sized to `rect`.

    Authored SVG shapes (shapes.SHAPE_PATHS) win; anything not in the library
    falls back to a procedural builder. Both the canvas and the inspector's
    preview tiles call this, so a tile can never disagree with what you get.
    """
    import shapes
    svg = shapes.path_for(style, rect)
    if svg is not None:
        # Wander the outline off its perfect curve — the difference between a
        # plotted vector and an inked balloon.
        return humanize(svg, HAND_WOBBLE.get(style, 1.0), seed)
    path = QPainterPath()
    if style == "twin":
        return humanize(_lobed_path(rect, TWIN_LOBES), 0.9, seed)
    if style == "triple":
        return humanize(_lobed_path(rect, TRIPLE_LOBES), 0.9, seed)
    if style == "rect":
        path.addRoundedRect(rect, 16, 16)
    elif style == "cloud":
        path = humanize(_cloud_path(rect), HAND_WOBBLE["cloud"], seed)
    elif style == "spiky":
        path = _spiky_path(rect)
    elif style == "scallop":
        path = _scallop_path(rect)
    elif style == "burst":
        path = _burst_path(rect)
    elif style == "wobbly":
        path = _wobbly_path(rect)
    elif style == "scrim":
        path.addRect(rect)     # sharp corners — Instagram/Snapchat look
    else:
        path = humanize(_organic_oval_path(rect), 1.0, seed)
    return path


class BubbleItem(QGraphicsItem):
    """Speech bubble on the photo canvas."""

    def __init__(self, scene_x: float, scene_y: float,
                 style: str = DEFAULT_STYLE, parent=None):
        super().__init__(parent)

        hw, hh = DEFAULT_W / 2, DEFAULT_H / 2
        self._body_rect = QRectF(-hw, -hh, DEFAULT_W, DEFAULT_H)

        self._style        = DEFAULT_STYLE
        self._fill_color   = QColor(255, 255, 255, 240)
        self._border_color = QColor(20, 20, 20)
        self._border_width = 2.0
        self._tail_position = "底部居中"
        self._tail_width = 40
        self._tail_shape = "wedge"     # wedge | curved | line | dots | none
        self._tail_count = 1           # 0-3 tails (Balloon+-style)
        self._text_alignment = int(Qt.AlignmentFlag.AlignCenter)
        # Text outline (comic lettering): 0 width = off.
        self._text_outline_color = QColor(0, 0, 0)
        self._text_outline_width = 0.0
        # Expression accents drawn AROUND the balloon (comic emphasis marks).
        # Lobed balloons (twin / triple) carry one text block per lobe.
        self._lobe_texts: list[str] = []
        self._editing_lobe: int = -1
        # Per-bubble phase so two balloons never ink identically.
        self._ink_seed: float = 0.0
        # Small, per-item vector caches. Keys include geometry rather than
        # relying on every setter/drag/undo path to invalidate them correctly.
        self._body_path_cache = None
        self._outline_path_cache = None
        self._ink_path_cache = []
        self._accents: set[str] = set()   # any combination of ACCENTS
        self._accent_amount = 50          # strength / density, %
        # Inset photo (Balloon+ "照片" tab): an image clipped to the bubble.
        self._inset_pixmap = None      # QPixmap | None
        self._inset_spacing = 25       # % inset from the bubble edge
        self._inset_blur = 3           # edge feather steps (0 = hard edge)
        self._inset_opacity = 100      # %
        self._inset_zoom = 100         # % of cover-fit scale
        self._inset_dx = 0             # pan, % of bubble width
        self._inset_dy = 0             # pan, % of bubble height
        self._inset_cache = None       # (key, QPixmap) rendered result
        self._outline_doc = None       # cached outline-tinted document clone
        self._outline_doc_key = None
        self._shadow = {
            "enabled": False,
            "color": QColor(0, 0, 0),
            "blur": 12,
            "offset_x": 4,
            "offset_y": 4,
            "opacity": 80,
        }

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,            True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,         True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable,          True)
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        self.setZValue(100)   # always float above overlay layers (z 1–99)
        self.setPos(scene_x, scene_y)
        self._ink_seed = (abs(hash((round(scene_x), round(scene_y))))
                          % 628) / 100.0

        # Undo tracking state
        self._drag_start_pos:  QPointF | None = None   # set on press, cleared on release
        self._text_before_edit: str | None    = None   # set on double-click
        self._is_editing:      bool           = False  # True while text editor is open
        self._layouting_text:  bool           = False  # guard against recursive auto-fit

        # Tail handles — primary + up to 2 extra (created lazily)
        self._tail = TailHandle(self)
        self._tail.setPos(0, hh + 54)
        self._tail.setVisible(False)
        self._extra_tails: list[TailHandle] = []

        # Text — default font is "Klee One" (manga/UTF-8 friendly, bundled).
        # Falls back gracefully to system fonts if the file isn't present.
        # Comic Neue Bold Italic: the slanted comic-lettering look from the
        # reference art. Klee One is a Japanese pen face and reads flat in Latin.
        _default_font = QFont("Comic Neue", 20)
        _default_font.setBold(True)
        _default_font.setItalic(True)
        self._font_pt: int = 20          # user's preferred point size; auto-shrink
                                          # may reduce it temporarily but will try
                                          # to restore it when text is removed.
        # Once the user picks a size (font-size slider / font change) the size is
        # authoritative: resizing the bubble no longer auto-shrinks the text — the
        # body grows to fit the chosen size instead. Applies to every bubble style.
        self._font_locked: bool = False
        # True only while a resize handle is being dragged. The font scales with
        # the box, so the body must NOT auto-grow to fit and fight the drag.
        self._resizing: bool = False
        # "text" style draws its glyphs manually (paint) with a dark halo so they
        # stay readable on any photo. Other styles render the live text item.
        self._text_halo: bool = False
        # Typography controls for the text style (Camtasia-like).
        self._letter_spacing: float = 0.0   # H. Spacing — extra px between glyphs
        self._line_spacing:   float = 0.0   # V. Spacing — extra px between lines
        self._fit_mode:  bool = False       # "文字适应框" active?
        self._fit_display: list = []        # [(line_text, pt, justify)] from fit
        self._line_bars: bool = False       # Instagram-style per-line bg bars
        self._text_manual_h: bool = False   # user set an explicit box height
                                             # (top/bottom handle) → don't auto-hug
        self._text_item = QGraphicsTextItem(self)
        self._text_item.setPlainText("在此输入...")
        self._text_item.setDefaultTextColor(QColor(15, 15, 15))
        self._text_item.setFont(_default_font)
        self._text_item.document().setDocumentMargin(0)
        self._text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self._text_item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        # Let clicks on the glyphs fall through to the parent bubble so it can be
        # dragged from anywhere — otherwise grabbing the text fails to move it.
        # Re-enabled only while the text editor is open (see mouseDoubleClickEvent).
        self._text_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        # Grow / shrink font in real time as the user types or pastes text
        self._text_item.document().contentsChanged.connect(self._on_text_contents_changed)
        self._reposition_text()

        # Resize handles
        self._handles: dict[str, ResizeHandle] = {}
        for anchor in ANCHORS:
            h = ResizeHandle(anchor, self)
            h.setVisible(False)
            self._handles[anchor] = h
        self._update_handle_positions()

        # User-saved "Default Balloon Settings" (appearance only; cheap no-op
        # when nothing was saved). Applied before style-specific overrides.
        try:
            import bubble_defaults
            bubble_defaults.apply_to_bubble(self)
            self._sync_tail_handles()
        except Exception:
            import logging
            logging.getLogger("sbe").exception("应用气泡默认值失败")

        if style != DEFAULT_STYLE:
            self.set_style(style)

    # ------------------------------------------------------------------
    # Getters (used by PropertiesPanel)
    # ------------------------------------------------------------------

    @property
    def body_rect(self) -> QRectF:
        return QRectF(self._body_rect)

    def get_style(self) -> str:
        return self._style

    def get_font(self) -> QFont:
        return QFont(self._text_item.font())

    def get_text_color(self) -> QColor:
        return QColor(self._text_item.defaultTextColor())

    def get_fill_color(self) -> QColor:
        return QColor(self._fill_color)

    def get_border_color(self) -> QColor:
        return QColor(self._border_color)

    def get_border_width(self) -> float:
        return self._border_width

    def get_text(self) -> str:
        return self._text_item.toPlainText()

    def get_text_alignment(self) -> int:
        return self._text_alignment

    def get_tail_position(self) -> str:
        return self._tail_position

    def get_tail_width(self) -> int:
        return self._tail_width

    def get_tail_shape(self) -> str:
        return self._tail_shape

    def get_tail_count(self) -> int:
        return self._tail_count

    def get_text_outline_color(self) -> QColor:
        return QColor(self._text_outline_color)

    def get_text_outline_width(self) -> float:
        return self._text_outline_width

    def get_shadow(self) -> dict:
        shadow = dict(self._shadow)
        shadow["color"] = QColor(self._shadow["color"])
        return shadow

    # ------------------------------------------------------------------
    # Setters
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Internal helper — scene notification for properties panel refresh
    # ------------------------------------------------------------------

    def _notify_changed(self):
        """Tell the scene that this bubble's visual properties changed.

        PhotoScene.bubble_changed is picked up by MainWindow, which refreshes
        the PropertiesPanel whenever the changed bubble is currently selected.
        """
        scene = self.scene()
        if scene and hasattr(scene, 'bubble_changed'):
            scene.bubble_changed.emit(self)

    # ------------------------------------------------------------------

    def set_style(self, style: str):
        # prepareGeometryChange() BEFORE we change anything so Qt invalidates
        # the OLD bounding rect (which included the tail area).
        # Without this, switching styles can leave ghost artefacts on screen.
        self.prepareGeometryChange()
        if self.scene():
            self.scene().update()   # force full scene repaint for good measure
        prev_style = self._style
        self._style = style
        # Classic thought-bubble pairing: switching to cloud with the default
        # wedge tail auto-picks the dot chain (user can still change it).
        if style == "cloud" and prev_style != "cloud" and self._tail_shape == "wedge":
            self._tail_shape = "dots"
        # Tails are hidden for styles that have no bubble body
        self._sync_tail_handles()

        # Switching AWAY from scrim: body_rect is still full-canvas-width and
        # flat, which breaks cloud/oval/spiky shape geometry (Audi logo effect).
        # Reset to the default speech-bubble dimensions before changing style.
        if prev_style == "scrim" and style != "scrim":
            hw, hh = DEFAULT_W / 2, DEFAULT_H / 2
            self._body_rect = QRectF(-hw, -hh, DEFAULT_W, DEFAULT_H)
            self._reposition_text()
            self._update_handle_positions()

        # Scrim: apply dark-strip defaults, compact height, snap to full width
        if style == "scrim" and prev_style != "scrim":
            self._fill_color   = QColor(0, 0, 0, 200)    # 78 % opacity — Instagram look
            self._border_width = 0.0
            self._text_item.setDefaultTextColor(QColor(255, 255, 255))
            # Compact height: ~7 % of scene height so it's a slim caption strip
            scene = self.scene()
            if scene and hasattr(scene, 'has_photo') and scene.has_photo():
                compact_h = max(44.0, scene.sceneRect().height() * 0.07)
            else:
                compact_h = 60.0
            # Font is derived from the strip height, so the caption stays
            # proportionate whether the photo is 800 px or 4 K. A fixed 24 pt
            # was a speck inside a 280 px strip on a high-resolution photo.
            scrim_font = QFont("Montserrat", max(10, int(compact_h * 0.34)))
            scrim_font.setBold(True)
            self._font_pt = scrim_font.pointSize()
            self._text_item.setFont(scrim_font)
            cur_w = self._body_rect.width()
            self._body_rect = QRectF(-cur_w / 2, -compact_h / 2, cur_w, compact_h)
            self._snap_to_scrim()

        # Caption: stroke-text overlay — no background, no tail, white text by default
        if style == "caption" and prev_style != "caption":
            self._fill_color   = QColor(0, 0, 0, 0)     # transparent background
            self._border_color = QColor(0, 0, 0)         # black outline
            self._border_width = 3.0                     # outline offset in px
            self._text_item.setDefaultTextColor(QColor(255, 255, 255))
            cap_font = QFont("Montserrat", 34)
            if not cap_font.exactMatch():
                cap_font = QFont("Arial Black", 34)
            cap_font.setCapitalization(QFont.Capitalization.AllUppercase)
            self._font_pt = 34
            self._text_item.setFont(cap_font)
            self._text_item.setVisible(False)            # paint() draws stroke text
            self._shadow = {
                "enabled": True,
                "color": QColor(0, 0, 0),
                "blur": 10,
                "offset_x": 2,
                "offset_y": 3,
                "opacity": 75,
            }
            self._reposition_text()

        # Leaving caption: restore text item and defaults
        if prev_style == "caption" and style != "caption":
            self._text_item.setVisible(True)
            self._text_item.setDefaultTextColor(QColor(15, 15, 15))

        # Text only: a real text object (Camtasia-style). Default to a readable
        # bold face — NOT a condensed display font — so long pasted text stays
        # legible. paint() renders the glyphs with a dark halo for contrast.
        if style == "text" and prev_style != "text":
            # Default text look = the Instagram preset: Inter Bold, white, on
            # dark rounded per-line bars, left-aligned.
            fam = "Inter" if "Inter" in QFontDatabase.families() else "Montserrat"
            text_font = QFont(fam, 32)
            text_font.setBold(True)
            self._font_pt = 32
            self._text_item.setFont(text_font)
            self._text_item.setDefaultTextColor(QColor(255, 255, 255))
            self._text_halo = False
            self._line_bars = True
            self._fill_color = QColor(0, 0, 0, 205)   # bar colour
            self._text_alignment = int(Qt.AlignmentFlag.AlignLeft)
            # A wide default box so pasted paragraphs wrap into a few lines
            # instead of a tall, narrow column that runs off the canvas.
            tw = 520.0
            cy = self._body_rect.center().y()
            self._body_rect = QRectF(-tw / 2, cy - DEFAULT_H / 2, tw, DEFAULT_H)
            self._reposition_text()

        # Leaving text for an opaque-body style: white-on-white would be
        # invisible, so restore the dark default (scrim/caption set their own).
        if prev_style == "text" and style not in ("text", "scrim", "caption"):
            self._text_item.setDefaultTextColor(QColor(15, 15, 15))
        if style != "text":
            self._text_halo = False
            self._line_bars = False

        # Entering a lobed style: seed the lobes from the existing single text so
        # nothing the user typed is silently dropped.
        if self.is_lobed():
            n = self.lobe_count()
            if not any(t.strip() for t in self._lobe_texts):
                current = self._text_item.toPlainText().strip()
                if current in ("", "在此输入..."):
                    self._lobe_texts = ["" for _ in range(n)]
                else:
                    parts = [p.strip() for p in current.split("\n") if p.strip()]
                    self._lobe_texts = [
                        parts[i] if i < len(parts) else "" for i in range(n)]
            while len(self._lobe_texts) < n:
                self._lobe_texts.append("")

        # The unreliable graphics-effect shadow is replaced by the manual halo.
        self._apply_text_shadow_effect(False)
        # text + caption paint their glyphs in paint(); hide the live item
        # except while the inline editor is open.
        self._text_item.setVisible(
            (self._style not in ("text", "caption") and not self.is_lobed())
            or self._is_editing)

        self.update()
        self._notify_changed()

    def _apply_text_shadow_effect(self, enabled: bool):
        """Toggle a soft drop shadow on the live text item (used by 'text' style
        so white overlay text stays legible over busy or light photos)."""
        if enabled:
            eff = QGraphicsDropShadowEffect()
            eff.setBlurRadius(8)
            eff.setColor(QColor(0, 0, 0, 200))
            eff.setOffset(0, 2)
            self._text_item.setGraphicsEffect(eff)
        else:
            self._text_item.setGraphicsEffect(None)

    def _text_panel_rect(self) -> QRectF:
        """Background-panel rect for the text style: hugs the rendered lines
        (widest line + padding) instead of spanning the whole wrap box."""
        r = self._body_rect
        pad_x, pad_y = 18, 10
        avail_w = max(10.0, r.width() - pad_x)
        blocks, total = self._text_blocks(avail_w)
        if not blocks:
            return QRectF(r)
        widest = 0.0
        for text, _font, fm, _h, _justify in blocks:
            if text:
                widest = max(widest, fm.horizontalAdvance(text))
        if widest <= 0:
            return QRectF(r)
        w = min(r.width(), widest + pad_x * 1.6)
        h = min(r.height(), total + pad_y * 1.6)
        align = self._text_alignment
        if align & int(Qt.AlignmentFlag.AlignLeft):
            x = r.left()
        elif align & int(Qt.AlignmentFlag.AlignRight):
            x = r.right() - w
        else:
            x = r.center().x() - w / 2
        return QRectF(x, r.center().y() - h / 2, w, h)

    def _paint_text_lines(self, painter: QPainter):
        """Render the text-style glyphs line by line: optional per-line bars
        (Instagram), a soft drop shadow, an optional thin outline, justification
        and V./H. spacing."""
        r = self._body_rect
        pad_x, pad_y = 18, 10
        avail_w = max(10.0, r.width() - pad_x)
        left = r.left() + pad_x / 2
        blocks, total = self._text_blocks(avail_w)
        if not blocks:
            return
        color = self._text_item.defaultTextColor()
        align = self._text_alignment
        painter.save()
        painter.setClipRect(r.adjusted(-2, -2, 2, 2))
        # Vertically centre the stack within the box.
        y = r.top() + pad_y + max(0.0, (r.height() - 2 * pad_y - total) / 2)
        for text, font, fm, h, justify in blocks:
            if text != "":
                painter.setFont(font)
                lw = fm.horizontalAdvance(text)
                if align & int(Qt.AlignmentFlag.AlignLeft):
                    x = left
                elif align & int(Qt.AlignmentFlag.AlignRight):
                    x = r.right() - pad_x / 2 - lw
                else:
                    x = r.center().x() - lw / 2
                baseline = y + fm.ascent()
                # Build per-word positions. Justified lines spread the extra
                # width across the gaps — but only when the stretch stays modest,
                # so short lines don't turn into ugly rivers of whitespace.
                words = text.split(" ")
                natural_gap = fm.horizontalAdvance(" ")
                gap = natural_gap
                stretched = False
                if justify and len(words) > 1:
                    word_w = sum(fm.horizontalAdvance(w) for w in words)
                    wide_gap = (avail_w - word_w) / (len(words) - 1)
                    if wide_gap <= natural_gap * 1.8:
                        gap = wide_gap
                        x = left
                        stretched = True
                # Instagram-style rounded background bar hugging the line.
                if self._line_bars:
                    bw = (avail_w if stretched else lw)
                    bar = QRectF(x - pad_x * 0.35, y,
                                 bw + pad_x * 0.7, fm.height())
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(self._fill_color if self._fill_color.alpha()
                                     else QColor(0, 0, 0, 200))
                    painter.drawRoundedRect(bar, 8, 8)

                def draw_line(pen_color):
                    painter.setPen(pen_color)
                    cx = x
                    for i, w in enumerate(words):
                        painter.drawText(QPointF(cx, baseline), w)
                        cx += fm.horizontalAdvance(w) + gap

                # Drop shadow is OPT-IN via the Shadow section — it used to be
                # forced on for every bar-less text object, which put a muddy
                # halo behind clean overlay text nobody asked for.
                if not self._line_bars and self._shadow.get("enabled", False):
                    so = max(1.0, font.pointSizeF() / 22.0)
                    sc = QColor(self._shadow.get("color", QColor(0, 0, 0)))
                    sc.setAlpha(round(max(0, min(100, self._shadow.get(
                        "opacity", 80))) * 255 / 100))
                    painter.save()
                    painter.translate(so + float(self._shadow.get("offset_x", 0)) * 0.25,
                                      so + float(self._shadow.get("offset_y", 0)) * 0.25)
                    draw_line(sc)
                    painter.restore()
                # Text outline is independent of the shadow and of the bars:
                # the halo preset or an explicit outline width should draw
                # whatever else is switched on.
                if self._text_halo or self._text_outline_width > 0:
                    if self._text_outline_width > 0:
                        o = self._text_outline_width
                        oc = QColor(self._text_outline_color)
                    else:
                        o = max(1.0, font.pointSizeF() / 26.0)
                        oc = QColor(0, 0, 0, 200)
                    for ox, oy in [(-o, -o), (o, -o), (-o, o), (o, o),
                                   (0, -o), (0, o), (-o, 0), (o, 0)]:
                        painter.save()
                        painter.translate(ox, oy)
                        draw_line(oc)
                        painter.restore()
                draw_line(color)
            y += h + self._line_spacing
        painter.restore()

    def apply_text_preset(self, preset: dict):
        """Apply a premade text *look* (font family/weight, colour, frame, halo,
        alignment) without touching the font size or box — so the size the user
        set with the corner handles survives switching between presets.

        Switches the bubble to the 'text' style first if needed."""
        if self._style != "text":
            self.set_style("text")
        fam = preset.get("family", "Montserrat")
        if fam not in QFontDatabase.families():
            fam = "Montserrat"
        # Keep the current point size; only change family + weight.
        font = QFont(self._text_item.font())
        font.setFamily(fam)
        font.setBold(bool(preset.get("bold", True)))
        self._text_item.setFont(font)
        r, g, b = preset.get("color", (255, 255, 255))
        self._text_item.setDefaultTextColor(QColor(r, g, b))
        self._fill_color = QColor(*preset.get("frame", (0, 0, 0, 0)))
        self._text_halo = bool(preset.get("halo", False))
        self._line_bars = bool(preset.get("bars", False))
        self._text_alignment = int(preset.get("align", self._text_alignment))
        self._reposition_text()
        self.update()
        self._notify_changed()

    # ------------------------------------------------------------------
    # Text typography: letter / line spacing + per-line "fit to box"
    # ------------------------------------------------------------------

    def get_letter_spacing(self) -> float:
        return self._letter_spacing

    def get_line_spacing(self) -> float:
        return self._line_spacing

    def set_letter_spacing(self, px: float):
        self._letter_spacing = float(px)
        # Mirror onto the live item too (editor + non-text styles).
        f = QFont(self._text_item.font())
        if px:
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, float(px))
        else:
            f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 100.0)
        self._text_item.setFont(f)
        self._reposition_text()
        self.update()
        self._notify_changed()

    def set_line_spacing(self, px: float):
        self._line_spacing = float(px)
        self._reposition_text()
        self.update()
        self._notify_changed()

    def _spaced_font(self, size=None) -> QFont:
        """A copy of the text font with the current letter spacing applied
        (optionally overriding the point size — used per line when fitting)."""
        f = QFont(self._text_item.font())
        if size is not None:
            f.setPointSizeF(float(size))
        if self._letter_spacing:
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,
                               float(self._letter_spacing))
        else:
            f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 100.0)
        return f

    def _text_display_lines(self, avail_w: float):
        """Return [(text, QFont, justify)] for each rendered line.

        In fit mode the precomputed block布局 is used (uniform size, justified
        edges); otherwise each paragraph is word-wrapped at the base size."""
        if self._fit_mode and self._fit_display:
            return [(t, self._spaced_font(s), j) for t, s, j in self._fit_display]
        paras = self._text_item.toPlainText().split("\n")
        base = self._spaced_font()
        fm = QFontMetricsF(base)
        out = []
        for p in paras:
            if p == "":
                out.append(("", base, False))
                continue
            cur = ""
            for word in p.split(" "):
                trial = word if cur == "" else cur + " " + word
                if cur == "" or fm.horizontalAdvance(trial) <= avail_w:
                    cur = trial
                else:
                    out.append((cur, base, False))
                    cur = word
            if cur != "":
                out.append((cur, base, False))
        return out

    def _text_blocks(self, avail_w: float):
        """[(text, font, metrics, height, justify)] + total stacked height."""
        blocks = []
        total = 0.0
        lines = self._text_display_lines(avail_w)
        for text, font, justify in lines:
            fm = QFontMetricsF(font)
            h = fm.height()
            blocks.append((text, font, fm, h, justify))
            total += h
        if len(lines) > 1:
            total += self._line_spacing * (len(lines) - 1)
        return blocks, total

    def clear_fit(self):
        if self._fit_mode:
            self._fit_mode = False
            self._fit_display = []

    def fit_text_to_box(self):
        """Camtasia-style "block text": re-flow ALL the text (ignoring the
        user's Enter breaks) into balanced lines, then size each line so it fills
        the box width with NATURAL spacing — no stretched-out gaps. The number of
        lines is chosen so the stack fills the box height. Balanced line widths
        keep the per-line sizes close, so it reads as one solid block."""
        if self._style != "text":
            return
        words = self._text_item.toPlainText().split()
        if not words:
            return
        pad_x, pad_y = 18, 10
        avail_w = max(10.0, self._body_rect.width() - pad_x)
        avail_h = max(10.0, self._body_rect.height() - 2 * pad_y)
        REF = 100.0
        fm_ref = QFontMetricsF(self._spaced_font(REF))
        space_w = fm_ref.horizontalAdvance(" ")
        word_w = [fm_ref.horizontalAdvance(w) for w in words]
        line_h_ref = fm_ref.height() / REF       # line height per point
        max_pt = avail_h / line_h_ref            # a line can't exceed box height

        def wrap(target: float):
            """Greedily wrap words so each line's REF width grows up to ~target.
            Returns list of (line_words, ref_width)."""
            lines, cur, cur_w = [], [], 0.0
            for wd, ww in zip(words, word_w):
                add = ww if not cur else ww + space_w
                if cur and cur_w + add > target:
                    lines.append((cur, cur_w))
                    cur, cur_w = [wd], ww
                else:
                    cur.append(wd)
                    cur_w += add
            if cur:
                lines.append((cur, cur_w))
            return lines

        def line_pt(ref_w: float) -> float:
            return min(max_pt, REF * avail_w / max(1.0, ref_w))

        def stack_height(lines):
            return sum(line_pt(w) * line_h_ref for _, w in lines) \
                + self._line_spacing * max(0, len(lines) - 1)

        # Bigger target → fewer/wider lines → smaller sizes → shorter stack, so
        # height decreases as target grows. Binary-search the target that fills
        # the height.
        lo, hi = max(word_w), max(word_w) + sum(word_w) + 1.0
        for _ in range(34):
            mid = (lo + hi) / 2
            if stack_height(wrap(mid)) > avail_h:
                lo = mid
            else:
                hi = mid
        lines = wrap(hi)
        # Keep the last (often short) remainder line from ballooning: cap it to
        # the size of the line above it.
        sizes = [line_pt(w) for _, w in lines]
        if len(sizes) >= 2:
            sizes[-1] = min(sizes[-1], sizes[-2])
        self._fit_display = [
            (" ".join(lw), max(6, round(s)),
             i != len(lines) - 1)          # justify all but the last (tiny snap)
            for i, ((lw, _w), s) in enumerate(zip(lines, sizes))
        ]
        self._fit_mode = True
        self.update()
        self._notify_changed()

    def set_fill_color(self, color: QColor):
        self._fill_color = color
        self.update()
        self._notify_changed()

    def set_border_color(self, color: QColor):
        self._border_color = color
        self.update()
        self._notify_changed()

    def set_border_width(self, w: float):
        self._border_width = w
        self.update()
        self._notify_changed()

    def set_body_rect(self, rect: QRectF):
        self.prepareGeometryChange()
        old = QRectF(self._body_rect)
        self._body_rect = QRectF(rect)
        # Scale the tails with the body. They used to snap back to a fixed 70 px
        # offset from the preset anchor, so enlarging a bubble left a stubby tail
        # and wiped out any tail the user had dragged into place.
        if old.width() > 1 and old.height() > 1:
            sx = rect.width() / old.width()
            sy = rect.height() / old.height()
            ocx, ocy = old.center().x(), old.center().y()
            ncx, ncy = rect.center().x(), rect.center().y()
            for handle in [self._tail] + self._extra_tails:
                p = handle.pos()
                handle.setPos(ncx + (p.x() - ocx) * sx,
                              ncy + (p.y() - ocy) * sy)
        # When the user manually resizes the bubble, try to restore the
        # preferred font size — the new (larger) rect may have room for it.
        cur = QFont(self._text_item.font())
        if 0 < cur.pointSize() < self._font_pt:
            cur.setPointSize(self._font_pt)
            self._text_item.setFont(cur)
        self._reposition_text()
        self._update_handle_positions()
        self.update()

    def set_font(self, font: QFont):
        # A manual font change ends per-line fit mode (one size again).
        self.clear_fit()
        # Preserve the active letter spacing across font swaps.
        if self._letter_spacing:
            font = QFont(font)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,
                                  float(self._letter_spacing))
        self._text_item.setFont(font)
        # Remember what the user actually wants so auto-shrink can restore it,
        # and lock it: the chosen size is now authoritative for this bubble.
        if font.pointSize() > 0:
            self._font_pt = font.pointSize()
            self._font_locked = True
        self._reposition_text()
        self.update()
        self._notify_changed()

    def _set_font_pt_silent(self, pt: int):
        """Set only the point size (no relayout / no notify). Used by the resize
        handles so text scales with the bubble; the following set_body_rect does
        the single布局 pass."""
        pt = int(pt)
        if pt <= 0:
            return
        f = QFont(self._text_item.font())
        f.setPointSize(pt)
        self._text_item.setFont(f)
        self._font_pt = pt
        self._font_locked = True

    def _fit_bounds(self, r: QRectF):
        """Text-safe (width, height) inside a bubble body of the current style —
        mirrors the wrap width used in _reposition_text_inner so a size that
        'fits' here won't get re-wrapped by the live text item."""
        style = self._style
        if style == "oval":
            return max(52.0, r.width() * OVAL_TEXT_FRAC), max(20.0, r.height() * 0.70)
        if style in ("rect", "scrim"):
            return max(52.0, r.width() - 18), max(20.0, r.height() - 28)
        if style == "caption":
            return max(52.0, r.width() - 12), max(20.0, r.height() - 16)
        if style in ("spiky", "burst"):
            # A starburst's SOLID core is only ~0.64 of its radius — the spikes
            # are empty space. Fitting text to the full box let it sail out past
            # the points.
            return max(52.0, r.width() * 0.62), max(20.0, r.height() * 0.58)
        if style == "scallop":
            return max(52.0, r.width() * 0.74), max(20.0, r.height() * 0.68)
        if style in ("twin", "triple"):
            # Lobed balloons pinch in the middle; keep text in the safe column.
            return max(52.0, r.width() * 0.62), max(20.0, r.height() * 0.78)
        return max(52.0, r.width() - 20), max(20.0, r.height() - 36)

    def _fit_font_for_rect(self, r: QRectF) -> int:
        """Largest point size at which the text FILLS the bubble in BOTH axes.

        The text is word-wrapped to the safe width, so as the size grows it
        reflows onto more lines and climbs to fill the safe height. A wide box
        keeps the text on one big line (width binds); a tall narrow box lets it
        wrap and grow to fill the height instead of leaving it empty. Explicit
        line breaks in the text are honoured."""
        from PyQt6.QtGui import QTextDocument, QTextOption
        text = self._text_item.toPlainText() or "在此输入..."
        sw, sh = self._fit_bounds(r)

        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setTextWidth(sw)
        opt = QTextOption()
        opt.setAlignment(Qt.AlignmentFlag(self._text_alignment))
        opt.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        doc.setDefaultTextOption(opt)
        base = QFont(self._text_item.font())

        lo, hi, best = 6, 400, 6
        while lo <= hi:
            mid = (lo + hi) // 2
            base.setPointSize(mid)
            doc.setDefaultFont(base)
            doc.setPlainText(text)
            # Height of the wrapped stack; idealWidth is the natural width the
            # longest line actually needs (<= sw unless a glyph can't fit).
            if doc.size().height() <= sh and doc.idealWidth() <= sw + 1.0:
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return best

    def apply_resize(self, rect: QRectF, font_pt: int | None = None):
        """Resize the body and size the text to FILL it (bigger bubble → bigger
        text, no empty space). Pass an explicit font_pt only for undo/redo."""
        if font_pt is None:
            font_pt = self._fit_font_for_rect(rect)
        if font_pt:
            self._set_font_pt_silent(font_pt)
        self.set_body_rect(rect)
        # Keep the inspector's Size slider in sync with the fitted size.
        self._notify_changed()

    def set_text_color(self, color: QColor):
        self._text_item.setDefaultTextColor(color)
        self.update()
        self._notify_changed()

    def set_text(self, text: str):
        # Changing the text invalidates per-line fit sizes.
        self.clear_fit()
        self._text_item.setPlainText(text)
        self._reposition_text()
        self.update()
        self._notify_changed()

    def set_text_alignment(self, alignment: int):
        self._text_alignment = alignment
        self._reposition_text()
        self.update()
        self._notify_changed()

    def set_tail_position(self, position: str):
        self.prepareGeometryChange()
        self._tail_position = position
        self._tail.setPos(self._tail_pos_for(position))
        self.update()
        self._notify_changed()

    # ------------------------------------------------------------------
    # Inset photo (Balloon+ "照片" tab)
    # ------------------------------------------------------------------

    def has_inset_photo(self) -> bool:
        return self._inset_pixmap is not None and not self._inset_pixmap.isNull()

    def get_inset_spacing(self) -> int:
        return self._inset_spacing

    def get_inset_blur(self) -> int:
        return self._inset_blur

    def get_inset_opacity(self) -> int:
        return self._inset_opacity

    def set_inset_pixmap(self, pixmap):
        self._inset_pixmap = pixmap
        self._inset_cache = None
        self.update()
        self._notify_changed()

    def set_inset_spacing(self, pct: int):
        self._inset_spacing = max(0, min(90, int(pct)))
        self._inset_cache = None
        self.update()
        self._notify_changed()

    def set_inset_blur(self, value: int):
        self._inset_blur = max(0, min(40, int(value)))
        self._inset_cache = None
        self.update()
        self._notify_changed()

    def set_inset_opacity(self, pct: int):
        self._inset_opacity = max(0, min(100, int(pct)))
        self._inset_cache = None
        self.update()
        self._notify_changed()

    def get_inset_zoom(self) -> int:
        return self._inset_zoom

    def get_inset_dx(self) -> int:
        return self._inset_dx

    def get_inset_dy(self) -> int:
        return self._inset_dy

    def set_inset_zoom(self, pct: int):
        self._inset_zoom = max(50, min(400, int(pct)))
        self._inset_cache = None
        self.update()
        self._notify_changed()

    def set_inset_offset(self, dx: int, dy: int):
        self._inset_dx = max(-100, min(100, int(dx)))
        self._inset_dy = max(-100, min(100, int(dy)))
        self._inset_cache = None
        self.update()
        self._notify_changed()

    def nudge_inset(self, dx_px: float, dy_px: float):
        """Pan the inset photo by a pixel delta (Alt+drag on the canvas)."""
        r = self._body_rect
        if r.width() <= 0 or r.height() <= 0:
            return
        self.set_inset_offset(self._inset_dx + round(dx_px / r.width() * 100),
                              self._inset_dy + round(dy_px / r.height() * 100))

    def clear_inset_photo(self):
        self._inset_pixmap = None
        self._inset_cache = None
        self.update()
        self._notify_changed()

    def _inset_shape_path(self) -> QPainterPath:
        """The body outline shrunk by `spacing` — the photo's clip region."""
        r = self._body_rect
        frac = self._inset_spacing / 100.0 * 0.5
        dx = r.width() * frac
        dy = r.height() * frac
        inner = r.adjusted(dx, dy, -dx, -dy)
        if inner.width() < 4 or inner.height() < 4:
            return QPainterPath()
        # Rebuild the body path at the inset size by scaling about the centre,
        # so the photo follows the bubble's silhouette (cloud stays cloudy).
        saved = self._body_rect
        try:
            self._body_rect = inner
            path = self._build_body_path()
        finally:
            self._body_rect = saved
        return path

    def _render_inset(self) -> "QPixmap | None":
        """Photo cropped to the inset silhouette, with a feathered edge.

        Rendered into an offscreen pixmap and cached: the alpha feather needs
        several composite passes and paint() runs on every repaint.
        """
        from PyQt6.QtGui import QPixmap, QRadialGradient
        if not self.has_inset_photo():
            return None
        path = self._inset_shape_path()
        if path.isEmpty():
            return None
        r = self._body_rect
        w, h = max(1, int(r.width())), max(1, int(r.height()))
        key = (id(self._inset_pixmap), w, h, self._inset_spacing,
               self._inset_blur, self._inset_opacity, self._style,
               self._inset_zoom, self._inset_dx, self._inset_dy)
        if self._inset_cache and self._inset_cache[0] == key:
            return self._inset_cache[1]

        out = QPixmap(w, h)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.translate(-r.left(), -r.top())

        # Cover-fit the source photo over the inset area.
        ip = self._inset_pixmap
        br = path.boundingRect()
        scale = max(br.width() / ip.width(), br.height() / ip.height())
        scale *= self._inset_zoom / 100.0
        sw, sh = ip.width() * scale, ip.height() * scale
        # Pan is expressed relative to the bubble, so it survives resizing, and
        # is clamped so the photo always covers the inset area — panning used to
        # be able to drag the image off its own edge and leave a bald patch.
        ox = r.width() * self._inset_dx / 100.0
        oy = r.height() * self._inset_dy / 100.0
        slack_x = max(0.0, (sw - br.width()) / 2.0)
        slack_y = max(0.0, (sh - br.height()) / 2.0)
        ox = max(-slack_x, min(ox, slack_x))
        oy = max(-slack_y, min(oy, slack_y))
        target = QRectF(br.center().x() - sw / 2 + ox,
                        br.center().y() - sh / 2 + oy, sw, sh)

        if self._inset_blur <= 0:
            p.setClipPath(path)
            p.drawPixmap(target, ip, QRectF(0, 0, ip.width(), ip.height()))
        else:
            # Feathered edge: draw the photo repeatedly through progressively
            # smaller clips at low alpha, which fades it out toward the border.
            steps = max(2, min(14, self._inset_blur))
            feather = min(br.width(), br.height()) * 0.06 * (self._inset_blur / 3.0)
            for i in range(steps):
                t = i / max(1, steps - 1)
                inset = feather * t
                sub = QPainterPath()
                sub.addPath(path)
                if inset > 0:
                    from PyQt6.QtGui import QTransform
                    cx, cy = br.center().x(), br.center().y()
                    fx = max(0.05, 1.0 - inset * 2 / max(1.0, br.width()))
                    fy = max(0.05, 1.0 - inset * 2 / max(1.0, br.height()))
                    tr = QTransform().translate(cx, cy).scale(fx, fy).translate(-cx, -cy)
                    sub = tr.map(path)
                p.save()
                p.setClipPath(sub)
                p.setOpacity(1.0 / steps * 1.8)
                p.drawPixmap(target, ip, QRectF(0, 0, ip.width(), ip.height()))
                p.restore()
        p.end()
        self._inset_cache = (key, out)
        return out

    def _paint_inset_photo(self, painter: QPainter):
        pm = self._render_inset()
        if pm is None:
            return
        r = self._body_rect
        painter.save()
        painter.setOpacity(self._inset_opacity / 100.0)
        painter.drawPixmap(QPointF(r.left(), r.top()), pm)
        painter.restore()

    def scale_for_canvas(self, canvas_w: float, canvas_h: float):
        """Size a NEWLY created bubble to suit the photo's resolution.

        A fixed 220x130 default is invisible on a 4000 px photo and enormous on
        a 400 px one, so the body, font, tail width and tail reach all scale by
        one factor derived from the canvas. Called once, right after creation.
        """
        if canvas_w <= 0 or canvas_h <= 0:
            return
        if self._style == "scrim":
            # set_style ran before the item had a scene, so it fell back to a
            # 60 px strip. Now that the canvas size is known, size the strip and
            # its caption from it: full width, ~7 % tall, font from that height.
            strip_h = max(44.0, canvas_h * 0.07)
            self.prepareGeometryChange()
            self._body_rect = QRectF(-canvas_w / 2, -strip_h / 2,
                                     canvas_w, strip_h)
            f = QFont(self._text_item.font())
            f.setPointSize(max(10, int(strip_h * 0.34)))
            self._font_pt = f.pointSize()
            self._text_item.setFont(f)
            self._reposition_text()
            self._update_handle_positions()
            self.update()
            return
        # Size from the frame's AREA, not its width: width alone swaps when the
        # photo is rotated, so bubbles added after a rotation came out visibly
        # smaller on the very same picture. sqrt(w*h) is rotation-invariant.
        target_w = math.sqrt(canvas_w * canvas_h) * 0.21
        factor = target_w / DEFAULT_W
        # Keep a new bubble compact on low-resolution portraits. The old 0.5
        # floor made a 220 px default at least 110 px wide even on a 320 px
        # image, before the view enlarged it again to fit the window.
        max_by_h = (canvas_h * 0.24) / DEFAULT_H
        factor = max(0.18, min(factor, max_by_h, 12.0))
        if abs(factor - 1.0) < 0.02:
            return

        self.prepareGeometryChange()
        r = self._body_rect
        self._body_rect = QRectF(-r.width() * factor / 2, -r.height() * factor / 2,
                                 r.width() * factor, r.height() * factor)
        self._tail_width = max(6, int(round(self._tail_width * factor)))
        # The outline must scale too, or a 2 px border is a hairline on a 4 K photo.
        self._border_width *= factor
        font = QFont(self._text_item.font())
        pt = max(6, int(round(max(6, font.pointSize()) * factor)))
        font.setPointSize(pt)
        self._font_pt = pt
        self._text_item.setFont(font)
        if self._text_outline_width > 0:
            self._text_outline_width *= factor
        sh = self._shadow
        sh["blur"] = int(round(sh.get("blur", 0) * factor))
        sh["offset_x"] = int(round(sh.get("offset_x", 0) * factor))
        sh["offset_y"] = int(round(sh.get("offset_y", 0) * factor))
        # Tail tips are in local coords — scale them with the body.
        for handle in [self._tail] + self._extra_tails:
            p = handle.pos()
            handle.setPos(p.x() * factor, p.y() * factor)
        self._reposition_text()
        self._update_handle_positions()
        self.update()

    def set_tail_width(self, width: int):
        self.prepareGeometryChange()
        self._tail_width = max(6, int(width))
        self.update()
        self._notify_changed()

    def set_tail_shape(self, shape: str):
        if shape not in TAIL_SHAPES:
            return
        self.prepareGeometryChange()
        self._tail_shape = shape
        self._sync_tail_handles()
        self.update()
        self._notify_changed()

    def set_tail_count(self, count: int):
        self.prepareGeometryChange()
        self._tail_count = max(0, min(3, int(count)))
        self._sync_tail_handles()
        self.update()
        self._notify_changed()

    def set_text_outline(self, color: QColor, width: float):
        self._text_outline_color = QColor(color)
        self._text_outline_width = max(0.0, float(width))
        self._outline_doc_key = None   # invalidate cache
        self.update()
        self._notify_changed()

    # ------------------------------------------------------------------
    # Tail helpers (shape / count)
    # ------------------------------------------------------------------

    def _tails_active(self) -> bool:
        return (self._style in TAILED_STYLES
                and self._tail_shape != "none"
                and self._tail_count > 0)

    def _tail_tips(self) -> list[QPointF]:
        """Positions (local coords) of the active tail tips."""
        if not self._tails_active():
            return []
        tips = [self._tail.pos()]
        for h in self._extra_tails[:self._tail_count - 1]:
            tips.append(h.pos())
        return tips[:self._tail_count]

    def _sync_tail_handles(self):
        """Create/show/hide tail handles to match count, shape and style."""
        # Lazily create the extra handles at spread-out default positions.
        while len(self._extra_tails) < max(0, self._tail_count - 1):
            h = TailHandle(self)
            r = self._body_rect
            idx = len(self._extra_tails)
            # Offsets are proportional to the body, so extra tails stay sane on
            # a bubble scaled up for a high-resolution photo.
            drop = r.bottom() + r.height() * 0.55
            if idx == 0:
                h.setPos(r.left() + r.width() * 0.22, drop)
            else:
                h.setPos(r.right() - r.width() * 0.22, drop)
            self._extra_tails.append(h)
        active = self._tails_active()
        show = self.isSelected() and active
        self._tail.setVisible(show)
        for i, h in enumerate(self._extra_tails):
            h.setVisible(show and i < self._tail_count - 1)

    def set_shadow(self, shadow: dict):
        old_enabled = self._shadow.get("enabled", False)
        new_shadow = dict(self._shadow)
        new_shadow.update(shadow)
        new_shadow["color"] = QColor(new_shadow.get("color", QColor(0, 0, 0)))
        if old_enabled or new_shadow.get("enabled", False):
            self.prepareGeometryChange()
        self._shadow = new_shadow
        self.update()
        self._notify_changed()

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------

    def _reposition_text(self):
        if self._layouting_text:
            return
        self._layouting_text = True
        try:
            self._reposition_text_inner()
        finally:
            self._layouting_text = False

    def _reposition_text_inner(self):
        r     = self._body_rect
        style = self._style

        current_font = QFont(self._text_item.font())
        if 0 < current_font.pointSize() < self._font_pt:
            current_font.setPointSize(self._font_pt)
            self._text_item.setFont(current_font)

        # "text" is a Camtasia-style text object: the font size is authoritative
        # (no auto-shrink), the box wraps text to its width and hugs its height.
        # Corner-resize scales the font (see ResizeHandle); side handles rewrap.
        if style == "text":
            pad_x, pad_y = 18, 10
            tw = max(40.0, r.width() - pad_x)
            # Keep the live editor's wrap + alignment in sync (used while typing).
            self._text_item.setTextWidth(tw)
            self._text_item.document().setDocumentMargin(0)
            opt = self._text_item.document().defaultTextOption()
            opt.setAlignment(Qt.AlignmentFlag(self._text_alignment))
            self._text_item.document().setDefaultTextOption(opt)
            self._text_item.setPos(r.left() + (r.width() - tw) / 2,
                                   r.top() + pad_y)
            # In fit mode (or when the user set an explicit height via the
            # top/bottom handle) the box stays put and text fills/centres in it.
            # Otherwise the box hugs the rendered line stack (honours V. Spacing).
            if not self._fit_mode and not self._text_manual_h:
                _blocks, total = self._text_blocks(tw)
                new_h = total + pad_y * 2
                # Never let a pasted paragraph grow the box past the canvas.
                scene = self.scene()
                if scene is not None:
                    new_h = min(new_h, scene.sceneRect().height() * 0.92)
                if abs(r.height() - new_h) > 0.5:
                    self.prepareGeometryChange()
                    cy = r.center().y()
                    self._body_rect = QRectF(r.left(), cy - new_h / 2,
                                             r.width(), new_h)
                    if hasattr(self, "_handles"):
                        self._update_handle_positions()
            return

        # Text layout is intentionally generous: pasted speech should stay
        # readable and use the centre of the bubble before auto-shrink kicks in.
        if style == "oval":
            # Use most of the centre of the bubble.  The previous 55% width
            # was safe near the top/bottom of an ellipse but made ordinary
            # pasted sentences wrap into too many lines and shrink too early.
            # Ovals are narrow near the top. Keep text in a speech-safe column
            # and bias it downward so the first line cannot escape the cap.
            tw    = max(52, r.width() * OVAL_TEXT_FRAC)
            v_pad = 54
            max_h = max(DEFAULT_H, r.width() * 1.35)
        elif style in ("rect", "scrim"):
            tw    = max(52, r.width() - 18)
            v_pad = 14
            max_h = max(DEFAULT_H, r.width() * 0.62)
        elif style == "caption":
            tw    = max(52, r.width() - 12)
            v_pad = 8
            max_h = max(DEFAULT_H, r.width() * 0.55)
        elif style in ("spiky", "burst"):
            # Match _fit_bounds: wrap inside the solid core, not the spikes.
            tw    = max(52, r.width() * 0.62)
            v_pad = r.height() * 0.42
            max_h = max(DEFAULT_H, r.width() * 0.80)
        elif style == "scallop":
            tw    = max(52, r.width() * 0.74)
            v_pad = r.height() * 0.32
            max_h = max(DEFAULT_H, r.width() * 0.85)
        elif style in ("twin", "triple"):
            tw    = max(52, r.width() * 0.62)
            v_pad = r.height() * 0.22
            max_h = max(DEFAULT_H, r.width() * 1.5)
        else:
            tw    = max(52, r.width() - 20)
            v_pad = 18
            max_h = max(DEFAULT_H, r.width() * 0.95)

        self._text_item.setTextWidth(tw)
        self._text_item.document().setDocumentMargin(0)
        opt = self._text_item.document().defaultTextOption()
        opt.setAlignment(Qt.AlignmentFlag(self._text_alignment))
        self._text_item.document().setDefaultTextOption(opt)

        th       = self._text_item.boundingRect().height()
        needed_h = th + v_pad

        if self._font_locked:
            # User-chosen size is authoritative: never auto-shrink. Let the body
            # grow vertically to fit the text at the chosen size (capped to the
            # canvas so a pasted wall of text can't escape the frame).
            scene = self.scene()
            ceil_h = scene.sceneRect().height() * 0.92 if scene is not None else needed_h
            # Grow the body to fit the text at the chosen size, but never past the
            # canvas ceiling (a pasted wall of text stays on-frame, may clip).
            max_h  = min(max(needed_h, DEFAULT_H), ceil_h)
        # Font shrink: keep the preferred size until the bubble would become
        # visually oversized. This preserves readable 10-24 word pasted text.
        elif needed_h > max_h:
            font = QFont(self._text_item.font())
            min_pt = max(9, min(self._font_pt, 12))
            while font.pointSize() > min_pt and needed_h > max_h:
                font.setPointSize(font.pointSize() - 1)
                self._text_item.setFont(font)
                self._text_item.setTextWidth(tw)
                self._text_item.document().setDocumentMargin(0)
                th       = self._text_item.boundingRect().height()
                needed_h = th + v_pad

        # Primary behaviour: grow the bubble body to fit the text.
        # While a resize handle is being dragged the user is authoritatively
        # setting the box size (and the font scales with it), so don't grow.
        if r.height() < needed_h and not self._resizing:
            self.prepareGeometryChange()
            cx, cy = r.center().x(), r.center().y()
            new_h = min(needed_h, max_h)
            self._body_rect = QRectF(r.left(), cy - new_h / 2,
                                     r.width(), new_h)
            r = self._body_rect
            if hasattr(self, "_handles"):
                self._update_handle_positions()

        # Final guard: whatever font the user picked, the rendered text must not
        # spill outside the shape's safe area. Swapping families at a fixed point
        # size is the case that broke — Dela Gothic at 40 pt is far taller and
        # wider than Klee at 40 pt, and a locked size skipped the auto-shrink.
        safe_w, safe_h = self._fit_bounds(r)
        guard_font = QFont(self._text_item.font())
        steps = 0
        while guard_font.pointSize() > 7 and steps < 80:
            self._text_item.setTextWidth(min(tw, safe_w))
            box = self._text_item.boundingRect()
            if box.height() <= safe_h + 0.5 and box.width() <= safe_w + 0.5:
                break
            guard_font.setPointSize(guard_font.pointSize() - 1)
            self._text_item.setFont(guard_font)
            steps += 1
        if steps:
            # Remember the size that actually fits, so a later relayout doesn't
            # restore the too-big one from _font_pt.
            self._font_pt = guard_font.pointSize()
            tw = min(tw, safe_w)
            self._text_item.setTextWidth(tw)
            th = self._text_item.boundingRect().height()

        # Centre text inside a padded safe area. This matters most for ovals,
        # where the visible body narrows near the top and bottom.
        top_pad = v_pad * 0.72 if style == "oval" else v_pad / 2
        safe_h = max(20.0, r.height() - v_pad)
        self._text_item.setPos(
            r.left() + (r.width() - tw) / 2,
            r.top()  + top_pad + (safe_h - th) / 2,
        )

    def _on_text_contents_changed(self):
        """Called whenever the text document changes (typing or paste).

        Re-runs布局 so the bubble grows or shrinks font in real time.
        """
        try:
            # Editing the content invalidates any per-line "fit" sizes.
            if self._is_editing:
                self.clear_fit()
            self._reposition_text()
            self.update()
        except Exception:
            import logging
            logging.getLogger("sbe").exception("气泡文字排版失败")

    def _update_handle_positions(self):
        r  = self._body_rect
        cx, cy = r.center().x(), r.center().y()
        l, t, ri, b = r.left(), r.top(), r.right(), r.bottom()
        for anchor, (x, y) in {
            "TL":(l,t),"TC":(cx,t),"TR":(ri,t),
            "ML":(l,cy),            "MR":(ri,cy),
            "BL":(l,b),"BC":(cx,b),"BR":(ri,b),
        }.items():
            self._handles[anchor].setPos(x, y)

    def _tail_pos_for(self, position: str) -> QPointF:
        r = self._body_rect
        # Reach scales with the bubble: a fixed 70 px stub looked absurd on a
        # bubble sized for a 4 K photo.
        offset = max(28.0, min(r.width(), r.height()) * 0.55)
        positions = {
            "左上": QPointF(r.left() + r.width() * 0.25, r.top() - offset),
            "顶部居中": QPointF(r.center().x(), r.top() - offset),
            "右上": QPointF(r.right() - r.width() * 0.25, r.top() - offset),
            "右": QPointF(r.right() + offset, r.center().y()),
            "右下": QPointF(r.right() - r.width() * 0.25, r.bottom() + offset),
            "底部居中": QPointF(r.center().x(), r.bottom() + offset),
            "左下": QPointF(r.left() + r.width() * 0.25, r.bottom() + offset),
            "左": QPointF(r.left() - offset, r.center().y()),
        }
        return positions.get(position, positions["底部居中"])

    # ------------------------------------------------------------------
    # QGraphicsItem overrides
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        pad = HANDLE_SIZE + 2
        r   = self._body_rect.adjusted(-pad, -pad, pad, pad)
        if self._style in ("text", "scrim", "caption"):
            return self._shadow_adjusted_rect(r)
        # Curved tails bow sideways, so pad tail tips generously.
        acc = self._accent_margin()
        if acc:
            r = r.adjusted(-acc, -acc, acc, acc)
        m = TAIL_DOT_R + self._tail_width
        for tip in self._tail_tips():
            r = r.united(QRectF(tip.x() - m, tip.y() - m, m * 2, m * 2))
        # Even with 0 active tails the handle may still be visible mid-toggle.
        t = self._tail.pos()
        r = r.united(QRectF(t.x() - TAIL_DOT_R, t.y() - TAIL_DOT_R,
                            TAIL_DOT_R * 2, TAIL_DOT_R * 2))
        return self._shadow_adjusted_rect(r)

    def _shadow_adjusted_rect(self, rect: QRectF) -> QRectF:
        if not self._shadow.get("enabled", False):
            return rect
        blur = float(self._shadow.get("blur", 0))
        ox = float(self._shadow.get("offset_x", 0))
        oy = float(self._shadow.get("offset_y", 0))
        shadow = rect.translated(ox, oy).adjusted(-blur, -blur, blur, blur)
        return rect.united(shadow)

    def shape(self) -> QPainterPath:
        if self._style in ("text", "scrim", "caption"):
            p = QPainterPath()
            p.addRect(self._body_rect)
            return p
        return self._outline_path()

    def paint(self, painter: QPainter,
              option: QStyleOptionGraphicsItem,
              widget: QWidget | None = None):

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._style == "text":
            # Optional rounded background panel. Two rules learned the hard way:
            #  - never together with per-line bars (the panel painted a long
            #    slab behind the tight bars, which looked broken);
            #  - hug the TEXT, not the layout box, or short text sits on a
            #    panel stretching the full wrap width.
            if self._fill_color.alpha() > 0 and not self._line_bars:
                panel = self._text_panel_rect()
                path = QPainterPath()
                path.addRoundedRect(panel, 16, 16)
                self._paint_shadow(painter, path)
                painter.setBrush(QBrush(self._fill_color))
                if self._border_width > 0:
                    painter.setPen(QPen(self._border_color, self._border_width,
                                        Qt.PenStyle.SolidLine,
                                        Qt.PenCapStyle.RoundCap,
                                        Qt.PenJoinStyle.RoundJoin))
                else:
                    painter.setPen(QPen(Qt.PenStyle.NoPen))
                painter.drawPath(path)
            # Glyphs drawn line-by-line (dark halo for contrast). This path
            # honours V./H. spacing and per-line "fit to box" sizes. While the
            # inline editor is open the live text item shows instead.
            if self._text_item.toPlainText() and not self._is_editing:
                self._paint_text_lines(painter)
            # Selection indicator when selected
            if self.isSelected():
                self._paint_selection_frame(
                    painter, self._body_rect.adjusted(2, 2, -2, -2))
            return

        if self._style == "caption":
            # Stroke text overlay: optional background rect, then outline
            # (8-direction shadow using _border_color + _border_width as offset),
            # then text fill (_text_item.defaultTextColor).
            # _text_item is hidden; everything is painted manually here.
            text = self._text_item.toPlainText()
            if text:
                painter.setFont(self._text_item.font())
                tp    = self._text_item.pos()
                tw    = self._text_item.textWidth()
                th    = self._text_item.boundingRect().height()
                tr    = QRectF(tp.x(), tp.y(), tw, th)
                flags = (int(Qt.AlignmentFlag.AlignCenter) |
                         int(Qt.TextFlag.TextWordWrap))
                # Background rect — only drawn when fill has any opacity
                if self._fill_color.alpha() > 0:
                    pad = 6
                    painter.fillRect(tr.adjusted(-pad, -pad, pad, pad),
                                     self._fill_color)
                # Outline via 8-direction offset; thickness controlled by border_width
                off = max(1, round(self._border_width)) if self._border_width > 0 else 0
                if off > 0:
                    painter.setPen(self._border_color)
                    for ox, oy in [(-off,-off),(0,-off),(off,-off),
                                   (-off,  0),          (off,  0),
                                   (-off, off),(0, off),(off, off)]:
                        painter.drawText(tr.adjusted(ox, oy, ox, oy), flags, text)
                # Text colour fill on top
                painter.setPen(self._text_item.defaultTextColor())
                painter.drawText(tr, flags, text)
            if self.isSelected():
                self._paint_selection_frame(
                    painter, self._body_rect.adjusted(2, 2, -2, -2))
            return

        pen   = QPen(self._border_color, self._border_width,
                     Qt.PenStyle.SolidLine,
                     Qt.PenCapStyle.RoundCap,
                     Qt.PenJoinStyle.RoundJoin)
        brush = QBrush(self._fill_color)

        if self._style == "scrim":
            self._paint_shadow(painter, self._build_body_path())
            # Dark semi-transparent horizontal strip — full-width, no tail
            painter.setBrush(brush)
            painter.setPen(pen if self._border_width > 0
                           else QPen(Qt.PenStyle.NoPen))
            painter.drawPath(self._build_body_path())
            self._paint_inset_photo(painter)

        else:
            # Body + all solid tails as one seamless outline.
            path = self._outline_path()
            # Accents go UNDER the balloon so the halftone reads as a shadow.
            self._paint_accents(painter, path)
            self._paint_shadow(painter, path)
            painter.setBrush(brush)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(path)
            # Ink the outline with a variable-width stroke instead of a uniform
            # pen — this is what makes it read as drawn rather than plotted.
            if self._border_width > 0:
                painter.setBrush(QBrush(self._border_color))
                painter.drawPath(self._cached_ink_stroke(
                    path, self._border_width, self._ink_seed))
            # Dot-chain tails are separate circles: fill them, then ink them.
            # They used to inherit the ink brush and render solid black.
            if self._tail_shape == "dots":
                for tip in self._tail_tips():
                    dots = self._thought_dots_path(tip)
                    if dots.isEmpty():
                        continue
                    painter.setBrush(brush)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawPath(dots)
                    if self._border_width > 0:
                        painter.setBrush(QBrush(self._border_color))
                        painter.drawPath(self._cached_ink_stroke(
                            dots, self._border_width, self._ink_seed + 1.3))
            self._paint_accents_over(painter, path)
            if self.is_lobed():
                self._paint_lobe_texts(painter)
            # Inset photo sits on the fill, under the text.
            self._paint_inset_photo(painter)

        # Comic-lettering outline behind the live glyphs — the child text item
        # paints after this, so its fill lands exactly on top.
        self._paint_live_text_outline(painter)

        # Selection dashed rectangle
        if self.isSelected():
            self._paint_selection_frame(painter, self._body_rect)

    # ------------------------------------------------------------------
    # Shape builders
    # ------------------------------------------------------------------

    def _build_body_path(self) -> QPainterPath:
        key = (self._style, QRectF(self._body_rect), self._ink_seed)
        if self._body_path_cache is None or self._body_path_cache[0] != key:
            self._body_path_cache = (
                key, build_body_path(self._style, self._body_rect, self._ink_seed))
        # QPainterPath is implicitly shared; a caller can mutate its copy
        # without corrupting the cached vector geometry.
        return QPainterPath(self._body_path_cache[1])

    def _cached_ink_stroke(self, path, width, seed):
        for source, cached_width, cached_seed, stroke in self._ink_path_cache:
            if cached_width == width and cached_seed == seed and source == path:
                return QPainterPath(stroke)
        stroke = ink_stroke(path, width, seed)
        # One body plus up to three dot tails; never accumulate drag history.
        self._ink_path_cache.append((QPainterPath(path), width, seed, stroke))
        self._ink_path_cache = self._ink_path_cache[-4:]
        return QPainterPath(stroke)


    def _paint_live_text_outline(self, painter: QPainter):
        """Draw the bubble text in the outline colour at 8 offsets so the child
        text item's fill glyphs get a comic-lettering stroke. Only for styles
        that render text via the live child item ("text"/"caption" paint their
        own glyphs and handle outlines themselves)."""
        if (self._text_outline_width <= 0
                or self._style in ("text", "caption")
                or self._is_editing
                or not self._text_item.isVisible()
                or not self._text_item.toPlainText().strip()):
            return
        doc = self._text_item.document()
        key = (doc.toPlainText(), self._text_item.font().key(),
               self._text_outline_color.rgba(), float(doc.textWidth()),
               int(self._text_alignment))
        if self._outline_doc is None or key != self._outline_doc_key:
            from PyQt6.QtGui import QTextCursor, QTextCharFormat
            clone = doc.clone()
            clone.setDefaultFont(self._text_item.font())
            clone.setDocumentMargin(doc.documentMargin())
            clone.setDefaultTextOption(doc.defaultTextOption())
            clone.setTextWidth(doc.textWidth())
            cur = QTextCursor(clone)
            cur.select(QTextCursor.SelectionType.Document)
            fmt = QTextCharFormat()
            fmt.setForeground(QBrush(self._text_outline_color))
            cur.mergeCharFormat(fmt)
            self._outline_doc = clone
            self._outline_doc_key = key
        w = self._text_outline_width
        pos = self._text_item.pos()
        for ox, oy in ((-w, -w), (0, -w), (w, -w), (-w, 0),
                       (w, 0), (-w, w), (0, w), (w, w)):
            painter.save()
            painter.translate(pos.x() + ox, pos.y() + oy)
            self._outline_doc.drawContents(painter)
            painter.restore()

    # ------------------------------------------------------------------
    # Expression accents (comic emphasis marks around the balloon)
    # ------------------------------------------------------------------

    def get_accents(self) -> set:
        return set(self._accents)

    def has_accent(self, kind: str) -> bool:
        return kind in self._accents

    def get_accent_amount(self) -> int:
        return self._accent_amount

    def set_accent(self, kind: str, on: bool):
        if kind not in ACCENTS:
            return
        self.prepareGeometryChange()
        if on:
            self._accents.add(kind)
        else:
            self._accents.discard(kind)
        self.update()
        self._notify_changed()

    def set_accents(self, kinds):
        self.prepareGeometryChange()
        self._accents = {k for k in kinds if k in ACCENTS}
        self.update()
        self._notify_changed()

    def set_accent_amount(self, amount: int):
        self._accent_amount = max(0, min(100, int(amount)))
        self.update()
        self._notify_changed()

    def _accent_margin(self) -> float:
        """Extra room the accents need outside the body (for boundingRect)."""
        if not self._accents:
            return 0.0
        r = self._body_rect
        # Scales with Amount: a big bolt or a wide puff trail was clipping
        # against a fixed margin.
        grow = 0.45 + 0.55 * self._accent_amount / 100.0
        return max(26.0, min(r.width(), r.height()) * 0.72 * grow)

    def _paint_halftone(self, painter: QPainter, outline: QPainterPath):
        """Offset dot-screen shadow — the classic printed-comic drop shadow."""
        r = self._body_rect
        base = min(r.width(), r.height())
        # Offset by a real amount: in printed comics the dot shadow is a bold
        # band you can read at a glance, not a hairline.
        off = max(8.0, base * 0.11)
        shadow = outline.translated(off, off).subtracted(outline)
        painter.save()
        painter.setClipPath(shadow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._border_color))
        step = max(3.5, base * 0.026)
        radius = step * (0.22 + 0.26 * self._accent_amount / 100.0)
        box = shadow.boundingRect()
        cx, cy = r.center().x() + off, r.center().y() + off
        reach = max(1.0, math.hypot(box.width(), box.height()) / 2.0)
        y = box.top()
        row = 0
        while y < box.bottom() + step:
            x = box.left() + (step / 2 if row % 2 else 0)
            while x < box.right() + step:
                # Fade the screen out toward the edge of the band.
                d = math.hypot(x - cx, y - cy) / reach
                rad = radius * max(0.25, 1.25 - d)
                painter.drawEllipse(QPointF(x, y), rad, rad)
                x += step
            y += step * 0.87
            row += 1
        painter.restore()

    def _paint_ticks(self, painter: QPainter, outline: QPainterPath):
        """Short radiating strokes — the 'this is important!' marks that sit
        just outside a balloon in comics."""
        r = self._body_rect
        cx, cy = r.center().x(), r.center().y()
        count = max(3, int(4 + self._accent_amount / 100.0 * 12))
        length = max(8.0, min(r.width(), r.height()) * 0.20)
        gap = max(4.0, min(r.width(), r.height()) * 0.05)
        width = max(1.5, min(r.width(), r.height()) * 0.018)
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(self._border_color, width, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        # Ticks cluster over the balloon's upper arc, the way they're inked.
        for i in range(count):
            t = (i + 0.5) / count
            angle = math.pi * (1.15 + 0.70 * t) + 0.06 * math.sin(i * 3.1)
            ux, uy = math.cos(angle), math.sin(angle)
            edge = self._edge_distance_at(angle, outline)
            if edge <= 0:
                continue
            scale = 0.65 + 0.6 * ((i * 7) % 5) / 5.0
            x0 = cx + ux * (edge + gap)
            y0 = cy + uy * (edge + gap)
            x1 = cx + ux * (edge + gap + length * scale)
            y1 = cy + uy * (edge + gap + length * scale)
            painter.drawLine(QPointF(x0, y0), QPointF(x1, y1))
        painter.restore()

    # ------------------------------------------------------------------
    # Lobed balloons: one text block per lobe
    # ------------------------------------------------------------------

    def is_lobed(self) -> bool:
        import shapes
        return shapes.lobe_count(self._style) > 0

    def lobe_count(self) -> int:
        import shapes
        return shapes.lobe_count(self._style)

    def get_lobe_text(self, index: int) -> str:
        if 0 <= index < len(self._lobe_texts):
            return self._lobe_texts[index]
        return ""

    def set_lobe_text(self, index: int, text: str):
        n = self.lobe_count()
        if not 0 <= index < n:
            return
        while len(self._lobe_texts) < n:
            self._lobe_texts.append("")
        self._lobe_texts[index] = text
        self.update()
        self._notify_changed()

    def _begin_lobe_edit(self, index: int):
        """打开 the inline editor over one lobe of a lobed balloon."""
        import shapes
        rects = shapes.lobe_rects(self._style, self._body_rect)
        if not 0 <= index < len(rects):
            return
        box = rects[index]
        self._editing_lobe = index
        self._is_editing = True
        self._text_before_edit = self.get_lobe_text(index)
        item = self._text_item
        item.setPlainText(self.get_lobe_text(index))
        item.setTextWidth(box.width())
        opt = item.document().defaultTextOption()
        opt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        item.document().setDefaultTextOption(opt)
        item.setPos(box.left(), box.center().y()
                    - item.boundingRect().height() / 2)
        item.setVisible(True)
        item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        item.setAcceptedMouseButtons(Qt.MouseButton.AllButtons)
        item.setFocus()
        cursor = item.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        item.setTextCursor(cursor)
        self.update()

    def _commit_lobe_edit(self):
        """Fold the inline editor's text back into the lobe it belongs to."""
        index = getattr(self, "_editing_lobe", -1)
        if index < 0:
            return
        text = self._text_item.toPlainText()
        self._editing_lobe = -1
        self._text_item.setVisible(False)
        before = self._text_before_edit
        self._text_before_edit = None
        if before is not None and text != before:
            stack = self._undo_stack()
            if stack:
                from undo_commands import LobeTextChangeCommand
                stack.push(LobeTextChangeCommand(self, index, before, text))
                return
        self.set_lobe_text(index, text)

    def _paint_lobe_texts(self, painter: QPainter):
        """Draw each lobe's text, auto-sized to that lobe's safe rect.

        Sizing is per lobe and recomputed every paint, so growing the balloon
        grows the text and shrinking it never lets text escape its lobe.
        """
        import shapes
        rects = shapes.lobe_rects(self._style, self._body_rect)
        if not rects:
            return
        base = QFont(self._text_item.font())
        colour = self._text_item.defaultTextColor()

        def fits(size: int) -> bool:
            probe = QFont(base)
            probe.setPointSize(size)
            fm = QFontMetricsF(probe)
            flags = (int(Qt.TextFlag.TextWordWrap)
                     | int(Qt.AlignmentFlag.AlignCenter))
            for idx, box in enumerate(rects):
                txt = self.get_lobe_text(idx).strip() or "在此输入..."
                bounds = fm.boundingRect(QRectF(0, 0, box.width(), 10000),
                                         flags, txt)
                if bounds.height() > box.height() or bounds.width() > box.width():
                    return False
            return True

        # One size for every lobe — sizing each lobe independently made them
        # visibly mismatched and looked like the font changing as you resized.
        lo, hi, best = 6, max(8, int(min(b.height() for b in rects))), 6
        while lo <= hi:
            mid = (lo + hi) // 2
            if fits(mid):
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
        font = QFont(base)
        font.setPointSize(best)

        editing = getattr(self, "_editing_lobe", -1)
        painter.save()
        painter.setFont(font)
        for i, box in enumerate(rects):
            if i == editing:
                continue          # the live editor is drawing this one
            text = self.get_lobe_text(i).strip()
            if not text:
                # Same affordance as every other style: show where to type.
                ph = QFont(font)
                ph.setPointSize(max(6, int(font.pointSize() * 0.9)))
                painter.setFont(ph)
                painter.setPen(QPen(QColor(colour.red(), colour.green(),
                                           colour.blue(), 110)))
                painter.drawText(box, int(Qt.TextFlag.TextWordWrap)
                                 | int(Qt.AlignmentFlag.AlignCenter),
                                 "在此输入...")
                painter.setFont(font)
                continue
            if self._text_outline_width > 0:
                painter.setPen(QPen(self._text_outline_color))
                o = self._text_outline_width
                for ox, oy in ((-o, -o), (o, -o), (-o, o), (o, o),
                               (0, -o), (0, o), (-o, 0), (o, 0)):
                    painter.drawText(box.translated(ox, oy),
                                     int(Qt.TextFlag.TextWordWrap)
                                     | int(Qt.AlignmentFlag.AlignCenter), text)
            painter.setPen(QPen(colour))
            painter.drawText(box, int(Qt.TextFlag.TextWordWrap)
                             | int(Qt.AlignmentFlag.AlignCenter), text)
        painter.restore()

    def _accent_anchor(self, angle: float, outline: QPainterPath, gap_frac=0.16):
        """A point just outside the outline in the given direction."""
        r = self._body_rect
        cx, cy = r.center().x(), r.center().y()
        edge = self._edge_distance_at(angle, outline)
        gap = min(r.width(), r.height()) * gap_frac
        return QPointF(cx + math.cos(angle) * (edge + gap),
                       cy + math.sin(angle) * (edge + gap))

    def _paint_impact(self, painter: QPainter, outline: QPainterPath):
        """Long tapered impact strokes — the heavier cousin of the ticks, the
        ones that fan out from the balloon in shout panels."""
        r = self._body_rect
        cx, cy = r.center().x(), r.center().y()
        count = max(3, int(3 + self._accent_amount / 100.0 * 7))
        reach = min(r.width(), r.height()) * 0.42
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._border_color))
        for i in range(count):
            t = (i + 0.5) / count
            angle = math.pi * (1.08 + 0.84 * t)
            edge = self._edge_distance_at(angle, outline)
            gap = min(r.width(), r.height()) * 0.07
            length = reach * (0.55 + 0.55 * ((i * 5) % 4) / 4.0)
            half = max(1.5, min(r.width(), r.height()) * 0.022)
            ux, uy = math.cos(angle), math.sin(angle)
            nx, ny = -uy, ux
            bx, by = cx + ux * (edge + gap), cy + uy * (edge + gap)
            tx, ty = cx + ux * (edge + gap + length), cy + uy * (edge + gap + length)
            wedge = QPainterPath(QPointF(bx + nx * half, by + ny * half))
            wedge.lineTo(QPointF(tx, ty))
            wedge.lineTo(QPointF(bx - nx * half, by - ny * half))
            wedge.closeSubpath()
            painter.drawPath(wedge)
        painter.restore()



    def _paint_bolt(self, painter: QPainter, outline: QPainterPath):
        """Lightning-bolt spur off the balloon — the shock/impact mark used in
        place of a tail in the reference sheets."""
        r = self._body_rect
        c = self._accent_anchor(math.radians(72), outline, 0.02)
        # Amount scales the bolt so the slider does something here too.
        h = max(14.0, min(r.width(), r.height())
                * (0.20 + 0.30 * self._accent_amount / 100.0))
        w = h * 0.44
        bolt = QPainterPath(QPointF(c.x() + w * 0.10, c.y() - h * 0.45))
        bolt.lineTo(QPointF(c.x() - w * 0.45, c.y() + h * 0.10))
        bolt.lineTo(QPointF(c.x() - w * 0.05, c.y() + h * 0.12))
        bolt.lineTo(QPointF(c.x() - w * 0.22, c.y() + h * 0.55))
        bolt.lineTo(QPointF(c.x() + w * 0.48, c.y() - h * 0.06))
        bolt.lineTo(QPointF(c.x() + w * 0.06, c.y() - h * 0.08))
        bolt.closeSubpath()
        painter.save()
        painter.setBrush(QBrush(self._fill_color if self._fill_color.alpha()
                                else QColor(255, 255, 255)))
        painter.setPen(QPen(self._border_color,
                            max(1.5, self._border_width * 0.8)))
        painter.drawPath(bolt)
        painter.restore()

    def _paint_puffs(self, painter: QPainter, outline: QPainterPath):
        """Little satellite bubbles hanging off the balloon."""
        r = self._body_rect
        base = min(r.width(), r.height())
        painter.save()
        painter.setBrush(QBrush(self._fill_color if self._fill_color.alpha()
                                else QColor(255, 255, 255)))
        painter.setPen(QPen(self._border_color,
                            max(1.4, self._border_width * 0.7)))
        amt = self._accent_amount / 100.0
        count = max(1, int(round(1 + amt * 4)))        # 1-5 satellites
        for i in range(count):
            angle_deg = -62 + i * 13
            size = 0.095 * (0.55 + 0.75 * amt) * (1.0 - i * 0.17)
            c = self._accent_anchor(math.radians(angle_deg), outline,
                                    0.04 + i * 0.035)
            rad = max(2.5, base * max(0.012, size))
            painter.drawEllipse(c, rad, rad * 0.9)
        painter.restore()


    def _paint_accents(self, painter: QPainter, outline: QPainterPath):
        """Marks drawn BEHIND the balloon: shading and radiating strokes."""
        if not self._accents:
            return
        if "halftone" in self._accents:
            self._paint_halftone(painter, outline)
        if "impact" in self._accents:
            self._paint_impact(painter, outline)
        if "ticks" in self._accents:
            self._paint_ticks(painter, outline)

    def _paint_accents_over(self, painter: QPainter, outline: QPainterPath):
        """Marks drawn IN FRONT: little objects with their own fill + outline,
        which would be clipped by the balloon if they went underneath."""
        if not self._accents:
            return
        if "puffs" in self._accents:
            self._paint_puffs(painter, outline)
        if "bolt" in self._accents:
            self._paint_bolt(painter, outline)

    def _paint_selection_frame(self, painter: QPainter, rect: QRectF):
        """Dark solid underlay + bright dashes on top, so the selection reads
        against both a white sky and a black shadow."""
        painter.setBrush(Qt.BrushStyle.NoBrush)
        underlay = QPen(QColor(10, 10, 10, 200), 2.6)
        underlay.setCosmetic(True)
        painter.setPen(underlay)
        painter.drawRect(rect)
        pen = QPen(QColor("#ff8a3d"), 1.8, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        pen.setDashPattern([5, 4])
        painter.setPen(pen)
        painter.drawRect(rect)

    def _paint_shadow(self, painter: QPainter, path: QPainterPath):
        """Offset drop shadow. `blur` now actually softens the edge: the shape
        is stamped several times at growing scale and falling alpha. It used to
        draw one hard translated copy, so Soft and Solid looked identical."""
        if not self._shadow.get("enabled", False):
            return
        colour = QColor(self._shadow.get("color", QColor(0, 0, 0)))
        alpha = round(max(0, min(100, self._shadow.get("opacity", 80))) * 255 / 100)
        ox = float(self._shadow.get("offset_x", 0))
        oy = float(self._shadow.get("offset_y", 0))
        blur = float(self._shadow.get("blur", 0))
        box = path.boundingRect()
        if box.width() <= 0 or box.height() <= 0:
            return

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        if blur <= 0.5:
            colour.setAlpha(alpha)
            painter.setBrush(QBrush(colour))
            painter.drawPath(path.translated(ox, oy))
        else:
            from PyQt6.QtGui import QTransform
            steps = 7
            cx, cy = box.center().x() + ox, box.center().y() + oy
            for i in range(steps, 0, -1):
                t = i / steps
                grow = 1.0 + (blur / max(box.width(), box.height())) * t * 1.6
                colour.setAlpha(max(1, int(alpha / steps * 1.25)))
                painter.setBrush(QBrush(colour))
                tr = (QTransform().translate(cx, cy).scale(grow, grow)
                      .translate(-cx, -cy))
                painter.drawPath(tr.map(path.translated(ox, oy)))
        painter.restore()

    def _edge_distance_at(self, angle: float, body: QPainterPath | None = None) -> float:
        """Distance from the body centre to the outline along `angle`."""
        r = self._body_rect
        cx, cy = r.center().x(), r.center().y()
        ux, uy = math.cos(angle), math.sin(angle)
        if body is None:
            body = self._build_body_path()
        hi = max(r.width(), r.height()) * 1.6
        lo = 0.0
        for _ in range(18):
            mid = (lo + hi) / 2.0
            if body.contains(QPointF(cx + ux * mid, cy + uy * mid)):
                lo = mid
            else:
                hi = mid
        return lo

    def _tail_geometry(self, tip: QPointF, width_scale: float = 1.0,
                       sink: float = 1.0):
        """(base_left, base_right, tip, unit_dir, unit_normal) or None.

        Returns None when the tip sits inside (or barely outside) the body —
        drawing a tail there would just smear a blob over the outline.
        """
        r = self._body_rect
        cx, cy = r.center().x(), r.center().y()
        dx, dy = tip.x() - cx, tip.y() - cy
        dist = math.hypot(dx, dy)
        if dist < 1.0:
            return None
        body = self._build_body_path()          # built once, reused below
        angle = math.atan2(dy, dx)
        edge_d = self._edge_distance_at(angle, body)
        # Tip must clear the outline by a visible margin.
        if dist <= edge_d + 4.0:
            return None

        half = max(2.5, self._tail_width * 0.5 * width_scale)
        # Angular half-spread that puts the two bases ~`half` apart along the
        # outline. Clamped so a wide tail on a small bubble can't wrap around.
        spread = min(math.pi / 3.0, math.atan2(half, max(10.0, edge_d)))

        # Seat BOTH bases at the shallowest outline depth across the whole base
        # arc. On a bumpy outline (cloud, scallop, burst) the arc can straddle a
        # valley; anchoring to the valley depth keeps the chord fully inside the
        # body, so the union welds flush instead of leaving a notch.
        steps = 8
        depth = min(
            self._edge_distance_at(angle - spread + 2 * spread * i / steps, body)
            for i in range(steps + 1)
        )
        # `sink` pushes the base chord further inside the body. A straight wedge
        # only needs a hairline of overlap, but a curved tail leaves the body at
        # an angle and needs real overlap or it reads as a separate comma
        # floating next to the bubble.
        depth = max(0.0, depth - max(1.0, sink))

        pts = [QPointF(cx + math.cos(a) * depth, cy + math.sin(a) * depth)
               for a in (angle - spread, angle + spread)]

        ux, uy = math.cos(angle), math.sin(angle)
        return pts[0], pts[1], QPointF(tip), (ux, uy), (-uy, ux)

    def _triangle_tail_path(self, tip: QPointF) -> QPainterPath:
        """Straight comic wedge: outline base → tip → outline base."""
        geo = self._tail_geometry(tip)
        if geo is None:
            return QPainterPath()
        b0, b1, t, _u, _n = geo
        path = QPainterPath(b0)
        path.lineTo(t)
        path.lineTo(b1)
        path.closeSubpath()
        return path

    def _curved_tail_path(self, tip: QPointF) -> QPainterPath:
        """Comma / swoosh tail: both flanks bow the same way, so the tail reads
        as one curved brushstroke instead of a straight wedge."""
        r = self._body_rect
        # Wider base and a deep sink, so the swoosh grows OUT of the balloon.
        geo = self._tail_geometry(
            tip, width_scale=1.3,
            sink=max(3.0, min(r.width(), r.height()) * 0.13))
        if geo is None:
            return QPainterPath()
        b0, b1, t, (ux, uy), (nx, ny) = geo
        mid = QPointF((b0.x() + b1.x()) / 2, (b0.y() + b1.y()) / 2)
        run = math.hypot(t.x() - mid.x(), t.y() - mid.y())

        # A comma tail is a stroke whose CENTRELINE curves while its width
        # tapers to nothing at the tip. Build it that way: walk the curved spine
        # and offset by a shrinking half-width, instead of guessing two flank
        # curves independently (that guessing is what produced the hooks).
        bow = run * 0.22                       # how far the spine leans sideways
        spine_c = QPointF(mid.x() + ux * run * 0.52 + nx * bow,
                          mid.y() + uy * run * 0.52 + ny * bow)
        half = math.hypot(b1.x() - b0.x(), b1.y() - b0.y()) / 2.0

        def spine(s: float) -> QPointF:
            """Quadratic bezier mid -> spine_c -> tip at parameter s."""
            m = 1.0 - s
            return QPointF(
                m * m * mid.x() + 2 * m * s * spine_c.x() + s * s * t.x(),
                m * m * mid.y() + 2 * m * s * spine_c.y() + s * s * t.y())

        STEPS = 14
        left, right = [], []
        for i in range(STEPS + 1):
            s = i / STEPS
            p = spine(s)
            nxt = spine(min(1.0, s + 0.02))
            prv = spine(max(0.0, s - 0.02))
            dx, dy = nxt.x() - prv.x(), nxt.y() - prv.y()
            d = math.hypot(dx, dy) or 1.0
            # Perpendicular to the spine at this point.
            px, py = -dy / d, dx / d
            # Gentle taper: stays full-bodied out of the balloon, then narrows
            # to the point. A steep taper pinched it to a thread at the base,
            # which is what made it look detached.
            w = half * (1.0 - s) ** 0.95
            left.append(QPointF(p.x() + px * w, p.y() + py * w))
            right.append(QPointF(p.x() - px * w, p.y() - py * w))

        path = QPainterPath(b0)
        for p in left[1:]:
            path.lineTo(p)
        path.lineTo(t)
        for p in reversed(right[1:]):
            path.lineTo(p)
        path.lineTo(b1)
        path.closeSubpath()
        return path

    def _line_tail_path(self, tip: QPointF) -> QPainterPath:
        """Thin tapered stick tail — the minimal manga pointer line."""
        geo = self._tail_geometry(tip, width_scale=0.34)
        if geo is None:
            return QPainterPath()
        b0, b1, t, _u, _n = geo
        path = QPainterPath(b0)
        path.lineTo(t)
        path.lineTo(b1)
        path.closeSubpath()
        return path

    def _tail_path_for(self, shape: str, tip: QPointF) -> QPainterPath:
        if shape == "curved":
            return self._curved_tail_path(tip)
        if shape == "line":
            return self._line_tail_path(tip)
        return self._triangle_tail_path(tip)

    def _outline_path(self) -> QPainterPath:
        """Body plus every active solid tail, united into ONE seamless outline
        (dot-chain tails are drawn separately in paint()).

        All styles go through the same direction-aware tail builder, so a tail
        welds correctly onto an oval, a cloud, a starburst or a wobbly box at
        any angle the user drags it to."""
        key = (self._style, QRectF(self._body_rect), self._ink_seed,
               self._tail_shape, self._tail_width,
               tuple((tip.x(), tip.y()) for tip in self._tail_tips()))
        if self._outline_path_cache is None or self._outline_path_cache[0] != key:
            self._outline_path_cache = (key, self._build_outline_path())
        return QPainterPath(self._outline_path_cache[1])

    def _build_outline_path(self) -> QPainterPath:
        path = self._build_body_path()
        if self._tail_shape in ("dots", "none"):
            return path
        for tip in self._tail_tips():
            tail = self._tail_path_for(self._tail_shape, tip)
            if not tail.isEmpty():
                path = path.united(tail)
        return path




    def _body_edge_point(self, tip: QPointF) -> QPointF:
        r = self._body_rect
        cx, cy = r.center().x(), r.center().y()
        dx = tip.x() - cx
        dy = tip.y() - cy
        dist = math.hypot(dx, dy) or 1
        ux, uy = dx / dist, dy / dist
        body = self._build_body_path()
        max_search = min(dist, max(r.width(), r.height()) * 1.5)
        lo, hi = 0.0, max_search
        for _ in range(22):
            mid = (lo + hi) / 2.0
            pt = QPointF(cx + ux * mid, cy + uy * mid)
            if body.contains(pt):
                lo = mid
            else:
                hi = mid
        return QPointF(cx + ux * lo, cy + uy * lo)

    def _cloud_edge_distance(self, tip: QPointF) -> float:
        """
        Binary-search for the distance from the body centre at which the ray
        toward 'tip' exits the body path (any style).  This is direction-aware,
        so the thought dots always start just outside the body regardless of
        which way the tail is pointing.
        """
        r  = self._body_rect
        cx, cy = r.center().x(), r.center().y()
        dx = tip.x() - cx
        dy = tip.y() - cy
        dist = math.hypot(dx, dy) or 1
        ux, uy = dx / dist, dy / dist

        body = self._build_body_path()
        max_search = min(dist, max(r.width(), r.height()))

        lo, hi = 0.0, max_search
        for _ in range(20):          # 20 iterations → sub-pixel precision
            mid = (lo + hi) / 2.0
            if body.contains(QPointF(cx + ux * mid, cy + uy * mid)):
                lo = mid             # still inside cloud → go further out
            else:
                hi = mid             # already outside → pull back
        return hi + 6               # 6 px gap so the first dot is clearly outside

    def _thought_dots_path(self, tip: QPointF) -> QPainterPath:
        """
        Thought-bubble dot chain from the cloud edge toward the tip.

        Dots scale in both size and spacing with the available tail length,
        so a short tail shows 2 small dots and a long tail shows up to 5
        larger ones — the tail visually "grows" as the user drags the red dot.
        """
        r  = self._body_rect
        cx, cy = r.center().x(), r.center().y()
        dx = tip.x() - cx
        dy = tip.y() - cy
        dist = math.hypot(dx, dy) or 1
        ux, uy = dx / dist, dy / dist

        edge      = self._cloud_edge_distance(tip)
        available = max(0.0, dist - edge - 8)   # usable space; 8 px margin before tip

        if available < 10:
            return QPainterPath()   # tail too short for any dots

        # Scale factor: 1.0 at 60 px of tail, up to 2.2 at ≥ 240 px
        scale = min(2.2, max(0.7, available / 60.0))

        # Dot specs: (fraction_of_available_length, base_radius)
        # Fractions spread dots evenly; radii shrink toward the tip
        dot_specs = [(0.12, 11), (0.38, 8), (0.60, 6)]
        if available > 80:
            dot_specs.append((0.75, 4))
        if available > 140:
            dot_specs.append((0.87, 3))

        path = QPainterPath()
        for frac, base_r in dot_specs:
            rad = max(2, int(base_r * scale))
            d   = edge + frac * available
            if d + rad > dist - 5:      # don't overlap tip
                break
            path.addEllipse(QPointF(cx + ux * d, cy + uy * d), rad, rad)
        return path

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # Clamp so the bubble body cannot be dragged outside the canvas.
            scene = self.scene()
            if scene:
                sr = scene.sceneRect()
                r  = self._body_rect
                # r edges are in local coords; item pos is the local origin in scene.
                x = max(sr.left() - r.left(),
                        min(value.x(), sr.right()  - r.right()))
                y = max(sr.top()  - r.top(),
                        min(value.y(), sr.bottom() - r.bottom()))
                return QPointF(x, y)

        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            selected = bool(value)
            for h in self._handles.values():
                h.setVisible(selected)
            self._sync_tail_handles()
        return super().itemChange(change, value)

    def lobe_index_at(self, local_pos: QPointF) -> int:
        """Which lobe a point falls in (nearest centre), or -1 if not lobed."""
        import shapes
        rects = shapes.lobe_rects(self._style, self._body_rect)
        if not rects:
            return -1
        for i, box in enumerate(rects):
            if box.contains(local_pos):
                return i
        return min(range(len(rects)),
                   key=lambda i: (rects[i].center() - local_pos).manhattanLength())

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        if (event.button() == Qt.MouseButton.LeftButton and self.is_lobed()):
            # Edit the clicked lobe IN PLACE on the canvas — the same gesture as
            # every other balloon. (The Text tab boxes still work as a fallback.)
            self._begin_lobe_edit(self.lobe_index_at(event.pos()))
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            # Snapshot text before editing so we can push an undo command later
            self._text_before_edit = self.get_text()
            self._is_editing = True
            if self._style in ("caption", "text"):
                # Temporarily show text item so the user can see what they type
                # (these styles normally paint their glyphs manually).
                self._text_item.setVisible(True)
            self._text_item.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextEditorInteraction)
            # Accept clicks again so the caret can be placed inside the text.
            self._text_item.setAcceptedMouseButtons(Qt.MouseButton.AllButtons)
            self._text_item.setFocus()
            cursor = self._text_item.textCursor()
            # Select-all only for the placeholder so the first keystroke replaces
            # it. For real text, place the caret at the end instead — selecting
            # the whole document meant one Backspace wiped everything.
            if self.get_text().strip() in ("", "在此输入..."):
                cursor.select(cursor.SelectionType.Document)
            else:
                cursor.movePosition(cursor.MoveOperation.End)
            self._text_item.setTextCursor(cursor)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        self._stop_editing()
        # Alt+drag pans the inset photo instead of moving the bubble.
        if (event.button() == Qt.MouseButton.LeftButton
                and event.modifiers() & Qt.KeyboardModifier.AltModifier
                and self.has_inset_photo()):
            self._panning_inset = True
            self._pan_last = event.scenePos()
            event.accept()
            return
        # Record position before a potential drag so MoveBubbleCommand can
        # capture the start state.
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if getattr(self, "_panning_inset", False):
            delta = event.scenePos() - self._pan_last
            self._pan_last = event.scenePos()
            self.nudge_inset(delta.x(), delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if getattr(self, "_panning_inset", False):
            self._panning_inset = False
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            old = self._drag_start_pos
            new = self.pos()
            # Only push a move command if the bubble actually moved
            if old is not None and (old - new).manhattanLength() > 1:
                stack = self._undo_stack()
                if stack:
                    from undo_commands import MoveBubbleCommand
                    stack.push(MoveBubbleCommand(self, old, new))
            self._drag_start_pos = None

    def _stop_editing(self):
        """Stop text editing; push TextChangeCommand if text was modified."""
        if getattr(self, "_editing_lobe", -1) >= 0:
            self._is_editing = False
            self._text_item.setTextInteractionFlags(
                Qt.TextInteractionFlag.NoTextInteraction)
            self._text_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self._text_item.clearFocus()
            self._commit_lobe_edit()
            return
        before = self._text_before_edit
        self._is_editing = False
        self._text_item.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction)
        # Drop the selection highlight. Clearing focus alone leaves the document's
        # cursor selection in place, which kept a dark band painted over the text
        # long after the user clicked away.
        cursor = self._text_item.textCursor()
        cursor.clearSelection()
        self._text_item.setTextCursor(cursor)
        # Back to pass-through so the bubble can be dragged from the glyphs again.
        self._text_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._text_item.clearFocus()
        if self._style in ("caption", "text"):
            self._text_item.setVisible(False)   # paint() takes over again
        if before is not None:
            after = self.get_text()
            if after != before:
                stack = self._undo_stack()
                if stack:
                    from undo_commands import TextChangeCommand
                    stack.push(TextChangeCommand(self, before, after))
            self._text_before_edit = None

    def _undo_stack(self):
        """Return the scene's QUndoStack if available, else None."""
        scene = self.scene()
        return getattr(scene, 'undo_stack', None) if scene else None

    def _snap_to_edge(self, edge: str):
        """Snap this rect bubble so it spans the full photo width and sits
        flush against the top or bottom edge of the image.

        This is the "caption bar" behaviour described in the spec (§8).
        """
        scene = self.scene()
        if not scene or not hasattr(scene, 'has_photo') or not scene.has_photo():
            return
        sr   = scene.sceneRect()
        w    = sr.width()
        h    = self._body_rect.height()   # keep current height

        # body_rect is in local coordinates, centred on the item's pos().
        new_rect = QRectF(-w / 2, -h / 2, w, h)
        self.set_body_rect(new_rect)

        if edge == "top":
            self.setPos(sr.center().x(), sr.top() + h / 2)
        else:
            self.setPos(sr.center().x(), sr.bottom() - h / 2)

    def _snap_to_scrim(self):
        """Expand to full scene width, keeping current vertical position."""
        scene = self.scene()
        if not scene or not hasattr(scene, 'has_photo') or not scene.has_photo():
            return
        sr = scene.sceneRect()
        w  = sr.width()
        h  = self._body_rect.height()
        self.set_body_rect(QRectF(-w / 2, -h / 2, w, h))
        self.setPos(sr.center().x(), self.pos().y())

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        menu = QMenu()
        clipboard = QApplication.clipboard()
        act_copy_text = menu.addAction("复制文字")
        act_paste_text = menu.addAction("粘贴文字")
        act_paste_text.setEnabled(bool(clipboard.text()))
        menu.addSeparator()
        act_del   = menu.addAction("删除")
        act_dup   = menu.addAction("创建副本")
        menu.addSeparator()
        menu.addSection("更换样式")
        act_oval    = menu.addAction("椭圆  — 对话气泡")
        act_cloud   = menu.addAction("云朵 — 思考气泡")
        act_rect    = menu.addAction("矩形 — 旁白条")
        act_spiky   = menu.addAction("Spiky — shout / explosion")
        act_scallop = menu.addAction("花边 — 柔花气泡")
        act_burst   = menu.addAction("放射形 — 闪电效果")
        act_wobbly  = menu.addAction("歪扭 — 手绘方框")
        act_text    = menu.addAction("仅文字 — 无气泡")
        act_scrim   = menu.addAction("遮罩 — 深色文字条")
        act_caption = menu.addAction("旁白框 — 描边文字叠加")
        # Premade text looks — applying one switches the bubble to text style.
        menu.addSeparator()
        preset_menu = menu.addMenu("文字样式")
        preset_acts = {}
        for preset in TEXT_PRESETS:
            act = preset_menu.addAction(preset["name"])
            preset_acts[act] = preset
        act_fit = None
        if self._style == "text":
            act_fit = menu.addAction("文字适应框")

        menu.addSeparator()
        act_front = menu.addAction("置于顶层")
        act_back  = menu.addAction("置于底层")

        # Snap options per style
        act_snap_top = act_snap_bot = act_snap_full = None
        if self._style in ("rect", "scrim"):
            menu.addSeparator()
            act_snap_top  = menu.addAction("吸附到顶部边缘")
            act_snap_bot  = menu.addAction("吸附到底部边缘")
        if self._style == "scrim":
            act_snap_full = menu.addAction("吸附到全宽")

        # Mark current style
        for act, s in [(act_oval,"oval"),(act_cloud,"cloud"),
                       (act_rect,"rect"),(act_spiky,"spiky"),
                       (act_scallop,"scallop"),(act_burst,"burst"),
                       (act_wobbly,"wobbly"),
                       (act_text,"text"),(act_scrim,"scrim"),
                       (act_caption,"caption")]:
            act.setCheckable(True)
            act.setChecked(self._style == s)

        chosen = menu.exec(event.screenPos())
        if   chosen == act_copy_text:
            clipboard.setText(self.get_text())
        elif chosen == act_paste_text:
            text = clipboard.text()
            if text:
                old = self.get_text()
                new = text
                stack = self._undo_stack()
                if stack and old != new:
                    from undo_commands import TextChangeCommand
                    stack.push(TextChangeCommand(self, old, new))
                else:
                    self.set_text(new)
        elif chosen == act_del:     self._delete()
        elif chosen == act_dup:     self._duplicate()
        elif chosen == act_oval:    self.set_style("oval")
        elif chosen == act_cloud:   self.set_style("cloud")
        elif chosen == act_rect:    self.set_style("rect")
        elif chosen == act_spiky:   self.set_style("spiky")
        elif chosen == act_scallop: self.set_style("scallop")
        elif chosen == act_burst:   self.set_style("burst")
        elif chosen == act_wobbly:  self.set_style("wobbly")
        elif chosen == act_text:    self.set_style("text")
        elif chosen == act_scrim:   self.set_style("scrim")
        elif chosen == act_caption: self.set_style("caption")
        elif chosen in preset_acts:
            self.apply_text_preset(preset_acts[chosen])
        elif act_fit and chosen == act_fit:
            self.fit_text_to_box()
        elif chosen == act_front: self.setZValue(self.zValue() + 1)
        elif chosen == act_back:  self.setZValue(max(0, self.zValue() - 1))
        elif act_snap_top  and chosen == act_snap_top:  self._snap_to_edge("top")
        elif act_snap_bot  and chosen == act_snap_bot:  self._snap_to_edge("bottom")
        elif act_snap_full and chosen == act_snap_full: self._snap_to_scrim()

    def _delete(self):
        if not self.scene():
            return
        stack = self._undo_stack()
        if stack:
            from undo_commands import DeleteBubbleCommand
            stack.push(DeleteBubbleCommand(self.scene(), self))
        else:
            self.scene().removeItem(self)

    def _duplicate(self):
        if not self.scene():
            return
        nb = BubbleItem(self.scenePos().x() + 25,
                        self.scenePos().y() + 25,
                        style=self._style)
        nb.set_text(self.get_text())
        nb._fill_color   = QColor(self._fill_color)
        nb._border_color = QColor(self._border_color)
        nb._border_width = self._border_width
        nb.set_font(self.get_font())
        nb._tail_shape    = self._tail_shape
        nb._tail_count    = self._tail_count
        nb._tail_width    = self._tail_width
        nb._tail_position = self._tail_position
        nb._tail.setPos(self._tail.pos())
        nb._sync_tail_handles()
        for src, dst in zip(self._extra_tails, nb._extra_tails):
            dst.setPos(src.pos())
        nb._text_outline_color = QColor(self._text_outline_color)
        nb._text_outline_width = self._text_outline_width
        nb._shadow = self.get_shadow()
        nb._accents = set(self._accents)
        nb._lobe_texts = list(self._lobe_texts)
        nb._accent_amount = self._accent_amount
        if self.has_inset_photo():
            nb._inset_pixmap = self._inset_pixmap
            nb._inset_spacing = self._inset_spacing
            nb._inset_blur = self._inset_blur
            nb._inset_opacity = self._inset_opacity
            nb._inset_zoom = self._inset_zoom
            nb._inset_dx = self._inset_dx
            nb._inset_dy = self._inset_dy
        # Caption & text carry explicit post-init state (manual-rendered glyphs,
        # text colour, halo) that __init__ doesn't reproduce on its own.
        if self._style in ("caption", "text"):
            nb._text_item.setDefaultTextColor(
                QColor(self._text_item.defaultTextColor()))
            nb._text_halo = self._text_halo
            nb._line_bars = self._line_bars
            nb._text_alignment = self._text_alignment
            nb._letter_spacing = self._letter_spacing
            nb._line_spacing = self._line_spacing
            nb._fit_mode = self._fit_mode
            nb._fit_display = list(self._fit_display)
            nb._text_manual_h = self._text_manual_h
            nb._body_rect = QRectF(self._body_rect)
            nb._text_item.setVisible(False)
            nb._reposition_text()
            nb.update()
        stack = self._undo_stack()
        if stack:
            from undo_commands import AddBubbleCommand
            stack.push(AddBubbleCommand(self.scene(), nb))
        else:
            self.scene().addItem(nb)
