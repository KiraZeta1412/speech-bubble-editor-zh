"""
undo_commands.py — QUndoCommand subclasses for the undo/redo stack.

Commands implemented:
  添加BubbleCommand     — redo = add item,    undo = remove item
  DeleteBubbleCommand  — redo = remove item, undo = add item back
  MoveBubbleCommand    — redo = move to new_pos, undo = move to old_pos
                         (consecutive moves of the same bubble are merged)
  ResizeBubbleCommand  — redo = resize to new_rect, undo = restore old_rect
  TextChangeCommand    — redo = new text, undo = old text
  StyleChangeCommand   — redo = new style, undo = old style
  FontChangeCommand    — redo = new font, undo = old font
  FillColorChangeCommand   — redo = new fill, undo = old fill
  BorderColorChangeCommand — redo = new border color, undo = old border color
  BorderWidthChangeCommand — redo = new width, undo = old width
  TextColorChangeCommand   — redo = new text color, undo = old text color
  TextAlignmentChangeCommand — redo = new alignment, undo = old alignment
  TailPositionChangeCommand — redo = new tail preset, undo = old preset
  TailWidthChangeCommand — redo = new tail width, undo = old width
  ShadowChangeCommand — redo = new shadow settings, undo = old settings
  ZValueChangeCommand — redo = new z, undo = old z
  MoveMediaCommand     — redo = move media to new_pos, undo = move to old_pos
  ResizeMediaCommand   — redo = resize + reposition, undo = restore original
  添加OverlayCommand    — redo = add overlay layer, undo = remove it
  RemoveOverlayCommand — redo = remove overlay layer, undo = add it back
"""

from PyQt6.QtGui import QUndoCommand, QFont, QColor, QPixmap
from PyQt6.QtCore import QPointF, QRectF, QRect

from constants import (
    MERGE_ID_MOVE_BUBBLE, MERGE_ID_MOVE_MEDIA,
    MERGE_ID_STYLE, MERGE_ID_FONT,
    MERGE_ID_FILL_COLOR, MERGE_ID_BORDER_COLOR, MERGE_ID_BORDER_WIDTH,
    MERGE_ID_TEXT_COLOR, MERGE_ID_TEXT_ALIGNMENT, MERGE_ID_TAIL_POSITION,
    MERGE_ID_TAIL_WIDTH, MERGE_ID_SHADOW, MERGE_ID_Z_VALUE,
    MERGE_ID_TAIL_SHAPE, MERGE_ID_TAIL_COUNT, MERGE_ID_TEXT_OUTLINE,
    MERGE_ID_INSET_PHOTO,
)


class AddBubbleCommand(QUndoCommand):
    def __init__(self, scene, bubble):
        super().__init__("添加气泡")
        self._scene  = scene
        self._bubble = bubble
        self._z      = None   # assigned on first redo, reused on later redos

    def redo(self):
        self._scene.addItem(self._bubble)
        # Newest item lands on top of every existing layer. Captured once so an
        # undo/redo cycle restores the original position instead of re-promoting.
        if self._z is None and hasattr(self._scene, "next_stack_z"):
            self._z = self._scene.next_stack_z()
        if self._z is not None:
            self._bubble.setZValue(self._z)
        self._scene.clearSelection()
        self._bubble.setSelected(True)

    def undo(self):
        self._scene.removeItem(self._bubble)


class ReorderPanelImagesCommand(QUndoCommand):
    """Move to an empty frame or swap two filled page frames."""

    def __init__(self, source, target, source_state, target_state):
        super().__init__("重新排列页面图片")
        self._source = source
        self._target = target
        self._source_state = source_state
        self._target_state = target_state

    def redo(self):
        self._source.set_image_state(self._target_state)
        self._target.set_image_state(self._source_state)

    def undo(self):
        self._source.set_image_state(self._source_state)
        self._target.set_image_state(self._target_state)


