"""
video_player.py — VideoPlayer: thin wrapper around OpenCV VideoCapture.

Provides:
  • Frame access as QPixmap or BGR numpy array
  • Trim in/out points
  • Cut ranges (frame ranges excluded from export)
  • Reverse flag
  • Ordered export-frame list respecting all edits

cv2 and numpy are imported lazily (inside methods) to avoid slowing startup.
"""

from __future__ import annotations

import threading
from collections import OrderedDict

from PyQt6.QtCore import QMetaObject, QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap

from constants import VIDEO_EXTENSIONS

# Memory budget for the frame cache across all sizes of video
_CACHE_BUDGET_MB = 256


class FrameCache:
    """
    LRU cache for decoded video frames (stored as BGR numpy arrays).

    Capacity is governed by a byte budget rather than a fixed frame count.
    Each frame's actual byte size (from numpy's nbytes) is tracked, and LRU
    entries are evicted until total usage falls within the budget.

    Examples at 256 MB budget:
        4 K  (3840×2160 × 3 bytes) ≈  11 frames
        1080p(1920×1080 × 3 bytes) ≈  42 frames
        720p (1280× 720 × 3 bytes) ≈  94 frames  (hard-capped at 128)
        480p ( 854× 480 × 3 bytes) ≈ 128 frames
    """

    _MAX_FRAMES = 128   # hard cap to avoid extreme caching on tiny resolutions

    def __init__(self):
        self._budget: int = _CACHE_BUDGET_MB * 1024 * 1024
        self._store: OrderedDict[int, object] = OrderedDict()
        self._bytes_used: int = 0

    # ------------------------------------------------------------------

    def get(self, idx: int) -> object | None:
        frame = self._store.get(idx)
        if frame is not None:
            self._store.move_to_end(idx)   # mark as recently used
        return frame

    def put(self, idx: int, frame: object):
        if idx in self._store:
            self._store.move_to_end(idx)
            return
        fb = frame.nbytes  # actual bytes for this numpy array
        self._store[idx] = frame
        self._bytes_used += fb
        # Evict LRU entries until within budget and under the hard frame cap.
        while (self._bytes_used > self._budget
               or len(self._store) > self._MAX_FRAMES) and len(self._store) > 1:
            _, evicted = self._store.popitem(last=False)
            self._bytes_used -= evicted.nbytes

    def clear(self):
        self._store.clear()
        self._bytes_used = 0


class FrameDecodeWorker(QObject):
    """
    Decodes video frames on a background thread to keep the UI thread responsive
    during scrubbing and playback.

    Usage:
        worker = FrameDecodeWorker(player)
        thread = QThread()
        worker.moveToThread(thread)
        thread.start()
        worker.frame_ready.connect(my_slot)   # auto QueuedConnection → UI thread
        worker.request(42)                    # schedule decode of frame 42

    Thread-safety contract:
        • request() is called from the UI thread.
        • _decode() runs on the background thread (via QueuedConnection).
        • VideoPlayer._read_frame() is only ever called from _decode(),
          so VideoCapture is never accessed concurrently.
        • pause() / resume() allow the export code (which runs on the UI thread
          and accesses the player directly) to safely serialize with decode.

    Stale-frame filtering:
        A generation counter (incremented via new_generation()) is stamped on
        each request and result.  Results from a superseded generation are
        silently dropped so a late-arriving decode from an old video never
        updates the new scene.
    """

    # Emits on the UI thread (auto QueuedConnection from background → UI).
    # Carries (generation, frame_idx, QImage).  Callers check generation.
    frame_ready = pyqtSignal(int, int, QImage)   # (generation, frame_idx, image)

    def __init__(self, player: VideoPlayer, generation: int = 0):
        super().__init__()
        self._player      = player
        self._lock        = threading.Lock()
        self._latest_idx  = -1
        self._generation  = generation  # unique across successive scene players
        self._req_gen     = 0     # generation stamped on the latest request
        self._in_flight   = 0     # number of _decode invocations queued/running
        self._paused      = False
        self._idle        = threading.Event()
        self._idle.set()          # starts idle

    # ------------------------------------------------------------------
    # Public API (called from UI thread)
    # ------------------------------------------------------------------

    def request(self, frame_idx: int):
        """Schedule an async frame decode.  Only the latest request is decoded."""
        with self._lock:
            if self._paused:
                return
            self._latest_idx = frame_idx
            self._req_gen    = self._generation
            if self._in_flight == 0:
                self._idle.clear()
            self._in_flight += 1
        QMetaObject.invokeMethod(self, "_decode", Qt.ConnectionType.QueuedConnection)

    def new_generation(self):
        """
        Increment the generation counter.  Call this when a new video is loaded
        so stale in-flight results from the old video are discarded.
        """
        with self._lock:
            self._generation += 1

    def pause(self):
        """
        Prevent new requests and wait (blocking) until any in-flight decode
        finishes.  Call before accessing the player directly (e.g. export).
        """
        with self._lock:
            self._paused = True
        self._idle.wait()

    def resume(self):
        """Re-enable request() after a pause."""
        with self._lock:
            self._paused = False

    # ------------------------------------------------------------------
    # Background-thread slot
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _decode(self):
        with self._lock:
            idx = self._latest_idx
            gen = self._req_gen
            self._in_flight -= 1
            stale = self._in_flight > 0
        try:
            if stale or idx == -1:
                return
            frame = self._player._read_frame(idx)
            if frame is not None:
                self.frame_ready.emit(gen, idx, VideoPlayer._bgr_to_image(frame))
        finally:
            # A zero queue length does not mean decoding is finished. Export
            # and media replacement must wait until read/conversion completes.
            with self._lock:
                if self._in_flight == 0:
                    self._idle.set()


