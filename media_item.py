"""
media_item.py — MediaItem: resizable background media item (photo or video frame).

Click to select → 4 corner resize handles appear.
Drag a corner to resize.  Drag the body to move.
Both resize and move are fully undoable (Ctrl+Z / Ctrl+Y).
"""

from PyQt6.QtWidgets import (
    QGraphicsObject, QGraphicsRectItem, QGraphicsItem,
    QGraphicsSceneMouseEvent, QGraphicsSceneContextMenuEvent,
    QMenu, QApplication,
)
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QPixmap, QPainter, QPen, QBrush, QColor, QCursor,
)

HANDLE_SIZE = 12
HANDLE_HIT  = 26
MIN_DISPLAY = 40.0


# ---------------------------------------------------------------------------
# MediaResizeHandle
# ---------------------------------------------------------------------------

class MediaResizeHandle(QGraphicsRectItem):
    """One corner resize handle on a MediaItem."""

    CURSORS = {
        "TL": Qt.CursorShape.SizeFDiagCursor,
        "TR": Qt.CursorShape.SizeBDiagCursor,
        "BL": Qt.CursorShape.SizeBDiagCursor,
        "BR": Qt.CursorShape.SizeFDiagCursor,
    }

    def __init__(self, corner: str, parent: "MediaItem"):
        s = HANDLE_SIZE
        super().__init__(-s / 2, -s / 2, s, s, parent)
        self._corner      = corner
        self._media       = parent
        self._dragging    = False
        self._start_mouse = QPointF()
        self._start_w     = 0.0
        self._start_h     = 0.0
        self._start_pos   = QPointF()
        self._hovered     = False

        self.setZValue(5)
        self.setCursor(QCursor(self.CURSORS[corner]))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setAcceptHoverEvents(True)
        self.setVisible(False)

    # Circular Camtasia-style handle with a generous hit area, matching bubbles.
    def boundingRect(self) -> QRectF:
        h = HANDLE_HIT / 2
        return QRectF(-h, -h, HANDLE_HIT, HANDLE_HIT)

    def shape(self):
        from PyQt6.QtGui import QPainterPath
        p = QPainterPath()
        p.addRect(self.boundingRect())
        return p

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = self._hovered or self._dragging
        s = (HANDLE_SIZE + 4) if active else HANDLE_SIZE
        r = QRectF(-s / 2, -s / 2, s, s)
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

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging        = True
            self._media._resizing = True
            self._start_mouse     = event.scenePos()
            self._start_w         = self._media.display_w
            self._start_h         = self._media.display_h
            self._start_pos       = self._media.pos()
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        if not self._dragging:
            return
        delta = event.scenePos() - self._start_mouse
        c = self._corner

        # Step 1: compute unconstrained new size from drag delta
        new_w = self._start_w
        new_h = self._start_h
        if "R" in c:
            new_w = max(MIN_DISPLAY, self._start_w + delta.x())
        if "L" in c:
            new_w = max(MIN_DISPLAY, self._start_w - delta.x())
        if "B" in c:
            new_h = max(MIN_DISPLAY, self._start_h + delta.y())
        if "T" in c:
            new_h = max(MIN_DISPLAY, self._start_h - delta.y())

        # Step 2: constrain to aspect ratio when Shift held or lock is active
        shift = bool(QApplication.keyboardModifiers()
                     & Qt.KeyboardModifier.ShiftModifier)
        if (shift or self._media._lock_ratio) and self._start_h > 0:
            aspect = self._start_w / self._start_h
            if abs(delta.x()) >= abs(delta.y()):
                new_h = max(MIN_DISPLAY, new_w / aspect)
            else:
                new_w = max(MIN_DISPLAY, new_h * aspect)

        # Step 3: adjust top-left position for L/T anchored corners
        new_x = self._start_pos.x()
        new_y = self._start_pos.y()
        if "L" in c:
            new_x = self._start_pos.x() + (self._start_w - new_w)
        if "T" in c:
            new_y = self._start_pos.y() + (self._start_h - new_h)

        self._media.set_display_size(new_w, new_h)
        self._media.setPos(new_x, new_y)

        # In dual mode snap right panel live — position only, NO sceneRect change.
        # Changing sceneRect on every mouse move causes Qt to auto-scroll the
        # viewport, which makes bubbles "disappear" from the visible area.
        sc = self._media.scene()
        if sc and hasattr(sc, "_snap_right_to_left"):
            sc._snap_right_to_left()

        event.accept()

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging        = False
            self._media._resizing = False
            self.update()
            sc      = self.scene()
            new_pos = self._media.pos()
            new_w   = self._media.display_w
            new_h   = self._media.display_h

            size_changed = (abs(new_w - self._start_w) > 0.5
                            or abs(new_h - self._start_h) > 0.5)
            pos_changed  = (new_pos - self._start_pos).manhattanLength() > 0.5

            if (size_changed or pos_changed) and sc and hasattr(sc, 'undo_stack'):
                from undo_commands import ResizeMediaCommand
                sc.undo_stack.push(ResizeMediaCommand(
                    sc, self._media,
                    self._start_pos, self._start_w, self._start_h,
                    new_pos, new_w, new_h,
                ))
                # push() immediately calls redo() which calls fit_scene_to_media()
                event.accept()
                return

            # No change, or no undo stack — still refresh scene rect
            if sc and hasattr(sc, "fit_scene_to_media"):
                sc.fit_scene_to_media()

        event.accept()