class DeleteBubbleCommand(QUndoCommand):
    def __init__(self, scene, bubble):
        super().__init__("删除气泡")
        self._scene  = scene
        self._bubble = bubble

    def redo(self):
        self._scene.removeItem(self._bubble)

    def undo(self):
        self._scene.addItem(self._bubble)
        self._scene.clearSelection()
        self._bubble.setSelected(True)


class MoveBubbleCommand(QUndoCommand):
    # All move commands share the same id so Qt can merge consecutive moves
    _ID = MERGE_ID_MOVE_BUBBLE

    def __init__(self, bubble, old_pos: QPointF, new_pos: QPointF):
        super().__init__("移动气泡")
        self._bubble  = bubble
        self._old_pos = QPointF(old_pos)
        self._new_pos = QPointF(new_pos)

    def id(self) -> int:
        return self._ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        """Merge a later move of the same bubble — keeps only start→end."""
        if isinstance(other, MoveBubbleCommand) and other._bubble is self._bubble:
            self._new_pos = QPointF(other._new_pos)
            return True
        return False

    def redo(self):
        self._bubble.setPos(self._new_pos)

    def undo(self):
        self._bubble.setPos(self._old_pos)


class ResizeBubbleCommand(QUndoCommand):
    def __init__(self, bubble, old_rect: QRectF, new_rect: QRectF,
                 old_font_pt: int | None = None, new_font_pt: int | None = None):
        super().__init__("调整气泡大小")
        self._bubble   = bubble
        self._old_rect = QRectF(old_rect)
        self._new_rect = QRectF(new_rect)
        # Speech-bubble resize also scales the text; carry the sizes so undo/redo
        # restore the font too. None for items that don't scale (text/redaction).
        self._old_font_pt = old_font_pt
        self._new_font_pt = new_font_pt

    def redo(self):
        if self._new_font_pt and hasattr(self._bubble, "apply_resize"):
            self._bubble.apply_resize(self._new_rect, self._new_font_pt)
        else:
            self._bubble.set_body_rect(self._new_rect)

    def undo(self):
        if self._old_font_pt and hasattr(self._bubble, "apply_resize"):
            self._bubble.apply_resize(self._old_rect, self._old_font_pt)
        else:
            self._bubble.set_body_rect(self._old_rect)


class TextChangeCommand(QUndoCommand):
    def __init__(self, bubble, old_text: str, new_text: str):
        super().__init__("编辑文字")
        self._bubble   = bubble
        self._old_text = old_text
        self._new_text = new_text

    def redo(self):
        self._bubble.set_text(self._new_text)

    def undo(self):
        self._bubble.set_text(self._old_text)


class MoveMediaCommand(QUndoCommand):
    """Undo/redo for dragging a MediaItem to a new position."""
    _ID = MERGE_ID_MOVE_MEDIA

    def __init__(self, scene, item, old_pos: QPointF, new_pos: QPointF):
        super().__init__("移动媒体")
        self._scene   = scene
        self._item    = item
        self._old_pos = QPointF(old_pos)
        self._new_pos = QPointF(new_pos)

    def id(self) -> int:
        return self._ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        if isinstance(other, MoveMediaCommand) and other._item is self._item:
            self._new_pos = QPointF(other._new_pos)
            return True
        return False

    def redo(self):
        self._item.setPos(self._new_pos)
        if not self._item._is_overlay and hasattr(self._scene, 'fit_scene_to_media'):
            self._scene.fit_scene_to_media()

    def undo(self):
        self._item.setPos(self._old_pos)
        if not self._item._is_overlay and hasattr(self._scene, 'fit_scene_to_media'):
            self._scene.fit_scene_to_media()


