"""
tool_sidebar.py — ToolSidebar: vertical icon strip on the left edge (v4 redesign).

Each tool button shows a purpose-built SVG icon above its label.
Active tool gets an accent-coloured left-edge indicator bar via QSS.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QToolButton, QButtonGroup
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QKeySequence

from icons import (
    make_icon, make_icon_pair, ACCENT, MUTED,
    ICON_SELECT, ICON_MOVE, ICON_BUBBLE,
    ICON_TEXT, ICON_LAYERS, ICON_MEME, ICON_DUAL, ICON_MANGA, ICON_COLLAGE,
    ICON_BLUR, ICON_PIXELATE, ICON_CROP, ICON_SPEEDLINES, ICON_ROTATE,
)

# (id, label, normal_svg, shortcut_or_none, checkable, in_tool_group)
TOOL_DEFS = [
    ("select",  "选择",  ICON_SELECT,  "V",      True,  True),
    ("move",    "移动",    ICON_MOVE,    "M",      True,  True),
    ("crop",    "裁剪",    ICON_CROP,    "C",      False, False),
    ("rotate",  "旋转",  ICON_ROTATE,  "R",      False, False),
    ("bubble",  "气泡",  ICON_BUBBLE,  "Ctrl+B", False, False),
    ("text",    "文字",    ICON_TEXT,    "T",      False, False),
    ("lines",   "线条",   ICON_SPEEDLINES, None,  False, False),
    ("redact",  "打码",    ICON_PIXELATE,None,     False, False),
    ("layers",  "图层",  ICON_LAYERS,  "Ctrl+L", False, False),
    ("meme",    "梗图",    ICON_MEME,    None,     True,  False),
    ("dual",    "双格",    ICON_DUAL,    None,     True,  False),
    ("collage", "拼贴", ICON_COLLAGE, None,     True,  False),
    ("manga",   "漫画",   ICON_MANGA,   None,     True,  False),
]

MEDIA_GATED = {"crop", "rotate", "bubble", "text", "lines", "redact",
               "layers", "meme", "dual"}


class ToolSidebar(QWidget):

    add_bubble_requested = pyqtSignal()
    add_text_requested   = pyqtSignal()
    crop_requested       = pyqtSignal()
    rotate_requested     = pyqtSignal()
    add_lines_requested  = pyqtSignal()
    add_redact_requested = pyqtSignal()
    add_layer_requested  = pyqtSignal()
    meme_toggled         = pyqtSignal(bool)
    dual_toggled         = pyqtSignal(bool)
    manga_toggled        = pyqtSignal(bool)
    collage_toggled      = pyqtSignal(bool)
    tool_changed         = pyqtSignal(str)   # "select" | "move"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._compact = False
        self._manual_compact_override = False
        self.setFixedWidth(104)
        self.setObjectName("ToolSidebar")
        self._buttons: dict[str, QToolButton] = {}
        self._build_ui()

    # ------------------------------------------------------------------

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 10, 8, 8)
        lay.setSpacing(1)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)

        group_breaks = {"crop", "bubble", "redact", "layers", "meme"}
        for tool_id, label, svg, shortcut, checkable, in_group in TOOL_DEFS:
            if tool_id in group_breaks:
                lay.addSpacing(6)
            btn = self._make_tool_btn(tool_id, label, svg, shortcut, checkable)
            self._buttons[tool_id] = btn

            if in_group:
                self._tool_group.addButton(btn)
            lay.addWidget(btn)

        # Wire non-group actions
        self._buttons["bubble"].clicked.connect(self.add_bubble_requested)
        self._buttons["text"].clicked.connect(self.add_text_requested)
        self._buttons["crop"].clicked.connect(self.crop_requested)
        self._buttons["rotate"].clicked.connect(self.rotate_requested)
        self._buttons["lines"].clicked.connect(self.add_lines_requested)
        self._buttons["redact"].clicked.connect(self.add_redact_requested)
        self._buttons["layers"].clicked.connect(self.add_layer_requested)
        self._buttons["meme"].toggled.connect(self.meme_toggled)
        self._buttons["dual"].toggled.connect(self.dual_toggled)
        self._buttons["manga"].toggled.connect(self.manga_toggled)
        self._buttons["collage"].toggled.connect(self.collage_toggled)

        # Select / Move switch the canvas interaction mode (edit vs hand-pan).
        self._buttons["select"].toggled.connect(
            lambda c: c and self.tool_changed.emit("select"))
        self._buttons["move"].toggled.connect(
            lambda c: c and self.tool_changed.emit("move"))

        # Default: Select checked
        self._buttons["select"].setChecked(True)

        lay.addStretch()

        # Collapse button
        self._collapse = QToolButton()
        self._collapse.setObjectName("SidebarCollapse")
        self._collapse.setText("«  紧凑")
        self._collapse.setFixedHeight(28)
        self._collapse.setToolTip("使用仅显示图标的紧凑工具栏")
        self._collapse.clicked.connect(self._toggle_compact)
        lay.addWidget(self._collapse)

    def _make_tool_btn(self, tool_id: str, label: str, svg: str,
                       shortcut: str | None, checkable: bool) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName(f"ToolBtn_{tool_id}")
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn.setText(label)
        btn.setFixedSize(88, 34)
        btn.setIconSize(QSize(18, 18))
        btn.setCheckable(checkable)
        btn.setAccessibleName(label)

        # Normal and accent icons
        icon_normal, icon_accent = make_icon_pair(svg, 20)
        btn.setIcon(icon_normal)
        btn._icon_normal = icon_normal   # type: ignore[attr-defined]
        btn._icon_accent = icon_accent   # type: ignore[attr-defined]

        if shortcut:
            btn.setShortcut(QKeySequence(shortcut))

        # Tooltip with shortcut hint
        tip = label
        if shortcut:
            tip += f"  ({shortcut})"
        btn.setToolTip(tip)

        # Swap icon on check state change
        if checkable:
            btn.toggled.connect(
                lambda checked, b=btn: b.setIcon(
                    b._icon_accent if checked else b._icon_normal   # type: ignore[attr-defined]
                )
            )

        return btn

    def _toggle_compact(self):
        self._manual_compact_override = True
        self.set_compact(not self._compact)

    def set_compact(self, compact: bool, automatic: bool = False):
        """Switch between labelled and icon-only tools without changing actions."""
        if automatic and self._manual_compact_override:
            return
        self._compact = bool(compact)
        self.setFixedWidth(56 if self._compact else 104)
        for tool_id, label, _svg, _shortcut, _checkable, _group in TOOL_DEFS:
            btn = self._buttons[tool_id]
            btn.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonIconOnly
                if self._compact else Qt.ToolButtonStyle.ToolButtonTextBesideIcon
            )
            btn.setFixedSize(40 if self._compact else 88, 34)
            btn.setText(label)
        self._collapse.setText("»" if self._compact else "«  紧凑")
        self._collapse.setToolTip(
            "显示工具名称" if self._compact else "使用仅显示图标的紧凑工具栏")

    # ------------------------------------------------------------------
    # Public API (mirrors v3 ToolSidebar)
    # ------------------------------------------------------------------

    def set_media_loaded(self, loaded: bool):
        for tool_id in MEDIA_GATED:
            btn = self._buttons.get(tool_id)
            if btn:
                btn.setEnabled(loaded)

    def set_meme_checked(self, checked: bool):
        btn = self._buttons["meme"]
        btn.blockSignals(True)
        btn.setChecked(checked)
        btn.setIcon(btn._icon_accent if checked else btn._icon_normal)   # type: ignore[attr-defined]
        btn.blockSignals(False)

    def set_dual_checked(self, checked: bool):
        btn = self._buttons["dual"]
        btn.blockSignals(True)
        btn.setChecked(checked)
        btn.setIcon(btn._icon_accent if checked else btn._icon_normal)   # type: ignore[attr-defined]
        btn.blockSignals(False)

    def set_manga_checked(self, checked: bool):
        btn = self._buttons["manga"]
        btn.blockSignals(True)
        btn.setChecked(checked)
        btn.setIcon(btn._icon_accent if checked else btn._icon_normal)   # type: ignore[attr-defined]
        btn.blockSignals(False)

    def set_collage_checked(self, checked: bool):
        btn = self._buttons["collage"]
        btn.blockSignals(True)
        btn.setChecked(checked)
        btn.setIcon(btn._icon_accent if checked else btn._icon_normal)   # type: ignore[attr-defined]
        btn.blockSignals(False)

    def set_meme_enabled(self, enabled: bool):
        self._buttons["meme"].setEnabled(enabled)

    def set_dual_enabled(self, enabled: bool):
        self._buttons["dual"].setEnabled(enabled)

    def set_manga_enabled(self, enabled: bool):
        self._buttons["manga"].setEnabled(enabled)

    def set_collage_enabled(self, enabled: bool):
        self._buttons["collage"].setEnabled(enabled)

    def set_manga_mode_active(self, active: bool, base_media_loaded: bool):
        """Enable page-safe tools in Comic mode, including on a blank page."""
        if active:
            for tool_id in ("bubble", "text", "lines", "redact", "layers"):
                self._buttons[tool_id].setEnabled(True)
            for tool_id in ("crop", "rotate", "meme", "dual"):
                self._buttons[tool_id].setEnabled(False)
        else:
            self.set_media_loaded(base_media_loaded)