# ---------------------------------------------------------------------------
# MediaItem
# ---------------------------------------------------------------------------

class MediaItem(QGraphicsObject):
    """
    Background media (photo or video frame) with 4 corner resize handles.

    The pixmap is drawn stretched to (display_w × display_h).
    For video playback: call set_pixmap() each frame — display size stays fixed.

    Intentionally does NOT use ItemSendsGeometryChanges: that flag causes
    fit_scene_to_media() → setSceneRect() to fire on every drag pixel, which
    triggers Qt's scrollbar recalculation and auto-scrolls the viewport,
    making speech bubbles appear to "vanish" during resize.
    Instead, scene updates happen only on mouse release (via undo commands).
    """

    def __init__(self, pixmap: QPixmap, is_overlay: bool = False):
        super().__init__()
        self._pixmap    = pixmap
        self._display_w = float(pixmap.width())
        self._display_h = float(pixmap.height())
        self._native_w  = float(pixmap.width())
        self._native_h  = float(pixmap.height())
        self._is_overlay = is_overlay
        self._flip_h = False
        self._flip_v = False
        self._video_player = None

        # Drag-state
        self._resizing:       bool           = False   # True while handle active
        self._drag_start_pos: QPointF | None = None
        self._lock_ratio:     bool           = True    # constrain resize to aspect ratio

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        # NOTE: ItemSendsGeometryChanges deliberately omitted — see class docstring
        if is_overlay:
            # Overlay z-value is set by the scene based on existing layers;
            # default to 1 so it appears above the background (-1).
            self.setZValue(1)
        else:
            self.setZValue(-1)

        self._handles = {
            c: MediaResizeHandle(c, self) for c in ("TL", "TR", "BL", "BR")
        }
        self._update_handle_positions()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def display_w(self) -> float:
        return self._display_w

    @property
    def display_h(self) -> float:
        return self._display_h

    def pixmap(self) -> QPixmap:
        return self._pixmap

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_pixmap(self, pixmap: QPixmap):
        """Replace pixmap (next video frame). Display size unchanged."""
        self._pixmap = pixmap
        self.update()

    def set_video_player(self, player):
        self._video_player = player

    def video_player(self):
        return self._video_player

    def has_video(self) -> bool:
        return self._video_player is not None and self._video_player.is_loaded()

    def set_display_size(self, w: float, h: float):
        self.prepareGeometryChange()
        self._display_w = max(MIN_DISPLAY, float(w))
        self._display_h = max(MIN_DISPLAY, float(h))
        self._update_handle_positions()
        self.update()

    def restore_native_size(self):
        """Reset to original pixel dimensions and position."""
        self.prepareGeometryChange()
        self._display_w = self._native_w
        self._display_h = self._native_h
        self._update_handle_positions()
        self.update()
        self.setPos(0, 0)

    def flip_horizontal(self):
        self._flip_h = not self._flip_h
        self.update()

    def flip_vertical(self):
        self._flip_v = not self._flip_v
        self.update()

    # ------------------------------------------------------------------
    # QGraphicsItem overrides
    # ------------------------------------------------------------------

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._display_w, self._display_h)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.save()
        if self._flip_h or self._flip_v:
            painter.translate(self._display_w if self._flip_h else 0,
                              self._display_h if self._flip_v else 0)
            painter.scale(-1 if self._flip_h else 1,
                          -1 if self._flip_v else 1)
        painter.drawPixmap(
            QRectF(0, 0, self._display_w, self._display_h),
            self._pixmap,
            QRectF(self._pixmap.rect()),
        )
        painter.restore()
        if self.isSelected():
            pen = QPen(QColor("#ff8a3d"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(1, 1, self._display_w - 2, self._display_h - 2))

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            for h in self._handles.values():
                h.setVisible(bool(value))
        return super().itemChange(change, value)

    # ------------------------------------------------------------------
    # Mouse events — move with undo support
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self._resizing:
            self._drag_start_pos = self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)   # Qt moves the item
        # Live snap in dual mode — position only, no sceneRect update
        sc = self.scene()
        if sc and hasattr(sc, "_snap_right_to_left") and not self._is_overlay:
            sc._snap_right_to_left()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and not self._resizing:
            old = self._drag_start_pos
            new = self.pos()
            self._drag_start_pos = None

            if old is not None and (old - new).manhattanLength() > 1:
                sc = self.scene()
                if sc and hasattr(sc, 'undo_stack'):
                    if self._is_overlay:
                        # For overlays, just record the move (no fit_scene_to_media)
                        from undo_commands import MoveMediaCommand
                        sc.undo_stack.push(MoveMediaCommand(sc, self, old, new))
                        return
                    else:
                        from undo_commands import MoveMediaCommand
                        sc.undo_stack.push(MoveMediaCommand(sc, self, old, new))
                        # push() calls redo() immediately → fit_scene_to_media()
                        return
                elif sc and hasattr(sc, 'fit_scene_to_media') and not self._is_overlay:
                    sc.fit_scene_to_media()
            else:
                # Click without move — still refresh scene rect (non-overlay only)
                sc = self.scene()
                if sc and hasattr(sc, 'fit_scene_to_media') and not self._is_overlay:
                    sc.fit_scene_to_media()

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        menu = QMenu()
        act_lock = menu.addAction("锁定宽高比")
        act_lock.setCheckable(True)
        act_lock.setChecked(self._lock_ratio)
        act_lock.setToolTip("拖动角点时按住 Shift 可临时锁定比例")

        act_front    = None
        act_forward  = None
        act_backward = None
        act_back     = None
        act_remove   = None

        if self._is_overlay:
            menu.addSeparator()
            act_front    = menu.addAction("置于顶层")
            act_forward  = menu.addAction("上移一层")
            act_backward = menu.addAction("下移一层")
            act_back     = menu.addAction("置于底层")
            menu.addSeparator()
            act_remove = menu.addAction("删除图层")

        chosen = menu.exec(event.screenPos())
        sc = self.scene()

        if chosen == act_lock:
            self._lock_ratio = not self._lock_ratio

        elif self._is_overlay and sc:
            layers = sc.get_overlay_layers() if hasattr(sc, 'get_overlay_layers') else []
            cur_z = self.zValue()

            if chosen == act_remove:
                if hasattr(sc, 'undo_stack'):
                    from undo_commands import RemoveOverlayCommand
                    sc.undo_stack.push(RemoveOverlayCommand(sc, self))
                else:
                    sc.remove_overlay(self)

            elif chosen == act_front:
                max_z = max((l.zValue() for l in layers), default=1)
                self.setZValue(max_z + 1)

            elif chosen == act_back:
                min_z = min((l.zValue() for l in layers), default=1)
                self.setZValue(max(1.0, min_z - 1))

            elif chosen == act_forward:
                above = sorted(
                    [l for l in layers if l is not self and l.zValue() > cur_z],
                    key=lambda l: l.zValue())
                if above:
                    nxt = above[0]
                    self.setZValue(nxt.zValue())
                    nxt.setZValue(cur_z)

            elif chosen == act_backward:
                below = sorted(
                    [l for l in layers if l is not self and l.zValue() < cur_z],
                    key=lambda l: l.zValue(), reverse=True)
                if below:
                    prv = below[0]
                    self.setZValue(prv.zValue())
                    prv.setZValue(cur_z)

        event.accept()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _update_handle_positions(self):
        w, h = self._display_w, self._display_h
        for corner, handle in self._handles.items():
            x = w if "R" in corner else 0.0
            y = h if "B" in corner else 0.0
            handle.setPos(x, y)