class ResizeMediaCommand(QUndoCommand):
    """Undo/redo for resizing a MediaItem via corner handles."""

    def __init__(self, scene, item,
                 old_pos: QPointF, old_w: float, old_h: float,
                 new_pos: QPointF, new_w: float, new_h: float):
        super().__init__("调整媒体大小")
        self._scene = scene
        self._item  = item
        self._old_pos = QPointF(old_pos)
        self._old_w, self._old_h = old_w, old_h
        self._new_pos = QPointF(new_pos)
        self._new_w, self._new_h = new_w, new_h

    def redo(self):
        self._item.set_display_size(self._new_w, self._new_h)
        self._item.setPos(self._new_pos)
        if not self._item._is_overlay and hasattr(self._scene, 'fit_scene_to_media'):
            self._scene.fit_scene_to_media()

    def undo(self):
        self._item.set_display_size(self._old_w, self._old_h)
        self._item.setPos(self._old_pos)
        if not self._item._is_overlay and hasattr(self._scene, 'fit_scene_to_media'):
            self._scene.fit_scene_to_media()


class AddOverlayCommand(QUndoCommand):
    """Undo/redo for adding an overlay layer to the scene."""

    def __init__(self, scene, item):
        super().__init__("添加图层")
        self._scene = scene
        self._item  = item

    def redo(self):
        if self._item not in self._scene._overlay_layers:
            self._scene._overlay_layers.append(self._item)
        if self._item.scene() is None:
            self._scene.addItem(self._item)
        self._scene.clearSelection()
        self._item.setSelected(True)
        self._scene.overlay_added.emit(self._item)

    def undo(self):
        if self._item in self._scene._overlay_layers:
            self._scene._overlay_layers.remove(self._item)
        if self._item.scene() is self._scene:
            self._scene.removeItem(self._item)
        self._scene.overlay_removed.emit(self._item)


class RemoveOverlayCommand(QUndoCommand):
    """Undo/redo for removing an overlay layer from the scene."""

    def __init__(self, scene, item):
        super().__init__("删除图层")
        self._scene = scene
        self._item  = item

    def redo(self):
        if self._item in self._scene._overlay_layers:
            self._scene._overlay_layers.remove(self._item)
        if self._item.scene() is self._scene:
            self._scene.removeItem(self._item)
        self._scene.overlay_removed.emit(self._item)

    def undo(self):
        if self._item not in self._scene._overlay_layers:
            self._scene._overlay_layers.append(self._item)
        if self._item.scene() is None:
            self._scene.addItem(self._item)
        self._scene.clearSelection()
        self._item.setSelected(True)
        self._scene.overlay_added.emit(self._item)


# ---------------------------------------------------------------------------
# Bubble property commands — style, font, colors, border width
# ---------------------------------------------------------------------------

class StyleChangeCommand(QUndoCommand):
    """Undo/redo for changing a bubble's style (oval, cloud, rect, …)."""
    _ID = MERGE_ID_STYLE

    def __init__(self, bubble, old_style: str, new_style: str):
        super().__init__("更换样式")
        self._bubble    = bubble
        self._old_style = old_style
        self._new_style = new_style

    def id(self) -> int:
        return self._ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        if isinstance(other, StyleChangeCommand) and other._bubble is self._bubble:
            self._new_style = other._new_style
            return True
        return False

    def redo(self):
        self._bubble.set_style(self._new_style)

    def undo(self):
        self._bubble.set_style(self._old_style)


class FontChangeCommand(QUndoCommand):
    """Undo/redo for changing a bubble's font (family, size, bold, italic)."""
    _ID = MERGE_ID_FONT

    def __init__(self, bubble, old_font: QFont, new_font: QFont):
        super().__init__("更换字体")
        self._bubble   = bubble
        self._old_font = QFont(old_font)
        self._new_font = QFont(new_font)

    def id(self) -> int:
        return self._ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        if isinstance(other, FontChangeCommand) and other._bubble is self._bubble:
            self._new_font = QFont(other._new_font)
            return True
        return False

    def redo(self):
        self._bubble.set_font(self._new_font)

    def undo(self):
        self._bubble.set_font(self._old_font)


