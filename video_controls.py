"""
video_controls.py — VideoControls: scrubber + playback + trim/cut/reverse UI (v4 redesign).

All transport buttons now use SVG icons from icons.py.
Supports dual video: a Left/Right toggle appears when a right player is set.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QFrame, QToolButton, QSlider, QCheckBox,
)
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint, pyqtSignal, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QPolygon, QIcon

from video_player import VideoPlayer
from icons import (
    make_icon, ACCENT, FG, MUTED,
    ICON_TO_START, ICON_STEP_BACK, ICON_PLAY, ICON_PAUSE,
    ICON_STEP_FWD, ICON_TO_END, ICON_FULLSCREEN,
    ICON_SET_IN, ICON_SET_OUT, ICON_CUT, ICON_MARKER, ICON_REVERSE,
)


# ---------------------------------------------------------------------------
# VideoScrubber — unchanged from v3
# ---------------------------------------------------------------------------

class VideoScrubber(QWidget):
    position_changed = pyqtSignal(int)
    trim_in_dragged  = pyqtSignal(int)
    trim_out_dragged = pyqtSignal(int)

    _MARKER_H    = 10
    _MARKER_GRAB = 14

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._frame_count  = 0
        self._current      = 0
        self._trim_in      = 0
        self._trim_out     = 0
        self._cuts: list[tuple[int, int]] = []
        self._dragging     = False
        self._trim_drag    = None
        self._last_emitted = -1

    def set_player(self, player: "VideoPlayer | None"):
        if player is None or not player.is_loaded():
            self._frame_count = 0
        else:
            self._frame_count = player.frame_count
            self._trim_in     = player.trim_in
            self._trim_out    = player.trim_out
            self._cuts        = player.cuts
        self._current = 0
        self.update()

    def set_current_frame(self, frame: int):
        self._current = frame
        self.update()

    def sync_from_player(self, player: "VideoPlayer"):
        self._trim_in  = player.trim_in
        self._trim_out = player.trim_out
        self._cuts     = player.cuts
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(40, 40, 40))
        if self._frame_count <= 0:
            return

        track_y = self._MARKER_H + 2
        track_h = h - track_y - 2

        painter.fillRect(0, track_y, w, track_h, QColor(80, 80, 80))

        in_x  = self._f2x(self._trim_in)
        out_x = self._f2x(self._trim_out)
        painter.fillRect(in_x, track_y, out_x - in_x, track_h,
                         QColor(255, 138, 61, 200))

        for cs, ce in self._cuts:
            cx = self._f2x(cs)
            cw = self._f2x(ce) - cx
            painter.fillRect(cx, track_y, cw, track_h, QColor(220, 50, 50, 200))

        painter.setBrush(QColor(34, 197, 94))
        painter.setPen(Qt.PenStyle.NoPen)
        ix = in_x
        painter.drawPolygon(QPolygon([
            QPoint(ix, 0), QPoint(ix + self._MARKER_H, 0), QPoint(ix, self._MARKER_H),
        ]))

        painter.setBrush(QColor(249, 115, 22))
        ox = out_x
        painter.drawPolygon(QPolygon([
            QPoint(ox, 0), QPoint(ox - self._MARKER_H, 0), QPoint(ox, self._MARKER_H),
        ]))

        px = self._f2x(self._current)
        painter.setPen(QPen(QColor(255, 138, 61), 2))
        painter.drawLine(px, 0, px, h)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        x = event.position().x()
        y = event.position().y()
        if self._frame_count > 0 and y <= self._MARKER_H + 4:
            in_x  = self._f2x(self._trim_in)
            out_x = self._f2x(self._trim_out)
            if abs(x - in_x) <= self._MARKER_GRAB:
                self._trim_drag = "in"
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                event.accept()
                return
            if abs(x - out_x) <= self._MARKER_GRAB:
                self._trim_drag = "out"
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                event.accept()
                return
        self._trim_drag = None
        self._dragging  = True
        self._seek(x)

    def mouseMoveEvent(self, event):
        x = event.position().x()
        if self._trim_drag == "in":
            frame = max(0, min(self._x2f(x), self._trim_out - 1))
            self._trim_in = frame
            self.update()
            self.trim_in_dragged.emit(frame)
        elif self._trim_drag == "out":
            frame = max(self._trim_in + 1, min(self._x2f(x), self._frame_count - 1))
            self._trim_out = frame
            self.update()
            self.trim_out_dragged.emit(frame)
        elif self._dragging:
            self._seek(x)

    def mouseReleaseEvent(self, event):
        if self._trim_drag in ("in", "out"):
            if self._trim_drag == "in":
                self.trim_in_dragged.emit(self._trim_in)
            else:
                self.trim_out_dragged.emit(self._trim_out)
            self._trim_drag = None
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        elif self._dragging:
            self._dragging = False
            if self._current != self._last_emitted:
                self._last_emitted = self._current
                self.position_changed.emit(self._current)

    def _f2x(self, frame: int) -> int:
        if self._frame_count <= 1:
            return 0
        return int(frame / (self._frame_count - 1) * self.width())

    def _x2f(self, x: float) -> int:
        if self.width() == 0 or self._frame_count <= 1:
            return 0
        t = max(0.0, min(1.0, x / self.width()))
        return int(round(t * (self._frame_count - 1)))

    def _seek(self, x: float):
        frame = self._x2f(x)
        if frame == self._current:
            return
        self._current = frame
        self.update()
        if not self._dragging or abs(frame - self._last_emitted) >= 4:
            self._last_emitted = frame
            self.position_changed.emit(frame)


# ---------------------------------------------------------------------------
# VideoControls
# ---------------------------------------------------------------------------

class VideoControls(QWidget):

    frame_changed       = pyqtSignal(int)
    right_frame_changed = pyqtSignal(int)
    trim_in_changed     = pyqtSignal(int)
    trim_out_changed    = pyqtSignal(int)
    cut_requested       = pyqtSignal()
    cuts_cleared        = pyqtSignal()
    reverse_toggled     = pyqtSignal()
    speed_changed       = pyqtSignal(int)
    audio_muted_changed = pyqtSignal(bool)
    fullscreen_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player:        "VideoPlayer | None" = None
        self._player_right:  "VideoPlayer | None" = None
        self._active_side    = "left"
        self._current_frame  = 0
        self._playing        = False
        self._snap_speed     = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_frame)

        self._build()
        self.setVisible(False)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(2)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        # L/R toggle (hidden until dual)
        self._btn_left = self._tbtn("L", 26, "编辑左侧媒体", checkable=True, checked=True)
        self._btn_right_side = self._tbtn("R", 26, "编辑右侧媒体", checkable=True)
        self._side_sep = self._tbtn("|", 10, "")
        self._side_sep.setEnabled(False)
        for w in (self._btn_left, self._btn_right_side, self._side_sep):
            btn_row.addWidget(w)
            w.setVisible(False)
        self._btn_left.clicked.connect(lambda: self._switch_side("left"))
        self._btn_right_side.clicked.connect(lambda: self._switch_side("right"))

        # Transport buttons with SVG icons
        icon_size = QSize(13, 13)

        def transport_btn(svg, tip, size=26):
            b = QPushButton()
            b.setIcon(make_icon(svg, 16, FG))
            b.setIconSize(icon_size)
            b.setFixedSize(size, 26)
            b.setToolTip(tip)
            return b

        self._btn_first  = transport_btn(ICON_TO_START,  "跳到第一帧  (Home)")
        self._btn_stepb  = transport_btn(ICON_STEP_BACK, "后退一帧  (←)")
        self._btn_play   = transport_btn(ICON_PLAY,      "播放  (空格键)", size=34)
        self._btn_stepf  = transport_btn(ICON_STEP_FWD,  "前进一帧  (→)")
        self._btn_last   = transport_btn(ICON_TO_END,    "跳到最后一帧  (End)")

        self._icon_play  = make_icon(ICON_PLAY,  16, FG)
        self._icon_pause = make_icon(ICON_PAUSE, 16, ACCENT)

        self._btn_first.clicked.connect(self._on_first_frame)
        self._btn_stepb.clicked.connect(self._on_step_back)
        self._btn_play.clicked.connect(self._toggle_play)
        self._btn_stepf.clicked.connect(self._on_step_forward)
        self._btn_last.clicked.connect(self._on_last_frame)

        for b in (self._btn_first, self._btn_stepb, self._btn_play,
                  self._btn_stepf, self._btn_last):
            btn_row.addWidget(b)

        self._mute_check = QCheckBox("静音")
        self._mute_check.setObjectName("MuteAudioCheck")
        self._mute_check.setToolTip("在预览和导出时静音此视频的音频")
        self._mute_check.toggled.connect(self._on_audio_muted)
        btn_row.addWidget(self._mute_check)

        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setFixedWidth(120)
        self._time_label.setObjectName("TimecodeLabel")
        btn_row.addWidget(self._time_label)

        btn_row.addStretch()

        # Edit buttons
        def edit_btn(svg, label, tip, checkable=False):
            b = QPushButton(label)
            b.setIcon(make_icon(svg, 13, MUTED))
            b.setIconSize(icon_size)
            b.setToolTip(tip)
            b.setFixedHeight(26)
            b.setCheckable(checkable)
            return b

        btn_in  = edit_btn(ICON_SET_IN,  "设置入点",  "将入点设置到当前帧  ([)")
        btn_out = edit_btn(ICON_SET_OUT, "设置出点", "将出点设置到当前帧  (])")
        btn_cut = edit_btn(ICON_CUT,     "剪切",     "从片段中剪掉选中的剪辑范围")
        btn_clr = edit_btn(ICON_MARKER,  "清除",     "清除所有剪切")
        self._btn_reverse = edit_btn(ICON_REVERSE, "反向",
                                     "Toggle playback / export reversal",
                                     checkable=True)

        btn_in.clicked.connect(self._on_set_in)
        btn_out.clicked.connect(self._on_set_out)
        btn_cut.clicked.connect(self._on_cut)
        btn_clr.clicked.connect(self._on_clear_cuts)
        self._btn_reverse.clicked.connect(self._on_reverse)

        for b in (btn_in, btn_out, btn_cut, btn_clr, self._btn_reverse):
            btn_row.addWidget(b)

        btn_row.addSpacing(6)
        self._speed_label = QLabel("100%")
        self._speed_label.setObjectName("TimecodeLabel")
        self._speed_label.setFixedWidth(42)
        self._speed_label.setToolTip("Playback/export speed")
        btn_row.addWidget(self._speed_label)

        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(10, 100)
        self._speed_slider.setValue(100)
        self._speed_slider.setFixedWidth(120)
        self._speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._speed_slider.setTickInterval(5)
        self._speed_slider.setToolTip("放慢视频：磁性吸附点位于 10%、25%、35%、50%、75%、100%")
        self._speed_slider.valueChanged.connect(self._on_speed_slider)
        self._speed_slider.sliderReleased.connect(self._snap_speed_slider)
        btn_row.addWidget(self._speed_slider)

        # Fullscreen
        fs_btn = transport_btn(ICON_FULLSCREEN, "切换全屏窗口  (F)")
        fs_btn.clicked.connect(self.fullscreen_requested)
        btn_row.addWidget(fs_btn)

        layout.addLayout(btn_row)

        self._scrubber = VideoScrubber()
        self._scrubber.position_changed.connect(self._on_scrub)
        self._scrubber.trim_in_dragged.connect(self.trim_in_changed)
        self._scrubber.trim_out_dragged.connect(self.trim_out_changed)
        layout.addWidget(self._scrubber)

    def _tbtn(self, text, size, tip, checkable=False, checked=False):
        b = QPushButton(text)
        b.setFixedSize(size, 26)
        b.setCheckable(checkable)
        if checked:
            b.setChecked(True)
        b.setToolTip(tip)
        return b

    # ------------------------------------------------------------------
    # Public API — unchanged interface from v3
    # ------------------------------------------------------------------

    def set_player(self, player: "VideoPlayer | None"):
        self._stop_playback()
        self._player = player
        self._current_frame = 0
        if self._active_side == "left":
            self._scrubber.set_player(player)
        if player and player.is_loaded():
            self._update_time_label(0)
            self._btn_reverse.setChecked(player.is_reversed)
            self._sync_speed_from_player(player)
            self._sync_audio_muted_from_player(player)
            self.setVisible(True)
        else:
            if not (self._player_right and self._player_right.is_loaded()):
                self.setVisible(False)
        self._update_side_toggle_visibility()

    def set_right_player(self, player: "VideoPlayer | None"):
        self._player_right = player
        has_left = self._player is not None and self._player.is_loaded()
        if player and player.is_loaded():
            if not has_left:
                self._active_side = "right"
                self._btn_left.setChecked(False)
                self._btn_right_side.setChecked(True)
            if self._active_side == "right":
                self._scrubber.set_player(player)
                self._btn_reverse.setChecked(player.is_reversed)
                self._sync_speed_from_player(player)
                self._sync_audio_muted_from_player(player)
                self._update_time_label_for(player, 0)
            self.setVisible(True)
        else:
            if self._active_side == "right":
                self._active_side = "left"
                self._btn_left.setChecked(True)
                self._btn_right_side.setChecked(False)
                self._scrubber.set_player(self._player)
                if self._player and self._player.is_loaded():
                    self._btn_reverse.setChecked(self._player.is_reversed)
                    self._sync_speed_from_player(self._player)
                    self._sync_audio_muted_from_player(self._player)
            if not has_left:
                self.setVisible(False)
        self._update_side_toggle_visibility()

    def set_current_frame(self, frame: int):
        self._current_frame = frame
        if self._active_side == "left":
            self._scrubber.set_current_frame(frame)
            self._update_time_label(frame)

    @property
    def current_frame(self) -> int:
        return self._current_frame

    def toggle_playback(self):
        self._toggle_play()

    def first_frame(self):
        self._on_first_frame()

    def last_frame(self):
        self._on_last_frame()

    def step_back(self):
        self._on_step_back()

    def step_forward(self):
        self._on_step_forward()

    def set_trim_in_to_current_frame(self):
        self._on_set_in()

    def set_trim_out_to_current_frame(self):
        self._on_set_out()

    def stop(self):
        self._stop_playback()

    def sync_markers(self):
        player = self._active_player
        if player:
            self._scrubber.sync_from_player(player)
            frame = (self._current_frame if self._active_side == "left"
                     else min(self._current_frame, player.frame_count - 1))
            self._update_time_label_for(player, frame)

    @property
    def active_side(self) -> str:
        return self._active_side

    @property
    def _active_player(self) -> "VideoPlayer | None":
        if self._active_side == "right" and self._player_right:
            return self._player_right
        return self._player

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def _toggle_play(self):
        active = self._active_player
        if not active or not active.is_loaded():
            return
        self._playing = not self._playing
        self._btn_play.setIcon(self._icon_pause if self._playing else self._icon_play)
        self._btn_play.setToolTip("暂停  (空格键)" if self._playing else "播放  (空格键)")
        if self._playing:
            if (self._current_frame < active.trim_in
                    or self._current_frame > active.trim_out):
                start = active.trim_out if active.is_reversed else active.trim_in
                self._current_frame = start
                self._scrubber.set_current_frame(self._current_frame)
            ms = max(1, int(1000 / active.playback_fps))
            self._timer.start(ms)
        else:
            self._timer.stop()

    def _stop_playback(self):
        self._playing = False
        self._timer.stop()
        self._btn_play.setIcon(self._icon_play)
        self._btn_play.setToolTip("播放  (空格键)")

    def _advance_frame(self):
        active = self._active_player
        if not active:
            return
        rev = active.is_reversed
        nxt = self._current_frame - 1 if rev else self._current_frame + 1
        while True:
            jumped = False
            for cs, ce in active.cuts:
                if cs <= active.trim_in and ce >= active.trim_out:
                    continue
                if cs <= nxt <= ce:
                    nxt = cs - 1 if rev else ce + 1
                    jumped = True
                    break
            if not jumped:
                break
        if rev:
            if nxt < active.trim_in:
                nxt = active.trim_out
            if nxt > active.trim_out:
                nxt = active.trim_out
        else:
            if nxt < active.trim_in:
                nxt = active.trim_in
            if nxt > active.trim_out:
                nxt = active.trim_in
        self._current_frame = nxt
        if self._active_side == "right":
            self._scrubber.set_current_frame(nxt)
            self._update_time_label_for(active, nxt)
            self.right_frame_changed.emit(nxt)
        else:
            self._scrubber.set_current_frame(nxt)
            self._update_time_label(nxt)
            self.frame_changed.emit(nxt)
            if self._player_right and self._player_right.is_loaded():
                self.right_frame_changed.emit(min(nxt, self._player_right.frame_count - 1))

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_scrub(self, frame: int):
        if self._active_side == "right":
            self._current_frame = frame
            self.right_frame_changed.emit(frame)
            if self._player_right:
                self._update_time_label_for(self._player_right, frame)
        else:
            self._current_frame = frame
            self._update_time_label(frame)
            self.frame_changed.emit(frame)

    def _on_set_in(self):
        self.trim_in_changed.emit(self._active_frame())

    def _on_set_out(self):
        self.trim_out_changed.emit(self._active_frame())

    def _on_cut(self):
        self.cut_requested.emit()

    def _on_clear_cuts(self):
        self.cuts_cleared.emit()

    def _on_reverse(self):
        self.reverse_toggled.emit()

    def _on_speed_slider(self, value: int):
        if self._snap_speed:
            return
        player = self._active_player
        if player:
            player.set_speed_percent(value)
        self._speed_label.setText(f"{value}%")
        self.speed_changed.emit(value)
        if player:
            self._update_time_label_for(player, self._active_frame())
        if self._playing and player:
            self._timer.start(max(1, int(1000 / player.playback_fps)))

    def _snap_speed_slider(self):
        stops = (10, 25, 35, 50, 75, 100)
        value = self._speed_slider.value()
        snapped = min(stops, key=lambda stop: abs(stop - value))
        self._snap_speed = True
        self._speed_slider.setValue(snapped)
        self._snap_speed = False
        self._on_speed_slider(snapped)

    def _on_audio_muted(self, muted: bool):
        player = self._active_player
        if player:
            player.set_audio_muted(muted)
        self.audio_muted_changed.emit(muted)

    def _on_first_frame(self):
        self._go_to_frame(0)

    def _on_last_frame(self):
        active = self._active_player
        if active:
            self._go_to_frame(active.frame_count - 1)

    def _on_step_back(self):
        self._go_to_frame(max(0, self._current_frame - 1))

    def _on_step_forward(self):
        active = self._active_player
        if active:
            self._go_to_frame(min(active.frame_count - 1, self._current_frame + 1))

    def _go_to_frame(self, frame: int):
        active = self._active_player
        if not active:
            return
        self._current_frame = frame
        self._scrubber.set_current_frame(frame)
        if self._active_side == "right":
            self._update_time_label_for(active, frame)
            self.right_frame_changed.emit(frame)
        else:
            self._update_time_label(frame)
            self.frame_changed.emit(frame)

    def _switch_side(self, side: str):
        self._active_side = side
        self._btn_left.setChecked(side == "left")
        self._btn_right_side.setChecked(side == "right")
        player = self._active_player
        self._scrubber.set_player(player)
        if player and player.is_loaded():
            self._btn_reverse.setChecked(player.is_reversed)
            self._sync_speed_from_player(player)
            self._sync_audio_muted_from_player(player)
            frame = self._current_frame if side == "left" \
                else min(self._current_frame, player.frame_count - 1)
            self._update_time_label_for(player, frame)

    def _update_side_toggle_visibility(self):
        has_left  = self._player is not None and self._player.is_loaded()
        has_right = self._player_right is not None and self._player_right.is_loaded()
        show = has_left and has_right
        for w in (self._btn_left, self._btn_right_side, self._side_sep):
            w.setVisible(show)

    def _active_frame(self) -> int:
        if self._active_side == "right" and self._player_right:
            return min(self._current_frame, self._player_right.frame_count - 1)
        return self._current_frame

    def _update_time_label(self, frame: int):
        if self._player:
            self._update_time_label_for(self._player, frame)

    def _update_time_label_for(self, player: "VideoPlayer", frame: int):
        fps = player.playback_fps or 25.0
        if player.trim_in > 0 or player.trim_out < player.frame_count - 1:
            in_s  = player.trim_in  / fps
            out_s = player.trim_out / fps
            self._time_label.setText(f"{self._fmt(in_s)}–{self._fmt(out_s)}")
        else:
            curr  = frame / fps
            total = player.frame_count / fps
            self._time_label.setText(f"{self._fmt(curr)} / {self._fmt(total)}")

    def _sync_speed_from_player(self, player: "VideoPlayer"):
        self._snap_speed = True
        self._speed_slider.setValue(player.speed_percent)
        self._snap_speed = False
        self._speed_label.setText(f"{player.speed_percent}%")

    def _sync_audio_muted_from_player(self, player: "VideoPlayer"):
        self._mute_check.blockSignals(True)
        self._mute_check.setChecked(player.audio_muted)
        self._mute_check.blockSignals(False)

    @staticmethod
    def _fmt(seconds: float) -> str:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}:{s:02d}"
