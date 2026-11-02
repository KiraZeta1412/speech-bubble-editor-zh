"""
toolbar.py — Top toolbar: Open, Export, Undo, Redo, Meme, Dual, About.
"""

from PyQt6.QtWidgets import QToolBar, QWidget, QSizePolicy
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtCore import pyqtSignal, QSize

from constants import VIDEO_EXTENSIONS, IMAGE_EXTENSIONS
from file_dialogs import open_file
ALL_EXTENSIONS   = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS


class MainToolbar(QToolBar):

    open_media_requested  = pyqtSignal(str)   # single signal for any media type
    export_requested      = pyqtSignal()
    undo_requested        = pyqtSignal()
    redo_requested        = pyqtSignal()
    add_bubble_requested  = pyqtSignal()
    add_layer_requested   = pyqtSignal()
    meme_toggled          = pyqtSignal(bool)
    dual_toggled          = pyqtSignal(bool)
    about_requested       = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("主工具栏", parent)
        self.setMovable(False)
        self.setIconSize(QSize(20, 20))
        self._build_actions()

    def _build_actions(self):
        # Open (universal — photos and videos)
        act = QAction("打开", self)
        act.setShortcut("Ctrl+O")
        ext_str = ", ".join(e.lstrip(".").upper() for e in ALL_EXTENSIONS[:8]) + "…"
        act.setToolTip(f"打开照片或视频 ({ext_str})  (Ctrl+O)")
        act.triggered.connect(self._on_open)
        self.addAction(act)

        self.addSeparator()

        # Export
        self.act_export = QAction("导出", self)
        self.act_export.setShortcut("Ctrl+E")
        self.act_export.setToolTip("导出（含气泡）(Ctrl+E)")
        self.act_export.setEnabled(False)
        self.act_export.triggered.connect(self.export_requested)
        self.addAction(self.act_export)

        self.addSeparator()

        # Undo
        self.act_undo = QAction("撤销", self)
        self.act_undo.setShortcut("Ctrl+Z")
        self.act_undo.setEnabled(False)
        self.act_undo.triggered.connect(self.undo_requested)
        self.addAction(self.act_undo)

        # Redo
        self.act_redo = QAction("重做", self)
        self.act_redo.setShortcuts([QKeySequence("Ctrl+Y"),
                                    QKeySequence("Ctrl+Shift+Z")])
        self.act_redo.setEnabled(False)
        self.act_redo.triggered.connect(self.redo_requested)
        self.addAction(self.act_redo)

        self.addSeparator()

        # Add Bubble
        self.act_add_bubble = QAction("＋ 气泡", self)
        self.act_add_bubble.setShortcut("Ctrl+B")
        self.act_add_bubble.setToolTip(
            "添加 a speech bubble to the canvas (Ctrl+B)\n"
            "You can also double-click anywhere on the canvas"
        )
        self.act_add_bubble.setEnabled(False)
        self.act_add_bubble.triggered.connect(self.add_bubble_requested)
        self.addAction(self.act_add_bubble)

        self.addSeparator()

        # Add Layer
        self.act_add_layer = QAction("+ 图层", self)
        self.act_add_layer.setShortcut("Ctrl+L")
        self.act_add_layer.setToolTip(
            "添加 a photo or video as an overlay layer (Ctrl+L)\n"
            "Layers can be freely positioned and resized on the canvas"
        )
        self.act_add_layer.setEnabled(False)
        self.act_add_layer.triggered.connect(self.add_layer_requested)
        self.addAction(self.act_add_layer)

        self.addSeparator()

        # Meme
        self.act_meme = QAction("梗图", self)
        self.act_meme.setCheckable(True)
        self.act_meme.setToolTip("在上下添加黑色字幕条（梗图风格）")
        self.act_meme.setEnabled(False)
        self.act_meme.toggled.connect(self.meme_toggled)
        self.addAction(self.act_meme)

        self.addSeparator()

        # Dual
        self.act_dual = QAction("双格", self)
        self.act_dual.setCheckable(True)
        self.act_dual.setToolTip("Side-by-side dual media mode (before / after)")
        self.act_dual.setEnabled(False)
        self.act_dual.toggled.connect(self.dual_toggled)
        self.addAction(self.act_dual)

        # About — right-aligned
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding,
                             QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        act_about = QAction("关于", self)
        act_about.setToolTip("关于对话气泡编辑器")
        act_about.triggered.connect(self.about_requested)
        self.addAction(act_about)

    # ------------------------------------------------------------------

    def _on_open(self):
        ext_list = " ".join(f"*{e}" for e in ALL_EXTENSIONS)
        # 走 file_dialogs.open_file：它会从上次打开的文件夹起步并记住这次的目录。
        # 以前这里直接调 QFileDialog 且目录传空字符串，导致每次都从软件所在目录开始。
        path = open_file(
            self, "打开媒体", f"所有支持的媒体 ({ext_list})")
        if path:
            self.open_media_requested.emit(path)

    def set_media_loaded(self, loaded: bool):
        self.act_export.setEnabled(loaded)
        self.act_add_bubble.setEnabled(loaded)
        self.act_add_layer.setEnabled(loaded)
        self.act_meme.setEnabled(loaded)
        self.act_dual.setEnabled(loaded)

    def set_layer_enabled(self, enabled: bool):
        self.act_add_layer.setEnabled(enabled)

    def set_meme_checked(self, checked: bool):
        self.act_meme.blockSignals(True)
        self.act_meme.setChecked(checked)
        self.act_meme.blockSignals(False)

    def set_dual_checked(self, checked: bool):
        self.act_dual.blockSignals(True)
        self.act_dual.setChecked(checked)
        self.act_dual.blockSignals(False)

    def set_meme_enabled(self, enabled: bool):
        self.act_meme.setEnabled(enabled)

    def set_dual_enabled(self, enabled: bool):
        self.act_dual.setEnabled(enabled)

    def set_undo_enabled(self, enabled: bool):
        self.act_undo.setEnabled(enabled)

    def set_redo_enabled(self, enabled: bool):
        self.act_redo.setEnabled(enabled)
