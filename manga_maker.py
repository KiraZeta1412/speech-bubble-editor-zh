"""Manga Maker canvas items and tier-based random page布局s.

The page布局 deliberately uses horizontal tiers instead of unconstrained
random rectangles.  This keeps the reading order clear while still producing
unequal, manga-like panel sizes on every regeneration.
"""

from __future__ import annotations

import random

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor, QBrush, QCursor, QFont, QPainter, QPainterPath, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsRectItem,
)

import i18n


PAGE_WIDTH = 1600.0
PAGE_HEIGHT = 2263.0
PAGE_MARGIN = 28.0
ROW_GUTTER = 18.0
COLUMN_GUTTER = 14.0
PANEL_COUNTS = (4, 6, 7, 8)

# Each tuple describes the number of panels in successive horizontal tiers.
# Keeping each tier internally aligned avoids ambiguous panel reading order.
TIER_PATTERNS = {
    4: ((2, 2), (1, 2, 1), (1, 1, 2), (2, 1, 1)),
    6: ((2, 2, 2), (1, 2, 3), (2, 1, 3), (3, 2, 1)),
    7: ((2, 2, 3), (1, 3, 3), (2, 3, 2), (3, 1, 3)),
    8: ((2, 3, 3), (3, 2, 3), (2, 2, 4), (1, 3, 4)),
}


def _random_weights(count: int, rng: random.Random, minimum: float,
                    variation: float = 0.55) -> list[float]:
    """Return ``count`` varied normalized weights, each above ``minimum``."""
    variation = max(0.0, min(1.0, variation))
    raw = [rng.uniform(1.0 - variation, 1.0 + variation) for _ in range(count)]
    total = sum(raw)
    available = 1.0 - minimum * count
    return [minimum + available * value / total for value in raw]


def generate_layout(panel_count: int | None = None, rng: random.Random | None = None,
                    options: dict | None = None):
    """Generate a compact, intentional manga composition with varied tiers."""
    rng = rng or random.SystemRandom()
    options = options or {}
    count = panel_count if panel_count in PANEL_COUNTS else rng.choice(PANEL_COUNTS)
    margin = float(options.get("margin", rng.uniform(18.0, 28.0)))
    row_gutter = float(options.get("row_gutter", rng.uniform(14.0, 24.0)))
    col_gutter = float(options.get("column_gutter", rng.uniform(9.0, 16.0)))
    variation = max(0.0, min(1.0, float(options.get("variation", 48)) / 100.0))
    composition = str(options.get("composition", "随机"))
    reading_direction = str(options.get("reading_direction", "从右到左"))

    candidates = list(TIER_PATTERNS[count])
    if composition == "突出":
        candidates = [pattern for pattern in candidates if 1 in pattern] or candidates
    elif composition == "均衡":
        candidates = [pattern for pattern in candidates
                      if max(pattern) - min(pattern) <= 1] or candidates
    elif composition == "对话":
        candidates = [pattern for pattern in candidates if max(pattern) <= 3] or candidates
    elif composition == "动作":
        candidates = [pattern for pattern in candidates
                      if max(pattern) >= 3 or 1 in pattern] or candidates

    pattern = rng.choice(candidates)
    row_count = len(pattern)

    usable_w = PAGE_WIDTH - 2 * margin
    usable_h = PAGE_HEIGHT - 2 * margin - row_gutter * (row_count - 1)
    row_weights = _random_weights(
        row_count, rng, 0.22 if row_count == 3 else 0.32, variation)
    feature_row = next((i for i, columns in enumerate(pattern) if columns == 1),
                       rng.randrange(row_count))
    emphasis = 1.0 + variation * rng.uniform(0.18, 0.48)
    if composition != "均衡":
        row_weights[feature_row] *= emphasis
    total_rows = sum(row_weights)
    row_weights = [weight / total_rows for weight in row_weights]

    rects: list[QRectF] = []
    y = margin
    for row_index, columns in enumerate(pattern):
        row_h = usable_h * row_weights[row_index]
        row_w = usable_w - col_gutter * (columns - 1)
        col_weights = _random_weights(
            columns, rng, 0.17 if columns >= 4 else 0.22, variation)
        x = margin
        row_rects = []
        for col_index in range(columns):
            panel_w = row_w * col_weights[col_index]
            row_rects.append(QRectF(x, y, panel_w, row_h))
            x += panel_w + col_gutter
        rects.extend(reversed(row_rects) if reading_direction == "从右到左"
                     else row_rects)
        y += row_h + row_gutter

    family = composition.lower() if composition != "随机" else "手绘墨线"
    name = f"{count} 格  ·  {family} " + "–".join(str(n) for n in pattern)
    return rects, name, count


