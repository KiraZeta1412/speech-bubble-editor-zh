"""
speedlines.py — SpeedLinesItem: manga-style motion/focus lines overlay.

Covers the photo frame with lines converging on a draggable focus point
(Balloon+-style "Speed Lines"). Three render kinds:

  "radial" — thin tapered lines from the frame edges toward the focus
  "burst"  — fewer, fatter sunburst wedges
  "streak" — horizontal motion streaks from the left/right edges

The item's hit area is only a band along the frame edges plus the focus
handle, so clicks and double-clicks in the middle of the photo still reach
the canvas (adding bubbles keeps working with an overlay active).
"""

import math

from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsEllipseItem, QGraphicsSceneMouseEvent, QMenu,
)
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen, QBrush, QCursor
from PyQt6.QtCore import Qt, QRectF, QPointF

EDGE_BAND = 26     # px of clickable band along the frame edges
KINDS = ("radial", "burst", "streak")


def _rand(seed: int, i: int) -> float:
    """Deterministic pseudo-random in [0, 1) — stable across repaints."""
    return (math.sin(seed * 12.9898 + i * 78.233) * 43758.5453) % 1.0


class FocusHandle(QGraphicsEllipseItem):
    """Draggable dot marking the convergence point of the lines."""

    R = 9

    def __init__(self, parent: "SpeedLinesItem"):
        r = self.R
        super().__init__(-r, -r, r * 2, r * 2, parent)
        self._lines = parent
        self._dragging = False
        self.setBrush(QBrush(QColor("#f87171")))
        self.setPen(QPen(QColor("#121212"), 2.0))
        self.setZValue(10)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.setToolTip("拖动以移动焦点")

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._dragging:
            p = self._lines.mapFromScene(event.scenePos())
            r = self._lines.frame_rect()
            x = max(r.left(), min(p.x(), r.right()))
            y = max(r.top(), min(p.y(), r.bottom()))
            self.setPos(x, y)
            self._lines.prepareGeometryChange()
            self._lines.update()
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            event.accept()
        else:
            event.ignore()