class FillColorChangeCommand(QUndoCommand):
    """Undo/redo for changing a bubble's fill color (includes alpha/opacity)."""
    _ID = MERGE_ID_FILL_COLOR

    def __init__(self, bubble, old_color: QColor, new_color: QColor):
        super().__init__("更换填充颜色")
        self._bubble    = bubble
        self._old_color = QColor(old_color)
        self._new_color = QColor(new_color)

    def id(self) -> int:
        return self._ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        if isinstance(other, FillColorChangeCommand) and other._bubble is self._bubble:
            self._new_color = QColor(other._new_color)
            return True
        return False

    def redo(self):
        self._bubble.set_fill_color(self._new_color)

    def undo(self):
        self._bubble.set_fill_color(self._old_color)


class BorderColorChangeCommand(QUndoCommand):
    """Undo/redo for changing a bubble's border color."""
    _ID = MERGE_ID_BORDER_COLOR

    def __init__(self, bubble, old_color: QColor, new_color: QColor):
        super().__init__("更换边框颜色")
        self._bubble    = bubble
        self._old_color = QColor(old_color)
        self._new_color = QColor(new_color)

    def id(self) -> int:
        return self._ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        if isinstance(other, BorderColorChangeCommand) and other._bubble is self._bubble:
            self._new_color = QColor(other._new_color)
            return True
        return False

    def redo(self):
        self._bubble.set_border_color(self._new_color)

    def undo(self):
        self._bubble.set_border_color(self._old_color)


class BorderWidthChangeCommand(QUndoCommand):
    """Undo/redo for changing a bubble's border width."""
    _ID = MERGE_ID_BORDER_WIDTH

    def __init__(self, bubble, old_width: float, new_width: float):
        super().__init__("更换边框宽度")
        self._bubble    = bubble
        self._old_width = old_width
        self._new_width = new_width

    def id(self) -> int:
        return self._ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        if isinstance(other, BorderWidthChangeCommand) and other._bubble is self._bubble:
            self._new_width = other._new_width
            return True
        return False

    def redo(self):
        self._bubble.set_border_width(self._new_width)

    def undo(self):
        self._bubble.set_border_width(self._old_width)


class TextColorChangeCommand(QUndoCommand):
    """Undo/redo for changing a bubble's text color."""
    _ID = MERGE_ID_TEXT_COLOR

    def __init__(self, bubble, old_color: QColor, new_color: QColor):
        super().__init__("更换文字颜色")
        self._bubble    = bubble
        self._old_color = QColor(old_color)
        self._new_color = QColor(new_color)

    def id(self) -> int:
        return self._ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        if isinstance(other, TextColorChangeCommand) and other._bubble is self._bubble:
            self._new_color = QColor(other._new_color)
            return True
        return False

    def redo(self):
        self._bubble.set_text_color(self._new_color)

    def undo(self):
        self._bubble.set_text_color(self._old_color)


class TextAlignmentChangeCommand(QUndoCommand):
    """Undo/redo for changing bubble text alignment."""
    _ID = MERGE_ID_TEXT_ALIGNMENT

    def __init__(self, bubble, old_alignment: int, new_alignment: int):
        super().__init__("更换文字对齐")
        self._bubble = bubble
        self._old_alignment = old_alignment
        self._new_alignment = new_alignment

    def id(self) -> int:
        return self._ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        if isinstance(other, TextAlignmentChangeCommand) and other._bubble is self._bubble:
            self._new_alignment = other._new_alignment
            return True
        return False

    def redo(self):
        self._bubble.set_text_alignment(self._new_alignment)

    def undo(self):
        self._bubble.set_text_alignment(self._old_alignment)


class TailPositionChangeCommand(QUndoCommand):
    """Undo/redo for changing the bubble tail position preset."""
    _ID = MERGE_ID_TAIL_POSITION

    def __init__(self, bubble, old_position: str, new_position: str):
        super().__init__("更换尾巴位置")
        self._bubble = bubble
        self._old_position = old_position
        self._new_position = new_position

    def id(self) -> int:
        return self._ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        if isinstance(other, TailPositionChangeCommand) and other._bubble is self._bubble:
            self._new_position = other._new_position
            return True
        return False

    def redo(self):
        self._bubble.set_tail_position(self._new_position)

    def undo(self):
        self._bubble.set_tail_position(self._old_position)


