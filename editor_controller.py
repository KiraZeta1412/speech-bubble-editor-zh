"""
editor_controller.py — EditorController: coordinates AppModel and PhotoScene.

Processes user actions, pushes undo commands, and keeps AppModel in sync.
MainWindow calls controller methods instead of talking to PhotoScene directly.
"""

import os

from PyQt6.QtCore import QObject, pyqtSignal

from app_model import AppModel
from constants import VIDEO_EXTENSIONS
from canvas import PhotoScene
from bubble import BubbleItem
from undo_commands import AddBubbleCommand, AddOverlayCommand


class EditorController(QObject):
    """
    Mediates between MainWindow (UI) and PhotoScene (data/rendering).

    Owns the AppModel and updates it on every state change.
    Emits coarse signals so MainWindow can update toolbar and panels
    without knowing scene internals.
    """

    media_loaded       = pyqtSignal(str, bool)   # path, is_video
    right_media_loaded = pyqtSignal(str, bool)   # path, is_video

    overlay_loaded = pyqtSignal(object)
    import_started = pyqtSignal(str)
    import_failed = pyqtSignal(str, str, str)
    import_busy_changed = pyqtSignal(bool)

    def __init__(self, scene: PhotoScene, parent=None):
        super().__init__(parent)
        self._model = AppModel()
        self._scene = scene
        self.last_error = ""
        self._loader = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def model(self) -> AppModel:
        return self._model

    @property
    def scene(self) -> PhotoScene:
        return self._scene

    @property
    def undo_stack(self):
        return self._scene.undo_stack

    # ------------------------------------------------------------------
    # Media
    # ------------------------------------------------------------------

    def open_media_async(self, path: str, target: str = 'left'):
        if self._loader is None:
            from media_loader import MediaLoader
            from PyQt6.QtWidgets import QApplication
            self._loader = MediaLoader(self)
            self._loader.ready.connect(self._install_import)
            self._loader.failed.connect(self.import_failed)
            self._loader.busy_changed.connect(self.import_busy_changed)
            QApplication.instance().aboutToQuit.connect(self._loader.shutdown)
        self.last_error = ''
        self.import_started.emit(path)
        self._loader.request(path, target)

    def cancel_import(self):
        if self._loader is not None:
            self._loader.cancel()

    def shutdown(self):
        if self._loader is not None:
            self._loader.shutdown()

    def _install_import(self, path, target, prepared):
        from PyQt6.QtGui import QPixmap
        try:
            pixmap = QPixmap.fromImage(prepared.image)
            is_video = prepared.player is not None
            if target == 'overlay':
                if not self._scene.has_photo():
                    return
                item = self._scene.create_overlay_from_media(pixmap, prepared.player)
                self._scene.undo_stack.push(AddOverlayCommand(self._scene, item))
                prepared.player = None
                self.overlay_loaded.emit(item)
                return
            if target == 'right':
                ok = self._scene.install_right_media(pixmap, prepared.player)
            else:
                ok = self._scene.install_media(pixmap, prepared.player)
            if not ok:
                return
            prepared.player = None  # ownership transferred to the scene
            if target == 'right':
                self._model.media_path_right = path
                self.right_media_loaded.emit(path, is_video)
            else:
                self._record_media_loaded(path, is_video)
        except Exception as error:
            self.last_error = str(error)
            self.import_failed.emit(path, target, self.last_error)
        finally:
            prepared.release()

    def _record_media_loaded(self, path, is_video):
        if self._scene._photo_item is not None:
            self._scene._photo_item._source_path = path
        self._model.media_path = path
        self._model.media_path_right = ''
        self._model.is_dual = False
        self._model.is_meme = False
        self._model.is_manga = False
        self._model.is_collage = False
        self.media_loaded.emit(path, is_video)

    def open_media(self, path: str) -> bool:
        """Load photo or video (auto-detected). Returns True on success."""
        self.cancel_import()
        self.last_error = ""
        is_video = os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS
        try:
            ok = (self._scene.load_video(path) if is_video
                  else self._scene.load_photo(path))
        except ModuleNotFoundError as error:
            if is_video and error.name == "cv2":
                self.last_error = (
                    "Video support requires OpenCV. Launch with the project "
                    "virtual environment or run: pip install -r requirements.txt")
                return False
            raise
        if ok:
            self._record_media_loaded(path, is_video)
        return ok

    def open_right_media(self, path: str) -> bool:
        """Load the right-panel photo or video. Returns True on success."""
        self.cancel_import()
        self.last_error = ""
        is_video = os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS
        try:
            ok = (self._scene.load_right_video(path) if is_video
                  else self._scene.load_right_photo(path))
        except ModuleNotFoundError as error:
            if is_video and error.name == "cv2":
                self.last_error = (
                    "Video support requires OpenCV. Launch with the project "
                    "virtual environment or run: pip install -r requirements.txt")
                return False
            raise
        if ok:
            self._model.media_path_right = path
            self.right_media_loaded.emit(path, is_video)
        return ok

    def reset_project(self):
        """Return the editor to a blank launch state."""
        self.cancel_import()
        self._scene.reset_project()
        self._model = AppModel()

    # ------------------------------------------------------------------
    # Bubbles & overlays
    # ------------------------------------------------------------------

    def add_bubble(self, x: float, y: float, style: str | None = None) -> BubbleItem:
        """Create a bubble at (x, y) and push it onto the undo stack.

        With no explicit style the user's saved default (Balloon+-style
        "Default Balloon Settings") decides what a double-click creates.
        """
        if style is None:
            import bubble_defaults
            style = bubble_defaults.default_style()
        bubble = BubbleItem(x, y, style=style)
        # Match the bubble to the photo's resolution before it lands on canvas.
        rect = self._scene.sceneRect()
        bubble.scale_for_canvas(rect.width(), rect.height())
        # Clamp into frame: clicking near an edge used to drop a bubble half
        # off the canvas (the scene only clamps once the item is moved).
        body = bubble.body_rect
        if rect.width() > body.width() and rect.height() > body.height():
            bubble.setPos(
                min(max(x, rect.left() - body.left()),
                    rect.right() - body.right()),
                min(max(y, rect.top() - body.top()),
                    rect.bottom() - body.bottom()))
        self._scene.undo_stack.push(AddBubbleCommand(self._scene, bubble))
        self._scene.clearSelection()
        bubble.setSelected(True)
        return bubble

    def add_redaction(self, x: float, y: float, mode: str = "mosaic"):
        """Create a redaction box at (x, y) on the undo stack."""
        from redaction import RedactionItem
        from undo_commands import AddBubbleCommand
        item = RedactionItem(x, y, mode=mode)
        self._scene.undo_stack.push(AddBubbleCommand(self._scene, item))
        self._scene.clearSelection()
        item.setSelected(True)
        return item

    def add_overlay(self, path: str):
        """Create an overlay from path and push it onto the undo stack.

        Returns the new MediaItem, or None if the file cannot be opened.
        """
        item = self._scene.create_overlay_item(path)
        if item is None:
            return None
        self._scene.undo_stack.push(AddOverlayCommand(self._scene, item))
        return item

    # ------------------------------------------------------------------
    # Modes
    # ------------------------------------------------------------------

    def set_meme_mode(self, enabled: bool):
        self.cancel_import()
        if enabled:
            self._scene.enable_meme_mode()
        else:
            self._scene.disable_meme_mode()
        self._model.is_meme = enabled

    def set_dual_mode(self, enabled: bool):
        self.cancel_import()
        if enabled:
            self._scene.enable_dual_mode()
        else:
            self._scene.disable_dual_mode()
        self._model.is_dual = enabled

    def set_manga_mode(self, enabled: bool):
        self.cancel_import()
        if enabled:
            self._scene.enable_manga_mode()
            self._model.is_meme = False
            self._model.is_dual = False
        else:
            self._scene.disable_manga_mode()
        self._model.is_manga = enabled

    def set_collage_mode(self, enabled: bool):
        self.cancel_import()
        if enabled:
            self._scene.enable_collage_mode()
            self._model.is_meme = False
            self._model.is_dual = False
            self._model.is_manga = False
        else:
            self._scene.disable_collage_mode()
        self._model.is_collage = enabled
