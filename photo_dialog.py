"""
photo_dialog.py — "气泡内照片" popup (Balloon+'s Photo tab as a dialog).

Keeps the inset-photo controls out of the always-on inspector: they only
matter once a bubble actually has a photo, so they live behind a button and
show a live preview of the bubble while you tune them.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QSizePolicy,
)
from PyQt6.QtGui import QPainter, QPixmap, QImage, QColor
from PyQt6.QtCore import Qt, QRectF, QSize

from constants import IMAGE_EXTENSIONS


class _DragPreview(QLabel):
    """Preview that pans the bubble's photo when you drag on it.

    Sliders for X/Y were the wrong control for a spatial value — you position
    a photo by moving it, not by nudging two numbers.
    """

    def __init__(self, owner):
        super().__init__()
        self._owner = owner
        self._last = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self._owner.can_pan()):
            self._last = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._last is None:
            return
        pos = event.position()
        self._owner.pan_by(pos.x() - self._last.x(), pos.y() - self._last.y())
        self._last = pos

    def mouseReleaseEvent(self, event):
        self._last = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class PhotoInBubbleDialog(QDialog):
    """Live-preview editor for a bubble's inset photo.

    Edits the bubble directly so the canvas updates as you drag; the caller
    wraps the whole session in a single undo command.
    """

    def __init__(self, bubble, parent=None):
        super().__init__(parent)
        self.setWindowTitle("气泡内照片")
        self.setModal(True)
        self.resize(430, 620)
        self._bubble = bubble

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        self._preview = _DragPreview(self)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(230)
        self._preview.setSizePolicy(QSizePolicy.Policy.Expanding,
                                    QSizePolicy.Policy.Expanding)
        lay.addWidget(self._preview, stretch=1)

        pick_row = QHBoxLayout()
        pick_row.setSpacing(8)
        self._pick = QPushButton("选择图片…")
        self._pick.setObjectName("LayerActionButton")
        self._pick.setMinimumHeight(32)
        self._pick.clicked.connect(self._on_pick)
        pick_row.addWidget(self._pick, stretch=2)
        self._remove = QPushButton("移除")
        self._remove.setObjectName("LayerActionButton")
        self._remove.setMinimumHeight(32)
        self._remove.clicked.connect(self._on_remove)
        pick_row.addWidget(self._remove, stretch=1)
        lay.addLayout(pick_row)

        self._sliders = {}
        for key, label, lo, hi, suffix in (
            ("spacing", "间距", 0, 90, " %"),
            ("blur", "模糊", 0, 40, ""),
            ("opacity", "不透明度", 0, 100, " %"),
            ("zoom", "缩放", 50, 400, " %"),
        ):
            row = QHBoxLayout()
            name = QLabel(label)
            name.setObjectName("InspectorLabel")
            name.setMinimumWidth(64)
            row.addWidget(name)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(lo, hi)
            row.addWidget(slider, stretch=1)
            value = QLabel()
            value.setObjectName("InspectorHint")
            value.setMinimumWidth(48)
            value.setAlignment(Qt.AlignmentFlag.AlignRight
                               | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(value)
            slider.valueChanged.connect(
                lambda v, k=key, lb=value, sf=suffix: self._on_slider(k, v, lb, sf))
            lay.addLayout(row)
            self._sliders[key] = (slider, value, suffix)

        hint = QLabel("Drag the preview to position the photo. "
                      "You can also Alt+drag the bubble on the canvas.")
        hint.setObjectName("InspectorHint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        buttons = QHBoxLayout()
        buttons.addStretch()
        done = QPushButton("完成")
        done.setObjectName("PrimaryButton")
        done.setMinimumSize(110, 34)
        done.setDefault(True)
        done.clicked.connect(self.accept)
        buttons.addWidget(done)
        lay.addLayout(buttons)

        self._loading = True
        self._load_from_bubble()
        self._loading = False
        self._refresh()

    # ------------------------------------------------------------------

    def _load_from_bubble(self):
        b = self._bubble
        values = {
            "spacing": b.get_inset_spacing(), "blur": b.get_inset_blur(),
            "opacity": b.get_inset_opacity(), "zoom": b.get_inset_zoom(),
        }
        for key, (slider, label, suffix) in self._sliders.items():
            slider.setValue(values[key])
            label.setText(f"{values[key]}{suffix}")

    def _on_slider(self, key: str, value: int, label: QLabel, suffix: str):
        label.setText(f"{value}{suffix}")
        if self._loading:
            return
        b = self._bubble
        if key == "spacing":
            b.set_inset_spacing(value)
        elif key == "blur":
            b.set_inset_blur(value)
        elif key == "opacity":
            b.set_inset_opacity(value)
        elif key == "zoom":
            b.set_inset_zoom(value)
        self._refresh()

    # -- panning ---------------------------------------------------------

    def can_pan(self) -> bool:
        return self._bubble.has_inset_photo()

    def pan_by(self, dx: float, dy: float):
        """Translate a drag on the preview into a pan of the inset photo."""
        if not self.can_pan():
            return
        pm = self._preview.pixmap()
        src = self._bubble.sceneBoundingRect()
        if pm is None or pm.width() < 1 or src.width() < 1:
            return
        scale = src.width() / pm.width()
        self._bubble.nudge_inset(dx * scale, dy * scale)
        self._refresh()

    def _on_pick(self):
        from file_dialogs import open_file
        exts = " ".join(f"*{e}" for e in IMAGE_EXTENSIONS)
        path = open_file(self, "为气泡选择图片", f"图片 ({exts})")
        if not path:
            return
        pm = QPixmap(path)
        if pm.isNull():
            return
        self._bubble.set_inset_pixmap(pm)
        self._refresh()

    def _on_remove(self):
        self._bubble.clear_inset_photo()
        self._refresh()

    def _refresh(self):
        has = self._bubble.has_inset_photo()
        self._pick.setText("更换图片…" if has else "选择图片…")
        self._remove.setEnabled(has)
        for slider, _label, _suffix in self._sliders.values():
            slider.setEnabled(has)

        # Render just this bubble into the preview.
        box = self._preview.size()
        w = max(80, box.width() - 8)
        h = max(80, box.height() - 8)
        image = QImage(w, h, QImage.Format.Format_ARGB32)
        image.fill(QColor("#232323"))
        scene = self._bubble.scene()
        if scene is not None:
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            src = self._bubble.sceneBoundingRect().adjusted(-10, -10, 10, 10)
            scene.render(painter, QRectF(0, 0, w, h), src,
                         Qt.AspectRatioMode.KeepAspectRatio)
            painter.end()
        self._preview.setPixmap(QPixmap.fromImage(image))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh()