class MangaPanelItem(QGraphicsObject):
    """A clipped viewport supporting crop drag and magnetic image reordering."""

    def __init__(self, index: int, rect: QRectF, pixmap: QPixmap | None = None,
                 style: dict | None = None, seed: int | None = None,
                 show_number: bool = False,
                 reading_direction: str = "从右到左"):
        super().__init__()
        self.index = index
        self._width = rect.width()
        self._height = rect.height()
        self._pixmap = QPixmap(pixmap) if pixmap is not None else QPixmap()
        self._zoom = 1.0
        self._offset = QPointF()
        self._drag_start: QPointF | None = None
        self._offset_start = QPointF()
        self._style = dict(style or {})
        self._seed = seed if seed is not None else random.SystemRandom().randrange(2**31)
        self._show_number = show_number
        self._reading_direction = reading_direction
        self._guides_visible = True
        self._active_frame = False
        self._drop_target = False
        self._reorder_drag = False
        self._blur_cache_key = None
        self._blur_cache = QPixmap()
        self._panel_path = QPainterPath()
        self._ink_path = QPainterPath()
        self._rebuild_panel_path()
        self.setPos(rect.topLeft())
        self.setZValue(-10)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._width, self._height)

    def shape(self):
        return QPainterPath(self._panel_path)

    def set_panel_rect(self, rect: QRectF):
        """Morph this panel to a new布局 rectangle without losing its image."""
        old_w = max(1.0, self._width)
        old_h = max(1.0, self._height)
        self.prepareGeometryChange()
        self._width = max(40.0, rect.width())
        self._height = max(40.0, rect.height())
        self.setPos(rect.topLeft())
        self._offset.setX(self._offset.x() * self._width / old_w)
        self._offset.setY(self._offset.y() * self._height / old_h)
        self._rebuild_panel_path()
        self._clamp_offset()
        self.update()

    def _rebuild_panel_path(self):
        roughness = float(self._style.get("roughness", 34.0))
        self._panel_path = self._make_hand_path(self._seed, roughness, 1.0)
        self._ink_path = self._make_hand_path(self._seed + 7919, roughness, 0.72)

    def _make_hand_path(self, seed: int, roughness: float,
                        strength: float) -> QPainterPath:
        """Mostly rectangular frame with bowed, imperfect pen-drawn edges."""
        rng = random.Random(seed)
        border_width = float(self._style.get("border_width", 6.0))
        corner_radius = max(0.0, float(self._style.get("corner_radius", 0.0)))
        if corner_radius > 0 or roughness <= 0:
            inset = max(0.0, border_width * 0.5)
            rect = QRectF(inset, inset, max(1.0, self._width - inset * 2),
                          max(1.0, self._height - inset * 2))
            path = QPainterPath()
            radius = min(corner_radius, rect.width() / 2, rect.height() / 2)
            path.addRoundedRect(rect, radius, radius)
            return path
        inset = max(2.0, border_width * 0.65)
        corner = min(4.0, roughness * 0.10) * strength
        wave = min(roughness * 0.34, self._width * 0.025,
                   self._height * 0.025) * strength

        left = inset + rng.uniform(-corner, corner)
        right = self._width - inset + rng.uniform(-corner, corner)
        top = inset + rng.uniform(-corner, corner)
        bottom = self._height - inset + rng.uniform(-corner, corner)

        tl = QPointF(left, top)
        tr = QPointF(right, top + rng.uniform(-corner, corner))
        br = QPointF(right + rng.uniform(-corner, corner), bottom)
        bl = QPointF(left + rng.uniform(-corner, corner),
                     bottom + rng.uniform(-corner, corner))

        path = QPainterPath(tl)
        path.cubicTo(
            QPointF(self._width * 0.33, top + rng.uniform(-wave, wave)),
            QPointF(self._width * 0.67, top + rng.uniform(-wave, wave)), tr)
        path.cubicTo(
            QPointF(right + rng.uniform(-wave, wave), self._height * 0.33),
            QPointF(right + rng.uniform(-wave, wave), self._height * 0.67), br)
        path.cubicTo(
            QPointF(self._width * 0.67, bottom + rng.uniform(-wave, wave)),
            QPointF(self._width * 0.33, bottom + rng.uniform(-wave, wave)), bl)
        path.cubicTo(
            QPointF(left + rng.uniform(-wave, wave), self._height * 0.67),
            QPointF(left + rng.uniform(-wave, wave), self._height * 0.33), tl)
        path.closeSubpath()
        return path

    def set_style(self, style: dict):
        self._style = dict(style)
        self._rebuild_panel_path()
        self.update()

    def set_number_guide(self, visible: bool, reading_direction: str):
        self._show_number = bool(visible)
        self._reading_direction = reading_direction
        self.update()

    def set_guides_visible(self, visible: bool):
        self._guides_visible = bool(visible)
        self.update()

    def set_active_frame(self, active: bool):
        self._active_frame = bool(active)
        self.update()

    def set_drop_target(self, active: bool):
        self._drop_target = bool(active)
        self.update()

    def pixmap(self) -> QPixmap:
        return QPixmap(self._pixmap)

    def has_image(self) -> bool:
        return not self._pixmap.isNull()

    def set_pixmap(self, pixmap: QPixmap):
        self._pixmap = QPixmap(pixmap)
        self._blur_cache_key = None
        self._blur_cache = QPixmap()
        self.reset_image()

    def clear_pixmap(self):
        self._pixmap = QPixmap()
        self._zoom = 1.0
        self._offset = QPointF()
        self._blur_cache_key = None
        self._blur_cache = QPixmap()
        self.update()

    def image_state(self):
        """Return the image and normalized crop so it can move between frames."""
        target = self._draw_geometry()
        max_x = max(0.0, (target.width() - self._width) / 2)
        max_y = max(0.0, (target.height() - self._height) / 2)
        norm_x = self._offset.x() / max_x if max_x > 0 else 0.0
        norm_y = self._offset.y() / max_y if max_y > 0 else 0.0
        return QPixmap(self._pixmap), float(self._zoom), norm_x, norm_y

    def set_image_state(self, state):
        pixmap, zoom, norm_x, norm_y = state
        self._pixmap = QPixmap(pixmap)
        self._zoom = max(0.10, min(5.0, float(zoom)))
        self._offset = QPointF()
        target = self._draw_geometry()
        max_x = max(0.0, (target.width() - self._width) / 2)
        max_y = max(0.0, (target.height() - self._height) / 2)
        self._offset = QPointF(float(norm_x) * max_x, float(norm_y) * max_y)
        self._clamp_offset()
        self.update()

    def reset_image(self):
        """Fill the frame edge-to-edge (100% cover scale)."""
        self._zoom = 1.0
        self._offset = QPointF()
        self.update()
        self._emit_zoom_changed()

    def zoom_image(self, factor: float):
        if self._pixmap.isNull():
            return
        self._zoom = max(0.10, min(5.0, self._zoom * factor))
        self._clamp_offset()
        self.update()
        self._emit_zoom_changed()

    def set_zoom_percent(self, percent: int):
        if self._pixmap.isNull():
            return
        self._zoom = max(0.10, min(5.0, float(percent) / 100.0))
        self._clamp_offset()
        self.update()
        self._emit_zoom_changed()

    def zoom_percent(self) -> int:
        return int(round(self._zoom * 100))

    def show_whole_image(self):
        """Contain the complete photo inside the frame without cropping it."""
        if self._pixmap.isNull():
            return
        iw, ih = max(1, self._pixmap.width()), max(1, self._pixmap.height())
        cover = max(self._width / iw, self._height / ih)
        contain = min(self._width / iw, self._height / ih)
        self._zoom = max(0.10, min(1.0, contain / max(cover, 1e-9)))
        self._offset = QPointF()
        self.update()
        self._emit_zoom_changed()

    def _emit_zoom_changed(self):
        scene = self.scene()
        if scene is not None and hasattr(scene, "manga_panel_zoom_changed"):
            scene.manga_panel_zoom_changed.emit(self.zoom_percent(), self.has_image())

    def _draw_geometry(self):
        if self._pixmap.isNull():
            return QRectF()
        iw = max(1, self._pixmap.width())
        ih = max(1, self._pixmap.height())
        cover = max(self._width / iw, self._height / ih)
        scale = cover * self._zoom
        w, h = iw * scale, ih * scale
        return QRectF(
            (self._width - w) / 2 + self._offset.x(),
            (self._height - h) / 2 + self._offset.y(),
            w,
            h,
        )

    def _clamp_offset(self):
        target = self._draw_geometry()
        if target.isNull():
            return
        max_x = max(0.0, (target.width() - self._width) / 2)
        max_y = max(0.0, (target.height() - self._height) / 2)
        self._offset.setX(max(-max_x, min(max_x, self._offset.x())))
        self._offset.setY(max(-max_y, min(max_y, self._offset.y())))

    def _blurred_background(self) -> QPixmap:
        """Cached soft cover image used behind a shrunken foreground photo."""
        width, height = max(1, int(self._width)), max(1, int(self._height))
        key = (int(self._pixmap.cacheKey()), width, height)
        if key == self._blur_cache_key and not self._blur_cache.isNull():
            return self._blur_cache
        cover = self._pixmap.scaled(
            width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation)
        x = max(0, (cover.width() - width) // 2)
        y = max(0, (cover.height() - height) // 2)
        cover = cover.copy(x, y, min(width, cover.width()),
                           min(height, cover.height()))
        tiny = cover.scaled(
            max(8, width // 26), max(8, height // 26),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self._blur_cache = tiny.scaled(
            width, height, Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self._blur_cache_key = key
        return self._blur_cache

    def paint(self, painter: QPainter, option, widget=None):
        frame = self.boundingRect()
        painter.save()
        painter.setClipPath(self._panel_path)
        if self._pixmap.isNull():
            empty_color = QColor(self._style.get("empty_color", "#f3f3f1"))
            placeholder_color = QColor(self._style.get("placeholder_color", "#777773"))
            painter.fillPath(self._panel_path, empty_color)

            icon_size = max(38, int(min(self._width, self._height) * 0.12))
            center = frame.center()
            painter.setPen(QPen(placeholder_color, 7, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(center.x() - icon_size / 2, center.y()),
                             QPointF(center.x() + icon_size / 2, center.y()))
            painter.drawLine(QPointF(center.x(), center.y() - icon_size / 2),
                             QPointF(center.x(), center.y() + icon_size / 2))
            font = QFont()
            font.setPixelSize(max(20, int(min(self._width, self._height) * 0.045)))
            font.setBold(True)
            painter.setFont(font)
            label_top = center.y() + icon_size / 2 + 28
            label_rect = QRectF(20, label_top, self._width - 40,
                                max(40, self._height - label_top - 20))
            painter.drawText(
                label_rect,
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                i18n.tr("点击打开图片\n双击或拖放"),
            )
        else:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            target = self._draw_geometry()
            exposed = (target.left() > frame.left() + 0.5
                       or target.top() > frame.top() + 0.5
                       or target.right() < frame.right() - 0.5
                       or target.bottom() < frame.bottom() - 0.5)
            painter.fillPath(
                self._panel_path,
                QColor(self._style.get("empty_color", "#252933")))
            if exposed and self._style.get("image_background", "blur") == "blur":
                background = self._blurred_background()
                painter.setOpacity(0.72)
                painter.drawPixmap(frame, background, QRectF(background.rect()))
                painter.setOpacity(1.0)
            painter.drawPixmap(target, self._pixmap,
                               QRectF(self._pixmap.rect()))
        painter.restore()

        border = (QColor("#ff8a3d") if self.isSelected()
                  else QColor(self._style.get("border_color", "#111111")))
        width = (max(7.0, float(self._style.get("border_width", 7.0)) + 3.0)
                 if self.isSelected() else float(self._style.get("border_width", 7.0)))
        if self.isSelected() or width > 0:
            painter.setPen(QPen(border, width, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self._panel_path)
        # A second independently bowed ink pass creates the imperfect overlap
        # of a nib tracing the frame twice; it is not a translated duplicate.
        if not self.isSelected() and float(self._style.get("roughness", 34.0)) > 2:
            ink = QColor(border)
            ink.setAlpha(105)
            painter.setPen(QPen(ink, max(1.0, width * 0.32),
                                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                                Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(self._ink_path)

        if ((self._active_frame and self._guides_visible and not self.isSelected())
                or self._drop_target):
            painter.save()
            accent = QColor("#ff8a3d")
            if self._drop_target:
                painter.fillPath(self._panel_path, QColor(255, 138, 61, 42))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(
                accent, 11.0 if self._drop_target else 5.0,
                Qt.PenStyle.SolidLine if self._drop_target else Qt.PenStyle.DashLine,
                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(self._panel_path)
            painter.restore()

        if self._show_number and self._guides_visible:
            diameter = max(42.0, min(68.0, min(self._width, self._height) * 0.11))
            pad = max(16.0, diameter * 0.34)
            x = (self._width - pad - diameter
                 if self._reading_direction == "从右到左" else pad)
            badge = QRectF(x, pad, diameter, diameter)
            painter.setPen(QPen(QColor("#ff8a3d"), 3.0))
            painter.setBrush(QColor(20, 20, 20, 205))
            painter.drawEllipse(badge)
            font = QFont()
            font.setPixelSize(max(20, int(diameter * 0.48)))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(badge, int(Qt.AlignmentFlag.AlignCenter),
                             str(self.index + 1))

    def hoverEnterEvent(self, event):
        self.setCursor(QCursor(
            Qt.CursorShape.OpenHandCursor if self.has_image()
            else Qt.CursorShape.PointingHandCursor))
        super().hoverEnterEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            scene = self.scene()
            if scene is not None and not self.isSelected():
                scene.clearSelection()
            self.setSelected(True)
            if self.has_image():
                mode = (scene.page_drag_mode() if scene is not None
                        and hasattr(scene, "page_drag_mode") else "crop")
                immediate_reorder = (
                    mode == "reorder"
                    or bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
                self._reorder_drag = immediate_reorder
                self._drag_start = event.scenePos()
                self._offset_start = QPointF(self._offset)
                if self._reorder_drag and hasattr(scene, "begin_panel_reorder"):
                    scene.begin_panel_reorder(self, event.scenePos())
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._reorder_drag:
            scene = self.scene()
            if scene is not None and hasattr(scene, "update_panel_reorder"):
                scene.update_panel_reorder(self, event.scenePos())
            event.accept()
            return
        if self._drag_start is not None:
            scene = self.scene()
            if (scene is not None
                    and hasattr(scene, "should_begin_panel_reorder")
                    and scene.should_begin_panel_reorder(self, event.scenePos())):
                # The gesture started as a crop. Restore that tentative crop,
                # then promote the same uninterrupted drag to magnetic reorder.
                self._offset = QPointF(self._offset_start)
                self._clamp_offset()
                self.update()
                self._drag_start = None
                if scene.begin_panel_reorder(self, event.scenePos()):
                    self._reorder_drag = True
                    scene.update_panel_reorder(self, event.scenePos())
                    event.accept()
                    return
            self._offset = self._offset_start + (event.scenePos() - self._drag_start)
            self._clamp_offset()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._reorder_drag:
            scene = self.scene()
            if scene is not None and hasattr(scene, "finish_panel_reorder"):
                scene.finish_panel_reorder(self, event.scenePos())
            self._reorder_drag = False
            self._drag_start = None
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start is not None:
            self._drag_start = None
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            scene = self.scene()
            if scene is not None and hasattr(scene, "request_open_manga_panel"):
                scene.request_open_manga_panel(self.index)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        if self.has_image():
            self.zoom_image(1.10 if event.delta() > 0 else 1 / 1.10)
            event.accept()
            return
        event.ignore()

    def contextMenuEvent(self, event):
        from PyQt6.QtWidgets import QMenu

        menu = QMenu()
        open_action = menu.addAction("打开 / Replace 图片…")
        fill_action = menu.addAction("充满画框")
        fit_action = menu.addAction("显示完整图片")
        clear_action = menu.addAction("清除分格")
        fill_action.setEnabled(self.has_image())
        fit_action.setEnabled(self.has_image())
        clear_action.setEnabled(self.has_image())
        chosen = menu.exec(event.screenPos())
        if chosen == open_action:
            scene = self.scene()
            if scene is not None and hasattr(scene, "request_open_manga_panel"):
                scene.request_open_manga_panel(self.index)
        elif chosen == fill_action:
            self.reset_image()
        elif chosen == fit_action:
            self.show_whole_image()
        elif chosen == clear_action:
            self.clear_pixmap()


def create_page_background(color: QColor | str = "#ffffff") -> QGraphicsRectItem:
    page = QGraphicsRectItem(0, 0, PAGE_WIDTH, PAGE_HEIGHT)
    page.setBrush(QBrush(QColor(color)))
    page.setPen(QPen(Qt.PenStyle.NoPen))
    page.setZValue(-20)
    return page
