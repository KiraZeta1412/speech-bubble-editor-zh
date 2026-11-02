"""
main_window.py — MainWindow: v4布局 with TopBar, ContextToolbar,
                 ToolSidebar, CanvasArea, InspectorDock, and StatusBar.
"""

import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMessageBox, QApplication, QLineEdit, QTextEdit, QPlainTextEdit,
    QComboBox, QSpinBox, QDoubleSpinBox, QSplitter,
)
from PyQt6.QtCore import Qt, QPointF, QEvent, QRect, QRectF, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut

from canvas import PhotoScene, PhotoView, ZoomBar
from top_bar import TopBar
from tool_sidebar import ToolSidebar
from context_toolbar import ContextToolbar
from manga_maker import MangaPanelItem
from inspector_dock import InspectorDock
from video_controls import VideoControls
from bubble import BubbleItem
from media_item import MediaItem
from editor_controller import EditorController
from version import __version__, __app_name__
from constants import VIDEO_EXTENSIONS, IMAGE_EXTENSIONS, ALL_EXTENSIONS
from file_dialogs import open_file
from redaction import STYLE_MOSAIC
from about_dialog import AboutDialog
from shortcuts_dialog import ShortcutsDialog


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{__app_name__} · v{__version__}")
        self.setMinimumSize(820, 620)
        self.resize(1440, 900)
        self._build_ui()
        self._connect_signals()
        QApplication.instance().installEventFilter(self)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.scene          = PhotoScene()
        self.controller     = EditorController(self.scene)
        self.view           = PhotoView(self.scene)
        self.zoom_bar       = ZoomBar(self.view)
        self.video_controls = VideoControls()

        self.top_bar      = TopBar(self)
        self.ctx_toolbar  = ContextToolbar(self)
        self.tool_sidebar = ToolSidebar(self)
        self.inspector    = InspectorDock(self)
        self.props        = self.inspector.props
        self.props.set_scene(self.scene)
        self.props.set_undo_stack(self.controller.undo_stack)

        # Canvas area: view + video controls
        canvas_widget = QWidget()
        canvas_widget.setObjectName("CanvasArea")
        canvas_vbox = QVBoxLayout(canvas_widget)
        canvas_vbox.setContentsMargins(0, 0, 0, 0)
        canvas_vbox.setSpacing(0)
        canvas_vbox.addWidget(self.view, stretch=1)
        canvas_vbox.addWidget(self.video_controls)
        self.zoom_bar.setVisible(False)   # zoom lives in TopBar only

        # Content row: labelled tools | resizable canvas/inspector workspace.
        workspace = QSplitter(Qt.Orientation.Horizontal)
        workspace.setObjectName("WorkspaceSplitter")
        workspace.setChildrenCollapsible(False)
        workspace.addWidget(canvas_widget)
        workspace.addWidget(self.inspector)
        workspace.setStretchFactor(0, 1)
        workspace.setStretchFactor(1, 0)
        workspace.setSizes([1000, 308])

        content = QWidget()
        content_hbox = QHBoxLayout(content)
        content_hbox.setContentsMargins(0, 0, 0, 0)
        content_hbox.setSpacing(0)
        content_hbox.addWidget(self.tool_sidebar)
        content_hbox.addWidget(workspace, stretch=1)

        # Main layout: TopBar → ContextToolbar → content
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(self.top_bar)
        vbox.addWidget(self.ctx_toolbar)
        vbox.addWidget(content, stretch=1)

        self.statusBar().showMessage("就绪")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = event.size().width() < 1100
        self.top_bar.set_compact(compact)
        self.tool_sidebar.set_compact(compact, automatic=True)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self):
        tb  = self.top_bar
        sb  = self.tool_sidebar
        ctx = self.ctx_toolbar
        sc  = self.scene
        vc  = self.video_controls

        # TopBar
        tb.open_media_requested.connect(self._on_open_media)
        tb.export_requested.connect(self._on_export)
        tb.undo_requested.connect(self.controller.undo_stack.undo)
        tb.redo_requested.connect(self.controller.undo_stack.redo)
        tb.reset_requested.connect(self._on_reset_project)
        tb.about_requested.connect(self._on_about)
        tb.shortcuts_requested.connect(self._on_shortcuts)
        tb.zoom_changed.connect(self._on_zoom_level)

        # ToolSidebar
        sb.add_bubble_requested.connect(self._on_add_bubble_clicked)
        sb.add_text_requested.connect(lambda: self._on_add_bubble_with_style("text"))
        sb.add_redact_requested.connect(self._on_add_redaction)
        sb.add_brush_requested.connect(self._on_add_brush)
        sb.add_layer_requested.connect(self._on_add_layer)
        sb.crop_requested.connect(self._on_crop)
        sb.rotate_requested.connect(self._on_rotate)
        sb.add_lines_requested.connect(self._on_add_speedlines)
        sb.meme_toggled.connect(self._on_meme_toggled)
        sb.dual_toggled.connect(self._on_dual_toggled)
        sb.manga_toggled.connect(self._on_manga_toggled)
        sb.collage_toggled.connect(self._on_collage_toggled)
        sb.tool_changed.connect(self.view.set_tool)

        # ContextToolbar
        ctx.align_requested.connect(self._on_context_align)
        ctx.z_requested.connect(self._on_context_z)
        ctx.delete_requested.connect(self._on_context_delete)
        ctx.flip_h_requested.connect(lambda: self._on_context_flip("h"))
        ctx.flip_v_requested.connect(lambda: self._on_context_flip("v"))

        # Undo/Redo state
        self.controller.undo_stack.canUndoChanged.connect(tb.set_undo_enabled)
        self.controller.undo_stack.canRedoChanged.connect(tb.set_redo_enabled)
        self.controller.media_loaded.connect(self._on_media_loaded)
        self.controller.right_media_loaded.connect(self._on_right_media_loaded)
        self.controller.import_started.connect(
            lambda path: self.statusBar().showMessage(f"Opening {os.path.basename(path)}…"))
        self.controller.import_failed.connect(self._on_import_failed)
        self.controller.overlay_loaded.connect(self._on_overlay_loaded)
        self.controller.import_busy_changed.connect(self._on_import_busy_changed)

        # Canvas
        sc.double_clicked_on_canvas.connect(self._on_canvas_double_click)
        sc.bubble_changed.connect(self.props.update_for_bubble)
        sc.open_right_media_requested.connect(self._on_open_right_media)
        sc.open_manga_panel_requested.connect(self._on_open_manga_panel)
        sc.manga_layout_changed.connect(self._on_manga_layout_changed)
        sc.selectionChanged.connect(self._on_selection_changed)
        sc.lobe_edit_requested.connect(self._on_lobe_edit_requested)

        # View
        self.view.zoom_changed.connect(self.zoom_bar.update_zoom)
        self.view.zoom_changed.connect(self.top_bar.update_zoom)
        self.view.open_media_requested.connect(self._show_open_dialog)
        self.view.photo_dropped.connect(self._on_open_media)
        self.view.right_media_dropped.connect(self._on_right_media_dropped)
        self.view.manga_media_dropped.connect(self._on_manga_media_dropped)

        # Manga Maker reuses the existing context row.
        self.ctx_toolbar.manga_regenerate_requested.connect(
            self._on_regenerate_manga)
        self.ctx_toolbar.manga_zoom_changed.connect(
            self.scene.set_selected_manga_zoom)
        self.ctx_toolbar.manga_fit_requested.connect(
            self.scene.fit_selected_manga_panel)
        self.scene.manga_panel_zoom_changed.connect(
            self.ctx_toolbar.set_manga_zoom)

        # VideoControls
        vc.frame_changed.connect(self._on_frame_changed)
        vc.right_frame_changed.connect(self._on_right_frame_changed)
        vc.trim_in_changed.connect(self._on_trim_in)
        vc.trim_out_changed.connect(self._on_trim_out)
        vc.cut_requested.connect(self._on_cut)
        vc.cuts_cleared.connect(self._on_clear_cuts)
        vc.reverse_toggled.connect(self._on_reverse)
        vc.fullscreen_requested.connect(self._toggle_fullscreen)

        # Inspector dual settings
        self.props.dual_gap_changed.connect(self.scene.set_dual_gap)
        self.props.dual_border_changed.connect(self.scene.set_dual_border)
        self.props.dual_feather_changed.connect(self.scene.set_dual_feather)
        self.props.add_bubble_requested.connect(self._on_add_bubble_with_style)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self).activated.connect(
            self.controller.undo_stack.redo
        )
        QShortcut(QKeySequence("Ctrl+/"), self).activated.connect(
            self._on_shortcuts
        )
        self._video_shortcuts = {
            Qt.Key.Key_Space: vc.toggle_playback,
            Qt.Key.Key_Left: vc.step_back,
            Qt.Key.Key_Right: vc.step_forward,
            Qt.Key.Key_Home: vc.first_frame,
            Qt.Key.Key_End: vc.last_frame,
            Qt.Key.Key_BracketLeft: vc.set_trim_in_to_current_frame,
            Qt.Key.Key_BracketRight: vc.set_trim_out_to_current_frame,
            Qt.Key.Key_F: self._toggle_fullscreen,
        }

    def eventFilter(self, obj, event):
        if not self.isActiveWindow():
            return super().eventFilter(obj, event)
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Delete and not self._focus_accepts_text():
                self._on_context_delete()
                return True
            callback = getattr(self, "_video_shortcuts", {}).get(event.key())
            if callback and self.video_controls.isVisible() and not self._focus_accepts_text():
                callback()
                return True
        return super().eventFilter(obj, event)

    def _focus_accepts_text(self) -> bool:
        widget = QApplication.focusWidget()
        return isinstance(widget, (
            QLineEdit, QTextEdit, QPlainTextEdit,
            QComboBox, QSpinBox, QDoubleSpinBox,
        ))

    # ------------------------------------------------------------------
    # Media loading
    # ------------------------------------------------------------------

    def _on_open_media(self, path: str):
        self.controller.open_media_async(path)

    def _on_import_failed(self, path, target, detail):
        self.statusBar().showMessage("无法打开媒体")
        message = f"无法打开：\n{path}"
        if detail:
            message += f"\n\n{detail}"
        title = {'right': '打开右侧媒体', 'overlay': '添加图层'}.get(target, '打开')
        QMessageBox.warning(self, title, message)

    def _on_import_busy_changed(self, busy):
        # Reset can cancel an import even when the starting canvas is empty.
        self.top_bar.set_reset_enabled(busy or self.scene.has_photo())
        if not busy and self.statusBar().currentMessage().startswith('正在打开 '):
            self.statusBar().showMessage(
                os.path.basename(self.controller.model.media_path) or '就绪')

    def closeEvent(self, event):
        self.video_controls.stop()
        self.controller.shutdown()
        self.scene.reset_project()
        super().closeEvent(event)

    def _on_media_loaded(self, path: str, is_video: bool):
        self.top_bar.set_media_loaded(True)
        self.top_bar.set_reset_enabled(True)
        self.tool_sidebar.set_media_loaded(True)
        self.tool_sidebar.set_meme_checked(False)
        self.tool_sidebar.set_dual_checked(False)
        self.tool_sidebar.set_manga_checked(False)
        self.tool_sidebar.set_collage_checked(False)
        self.ctx_toolbar.set_manga_mode(False)
        self.tool_sidebar.set_meme_enabled(True)
        self.tool_sidebar.set_dual_enabled(True)

        if is_video:
            self.video_controls.set_player(self.scene.video_player)
            self.video_controls.set_right_player(None)
        else:
            self.video_controls.set_player(None)
            self.video_controls.set_right_player(None)

        self.props.clear()
        self.ctx_toolbar.hide_toolbar()
        self.view.fit_photo()
        self.view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self.statusBar().showMessage(os.path.basename(path))

    # ------------------------------------------------------------------
    # Right media (dual mode)
    # ------------------------------------------------------------------

    def _on_open_right_media(self):
        ext_list = " ".join(f"*{e}" for e in ALL_EXTENSIONS)
        path = open_file(
            self,
            "打开右侧媒体",
            f"所有支持的媒体 ({ext_list})",
        )
        if path:
            self._on_right_media_dropped(path)

    def _on_right_media_dropped(self, path: str):
        self.controller.open_media_async(path, 'right')

    def _on_right_media_loaded(self, path: str, is_video: bool):
        self.video_controls.set_right_player(self.scene.video_player_right if is_video else None)
        self.view.fit_photo()
        self.statusBar().showMessage(os.path.basename(path))

    # ------------------------------------------------------------------
    # Overlay layers
    # ------------------------------------------------------------------

    def _on_add_layer(self):
        if not self.scene.has_photo():
            return
        ext_list = " ".join(f"*{e}" for e in ALL_EXTENSIONS)
        path = open_file(self, "添加图层", f"所有支持的媒体 ({ext_list})")
        if not path:
            return
        self.controller.open_media_async(path, 'overlay')

    def _on_overlay_loaded(self, item):
        self.statusBar().showMessage("已添加图层")
        if hasattr(item, "has_video") and item.has_video():
            self.video_controls.set_player(item.video_player())
            self.video_controls.set_right_player(None)

    def _on_lobe_edit_requested(self, bubble, index: int):
        """Double-clicking a lobed balloon jumps to that lobe's text box."""
        self.scene.clearSelection()
        bubble.setSelected(True)
        self.props.focus_lobe_editor(index)

    # ------------------------------------------------------------------
    # Crop + speed lines
    # ------------------------------------------------------------------

    def _on_crop(self):
        self.controller.cancel_import()
        if not self.scene.has_photo():
            return
        if self.scene.has_video():
            QMessageBox.information(
                self, "裁剪", "裁剪仅适用于照片。")
            return
        from crop_dialog import CropDialog
        from undo_commands import CropPhotoCommand, RotatePhotoCommand
        pm = self.scene.photo_pixmap
        dlg = CropDialog(pm, self)
        if not dlg.exec():
            return
        turns = dlg.rotation_turns()
        rect = dlg.crop_rect()
        # Rotation first: the crop rect was chosen against the rotated preview.
        stack = self.controller.undo_stack
        changed = False
        if turns:
            stack.beginMacro("旋转与裁剪")
            stack.push(RotatePhotoCommand(self.scene, turns))
            changed = True
        rotated = self.scene.photo_pixmap
        full = QRect(0, 0, rotated.width(), rotated.height())
        if rect.width() >= 8 and rect.height() >= 8 and rect != full:
            stack.push(CropPhotoCommand(self.scene, rect))
            changed = True
        if turns:
            stack.endMacro()
        if changed:
            self.view.fit_photo()

    def _on_rotate(self):
        self.controller.cancel_import()
        if not self.scene.has_photo():
            return
        if self.scene.has_video():
            QMessageBox.information(
                self, "旋转", "旋转仅适用于照片。")
            return
        from undo_commands import RotatePhotoCommand
        self.controller.undo_stack.push(RotatePhotoCommand(self.scene, 1))
        self.view.fit_photo()

    def _on_add_speedlines(self):
        if not self.scene.has_photo():
            return
        from speedlines import SpeedLinesItem
        from undo_commands import AddBubbleCommand
        page_mode = self.scene.is_manga_mode() or self.scene.is_collage_mode()
        active_panel = self.scene.active_page_panel() if page_mode else None
        if page_mode and active_panel is None:
            self.statusBar().showMessage(
                "Select a Comic/Collage frame before adding Lines")
            return

        # Page mode gets one Lines effect per frame; normal editing keeps the
        # original one-per-photo behavior.
        if page_mode:
            existing = [
                item for item in self.scene.items()
                if isinstance(item, SpeedLinesItem)
                and getattr(item, "_page_panel_index", None) == active_panel.index
            ]
        else:
            existing = [
                item for item in self.scene.items()
                if isinstance(item, SpeedLinesItem)
                and getattr(item, "_page_panel_index", None) is None
                and item.parentItem() is None
            ]
        if existing:
            self.scene.clearSelection()
            top = max(existing, key=lambda i: i.zValue())
            top.setSelected(True)
            if page_mode:
                self.scene.set_active_page_panel(active_panel.index)
            return
        frame = (active_panel.sceneBoundingRect() if page_mode
                 else self.scene._photo_frame_rect())
        item = SpeedLinesItem(frame)
        if page_mode:
            item._page_panel_index = active_panel.index
        self.controller.undo_stack.push(AddBubbleCommand(self.scene, item))
        self.scene.clearSelection()
        item.setSelected(True)
        if page_mode:
            self.scene.set_active_page_panel(active_panel.index)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _on_export(self):
        self.controller.cancel_import()
        # Export pulls in subprocess/archive helpers that are irrelevant until
        # the user actually exports. Keep them off the startup path.
        import export as exporter

        self.video_controls.stop()
        if self.scene.is_manga_mode():
            exporter.export_manga_photo(self, self.scene)
            return
        if self.scene.is_collage_mode():
            exporter.export_collage_photo(self, self.scene)
            return
        has_left_video  = self.scene.has_video()
        has_right_video = (self.scene.video_player_right is not None
                           and self.scene.video_player_right.is_loaded())

        if has_left_video or has_right_video:
            exporter.export_video(
                self, self.scene,
                self.scene._photo_item,
                self.scene.video_player,
                right_photo_item=self.scene._photo_item_right,
                right_player=self.scene.video_player_right,
                is_dual=self.scene.is_dual_mode(),
            )
        else:
            exporter.export_photo(
                self, self.scene,
                self.scene._photo_item,
                right_photo_item=self.scene._photo_item_right,
                is_dual=self.scene.is_dual_mode(),
            )

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def _on_zoom_level(self, key: str):
        if key in ("fit_width", "fit-width"):
            self.view.fit_width()
        elif key in ("fit_window", "fit-window"):
            self.view.fit_photo()
        else:
            try:
                self.view.set_zoom_percent(int(key))
            except ValueError:
                pass

    # ------------------------------------------------------------------
    # Modes
    # ------------------------------------------------------------------

    def _on_meme_toggled(self, enabled: bool):
        self.controller.set_meme_mode(enabled)
        self.view.fit_photo()

    def _on_dual_toggled(self, enabled: bool):
        self.controller.set_dual_mode(enabled)
        if enabled:
            if not self.scene.selectedItems():
                self.props.show_dual_settings()
        else:
            self.video_controls.set_right_player(None)
        self.view.fit_photo()

    def _on_manga_toggled(self, enabled: bool):
        self.video_controls.stop()
        if enabled:
            if self.scene.is_collage_mode():
                self.controller.set_collage_mode(False)
            self.tool_sidebar.set_collage_checked(False)
            self.tool_sidebar.set_meme_checked(False)
            self.tool_sidebar.set_dual_checked(False)
            self.controller.set_manga_mode(True)
            self.tool_sidebar.set_manga_mode_active(True, self.scene._photo_item is not None)
            self.top_bar.set_media_loaded(True)
            self.top_bar.set_reset_enabled(True)
            self.video_controls.set_player(None)
            self.video_controls.set_right_player(None)
            self.ctx_toolbar.hide_toolbar()
            self.ctx_toolbar.set_manga_mode(True)
            self.props.show_manga_settings()
            self.statusBar().showMessage(
                "漫画创作 — 双击或拖放图片到空分格")
        else:
            self.controller.set_manga_mode(False)
            self.ctx_toolbar.set_manga_mode(False)
            self.props.clear()
            base_loaded = self.scene._photo_item is not None
            self.tool_sidebar.set_manga_mode_active(False, base_loaded)
            self.top_bar.set_media_loaded(base_loaded)
            self.top_bar.set_reset_enabled(base_loaded)
            self._restore_standard_video_controls()
        self.view.fit_photo()

    def _on_collage_toggled(self, enabled: bool):
        self.video_controls.stop()
        if enabled:
            if self.scene.is_manga_mode():
                self.controller.set_manga_mode(False)
            self.tool_sidebar.set_manga_checked(False)
            self.tool_sidebar.set_meme_checked(False)
            self.tool_sidebar.set_dual_checked(False)
            self.controller.set_collage_mode(True)
            self.tool_sidebar.set_manga_mode_active(
                True, self.scene._photo_item is not None)
            self.top_bar.set_media_loaded(True)
            self.top_bar.set_reset_enabled(True)
            self.video_controls.set_player(None)
            self.video_controls.set_right_player(None)
            self.ctx_toolbar.set_collage_mode(True)
            self.props.show_manga_settings()
            self.statusBar().showMessage(
                "照片拼贴 — 双击或拖放图片到画框")
        else:
            self.controller.set_collage_mode(False)
            self.ctx_toolbar.set_collage_mode(False)
            self.props.clear()
            base_loaded = self.scene._photo_item is not None
            self.tool_sidebar.set_manga_mode_active(False, base_loaded)
            self.top_bar.set_media_loaded(base_loaded)
            self.top_bar.set_reset_enabled(base_loaded)
            self._restore_standard_video_controls()
        self.view.fit_photo()

    def _restore_standard_video_controls(self):
        """Reconnect the timeline after leaving a photo-only page mode."""
        if self.scene.is_manga_mode() or self.scene.is_collage_mode():
            self.video_controls.setVisible(False)
            return
        left = self.scene.video_player
        if left is not None and not left.is_loaded():
            left = None
        right = self.scene.video_player_right if self.scene.is_dual_mode() else None
        if right is not None and not right.is_loaded():
            right = None
        self.video_controls.set_player(left)
        self.video_controls.set_right_player(right)

    def _on_open_manga_panel(self, index: int):
        ext_list = " ".join(f"*{e}" for e in IMAGE_EXTENSIONS)
        label = "拼贴画框" if self.scene.is_collage_mode() else "漫画分格"
        path = open_file(self, f"打开 {label} 图片",
                         f"图片 ({ext_list})")
        if path:
            self._on_manga_media_dropped(path, index)

    def _on_manga_media_dropped(self, path: str, index: int):
        if not self.scene.load_manga_panel(index, path):
            title = "照片拼贴" if self.scene.is_collage_mode() else "漫画创作"
            QMessageBox.warning(self, title, f"无法打开：\n{path}")
        else:
            unit = "画框" if self.scene.is_collage_mode() else "分格"
            self.statusBar().showMessage(
                f"{unit} {index + 1}: {os.path.basename(path)}")

    def _on_regenerate_manga(self):
        self.scene.clearSelection()
        if self.scene.is_collage_mode():
            self.scene.shuffle_collage_layout()
            self.props.show_manga_settings()
        else:
            self.scene.regenerate_manga_layout()
        self.view.fit_photo()

    def _on_manga_layout_changed(self, name: str):
        self.ctx_toolbar.set_manga_layout_name(name)
        if self.scene.is_manga_mode() or self.scene.is_collage_mode():
            QTimer.singleShot(0, self.view.fit_photo)

    # ------------------------------------------------------------------
    # Video controls
    # ------------------------------------------------------------------

    def _on_frame_changed(self, frame: int):
        self.scene.update_frame(frame)
        self.video_controls.set_current_frame(frame)

    def _on_right_frame_changed(self, frame: int):
        self.scene.update_right_frame(frame)

    def _on_trim_in(self, frame: int):
        player = self._active_player()
        if player:
            player.set_trim_in(frame)
            self.video_controls.sync_markers()

    def _on_trim_out(self, frame: int):
        player = self._active_player()
        if player:
            player.set_trim_out(frame)
            self.video_controls.sync_markers()

    def _on_cut(self):
        player = self._active_player()
        if not player:
            return
        s, e = player.trim_in, player.trim_out
        if s >= e:
            return
        player.add_cut(s, e)
        player.set_trim_in(0)
        player.set_trim_out(player.frame_count - 1)
        self.video_controls.sync_markers()
        cur = self.video_controls.current_frame
        if s <= cur <= e:
            next_frame = e + 1
            if next_frame > player.frame_count - 1:
                next_frame = 0
            self.video_controls._current_frame = next_frame
            self._on_frame_changed(next_frame)

    def _on_clear_cuts(self):
        player = self._active_player()
        if player:
            player.clear_cuts()
            self.video_controls.sync_markers()

    def _on_reverse(self):
        player = self._active_player()
        if player:
            player.toggle_reverse()

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _active_player(self):
        active = getattr(self.video_controls, "_active_player", None)
        if (
            active
            and active is not self.scene.video_player
            and active is not self.scene.video_player_right
        ):
            return active
        if self.video_controls.active_side == "right":
            return self.scene.video_player_right
        return self.scene.video_player

    # ------------------------------------------------------------------
    # Canvas interactions
    # ------------------------------------------------------------------

    def _show_open_dialog(self):
        ext_list = " ".join(f"*{e}" for e in ALL_EXTENSIONS)
        path = open_file(self, "打开媒体", f"所有支持的媒体 ({ext_list})")
        if path:
            self._on_open_media(path)

    def _on_reset_project(self):
        self.video_controls.stop()
        self.controller.reset_project()
        self.video_controls.set_right_player(None)
        self.video_controls.set_player(None)
        self.props.clear()
        self.ctx_toolbar.hide_toolbar()
        self.top_bar.set_media_loaded(False)
        self.top_bar.set_reset_enabled(False)
        self.tool_sidebar.set_media_loaded(False)
        self.tool_sidebar.set_meme_checked(False)
        self.tool_sidebar.set_dual_checked(False)
        self.tool_sidebar.set_manga_checked(False)
        self.tool_sidebar.set_collage_checked(False)
        self.ctx_toolbar.set_manga_mode(False)
        self.view.resetTransform()
        self.view.viewport().update()
        self.statusBar().showMessage("就绪")

    def _on_add_bubble_clicked(self):
        if not self.scene.has_photo():
            return
        c = self.scene.sceneRect().center()
        self._on_canvas_double_click(c.x(), c.y())

    def _on_add_bubble_with_style(self, style: str):
        if not self.scene.has_photo():
            return
        c = self.scene.sceneRect().center()
        bubble = self.controller.add_bubble(c.x(), c.y(), style=style)
        self.props.update_for_bubble(bubble)
        self.ctx_toolbar.show_for_bubble()

    def _on_canvas_double_click(self, x: float, y: float):
        bubble = self.controller.add_bubble(x, y)
        self.props.update_for_bubble(bubble)
        self.ctx_toolbar.show_for_bubble()

    def _on_add_redaction(self, mode: str | None = None):
        """新增一块打码区域。样式可在属性面板里随时切换。"""
        if not self.scene.has_photo():
            return
        page_mode = self.scene.is_manga_mode() or self.scene.is_collage_mode()
        active_panel = self.scene.active_page_panel() if page_mode else None
        if page_mode and active_panel is None:
            self.statusBar().showMessage(
                "添加打码前请先选中一个漫画分格或拼贴画框")
            return
        frame = (active_panel.sceneBoundingRect() if active_panel is not None
                 else self.scene.sceneRect())
        c = frame.center()
        # 默认用上次用过的样式；没有就用马赛克
        style = mode or getattr(self, "_last_redact_style", None) or STYLE_MOSAIC
        item = self.controller.add_redaction(c.x(), c.y(), mode=style)
        self._last_redact_style = item.get_mode()
        if active_panel is not None:
            item.attach_to_page_panel(active_panel.index, frame)
            self.scene.set_active_page_panel(active_panel.index)
        self.props.update_for_redaction(item)
        self.ctx_toolbar.hide_toolbar()

    def _on_add_brush(self):
        """新增一块笔刷打码 —— 创建后直接进入涂抹模式，在画布上拖动即可刷。"""
        if not self.scene.has_photo():
            return
        page_mode = self.scene.is_manga_mode() or self.scene.is_collage_mode()
        active_panel = self.scene.active_page_panel() if page_mode else None
        if page_mode and active_panel is None:
            self.statusBar().showMessage(
                "添加打码前请先选中一个漫画分格或拼贴画框")
            return
        frame = (active_panel.sceneBoundingRect() if active_panel is not None
                 else self.scene.sceneRect())
        c = frame.center()
        style = getattr(self, "_last_redact_style", None) or STYLE_MOSAIC
        item = self.controller.add_brush_redaction(c.x(), c.y(), mode=style)
        if active_panel is not None:
            item._page_panel_index = active_panel.index
            item._page_frame = QRectF(frame)
            self.scene.set_active_page_panel(active_panel.index)
        self.props.update_for_redaction(item)
        self.ctx_toolbar.hide_toolbar()
        self.statusBar().showMessage("在画布上拖动涂抹需要打码的区域")

    # ------------------------------------------------------------------
    # Selection → inspector + ContextToolbar
    # ------------------------------------------------------------------

    def _on_selection_changed(self):
        try:
            selected = self.scene.selectedItems()
        except RuntimeError:
            return
        from redaction import RedactionItem
        from speedlines import SpeedLinesItem
        bubbles  = [i for i in selected if isinstance(i, BubbleItem)]
        redacts  = [i for i in selected if isinstance(i, RedactionItem)]
        lines    = [i for i in selected if isinstance(i, SpeedLinesItem)]
        media    = [i for i in selected if isinstance(i, MediaItem)]
        manga    = [i for i in selected if isinstance(i, MangaPanelItem)]
        if bubbles:
            self.props.update_for_bubble(bubbles[0])
            self.ctx_toolbar.show_for_bubble()
        elif redacts:
            self.props.update_for_redaction(redacts[0])
            self.ctx_toolbar.hide_toolbar()
        elif lines:
            self.props.update_for_speedlines(lines[0])
            self.ctx_toolbar.hide_toolbar()
        elif media:
            self.props.update_for_media(media[0])
            self.ctx_toolbar.show_for_media()
            if hasattr(media[0], "has_video") and media[0].has_video():
                self.video_controls.set_player(media[0].video_player())
                self.video_controls.set_right_player(None)
        elif manga:
            self.props.show_manga_settings()
            self.ctx_toolbar.show_for_manga_panel(
                manga[0].zoom_percent(), manga[0].has_image())
        elif self.scene.is_manga_mode() or self.scene.is_collage_mode():
            self.props.show_manga_settings()
            self.ctx_toolbar.hide_toolbar()
        elif self.scene.is_dual_mode():
            self.props.show_dual_settings()
            self.ctx_toolbar.hide_toolbar()
        else:
            self.props.clear()
            self.ctx_toolbar.hide_toolbar()

    # ------------------------------------------------------------------
    # ContextToolbar actions
    # ------------------------------------------------------------------

    def _on_context_align(self, mode: str):
        selected = self.scene.selectedItems()
        if not selected:
            return
        item = selected[0]
        if not isinstance(item, (BubbleItem, MediaItem)):
            return
        sr  = self.scene.sceneRect()
        pos = item.pos()
        new_pos = QPointF(pos)
        if isinstance(item, BubbleItem):
            r = item.body_rect
            left = r.left()
            right = r.right()
            top = r.top()
            bottom = r.bottom()
            center_offset_x = 0
            center_offset_y = 0
        else:
            r = item.boundingRect()
            left = r.left()
            right = r.right()
            top = r.top()
            bottom = r.bottom()
            center_offset_x = r.width() / 2
            center_offset_y = r.height() / 2
        if mode == "left":
            new_pos.setX(sr.left() - left)
        elif mode == "hcenter":
            new_pos.setX(sr.center().x() - center_offset_x)
        elif mode == "right":
            new_pos.setX(sr.right() - right)
        elif mode == "top":
            new_pos.setY(sr.top() - top)
        elif mode == "vcenter":
            new_pos.setY(sr.center().y() - center_offset_y)
        elif mode == "bottom":
            new_pos.setY(sr.bottom() - bottom)
        if (new_pos - pos).manhattanLength() > 0.5:
            if isinstance(item, BubbleItem):
                from undo_commands import MoveBubbleCommand
                self.controller.undo_stack.push(MoveBubbleCommand(item, pos, new_pos))
            else:
                from undo_commands import MoveMediaCommand
                self.controller.undo_stack.push(MoveMediaCommand(self.scene, item, pos, new_pos))

    def _on_context_z(self, mode: str):
        selected = self.scene.selectedItems()
        if not selected:
            return
        ordered = self._stack_items_bottom_to_top()
        candidates = [i for i in selected if i in ordered]
        if not candidates:
            return
        item = max(candidates, key=lambda i: i.zValue())
        self._apply_stack_order(ordered)
        ordered = self._stack_items_bottom_to_top()
        index = ordered.index(item)
        if mode == "front":
            new_index = len(ordered) - 1
        elif mode == "forward":
            new_index = min(len(ordered) - 1, index + 1)
        elif mode == "backward":
            new_index = max(0, index - 1)
        elif mode == "back":
            new_index = 0
        else:
            return
        if new_index == index:
            return
        moved = ordered.pop(index)
        ordered.insert(new_index, moved)
        self._apply_stack_order(ordered)
        item.setSelected(True)
        self._refresh_layers_panel()
        self.statusBar().showMessage("图层顺序已更改")

    def _stack_items_bottom_to_top(self):
        items = [
            i for i in self.scene.items()
            if isinstance(i, BubbleItem)
            or (isinstance(i, MediaItem) and getattr(i, "_is_overlay", False))
        ]
        return sorted(items, key=lambda i: i.zValue())

    def _apply_stack_order(self, ordered):
        for idx, item in enumerate(ordered):
            item.setZValue(float(10 + idx * 10))
        self.scene.update()

    def _refresh_layers_panel(self):
        refresh = getattr(self.props, "_refresh_layers", None)
        if callable(refresh):
            refresh()

    def _on_context_flip(self, axis: str):
        selected = self.scene.selectedItems()
        if not selected:
            return
        item = selected[0]
        if isinstance(item, MediaItem):
            if axis == "h" and hasattr(item, "flip_horizontal"):
                item.flip_horizontal()
            elif axis == "v" and hasattr(item, "flip_vertical"):
                item.flip_vertical()
            else:
                return
            self.scene.update()
        elif isinstance(item, BubbleItem):
            if axis == "h":
                item.setScale(item.scale() * -1)
            else:
                item.setTransform(item.transform().scale(1, -1), True)
            item.update()

    def _on_context_delete(self):
        selected = self.scene.selectedItems()
        if not selected:
            return
        item = selected[0]
        if isinstance(item, BubbleItem):
            item._delete()
        elif isinstance(item, MediaItem) and getattr(item, "_is_overlay", False):
            from undo_commands import RemoveOverlayCommand
            self.controller.undo_stack.push(RemoveOverlayCommand(self.scene, item))
        else:
            from redaction import RedactionItem
            from speedlines import SpeedLinesItem
            if isinstance(item, (RedactionItem, SpeedLinesItem)):
                from undo_commands import DeleteBubbleCommand
                self.controller.undo_stack.push(
                    DeleteBubbleCommand(self.scene, item))

    # ------------------------------------------------------------------
    # About
    # ------------------------------------------------------------------

    def _on_about(self):
        AboutDialog(self).exec()

    def _on_shortcuts(self):
        ShortcutsDialog(self).exec()
