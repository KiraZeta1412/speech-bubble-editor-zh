"""
frame_dialog.py — "Save / Share" style export dialog with a live preview.

Mirrors Balloon+'s export screen: a frame-style row, frame colour swatches, a
two-tone toggle, a caption with position/font/size, and an output size choice.
Returns the chosen FrameSettings plus a size scale via `result_settings()`.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QToolButton,
    QButtonGroup, QWidget, QLineEdit, QSlider, QComboBox, QCheckBox,
    QSizePolicy,
)
from PyQt6.QtGui import QPainter, QColor, QPixmap, QImage, QFontDatabase, QFont, QPen
from PyQt6.QtCore import Qt, QRectF, QSize

from frames import FrameSettings, FRAME_STYLES, FRAME_COLORS, apply_frame

SIZE_CHOICES = (("小", 0.35), ("中", 0.6), ("大", 0.8), ("原始", 1.0))


class FrameStyleButton(QToolButton):
    """Preview tile: a photo rectangle wearing that frame style."""

    def __init__(self, key: str, outer: float, inner: float, parent=None):
        super().__init__(parent)
        self._key, self._outer, self._inner = key, outer, inner
        self.setObjectName("StyleButton")
        self.setCheckable(True)
        self.setFixedSize(52, 44)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.isChecked():
            bg, border = QColor(255, 138, 61, 32), QColor("#ff8a3d")
        elif self.underMouse():
            bg, border = QColor("#333333"), QColor("#4a4a4a")
        else:
            bg, border = QColor("#2a2a2a"), QColor("#3a3a3a")
        p.setPen(QPen(border, 1.4))
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 7, 7)

        outer_r = QRectF(10, 8, 32, 28)
        if self._key == "none":
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor("#9a9a9a"), 1.2, Qt.PenStyle.DashLine))
            p.drawRect(outer_r)
            return
        b = max(2.0, 28 * self._outer * 4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#e6e6e6"))
        p.drawRect(outer_r)
        inner_r = outer_r.adjusted(b, b, -b, -b)
        if self._inner > 0:
            p.setBrush(QColor("#141414"))
            p.drawRect(inner_r)
            k = max(1.0, 28 * self._inner * 4)
            inner_r = inner_r.adjusted(k, k, -k, -k)
        p.setBrush(QColor("#6f7d8c"))
        p.drawRect(inner_r)


class ColorSwatch(QToolButton):
    def __init__(self, hexv: str, parent=None):
        super().__init__(parent)
        self._c = QColor(hexv)
        self.setObjectName("StyleButton")
        self.setCheckable(True)
        self.setFixedSize(34, 30)
        self.setToolTip(hexv.upper())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        border = QColor("#ff8a3d") if self.isChecked() else QColor("#3a3a3a")
        p.setPen(QPen(border, 2.0 if self.isChecked() else 1.2))
        p.setBrush(self._c)
        p.drawRoundedRect(QRectF(2, 2, self.width() - 4, self.height() - 4), 5, 5)


class FrameDialog(QDialog):
    def __init__(self, source: QImage, parent=None):
        super().__init__(parent)
        self.setWindowTitle("导出 — 画框与说明文字")
        self.setModal(True)
        self.resize(720, 780)
        self._source = source
        self._cfg = FrameSettings()
        self._scale = 1.0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(9)

        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(300)
        self._preview.setSizePolicy(QSizePolicy.Policy.Expanding,
                                    QSizePolicy.Policy.Expanding)
        lay.addWidget(self._preview, stretch=1)

        # --- frame styles -------------------------------------------------
        lay.addWidget(self._section_label("画框"))
        style_row = QHBoxLayout()
        style_row.setSpacing(6)
        self._style_group = QButtonGroup(self)
        self._style_group.setExclusive(True)
        for key, label, outer, inner, tip in FRAME_STYLES:
            btn = FrameStyleButton(key, outer, inner)
            btn.setToolTip(f"{label} — {tip}")
            btn.clicked.connect(lambda _c, k=key: self._set_style(k))
            self._style_group.addButton(btn)
            style_row.addWidget(btn)
            if key == "none":
                btn.setChecked(True)
        style_row.addStretch()
        lay.addLayout(style_row)

        # --- colours + two-tone -------------------------------------------
        lay.addWidget(self._section_label("画框颜色"))
        color_row = QHBoxLayout()
        color_row.setSpacing(6)
        self._color_group = QButtonGroup(self)
        self._color_group.setExclusive(True)
        for hexv in FRAME_COLORS:
            sw = ColorSwatch(hexv)
            sw.clicked.connect(lambda _c, h=hexv: self._set_color(h))
            self._color_group.addButton(sw)
            color_row.addWidget(sw)
            if hexv == "#ffffff":
                sw.setChecked(True)
        color_row.addStretch()
        self._two_tone = QCheckBox("双色")
        self._two_tone.setToolTip("为画框添加对比色")
        self._two_tone.toggled.connect(self._set_two_tone)
        color_row.addWidget(self._two_tone)
        lay.addLayout(color_row)

        # --- caption -------------------------------------------------------
        lay.addWidget(self._section_label("旁白框"))
        cap_row = QHBoxLayout()
        cap_row.setSpacing(8)
        self._caption = QLineEdit()
        self._caption.setPlaceholderText("可选：在画框上打印说明文字")
        self._caption.textChanged.connect(self._set_caption)
        cap_row.addWidget(self._caption, stretch=1)
        self._pos_combo = QComboBox()
        self._pos_combo.addItems(("底部", "顶部"))
        self._pos_combo.setToolTip("说明文字位置")
        self._pos_combo.currentTextChanged.connect(
            lambda t: self._update(caption_position=t.lower()))
        cap_row.addWidget(self._pos_combo)
        lay.addLayout(cap_row)

        font_row = QHBoxLayout()
        font_row.setSpacing(8)
        self._font_combo = QComboBox()
        available = set(QFontDatabase.families())
        fonts = [f for f in ("Inter", "Comic Neue", "Klee One", "Anton", "Bangers",
                             "Permanent Marker", "Patrick Hand", "Montserrat")
                 if f in available] or sorted(available)[:8]
        self._font_combo.addItems(fonts)
        self._font_combo.currentTextChanged.connect(
            lambda t: self._update(caption_font=t))
        font_row.addWidget(self._font_combo, stretch=1)
        font_row.addWidget(QLabel("大小"))
        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._size_slider.setRange(4, 30)
        self._size_slider.setValue(10)
        self._size_slider.setFixedWidth(150)
        self._size_slider.valueChanged.connect(
            lambda v: self._update(caption_size=v))
        font_row.addWidget(self._size_slider)
        lay.addLayout(font_row)

        # --- output size ----------------------------------------------------
        size_row = QHBoxLayout()
        size_row.setSpacing(6)
        self._size_label = QLabel()
        size_row.addWidget(self._size_label, stretch=1)
        self._size_group = QButtonGroup(self)
        self._size_group.setExclusive(True)
        for label, factor in SIZE_CHOICES:
            btn = QToolButton()
            btn.setObjectName("AlignButton")
            btn.setText(label)
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.setMinimumWidth(72)
            btn.clicked.connect(lambda _c, f=factor: self._set_scale(f))
            self._size_group.addButton(btn)
            size_row.addWidget(btn)
            if factor == 1.0:
                btn.setChecked(True)
        lay.addLayout(size_row)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("取消")
        cancel.setMinimumSize(96, 34)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        ok = QPushButton("导出…")
        ok.setObjectName("PrimaryButton")
        ok.setMinimumSize(110, 34)
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        buttons.addWidget(ok)
        lay.addLayout(buttons)

        self._refresh()

    # ------------------------------------------------------------------

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("InspectorSectionTitle")
        return lbl

    def _set_style(self, key: str):
        self._update(style=key)

    def _set_color(self, hexv: str):
        # Pair each frame colour with a sensible contrasting second tone.
        accent = "#000000" if hexv.lower() in ("#ffffff", "#f6cfe0", "#b8d4c2",
                                               "#c9b79c") else "#ffffff"
        self._update(color=hexv, accent=accent)

    def _set_two_tone(self, on: bool):
        self._update(two_tone=on)

    def _set_caption(self, text: str):
        self._update(caption=text)

    def _set_scale(self, factor: float):
        self._scale = factor
        self._refresh()

    def _update(self, **changes):
        for key, value in changes.items():
            setattr(self._cfg, key, value)
        self._refresh()

    def _refresh(self):
        framed = apply_frame(self._source, self._cfg)
        w = max(1, int(framed.width() * self._scale))
        h = max(1, int(framed.height() * self._scale))
        self._size_label.setText(f"输出尺寸：  {w} × {h} px")
        box = self._preview.size()
        pm = QPixmap.fromImage(framed).scaled(
            QSize(max(80, box.width() - 8), max(80, box.height() - 8)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self._preview.setPixmap(pm)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh()

    # ------------------------------------------------------------------

    def settings(self) -> FrameSettings:
        return self._cfg

    def scale(self) -> float:
        return self._scale