class SpeedLinesItem(QGraphicsItem):
    """Full-frame speed-lines overlay with a draggable focus point."""

    def __init__(self, frame: QRectF, parent=None):
        super().__init__(parent)
        self._frame = QRectF(frame)   # scene-aligned; item stays at (0, 0)
        self._kind = "radial"
        # Manga speed lines read as a texture, not as individual strokes: a
        # dense fan blends into a clean inner edge, a sparse one looks like
        # scattered spikes.
        self._density = 110           # number of lines
        # Line weight is proportional to the photo: a fixed 10 px is a bold
        # manga streak on a 900 px image and an invisible hair on a 4 K one.
        self._thickness = max(4.0, frame.width() / 90.0)
        self._inner = 55              # % of the edge distance kept clear
        self._color = QColor(15, 15, 15)
        self._seed = 7

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(60)            # above photo/overlays, below bubbles (100)

        self._focus = FocusHandle(self)
        self._focus.setPos(frame.center())
        self._focus.setVisible(False)

    # ------------------------------------------------------------------
    # Accessors (inspector)
    # ------------------------------------------------------------------

    def frame_rect(self) -> QRectF:
        return QRectF(self._frame)

    def get_kind(self) -> str:
        return self._kind

    def get_density(self) -> int:
        return self._density

    def get_thickness(self) -> float:
        return self._thickness

    def get_inner(self) -> int:
        return self._inner

    def get_color(self) -> QColor:
        return QColor(self._color)

    def set_kind(self, kind: str):
        if kind in KINDS:
            self._kind = kind
            self.update()

    def set_density(self, n: int):
        self._density = max(4, min(320, int(n)))
        self.update()

    def set_thickness(self, w: float):
        self._thickness = max(1.0, float(w))
        self.update()

    def set_inner(self, pct: int):
        self._inner = max(5, min(90, int(pct)))
        self.update()

    def set_color(self, color: QColor):
        self._color = QColor(color)
        self.update()

    def set_frame(self, frame: QRectF):
        """Follow the photo after a crop or reload."""
        old = QRectF(self._frame)
        focus = self._focus.pos()
        nx = ((focus.x() - old.left()) / old.width()
              if old.width() > 0 else 0.5)
        ny = ((focus.y() - old.top()) / old.height()
              if old.height() > 0 else 0.5)
        self.prepareGeometryChange()
        self._frame = QRectF(frame)
        self._focus.setPos(frame.left() + max(0.0, min(1.0, nx)) * frame.width(),
                           frame.top() + max(0.0, min(1.0, ny)) * frame.height())
        self.update()

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        return self._frame.adjusted(-2, -2, 2, 2)

    def shape(self) -> QPainterPath:
        """Edge band only — the frame centre stays click-through."""
        outer = QPainterPath()
        outer.addRect(self._frame)
        inner = QPainterPath()
        inner.addRect(self._frame.adjusted(EDGE_BAND, EDGE_BAND,
                                           -EDGE_BAND, -EDGE_BAND))
        return outer.subtracted(inner)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def _edge_distance(self, focus: QPointF, ux: float, uy: float) -> float:
        """Distance from focus to the frame edge along direction (ux, uy)."""
        r = self._frame
        best = float("inf")
        if ux > 1e-9:
            best = min(best, (r.right() - focus.x()) / ux)
        elif ux < -1e-9:
            best = min(best, (r.left() - focus.x()) / ux)
        if uy > 1e-9:
            best = min(best, (r.bottom() - focus.y()) / uy)
        elif uy < -1e-9:
            best = min(best, (r.top() - focus.y()) / uy)
        return 0.0 if best == float("inf") else max(0.0, best)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(self._frame)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._color))
        focus = self._focus.pos()

        if self._kind == "streak":
            self._paint_streaks(painter, focus)
        else:
            burst = self._kind == "burst"
            n = self._density if not burst else max(4, self._density // 4)
            base_w = self._thickness * (3.2 if burst else 1.0)
            for i in range(n):
                # Only a slight angular jitter: heavy jitter left visible gaps
                # and clumps instead of an even fan.
                a = (2 * math.pi * i / n
                     + (_rand(self._seed, i) - 0.5) * (2 * math.pi / n) * 0.45)
                ux, uy = math.cos(a), math.sin(a)
                edge = self._edge_distance(focus, ux, uy)
                if edge < 4:
                    continue
                # Inner ends vary only a little, so together they describe a
                # smooth opening around the focus rather than a ragged ring.
                inner_frac = (self._inner / 100.0
                              * (0.94 + 0.13 * _rand(self._seed, i + 991)))
                start = edge * min(0.97, inner_frac)
                w = base_w * (0.55 + 0.7 * _rand(self._seed, i + 313))
                nx, ny = -uy, ux
                ex, ey = focus.x() + ux * edge, focus.y() + uy * edge
                sx, sy = focus.x() + ux * start, focus.y() + uy * start
                # Curved flanks instead of a flat triangle: the stroke narrows
                # gradually and its point melts into the page like inked lines.
                mx, my = (ex + sx) / 2.0, (ey + sy) / 2.0
                path = QPainterPath(QPointF(ex + nx * w / 2, ey + ny * w / 2))
                path.quadTo(QPointF(mx + nx * w * 0.18, my + ny * w * 0.18),
                            QPointF(sx, sy))
                path.quadTo(QPointF(mx - nx * w * 0.18, my - ny * w * 0.18),
                            QPointF(ex - nx * w / 2, ey - ny * w / 2))
                path.closeSubpath()
                painter.drawPath(path)

        if self.isSelected():
            painter.setClipping(False)
            painter.setPen(QPen(QColor("#ff8a3d"), 1.5, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self._frame.adjusted(1, 1, -1, -1))

    def _paint_streaks(self, painter: QPainter, focus: QPointF):
        """Horizontal motion streaks from the left and right edges."""
        r = self._frame
        n = max(4, self._density)
        for i in range(n):
            t = (i + 0.5) / n
            y = r.top() + t * r.height() \
                + (_rand(self._seed, i) - 0.5) * r.height() / n
            from_left = i % 2 == 0
            max_reach = (focus.x() - r.left()) if from_left \
                else (r.right() - focus.x())
            if max_reach < 8:
                continue
            reach = max_reach * (1.0 - self._inner / 100.0) \
                * (0.55 + 0.7 * _rand(self._seed, i + 517))
            w = self._thickness * (0.35 + 0.75 * _rand(self._seed, i + 129))
            if from_left:
                x0, x1 = r.left(), r.left() + reach
            else:
                x0, x1 = r.right(), r.right() - reach
            path = QPainterPath(QPointF(x0, y - w / 2))
            path.lineTo(QPointF(x0, y + w / 2))
            path.lineTo(QPointF(x1, y))
            path.closeSubpath()
            painter.drawPath(path)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._focus.setVisible(bool(value))
        return super().itemChange(change, value)

    def contextMenuEvent(self, event):
        menu = QMenu()
        act_del = menu.addAction("删除速度线")
        chosen = menu.exec(event.screenPos())
        if chosen == act_del:
            scene = self.scene()
            stack = getattr(scene, "undo_stack", None) if scene else None
            if stack:
                from undo_commands import DeleteBubbleCommand
                stack.push(DeleteBubbleCommand(scene, self))
            elif scene:
                scene.removeItem(self)
