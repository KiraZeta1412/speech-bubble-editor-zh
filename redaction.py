"""
redaction.py — RedactionItem: a resizable box that blurs or pixelates the part
of the photo beneath it. Used to hide faces, plates, names, etc.

The box samples the underlying photo pixmap at source resolution and renders a
blurred or pixelated version in its place, so it looks right both on screen and
in exports (export goes through the same paint() via QGraphicsScene.render()).

Resize handles are reused from bubble.py — RedactionItem exposes the small
duck-typed surface (body_rect / set_body_rect / get_style / get_font /
_undo_stack / _handles) that ResizeHandle expects.
"""

from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsSceneMouseEvent,
    QGraphicsSceneContextMenuEvent, QMenu, QApplication,
)
from PyQt6.QtGui import QColor, QPen, QPainter, QFont, QPixmap
from PyQt6.QtCore import Qt, QRectF, QPointF

from bubble import ResizeHandle, ANCHORS, HANDLE_SIZE

DEFAULT_W = 220
DEFAULT_H = 150


class RedactionItem(QGraphicsItem):
    """A blur/pixelate redaction box."""

    def __init__(self, scene_x: float, scene_y: float, mode: str = "blur"):
        super().__init__()
        hw, hh = DEFAULT_W / 2, DEFAULT_H / 2
        self._rect = QRectF(-hw, -hh, DEFAULT_W, DEFAULT_H)
        self._mode = mode if mode in ("blur", "pixelate") else "blur"
        self._intensity = 55           # 1..100 (blur strength / pixel coarseness)
        self._drag_start_pos: QPointF | None = None
        self._page_panel_index: int | None = None
        self._page_frame = QRectF()

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,            True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,         True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        # Above the photo/overlays but below bubbles (bubbles sit at z=100).
        self.setZValue(90)
        self.setPos(scene_x, scene_y)

        self._handles: dict[str, ResizeHandle] = {}
        for anchor in ANCHORS:
            h = ResizeHandle(anchor, self)
            h.setVisible(False)
            self._handles[anchor] = h
        self._update_handle_positions()

    # ------------------------------------------------------------------
    # Duck-typed surface used by ResizeHandle / ResizeBubbleCommand
    # ------------------------------------------------------------------

    @property
    def body_rect(self) -> QRectF:
        return self._rect

    def set_body_rect(self, rect: QRectF):
        self.prepareGeometryChange()
        self._rect = QRectF(rect)
        self._update_handle_positions()
        self.update()

    def get_style(self) -> str:
        return self._mode          # not "text", so ResizeHandle won't font-scale

    def get_font(self) -> QFont:
        return QFont()             # ResizeHandle reads pointSize() on press

    def _undo_stack(self):
        scene = self.scene()
        return getattr(scene, "undo_stack", None) if scene else None

    def _update_handle_positions(self):
        r = self._rect
        cx, cy = r.center().x(), r.center().y()
        l, t, ri, b = r.left(), r.top(), r.right(), r.bottom()
        for anchor, (x, y) in {
            "TL": (l, t), "TC": (cx, t), "TR": (ri, t),
            "ML": (l, cy),               "MR": (ri, cy),
            "BL": (l, b), "BC": (cx, b), "BR": (ri, b),
        }.items():
            self._handles[anchor].setPos(x, y)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str):
        if mode in ("blur", "pixelate"):
            self._mode = mode
            self.update()

    def get_intensity(self) -> int:
        return self._intensity

    def set_intensity(self, value: int):
        self._intensity = max(1, min(100, int(value)))
        self.update()

    def attach_to_page_panel(self, index: int, frame: QRectF):
        """Bind this effect to one Comic/Collage frame."""
        self._page_panel_index = int(index)
        self._page_frame = QRectF(frame)
        width = max(50.0, min(220.0, frame.width() * 0.38))
        height = max(40.0, min(150.0, frame.height() * 0.28))
        self.set_body_rect(QRectF(-width / 2, -height / 2, width, height))
        self.setPos(frame.center())
        self.update()

    def set_frame(self, frame: QRectF):
        """Follow a live page relayout while preserving relative placement."""
        frame = QRectF(frame)
        old = QRectF(self._page_frame)
        if old.width() > 0 and old.height() > 0:
            nx = (self.pos().x() - old.left()) / old.width()
            ny = (self.pos().y() - old.top()) / old.height()
            sx = frame.width() / old.width()
            sy = frame.height() / old.height()
            r = self._rect
            self.set_body_rect(QRectF(
                -r.width() * sx / 2, -r.height() * sy / 2,
                r.width() * sx, r.height() * sy))
            self._page_frame = frame
            self.setPos(frame.left() + nx * frame.width(),
                        frame.top() + ny * frame.height())
        else:
            self._page_frame = frame
        self.update()

    # ------------------------------------------------------------------
    # Geometry / painting
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        pad = HANDLE_SIZE + 2
        return self._rect.adjusted(-pad, -pad, pad, pad)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = self._rect
        src = self._sample_source()
        if src is not None and not src.isNull():
            proc = (self._pixelate(src, r) if self._mode == "pixelate"
                    else self._blur(src, r))
            painter.drawPixmap(r, proc, QRectF(proc.rect()))
        else:
            # No photo loaded yet — show a neutral placeholder.
            painter.fillRect(r, QColor(28, 33, 42, 200))

        # Outline only while selected — otherwise the box blends into the photo
        # (no permanent thin rectangle around the redacted area).
        if self.isSelected():
            painter.setPen(QPen(QColor("#ff8a3d"), 1.5, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)

    def _sample_source(self) -> QPixmap | None:
        """Grab the photo region under this box at source resolution."""
        scene = self.scene()
        if scene is not None and self._page_panel_index is not None:
            panels = getattr(scene, "_manga_panels", ())
            panel = next((p for p in panels
                          if p.index == self._page_panel_index), None)
            if panel is None or not panel.has_image():
                return None
            pm = panel.pixmap()
            target = panel._draw_geometry()
            if pm.isNull() or target.width() <= 0 or target.height() <= 0:
                return None
            local = panel.mapFromScene(
                self.mapToScene(self._rect)).boundingRect()
            src = QRectF(
                (local.x() - target.x()) * pm.width() / target.width(),
                (local.y() - target.y()) * pm.height() / target.height(),
                local.width() * pm.width() / target.width(),
                local.height() * pm.height() / target.height(),
            ).intersected(QRectF(pm.rect()))
            return pm.copy(src.toRect()) if src.width() >= 1 and src.height() >= 1 else None
        photo = getattr(scene, "_photo_item", None) if scene else None
        if photo is None:
            return None
        pm = photo.pixmap()
        if pm is None or pm.isNull():
            return None
        dw, dh = float(photo.display_w), float(photo.display_h)
        if dw <= 0 or dh <= 0:
            return None
        nw, nh = pm.width(), pm.height()
        srect = self.mapToScene(self._rect).boundingRect()
        sx, sy = nw / dw, nh / dh
        src = QRectF((srect.x() - photo.pos().x()) * sx,
                     (srect.y() - photo.pos().y()) * sy,
                     srect.width() * sx, srect.height() * sy)
        src = src.intersected(QRectF(0, 0, nw, nh))
        if src.width() < 1 or src.height() < 1:
            return None
        return pm.copy(src.toRect())

    def _pixelate(self, src: QPixmap, rect: QRectF) -> QPixmap:
        w, h = max(1, int(rect.width())), max(1, int(rect.height()))
        block = 3 + int(self._intensity / 100 * 45)     # coarser with intensity
        sw, sh = max(1, w // block), max(1, h // block)
        small = src.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio,
                           Qt.TransformationMode.FastTransformation)
        return small.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.FastTransformation)

    def _blur(self, src: QPixmap, rect: QRectF) -> QPixmap:
        w, h = max(1, int(rect.width())), max(1, int(rect.height()))
        factor = 1.0 + self._intensity / 100 * 24.0     # stronger with intensity
        sw, sh = max(1, int(w / factor)), max(1, int(h / factor))
        # Smooth down- then up-scale gives a fast, recognisable blur.
        small = src.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
        return small.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            scene = self.scene()
            if scene:
                sr = (self._page_frame if self._page_panel_index is not None
                      and not self._page_frame.isNull() else scene.sceneRect())
                r = self._rect
                x = max(sr.left() - r.left(),
                        min(value.x(), sr.right() - r.right()))
                y = max(sr.top() - r.top(),
                        min(value.y(), sr.bottom() - r.bottom()))
                return QPointF(x, y)
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            for h in self._handles.values():
                h.setVisible(bool(value))
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.update()   # re-sample the new region under the box
        return super().itemChange(change, value)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = self.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            old, new = self._drag_start_pos, self.pos()
            if old is not None and (old - new).manhattanLength() > 1:
                stack = self._undo_stack()
                if stack:
                    from undo_commands import MoveBubbleCommand
                    stack.push(MoveBubbleCommand(self, old, new))
            self._drag_start_pos = None

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        menu = QMenu()
        act_blur  = menu.addAction("模糊模式")
        act_pix   = menu.addAction("像素化模式")
        for act, m in ((act_blur, "blur"), (act_pix, "pixelate")):
            act.setCheckable(True)
            act.setChecked(self._mode == m)
        menu.addSeparator()
        act_dup = menu.addAction("创建副本")
        act_del = menu.addAction("删除")
        chosen = menu.exec(event.screenPos())
        if   chosen == act_blur: self.set_mode("blur")
        elif chosen == act_pix:  self.set_mode("pixelate")
        elif chosen == act_dup:  self._duplicate()
        elif chosen == act_del:  self._delete()

    def _delete(self):
        scene = self.scene()
        if not scene:
            return
        stack = self._undo_stack()
        if stack:
            from undo_commands import DeleteBubbleCommand
            stack.push(DeleteBubbleCommand(scene, self))
        else:
            scene.removeItem(self)

    def _duplicate(self):
        scene = self.scene()
        if not scene:
            return
        nb = RedactionItem(self.scenePos().x() + 25,
                           self.scenePos().y() + 25, mode=self._mode)
        nb.set_body_rect(QRectF(self._rect))
        nb.set_intensity(self._intensity)
        if self._page_panel_index is not None:
            nb._page_panel_index = self._page_panel_index
            nb._page_frame = QRectF(self._page_frame)
        stack = self._undo_stack()
        if stack:
            from undo_commands import AddBubbleCommand
            stack.push(AddBubbleCommand(scene, nb))
        else:
            scene.addItem(nb)
