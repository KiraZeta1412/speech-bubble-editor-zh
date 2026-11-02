"""
crop_dialog.py — CropDialog: Balloon+-style photo cropping.

A modal dialog with a draggable/resizable crop rectangle over the photo,
aspect-ratio chips (Free / 1:1 / 4:3 / 3:2 / 16:9 / 9:16) and a live
width x height readout in photo pixels. Returns the chosen QRect via
crop_rect() after exec() accepts.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QToolButton,
    QButtonGroup, QWidget, QSizePolicy,
)
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPixmap
from PyQt6.QtCore import Qt, QRect, QRectF, QPointF

ASPECTS = (
    ("自由", None), ("1:1", 1.0), ("4:3", 4 / 3), ("3:2", 3 / 2),
    ("16:9", 16 / 9),
)

HANDLE = 12      # visual handle size (widget px)
HIT = 22         # grab tolerance (widget px)


class _CropArea(QWidget):
    """Photo preview with the interactive crop rectangle."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._pix = pixmap
        self._ratio = None           # None = free
        self._portrait = False       # flip the ratio chips to portrait
        # Crop rect in PHOTO pixel coordinates
        self._rect = QRectF(0, 0, pixmap.width(), pixmap.height())
        self._drag_mode: str | None = None   # "move" | "TL" | "TR" | "BL" | "BR"
        self._drag_start = QPointF()
        self._rect_start = QRectF()
        self.setMinimumSize(520, 380)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._on_change = None       # callback(rect)

    # -- coordinate mapping ------------------------------------------------

    def _view_geometry(self):
        """(scale, offset_x, offset_y) mapping photo px → widget px."""
        aw = self.width() - 24
        ah = self.height() - 24
        pw, ph = self._pix.width(), self._pix.height()
        scale = min(aw / pw, ah / ph)
        ox = (self.width() - pw * scale) / 2
        oy = (self.height() - ph * scale) / 2
        return scale, ox, oy

    def _to_widget(self, r: QRectF) -> QRectF:
        s, ox, oy = self._view_geometry()
        return QRectF(ox + r.x() * s, oy + r.y() * s,
                      r.width() * s, r.height() * s)

    def _to_photo(self, p: QPointF) -> QPointF:
        s, ox, oy = self._view_geometry()
        return QPointF((p.x() - ox) / s, (p.y() - oy) / s)

    # -- public ------------------------------------------------------------

    def crop_rect(self) -> QRect:
        return self._rect.toAlignedRect().intersected(
            QRect(0, 0, self._pix.width(), self._pix.height()))

    def rotate(self, turns: int):
        """Rotate the working image; the crop rect resets to the new frame."""
        from PyQt6.QtGui import QTransform
        self._pix = self._pix.transformed(
            QTransform().rotate(90 * turns),
            Qt.TransformationMode.SmoothTransformation)
        self._rect = QRectF(0, 0, self._pix.width(), self._pix.height())
        if self._ratio is not None:
            self._fit_ratio_rect()
        self._changed()
        self.update()

    def set_ratio(self, ratio: float | None):
        self._ratio = ratio
        if ratio is not None:
            self._fit_ratio_rect()
            self._changed()
        self.update()

    def set_portrait(self, portrait: bool):
        self._portrait = portrait
        if self._ratio is not None:
            self._fit_ratio_rect()
            self._changed()
        self.update()

    def _effective_ratio(self) -> float | None:
        if self._ratio is None:
            return None
        return 1.0 / self._ratio if self._portrait else self._ratio

    def _fit_ratio_rect(self):
        """Snap to the LARGEST crop of the chosen ratio that fits the photo,
        centred on the current selection. Never shrinks below the maximum fit,
        so clicking through the chips can't collapse the rect."""
        ratio = self._effective_ratio()
        pw, ph = float(self._pix.width()), float(self._pix.height())
        w = pw
        h = w / ratio
        if h > ph:
            h = ph
            w = h * ratio
        cx, cy = self._rect.center().x(), self._rect.center().y()
        self._rect = QRectF(cx - w / 2, cy - h / 2, w, h)
        self._clamp()

    def _changed(self):
        if self._on_change:
            self._on_change(self.crop_rect())

    def _clamp(self):
        pw, ph = self._pix.width(), self._pix.height()
        r = self._rect
        w = min(r.width(), pw)
        h = min(r.height(), ph)
        x = max(0.0, min(r.x(), pw - w))
        y = max(0.0, min(r.y(), ph - h))
        self._rect = QRectF(x, y, w, h)

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#141414"))
        s, ox, oy = self._view_geometry()
        target = QRectF(ox, oy, self._pix.width() * s, self._pix.height() * s)
        p.drawPixmap(target, self._pix,
                     QRectF(0, 0, self._pix.width(), self._pix.height()))

        # Dim everything outside the crop rect
        vr = self._to_widget(self._rect)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 140))
        for shade in (
            QRectF(target.left(), target.top(), target.width(), vr.top() - target.top()),
            QRectF(target.left(), vr.bottom(), target.width(), target.bottom() - vr.bottom()),
            QRectF(target.left(), vr.top(), vr.left() - target.left(), vr.height()),
            QRectF(vr.right(), vr.top(), target.right() - vr.right(), vr.height()),
        ):
            if shade.width() > 0 and shade.height() > 0:
                p.drawRect(shade)

        # Crop border + thirds grid
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#ffffff"), 1.6, Qt.PenStyle.DashLine))
        p.drawRect(vr)
        p.setPen(QPen(QColor(255, 255, 255, 70), 1.0))
        for i in (1, 2):
            x = vr.left() + vr.width() * i / 3
            y = vr.top() + vr.height() * i / 3
            p.drawLine(QPointF(x, vr.top()), QPointF(x, vr.bottom()))
            p.drawLine(QPointF(vr.left(), y), QPointF(vr.right(), y))

        # Corner handles
        p.setPen(QPen(QColor("#121212"), 1.5))
        p.setBrush(QBrush(QColor("#ff8a3d")))
        for cx, cy in ((vr.left(), vr.top()), (vr.right(), vr.top()),
                       (vr.left(), vr.bottom()), (vr.right(), vr.bottom())):
            p.drawRect(QRectF(cx - HANDLE / 2, cy - HANDLE / 2, HANDLE, HANDLE))

    # -- interaction -------------------------------------------------------

    def _hit_test(self, pos: QPointF) -> str | None:
        vr = self._to_widget(self._rect)
        corners = {"TL": (vr.left(), vr.top()), "TR": (vr.right(), vr.top()),
                   "BL": (vr.left(), vr.bottom()), "BR": (vr.right(), vr.bottom())}
        for name, (cx, cy) in corners.items():
            if abs(pos.x() - cx) <= HIT and abs(pos.y() - cy) <= HIT:
                return name
        if vr.contains(pos):
            return "move"
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            mode = self._hit_test(QPointF(event.position()))
            if mode:
                self._drag_mode = mode
                self._drag_start = self._to_photo(QPointF(event.position()))
                self._rect_start = QRectF(self._rect)

    def mouseMoveEvent(self, event):
        pos = QPointF(event.position())
        if self._drag_mode is None:
            mode = self._hit_test(pos)
            cursors = {"TL": Qt.CursorShape.SizeFDiagCursor,
                       "BR": Qt.CursorShape.SizeFDiagCursor,
                       "TR": Qt.CursorShape.SizeBDiagCursor,
                       "BL": Qt.CursorShape.SizeBDiagCursor,
                       "move": Qt.CursorShape.SizeAllCursor}
            self.setCursor(cursors.get(mode, Qt.CursorShape.ArrowCursor))
            return
        delta = self._to_photo(pos) - self._drag_start
        r = QRectF(self._rect_start)
        MIN = 32.0
        if self._drag_mode == "move":
            r.translate(delta)
        else:
            if "L" in self._drag_mode:
                r.setLeft(min(r.left() + delta.x(), r.right() - MIN))
            if "R" in self._drag_mode:
                r.setRight(max(r.right() + delta.x(), r.left() + MIN))
            if "T" in self._drag_mode:
                r.setTop(min(r.top() + delta.y(), r.bottom() - MIN))
            if "B" in self._drag_mode:
                r.setBottom(max(r.bottom() + delta.y(), r.top() + MIN))
            ratio = self._effective_ratio()
            if ratio is not None:
                # Constrain: adjust height to the dragged width, anchored on
                # the corner opposite the one being dragged.
                w = r.width()
                h = w / ratio
                if "T" in self._drag_mode:
                    r.setTop(r.bottom() - h)
                else:
                    r.setBottom(r.top() + h)
        self._rect = r
        self._clamp()
        self._changed()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_mode = None