class TailWidthChangeCommand(QUndoCommand):
    """Undo/redo for changing the bubble tail width."""
    _ID = MERGE_ID_TAIL_WIDTH

    def __init__(self, bubble, old_width: int, new_width: int):
        super().__init__("更换尾巴宽度")
        self._bubble = bubble
        self._old_width = old_width
        self._new_width = new_width

    def id(self) -> int:
        return self._ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        if isinstance(other, TailWidthChangeCommand) and other._bubble is self._bubble:
            self._new_width = other._new_width
            return True
        return False

    def redo(self):
        self._bubble.set_tail_width(self._new_width)

    def undo(self):
        self._bubble.set_tail_width(self._old_width)


class LobeTextChangeCommand(QUndoCommand):
    """Undo/redo for editing one lobe of a twin/triple balloon."""

    def __init__(self, bubble, index: int, old_text: str, new_text: str):
        super().__init__("编辑气泡瓣文字")
        self._bubble = bubble
        self._index = index
        self._old = old_text
        self._new = new_text

    def redo(self):
        self._bubble.set_lobe_text(self._index, self._new)

    def undo(self):
        self._bubble.set_lobe_text(self._index, self._old)


class InsetPhotoCommand(QUndoCommand):
    """Undo/redo for the photo inset inside a bubble (image + its sliders)."""
    _ID = MERGE_ID_INSET_PHOTO

    def __init__(self, bubble, old_state: dict, new_state: dict):
        super().__init__("更换气泡照片")
        self._bubble = bubble
        self._old = dict(old_state)
        self._new = dict(new_state)

    def id(self) -> int:
        return self._ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        if isinstance(other, InsetPhotoCommand) and other._bubble is self._bubble:
            self._new = dict(other._new)
            return True
        return False

    @staticmethod
    def _apply(bubble, state: dict):
        bubble._inset_pixmap = state.get("pixmap")
        bubble._inset_spacing = int(state.get("spacing", 25))
        bubble._inset_blur = int(state.get("blur", 3))
        bubble._inset_opacity = int(state.get("opacity", 100))
        bubble._inset_zoom = int(state.get("zoom", 100))
        bubble._inset_dx = int(state.get("dx", 0))
        bubble._inset_dy = int(state.get("dy", 0))
        bubble._inset_cache = None
        bubble.update()
        bubble._notify_changed()

    def redo(self):
        self._apply(self._bubble, self._new)

    def undo(self):
        self._apply(self._bubble, self._old)


class RotatePhotoCommand(QUndoCommand):
    """Undo/redo for rotating the base photo in 90° steps.

    Self-inverse: undoing N turns clockwise is 4-N turns clockwise, so no
    pixmap copy is kept.
    """

    def __init__(self, scene, turns: int):
        super().__init__("旋转照片")
        self._scene = scene
        self._turns = turns % 4
        self._saved = None   # item positions before the first rotation

    def redo(self):
        if self._saved is None and hasattr(self._scene, "stackable_items"):
            self._saved = [(i, QPointF(i.pos()))
                           for i in self._scene.stackable_items()]
        self._scene.apply_rotation(self._turns)

    def undo(self):
        self._scene.apply_rotation((4 - self._turns) % 4)
        # Rotating into a narrower frame makes the canvas clamp items inward,
        # so the inverse rotation alone cannot put them back — restore the
        # positions captured before the original turn.
        for item, pos in (self._saved or []):
            item.setPos(pos)