class VideoPlayer:
    """
    Wraps an OpenCV VideoCapture with editing metadata.

    Usage:
        p = VideoPlayer()
        if p.load("/path/to/clip.mp4"):
            pixmap = p.get_frame_pixmap(0)
    """

    def __init__(self):
        self._cap         = None
        self._path        = ""
        self._fps         = 25.0
        self._frame_count = 0
        self._width       = 0
        self._height      = 0
        self._trim_in     = 0
        self._trim_out    = 0
        self._cuts: list[tuple[int, int]] = []
        self._reversed    = False
        self._speed_percent = 100
        self._audio_muted = False
        self._last_read   = -1   # track last frame read for sequential optimisation
        self._cache: FrameCache | None = None

    # ------------------------------------------------------------------
    # Load / release
    # ------------------------------------------------------------------

    def load(self, path: str) -> bool:
        """打开 a video file.  Returns False if the file cannot be opened."""
        import cv2
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return False
        fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fc <= 0:
            cap.release()
            return False

        # Release any previously loaded video
        self.release()

        self._cap         = cap
        self._path        = path
        self._fps         = cap.get(cv2.CAP_PROP_FPS) or 25.0
        self._frame_count = fc
        self._width       = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height      = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._trim_in     = 0
        self._trim_out    = fc - 1
        self._cuts        = []
        self._reversed    = False
        self._speed_percent = 100
        self._audio_muted = False
        self._last_read   = -1
        self._cache       = FrameCache()
        return True

    def release(self):
        """Release the underlying VideoCapture and drop the frame cache."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._last_read = -1
        if self._cache is not None:
            self._cache.clear()
            self._cache = None

    def is_loaded(self) -> bool:
        return self._cap is not None

    # ------------------------------------------------------------------
    # Frame access
    # ------------------------------------------------------------------

    def get_frame_pixmap(self, frame_idx: int) -> QPixmap | None:
        """Return frame_idx as a QPixmap (RGB), or None on error."""
        frame = self._read_frame(frame_idx)
        if frame is None:
            return None
        return self._bgr_to_pixmap(frame)

    def get_frame_ndarray(self, frame_idx: int) -> object | None:
        """Return frame_idx as a BGR numpy array, or None on error."""
        return self._read_frame(frame_idx)

    def _read_frame(self, frame_idx: int) -> object | None:
        import cv2
        if not self.is_loaded():
            return None
        frame_idx = max(0, min(frame_idx, self._frame_count - 1))

        # Cache hit — return immediately without touching OpenCV
        if self._cache is not None:
            cached = self._cache.get(frame_idx)
            if cached is not None:
                return cached

        # Cache miss — decode from disk
        # Skip the expensive seek when reading the next sequential frame
        if frame_idx != self._last_read + 1:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, float(frame_idx))
        ret, frame = self._cap.read()
        self._last_read = frame_idx if ret else -1

        if ret and self._cache is not None:
            self._cache.put(frame_idx, frame)

        return frame if ret else None

    # ------------------------------------------------------------------
    # Properties (read-only)
    # ------------------------------------------------------------------

    @property
    def path(self) -> str:        return self._path
    @property
    def fps(self) -> float:       return self._fps
    @property
    def frame_count(self) -> int: return self._frame_count
    @property
    def width(self) -> int:       return self._width
    @property
    def height(self) -> int:      return self._height
    @property
    def trim_in(self) -> int:     return self._trim_in
    @property
    def trim_out(self) -> int:    return self._trim_out
    @property
    def is_reversed(self) -> bool: return self._reversed
    @property
    def cuts(self) -> list[tuple[int, int]]: return list(self._cuts)
    @property
    def speed_percent(self) -> int: return self._speed_percent
    @property
    def speed_factor(self) -> float: return max(0.10, min(1.0, self._speed_percent / 100.0))
    @property
    def playback_fps(self) -> float: return max(1.0, self._fps * self.speed_factor)
    @property
    def audio_muted(self) -> bool: return self._audio_muted

    @property
    def original_fourcc(self) -> str:
        """Four-character codec string of the source video."""
        import cv2
        if not self.is_loaded():
            return 'mp4v'
        v = int(self._cap.get(cv2.CAP_PROP_FOURCC))
        return ''.join(chr((v >> i) & 0xFF) for i in (0, 8, 16, 24)).strip('\x00') or 'mp4v'

    def duration_seconds(self) -> float:
        return self._frame_count / self._fps if self._fps else 0.0

    # ------------------------------------------------------------------
    # Editing controls
    # ------------------------------------------------------------------

    def set_trim_in(self, frame: int):
        self._trim_in = max(0, min(frame, self._trim_out))

    def set_trim_out(self, frame: int):
        self._trim_out = max(self._trim_in, min(frame, self._frame_count - 1))

    def add_cut(self, start: int, end: int):
        """Mark the range [start, end] to be excluded from export."""
        self._cuts.append((min(start, end), max(start, end)))

    def clear_cuts(self):
        self._cuts.clear()

    def toggle_reverse(self):
        self._reversed = not self._reversed

    def set_speed_percent(self, value: int):
        self._speed_percent = max(10, min(100, int(value)))

    def set_audio_muted(self, muted: bool):
        self._audio_muted = bool(muted)

    def reset_edits(self):
        """Reset trim, cuts, and reverse to defaults."""
        self._trim_in  = 0
        self._trim_out = self._frame_count - 1
        self._cuts.clear()
        self._reversed = False
        self._speed_percent = 100
        self._audio_muted = False

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def get_export_frames(self) -> list[int]:
        """
        Return the ordered list of frame indices to render during export,
        after applying trim, cuts, and reverse.
        """
        cut_set: set[int] = set()
        for s, e in self._cuts:
            # Never let a single cut silently erase the entire video
            if (s <= self._trim_in and e >= self._trim_out):
                continue
            cut_set.update(range(s, e + 1))

        frames = [f for f in range(self._trim_in, self._trim_out + 1)
                  if f not in cut_set]
        if self._reversed:
            frames.reverse()
        return frames

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _bgr_to_pixmap(frame) -> QPixmap:
        return QPixmap.fromImage(VideoPlayer._bgr_to_image(frame))

    @staticmethod
    def _bgr_to_image(frame) -> QImage:
        """Own the pixel memory so an image can safely cross worker threads."""
        import cv2
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch  = frame_rgb.shape
        img = QImage(frame_rgb.tobytes(), w, h, ch * w,
                     QImage.Format.Format_RGB888)
        return img.copy()

    @staticmethod
    def qimage_to_bgr(img: QImage) -> object:
        """Convert a QImage to a BGR numpy array for OpenCV."""
        import cv2
        import numpy as np
        img = img.convertToFormat(QImage.Format.Format_RGB888)
        w, h = img.width(), img.height()
        ptr  = img.bits()
        ptr.setsize(h * w * 3)
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 3)).copy()
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