class CropDialog(QDialog):
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("裁剪图片")
        self.setModal(True)
        self.resize(760, 620)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        self._area = _CropArea(pixmap)
        lay.addWidget(self._area, stretch=1)

        info_row = QHBoxLayout()
        self._size_label = QLabel()
        self._size_label.setStyleSheet("color: #9a9a9a; font-size: 12px;")
        info_row.addWidget(self._size_label)
        info_row.addStretch()
        info_row.addWidget(QLabel("旋转"))
        self._turns = 0
        for label, turns, tip in (("↺", 3, "逆时针旋转 90°"),
                                  ("↻", 1, "顺时针旋转 90°")):
            btn = QToolButton()
            btn.setObjectName("AlignButton")
            btn.setText(label)
            btn.setFixedSize(34, 30)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _c, t=turns: self._rotate(t))
            info_row.addWidget(btn)
        lay.addLayout(info_row)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(QLabel("宽高比"))
        self._ratio_group = QButtonGroup(self)
        self._ratio_group.setExclusive(True)
        for label, ratio in ASPECTS:
            btn = QToolButton()
            btn.setObjectName("AlignButton")
            btn.setText(label)
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.setMinimumWidth(52)
            btn.clicked.connect(lambda _c, rr=ratio: self._area.set_ratio(rr))
            self._ratio_group.addButton(btn)
            chips.addWidget(btn)
            if ratio is None:
                btn.setChecked(True)

        self._portrait_btn = QToolButton()
        self._portrait_btn.setObjectName("AlignButton")
        self._portrait_btn.setText("竖版")
        self._portrait_btn.setCheckable(True)
        self._portrait_btn.setFixedHeight(30)
        self._portrait_btn.setMinimumWidth(64)
        self._portrait_btn.setToolTip(
            "将宽高比切换为竖版（如 16:9 变为 9:16）")
        self._portrait_btn.toggled.connect(self._area.set_portrait)
        chips.addSpacing(10)
        chips.addWidget(self._portrait_btn)
        chips.addStretch()
        lay.addLayout(chips)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("取消")
        cancel.setMinimumSize(96, 34)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        ok = QPushButton("裁剪")
        ok.setObjectName("PrimaryButton")
        ok.setMinimumSize(96, 34)
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        buttons.addWidget(ok)
        lay.addLayout(buttons)

        self._area._on_change = self._update_size_label
        self._update_size_label(self._area.crop_rect())

    def _rotate(self, turns: int):
        """Rotation is applied to the photo itself when the dialog is accepted;
        here it just spins the working preview so the crop is chosen against
        the final orientation."""
        self._turns = (self._turns + turns) % 4
        self._area.rotate(turns)

    def _update_size_label(self, rect: QRect):
        self._size_label.setText(f"裁剪尺寸：  {rect.width()} × {rect.height()} px")

    def crop_rect(self) -> QRect:
        return self._area.crop_rect()

    def rotation_turns(self) -> int:
        """Net 90° clockwise turns chosen in the dialog (0-3)."""
        return self._turns