class CropPhotoCommand(QUndoCommand):
    """Undo/redo for cropping the base photo (keeps a copy of the original)."""

    def __init__(self, scene, rect: QRect):
        super().__init__("裁剪照片")
        self._scene = scene
        self._rect = QRect(rect)
        self._original = QPixmap(scene.photo_pixmap)

    def redo(self):
        self._scene.apply_crop(self._rect)

    def undo(self):
        self._scene.restore_photo(self._original, self._rect)


class TailShapeChangeCommand(QUndoCommand):
    """Undo/redo for changing the tail render shape (wedge/curved/line/dots/none)."""
    _ID = MERGE_ID_TAIL_SHAPE

    def __init__(self, bubble, old_shape: str, new_shape: str):
        super().__init__("更换尾巴形状")
        self._bubble = bubble
        self._old_shape = old_shape
        self._new_shape = new_shape

    def id(self) -> int:
        return self._ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        if isinstance(other, TailShapeChangeCommand) and other._bubble is self._bubble:
            self._new_shape = other._new_shape
            return True
        return False

    def redo(self):
        self._bubble.set_tail_shape(self._new_shape)

    def undo(self):
        self._bubble.set_tail_shape(self._old_shape)


class TailCountChangeCommand(QUndoCommand):
    """Undo/redo for changing the number of tails (0-3)."""
    _ID = MERGE_ID_TAIL_COUNT

    def __init__(self, bubble, old_count: int, new_count: int):
        super().__init__("更换尾巴数量")
        self._bubble = bubble
        self._old_count = old_count
        self._new_count = new_count

    def id(self) -> int:
        return self._ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        if isinstance(other, TailCountChangeCommand) and other._bubble is self._bubble:
            self._new_count = other._new_count
            return True
        return False

    def redo(self):
        self._bubble.set_tail_count(self._new_count)

    def undo(self):
        self._bubble.set_tail_count(self._old_count)


class TextOutlineChangeCommand(QUndoCommand):
    """Undo/redo for the text outline colour + width."""
    _ID = MERGE_ID_TEXT_OUTLINE

    def __init__(self, bubble, old_color: QColor, old_width: float,
                 new_color: QColor, new_width: float):
        super().__init__("更换文字描边")
        self._bubble = bubble
        self._old = (QColor(old_color), float(old_width))
        self._new = (QColor(new_color), float(new_width))

    def id(self) -> int:
        return self._ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        if isinstance(other, TextOutlineChangeCommand) and other._bubble is self._bubble:
            self._new = other._new
            return True
        return False

    def redo(self):
        self._bubble.set_text_outline(*self._new)

    def undo(self):
        self._bubble.set_text_outline(*self._old)


class ShadowChangeCommand(QUndoCommand):
    """Undo/redo for changing bubble shadow settings."""
    _ID = MERGE_ID_SHADOW

    def __init__(self, bubble, old_shadow: dict, new_shadow: dict):
        super().__init__("更换阴影")
        self._bubble = bubble
        self._old_shadow = dict(old_shadow)
        self._new_shadow = dict(new_shadow)

    def id(self) -> int:
        return self._ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        if isinstance(other, ShadowChangeCommand) and other._bubble is self._bubble:
            self._new_shadow = dict(other._new_shadow)
            return True
        return False

    def redo(self):
        self._bubble.set_shadow(self._new_shadow)

    def undo(self):
        self._bubble.set_shadow(self._old_shadow)


class ZValueChangeCommand(QUndoCommand):
    """Undo/redo for changing item stacking order."""
    _ID = MERGE_ID_Z_VALUE

    def __init__(self, item, old_z: float, new_z: float):
        super().__init__("更改图层顺序")
        self._item = item
        self._old_z = old_z
        self._new_z = new_z

    def id(self) -> int:
        return self._ID

    def mergeWith(self, other: QUndoCommand) -> bool:
        if isinstance(other, ZValueChangeCommand) and other._item is self._item:
            self._new_z = other._new_z
            return True
        return False

    def redo(self):
        self._item.setZValue(self._new_z)

    def undo(self):
        self._item.setZValue(self._old_z)
