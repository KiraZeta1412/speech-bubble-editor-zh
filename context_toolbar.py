"""
context_toolbar.py — ContextToolbar: dynamic bar shown when a bubble/item is selected.

Sits between TopBar and the canvas content area. Provides:
  - Alignment (left/hcenter/right/top/vcenter/bottom)
  - Layer order (bring to front/forward/backward/back)
  - Transform (flip H/V — UI only, handler is no-op until implemented)
  - Delete

Signal names match what main_window.py expects:
  align_requested(str)     — "left"|"hcenter"|"right"|"top"|"vcenter"|"bottom"
  z_requested(str)         — "front"|"forward"|"backward"|"back"
  flip_h_requested()
  flip_v_requested()
  delete_requested()

Visibility API:
  show_for_bubble()
  show_for_media()
  hide_toolbar()
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QFrame, QSlider,
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QColor

from icons import (
    make_icon, ACCENT, FG, MUTED, DANGER,
    ICON_ALIGN_LEFT, ICON_ALIGN_HCENTER, ICON_ALIGN_RIGHT,
    ICON_ALIGN_TOP, ICON_ALIGN_VCENTER, ICON_ALIGN_BOTTOM,
    ICON_TO_FRONT, ICON_BRING_FWD, ICON_SEND_BACK, ICON_TO_BACK,
    ICON_FLIP_H, ICON_FLIP_V, ICON_DELETE,
)


class ContextToolbar(QWidget):

    align_requested  = pyqtSignal(str)   # "left"|"hcenter"|"right"|"top"|"vcenter"|"bottom"
    z_requested      = pyqtSignal(str)   # "front"|"forward"|"backward"|"back"
    flip_h_requested = pyqtSignal()
    flip_v_requested = pyqtSignal()
    delete_requested = pyqtSignal()
    manga_regenerate_requested = pyqtSignal()
    manga_zoom_changed = pyqtSignal(int)
    manga_fit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ContextToolbar")
        self.setFixedHeight(38)
        self._action_widgets = []
        self._manga_active = False
        self._page_mode = "manga"
        self._updating_manga_zoom = False
        self._build_ui()
        self.hide_toolbar()

    # ------------------------------------------------------------------

    def _build_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(0)

        self._selection_group = QWidget()
        normal = QHBoxLayout(self._selection_group)
        normal.setContentsMargins(0, 0, 0, 0)
        normal.setSpacing(2)
        lay.addWidget(self._selection_group, stretch=1)

        # ── Selection chip ─────────────────────────────────────────────
        self._chip = QLabel("已选中气泡")
        self._chip.setObjectName("ContextChip")
        self._chip.setFixedHeight(24)
        # Fixed width: the chip's text changes with the selection, and letting
        # it resize shoved every toolbar button sideways on each click.
        self._chip.setFixedWidth(118)
        self._chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        normal.addWidget(self._chip)
        normal.addSpacing(8)

        # ── Alignment group ────────────────────────────────────────────
        ALIGN = [
            (ICON_ALIGN_LEFT,    "left",    "左边缘对齐画布"),
            (ICON_ALIGN_HCENTER, "hcenter", "在画布上水平居中"),
            (ICON_ALIGN_RIGHT,   "right",   "右边缘对齐画布"),
            (ICON_ALIGN_TOP,     "top",     "上边缘对齐画布"),
            (ICON_ALIGN_VCENTER, "vcenter", "在画布上垂直居中"),
            (ICON_ALIGN_BOTTOM,  "bottom",  "下边缘对齐画布"),
        ]
        for svg, mode, tip in ALIGN:
            btn = self._ctx_btn(svg, tip)
            btn.clicked.connect(lambda _, m=mode: self.align_requested.emit(m))
            self._action_widgets.append(btn)
            normal.addWidget(btn)

        normal.addWidget(self._sep())

        # ── Layer order ────────────────────────────────────────────────
        ORDER = [
            (ICON_TO_FRONT,  "front",    "移到最前 — 置于所有图层之上"),
            (ICON_BRING_FWD, "forward",  "上移一层 — 向上移动一层"),
            (ICON_SEND_BACK, "backward", "下移一层 — 向下移动一层"),
            (ICON_TO_BACK,   "back",     "移到最底 — 置于所有图层之下"),
        ]
        for svg, mode, tip in ORDER:
            btn = self._ctx_btn(svg, tip)
            btn.clicked.connect(lambda _, m=mode: self.z_requested.emit(m))
            self._action_widgets.append(btn)
            normal.addWidget(btn)

        normal.addWidget(self._sep())

        # ── Transform ─────────────────────────────────────────────────
        flip_h_btn = self._ctx_btn(ICON_FLIP_H, "水平翻转")
        flip_h_btn.clicked.connect(self.flip_h_requested)
        self._action_widgets.append(flip_h_btn)
        normal.addWidget(flip_h_btn)

        flip_v_btn = self._ctx_btn(ICON_FLIP_V, "垂直翻转")
        flip_v_btn.clicked.connect(self.flip_v_requested)
        self._action_widgets.append(flip_v_btn)
        normal.addWidget(flip_v_btn)

        normal.addWidget(self._sep())

        # ── Delete ────────────────────────────────────────────────────
        del_btn = self._ctx_btn(ICON_DELETE, "删除选中的气泡  (Del)",
                                danger=True)
        del_btn.setObjectName("ContextDeleteBtn")
        del_btn.clicked.connect(self.delete_requested)
        self._action_widgets.append(del_btn)
        normal.addWidget(del_btn)

        normal.addStretch()

        # Manga Maker replaces this bar in-place; it never adds a second row.
        self._manga_group = QWidget()
        manga = QHBoxLayout(self._manga_group)
        manga.setContentsMargins(0, 0, 0, 0)
        manga.setSpacing(6)

        self._page_mode_chip = QLabel("漫画制作")
        self._page_mode_chip.setObjectName("MangaChip")
        self._page_mode_chip.setFixedHeight(24)
        manga.addWidget(self._page_mode_chip)
        self._manga_layout_label = QLabel("随机页面")
        self._manga_layout_label.setObjectName("MangaLayoutLabel")
        manga.addWidget(self._manga_layout_label)
        manga.addStretch()

        self._page_hint = QLabel("向内拖拽可裁剪 · 向外拖拽可重新排序")
        self._page_hint.setObjectName("MangaHint")
        self._page_hint.setToolTip(
            "点击分格将其选中，然后在画框内拖动图片即可裁剪")
        manga.addWidget(self._page_hint)

        zoom_label = QLabel("缩放")
        zoom_label.setObjectName("MangaHint")
        zoom_label.setToolTip(
            "在不改变分格的情况下调整分格内选中图片的大小")
        manga.addWidget(zoom_label)
        self._manga_zoom = QSlider(Qt.Orientation.Horizontal)
        self._manga_zoom.setRange(10, 500)
        self._manga_zoom.setValue(100)
        self._manga_zoom.setFixedWidth(130)
        self._manga_zoom.setToolTip("调整分格内选中图片的大小")
        self._manga_zoom.valueChanged.connect(self._on_manga_zoom)
        manga.addWidget(self._manga_zoom)
        self._manga_zoom_value = QLabel("100%")
        self._manga_zoom_value.setObjectName("MangaLayoutLabel")
        self._manga_zoom_value.setFixedWidth(42)
        manga.addWidget(self._manga_zoom_value)

        fit = QPushButton("显示全部")
        fit.setToolTip(
            "缩小选中的照片，直到整张图片都可见")
        fit.setFixedHeight(26)
        fit.clicked.connect(self.manga_fit_requested)
        manga.addWidget(fit)

        self._page_regenerate = QPushButton("↻  重新生成")
        self._page_regenerate.setObjectName("MangaRegenerateBtn")
        self._page_regenerate.setToolTip(
            "生成另一种 4、6、7 或 8 格漫画页面")
        self._page_regenerate.setFixedHeight(26)
        self._page_regenerate.clicked.connect(self.manga_regenerate_requested)
        manga.addWidget(self._page_regenerate)

        lay.addWidget(self._manga_group, stretch=1)
        self._manga_group.hide()

        # Idle content occupies the same fixed row as selection/page controls.
        # Swapping content instead of hiding the toolbar prevents Fit Window
        # from recomputing zoom whenever selection changes.
        self._idle_group = QWidget()
        idle = QHBoxLayout(self._idle_group)
        idle.setContentsMargins(4, 0, 4, 0)
        idle_hint = QLabel("选择气泡或图层以使用对齐与排列控制")
        idle_hint.setObjectName("ContextIdleHint")
        idle.addWidget(idle_hint)
        idle.addStretch()
        lay.addWidget(self._idle_group, stretch=1)
        self._idle_group.hide()

    def _on_manga_zoom(self, value: int):
        self._manga_zoom_value.setText(f"{value}%")
        if not self._updating_manga_zoom:
            self.manga_zoom_changed.emit(value)

    def _refresh_page_hint(self):
        unit = "frame" if self._page_mode == "collage" else "panel"
        self._page_hint.setText("向内拖拽可裁剪 · 向外拖拽可重新排序")
        self._page_hint.setToolTip(
            f"在激活的{unit}内拖动可重新定位裁剪；继续拖到"
            f"外部的另一{unit}上可移动或交换；按住 Shift 拖动可立即重排。")

    # ------------------------------------------------------------------

    def _ctx_btn(self, svg: str, tip: str, danger: bool = False) -> QPushButton:
        color = DANGER if danger else FG
        btn = QPushButton()
        btn.setObjectName("ContextDeleteBtn" if danger else "ContextBtn")
        btn.setIcon(make_icon(svg, 20, color))
        btn.setIconSize(QSize(18, 18))
        btn.setFixedSize(30, 26)
        btn.setToolTip(tip)
        btn.setFlat(True)
        return btn

    def _sep(self) -> QFrame:
        sep = QFrame()
        sep.setObjectName("ContextSep")
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedSize(1, 18)
        return sep

    # ------------------------------------------------------------------
    # Public visibility API (called by main_window.py)
    # ------------------------------------------------------------------

    def show_for_bubble(self):
        self.show()
        self._idle_group.hide()
        self._selection_group.show()
        self._manga_group.hide()
        self._chip.setText("已选中气泡")
        self._set_actions_enabled(True)

    def show_for_media(self):
        self.show()
        self._idle_group.hide()
        self._selection_group.show()
        self._manga_group.hide()
        self._chip.setText("已选中图层")
        self._set_actions_enabled(True)

    def hide_toolbar(self):
        if self._manga_active:
            self.show()
            self._idle_group.hide()
            self._selection_group.hide()
            self._manga_group.show()
            return
        self.show()
        self._selection_group.hide()
        self._manga_group.hide()
        self._idle_group.show()

    def set_manga_mode(self, active: bool):
        self.set_page_mode("manga" if active else None)

    def set_collage_mode(self, active: bool):
        self.set_page_mode("collage" if active else None)

    def set_page_mode(self, mode: str | None):
        self._manga_active = mode is not None
        if mode is not None:
            self._page_mode = mode
        if mode == "collage":
            self._page_mode_chip.setText("照片拼贴")
            self._page_regenerate.setText("↻  随机排列")
            self._page_regenerate.setToolTip(
                "保留照片的同时尝试另一种拼贴布局")
        else:
            self._page_mode_chip.setText("漫画制作")
            self._page_regenerate.setText("↻  重新生成")
            self._page_regenerate.setToolTip(
                "使用当前形状设置生成另一种漫画构图")
        self._refresh_page_hint()
        if mode is not None:
            self.set_manga_zoom(100, False)
        self.hide_toolbar()

    def set_manga_layout_name(self, name: str):
        self._manga_layout_label.setText(name)

    def show_for_manga_panel(self, zoom_percent: int, has_image: bool = True):
        self.show()
        self._idle_group.hide()
        self._selection_group.hide()
        self._manga_group.show()
        self.set_manga_zoom(zoom_percent, has_image)

    def set_manga_zoom(self, percent: int, enabled: bool = True):
        self._updating_manga_zoom = True
        try:
            self._manga_zoom.setValue(max(10, min(500, int(percent))))
            self._manga_zoom.setEnabled(enabled)
        finally:
            self._updating_manga_zoom = False

    def _set_actions_enabled(self, enabled: bool):
        for widget in self._action_widgets:
            widget.setEnabled(enabled)
