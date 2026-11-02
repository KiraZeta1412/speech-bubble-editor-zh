"""
top_bar.py — TopBar: application header bar (v4 redesign).

Layout (left → right):
  Logo icon · App name · Byline  ···  打开  Export  | Undo  Redo  | Zoom ▾  ···  Gear  | ⋮
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QToolButton,
    QFrame, QMenu, QSizePolicy, QWidgetAction,
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import (QKeySequence, QAction, QIcon, QPixmap, QPainter,
                         QColor, QDesktopServices)
from PyQt6.QtCore import QUrl
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import QByteArray

from constants import (ALL_EXTENSIONS, URL_HOMEPAGE, URL_REPO,
                       URL_RELEASES, URL_ISSUES)
from version import __app_name__, __version__
from file_dialogs import open_file
from icons import (
    make_icon, ACCENT, FG, MUTED,
    ICON_OPEN, ICON_EXPORT, ICON_UNDO, ICON_REDO,
    ICON_RESET, ICON_ZOOM, ICON_KEYBOARD, ICON_MORE,
)


class TopBar(QWidget):

    open_media_requested  = pyqtSignal(str)
    export_requested      = pyqtSignal()
    undo_requested        = pyqtSignal()
    redo_requested        = pyqtSignal()
    reset_requested       = pyqtSignal()
    about_requested       = pyqtSignal()
    shortcuts_requested   = pyqtSignal()
    zoom_changed          = pyqtSignal(object)   # int (percent) or str ("fit-width"/"fit-window")
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setObjectName("TopBar")
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(6)

        # ── Logo ──────────────────────────────────────────────────────
        logo_icon = QLabel()
        logo_icon.setFixedSize(22, 22)
        logo_pix = self._make_logo_pixmap(22)
        logo_icon.setPixmap(logo_pix)
        lay.addWidget(logo_icon)

        app_name = QLabel(__app_name__)
        app_name.setObjectName("TopBarLogo")
        lay.addWidget(app_name)

        byline = QLabel("由 Long Weekend Labs 出品")
        byline.setObjectName("TopBarByline")
        byline.setMinimumWidth(138)
        byline.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        lay.addWidget(byline)
        self._byline = byline

        lay.addStretch(1)

        # ── Open ──────────────────────────────────────────────────────
        self.btn_open = self._action_btn(
            icon=make_icon(ICON_OPEN, 20, FG),
            label="打开…",
            tooltip="打开照片或视频  (Ctrl+O)",
            shortcut="Ctrl+O",
        )
        self.btn_open.clicked.connect(self._on_open)
        lay.addWidget(self.btn_open)

        # ── Export ────────────────────────────────────────────────────
        self.btn_export = self._action_btn(
            icon=make_icon(ICON_EXPORT, 20, "#ffffff"),
            label="导出…",
            tooltip="导出气泡  (Ctrl+E)",
            shortcut="Ctrl+E",
            accent=True,
        )
        self.btn_export.setObjectName("BtnExport")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_requested)
        lay.addWidget(self.btn_export)

        lay.addWidget(self._separator())

        # ── Undo / Redo ───────────────────────────────────────────────
        self.btn_undo = self._action_btn(
            icon=make_icon(ICON_UNDO, 20, MUTED),
            label="撤销",
            tooltip="撤销  (Ctrl+Z)",
            shortcut="Ctrl+Z",
        )
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self.undo_requested)
        lay.addWidget(self.btn_undo)

        self.btn_redo = self._action_btn(
            icon=make_icon(ICON_REDO, 20, MUTED),
            label="重做",
            tooltip="Redo  (Ctrl+Y / Ctrl+Shift+Z)",
            shortcut="Ctrl+Y",
        )
        self.btn_redo.setEnabled(False)
        self.btn_redo.clicked.connect(self.redo_requested)
        lay.addWidget(self.btn_redo)

        self.btn_reset = self._action_btn(
            icon=make_icon(ICON_RESET, 20, MUTED),
            label="重置",
            tooltip="开始新项目  (Ctrl+N)",
            shortcut="Ctrl+N",
        )
        self.btn_reset.setEnabled(False)
        self.btn_reset.clicked.connect(self.reset_requested)
        lay.addWidget(self.btn_reset)

        lay.addWidget(self._separator())

        # ── Zoom picker ───────────────────────────────────────────────
        self._zoom_level = 100
        self.btn_zoom = QPushButton()
        self.btn_zoom.setObjectName("ZoomBtn")
        self.btn_zoom.setFixedHeight(32)
        self.btn_zoom.setMinimumWidth(110)
        self.btn_zoom.setIcon(make_icon(ICON_ZOOM, 20, MUTED))
        self.btn_zoom.setIconSize(QSize(14, 14))
        self.btn_zoom.setToolTip("缩放级别 — 点击更改")
        self.btn_zoom.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._update_zoom_label()
        self.btn_zoom.clicked.connect(self._show_zoom_menu)
        lay.addWidget(self.btn_zoom)

        lay.addStretch(1)

        # ── Right icon buttons ─────────────────────────────────────────
        self.btn_shortcuts = self._icon_btn(
            make_icon(ICON_KEYBOARD, 20, MUTED),
            "Keyboard shortcuts  (Ctrl+/)",
        )
        self.btn_shortcuts.setShortcut(QKeySequence("Ctrl+/"))
        self.btn_shortcuts.clicked.connect(self.shortcuts_requested)
        lay.addWidget(self.btn_shortcuts)

        lay.addWidget(self._separator())

        # ── ⋮ More menu ───────────────────────────────────────────────
        self.btn_more = self._icon_btn(
            make_icon(ICON_MORE, 20, MUTED),
            "更多选项 — 关于、帮助、反馈",
        )
        self.btn_more.clicked.connect(self._show_more_menu)
        lay.addWidget(self.btn_more)
        self._compact = False

    # ------------------------------------------------------------------
    # Widget factories
    # ------------------------------------------------------------------

    def _action_btn(self, icon: QIcon, label: str, tooltip: str,
                    shortcut: str = "", accent: bool = False) -> QPushButton:
        btn = QPushButton(label)
        btn.setIcon(icon)
        btn.setIconSize(QSize(15, 15))
        btn.setFixedHeight(32)
        btn.setToolTip(tooltip)
        if shortcut:
            btn.setShortcut(QKeySequence(shortcut))
        return btn

    def _icon_btn(self, icon: QIcon, tooltip: str) -> QToolButton:
        btn = QToolButton()
        btn.setIcon(icon)
        btn.setIconSize(QSize(15, 15))
        btn.setFixedSize(32, 32)
        btn.setToolTip(tooltip)
        return btn

    def _separator(self) -> QFrame:
        sep = QFrame()
        sep.setObjectName("TopBarSeparator")
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedSize(1, 22)
        return sep

    def _make_logo_pixmap(self, size: int) -> QPixmap:
        """Speech-bubble logo mark in accent color."""
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10" fill="{ACCENT}" opacity="0.15"/>
            <path d="M8 12h8M8 8h8M8 16h5" stroke="{ACCENT}" stroke-width="2" stroke-linecap="round"/>
            <circle cx="12" cy="12" r="10" stroke="{ACCENT}" stroke-width="1.5" fill="none"/>
        </svg>'''
        renderer = QSvgRenderer(QByteArray(svg.encode()))
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        renderer.render(p)
        p.end()
        return pix

    # ------------------------------------------------------------------
    # Zoom menu
    # ------------------------------------------------------------------

    def _show_zoom_menu(self):
        menu = QMenu(self)
        menu.setObjectName("ZoomMenu")

        LEVELS = [
            ("200%",       200),
            ("150%",       150),
            ("100%",       100),
            ("75%",        75),
            ("50%",        50),
            None,
            ("适应宽度",  "fit-width"),
            ("适应窗口", "fit-window"),
        ]
        for item in LEVELS:
            if item is None:
                menu.addSeparator()
                continue
            label, value = item
            act = QAction(label, menu)
            if value == self._zoom_level:
                act.setCheckable(True)
                act.setChecked(True)
            act.triggered.connect(lambda checked=False, v=value: self._on_zoom(v))
            menu.addAction(act)

        # Show below the zoom button
        pos = self.btn_zoom.mapToGlobal(
            self.btn_zoom.rect().bottomLeft()
        )
        menu.exec(pos)

    def _on_zoom(self, value):
        self._zoom_level = value
        self._update_zoom_label()
        self.zoom_changed.emit(value)

    def _update_zoom_label(self):
        z = self._zoom_level
        if isinstance(z, int):
            label = f"  {z}%  "
        elif z == "fit-width":
            label = "  适应宽度  "
        else:
            label = "  适应窗口  "
        self.btn_zoom.setText(label)

    # ------------------------------------------------------------------
    # More menu
    # ------------------------------------------------------------------

    def _send_feedback(self):
        """打开 a new issue pre-filled with the build the report came from."""
        title = QUrl.toPercentEncoding(
            f"{__app_name__} {__version__} 反馈"
        ).data().decode()
        QDesktopServices.openUrl(QUrl(f"{URL_ISSUES}/new?title={title}"))

    def _show_more_menu(self):
        menu = QMenu(self)

        def _open(url):
            QDesktopServices.openUrl(QUrl(url))

        ITEMS = [
            ("新建项目", self.reset_requested.emit, self.btn_reset.isEnabled()),
            None,
            ("键盘快捷键",        self.shortcuts_requested.emit),
            None,
            ("关于对话气泡编辑器",  self.about_requested.emit),
            ("更新说明",               lambda: _open(URL_RELEASES)),
            ("帮助与文档",        lambda: _open(URL_HOMEPAGE)),
            None,
            ("发送反馈",               self._send_feedback),
            ("在 GitHub 上查看",              lambda: _open(URL_REPO)),
            None,
            ("检查更新",           lambda: _open(URL_RELEASES)),
        ]
        for item in ITEMS:
            if item is None:
                menu.addSeparator()
                continue
            if len(item) == 3:
                label, callback, enabled = item
            else:
                label, callback = item
                enabled = callback is not None
            act = QAction(label, menu)
            if callback:
                act.triggered.connect(callback)
            act.setEnabled(enabled)
            menu.addAction(act)

        pos = self.btn_more.mapToGlobal(
            self.btn_more.rect().bottomRight()
        )
        # align right edge of menu to button right edge
        menu.exec(pos)

    # ------------------------------------------------------------------
    # Open dialog
    # ------------------------------------------------------------------

    def _on_open(self):
        ext_list = " ".join(f"*{e}" for e in ALL_EXTENSIONS)
        path = open_file(self, "打开媒体", f"所有支持的媒体 ({ext_list})")
        if path:
            self.open_media_requested.emit(path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_media_loaded(self, loaded: bool):
        self.btn_export.setEnabled(loaded)

    def set_undo_enabled(self, enabled: bool):
        self.btn_undo.setEnabled(enabled)

    def set_redo_enabled(self, enabled: bool):
        self.btn_redo.setEnabled(enabled)

    def set_reset_enabled(self, enabled: bool):
        self.btn_reset.setEnabled(enabled)

    def set_compact(self, compact: bool):
        """Keep primary actions readable while collapsing secondary chrome."""
        compact = bool(compact)
        if compact == self._compact:
            return
        self._compact = compact
        self._byline.setVisible(not compact)
        self.btn_undo.setText("" if compact else "撤销")
        self.btn_redo.setText("" if compact else "重做")
        self.btn_reset.setVisible(not compact)
        for btn in (self.btn_undo, self.btn_redo):
            btn.setFixedWidth(34 if compact else btn.sizeHint().width())
        self.btn_zoom.setMinimumWidth(84 if compact else 110)

    def update_zoom(self, percent: int):
        """Called by PhotoView.zoom_changed signal."""
        self._zoom_level = percent
        self._update_zoom_label()
