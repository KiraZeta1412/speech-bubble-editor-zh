"""Decode imports off the GUI thread; publish only the latest request.

Workers create QImages, never QPixmaps or scene items. VideoCapture ownership
passes to the scene only after the opening worker has finished.
"""
from dataclasses import dataclass
import os

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QImage, QImageReader

from constants import VIDEO_EXTENSIONS
from video_player import VideoPlayer


@dataclass
class PreparedMedia:
    image: QImage
    player: VideoPlayer | None = None

    def release(self):
        if self.player is not None:
            self.player.release()
            self.player = None


def decode_media(path):
    if os.path.splitext(path)[1].lower() not in VIDEO_EXTENSIONS:
        reader = QImageReader(path)
        image = reader.read()
        if image.isNull():
            raise ValueError(reader.errorString())
        return PreparedMedia(image)
    player = VideoPlayer()
    try:
        if not player.load(path):
            raise ValueError('无法打开该视频。')
        frame = player.get_frame_ndarray(0)
        if frame is None:
            raise ValueError('无法解码视频首帧。')
        return PreparedMedia(VideoPlayer._bgr_to_image(frame), player)
    except Exception:
        player.release()
        raise


class _LoadJob(QThread):
    def __init__(self, token, path, target, parent):
        super().__init__(parent)
        self.token, self.path, self.target = token, path, target
        self.result = None
        self.error = ''

    def run(self):
        try:
            self.result = decode_media(self.path)
        except Exception as error:
            self.error = str(error) or type(error).__name__


class MediaLoader(QObject):
    ready = pyqtSignal(str, str, object)
    failed = pyqtSignal(str, str, str)
    busy_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._token = 0
        self._job = None
        self._pending = None
        self._closed = False

    def request(self, path, target='left'):
        if self._closed:
            return
        self._token += 1
        self._pending = (self._token, path, target)
        self.busy_changed.emit(True)
        if self._job is None:
            self._start_pending()

    def _start_pending(self):
        self._job = _LoadJob(*self._pending, self)
        self._pending = None
        self._job.finished.connect(self._finished)
        self._job.start()

    @pyqtSlot()
    def _finished(self):
        job = self.sender()
        result, job.result = job.result, None
        if job is self._job:
            self._job = None
        if not self._closed and job.token == self._token:
            if result is not None:
                self.ready.emit(job.path, job.target, result)
            else:
                self.failed.emit(job.path, job.target, job.error)
        elif result is not None:
            result.release()
        job.deleteLater()
        if not self._closed and self._pending is not None and self._job is None:
            self._start_pending()
        elif self._job is None:
            self.busy_changed.emit(False)

    def cancel(self):
        # In-flight native decode is allowed to finish safely, then discarded.
        # Keep only one worker and one pending path, not a queue of full images.
        self._token += 1
        self._pending = None
        self.busy_changed.emit(False)

    def shutdown(self):
        self._closed = True
        self.cancel()
        if self._job is not None:
            self._job.wait()
            if self._job.result is not None:
                self._job.result.release()
                self._job.result = None
