"""
export.py — Export logic for both photos and videos.

Photo export:  renders bubbles at full source resolution → PNG/JPEG/WebP.
Video export:  renders each export frame with bubbles via OpenCV, then
               muxes original audio back in with FFmpeg (if available).
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog, QApplication

from video_player import VideoPlayer
import file_dialogs


def _find_ffmpeg() -> str | None:
    """Return path to FFmpeg: bundled copy first, then system PATH."""
    if hasattr(sys, "_MEIPASS"):
        executable = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        bundled = os.path.join(sys._MEIPASS, executable)
        if os.path.isfile(bundled):
            return bundled
    return shutil.which("ffmpeg")


# ---------------------------------------------------------------------------
# Photo export
# ---------------------------------------------------------------------------

def export_photo(parent, scene, photo_item, right_photo_item=None, is_dual=False):
    """
    Export the current scene to a full-resolution image file.

    In single mode: renders left photo at full resolution with bubbles.
    In dual mode:   side-by-side composite of left + right at their native sizes.
    """
    if photo_item is None or photo_item.pixmap().isNull():
        QMessageBox.warning(parent, "导出", "未加载照片。")
        return

    # Render first, so the frame dialog can preview the real composited photo.
    if is_dual and right_photo_item and not right_photo_item.pixmap().isNull():
        image = _render_dual_photo(scene, photo_item, right_photo_item)
    else:
        image = _render_single_photo(scene, photo_item)

    from frame_dialog import FrameDialog
    from frames import apply_frame
    dlg = FrameDialog(image, parent)
    if not dlg.exec():
        return
    image = apply_frame(image, dlg.settings())
    scale = dlg.scale()
    if scale < 1.0:
        image = image.scaled(
            max(1, int(image.width() * scale)), max(1, int(image.height() * scale)),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation)

    src_path = getattr(photo_item, '_source_path', '')
    base = os.path.splitext(os.path.basename(src_path))[0] if src_path else "photo"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = _save_dialog(parent, "导出照片", f"{base}-{timestamp}")
    if not path:
        return

    _save_image(parent, image, path)


def _render_single_photo(scene, photo_item) -> QImage:
    # Use native pixmap dimensions for full-resolution export
    W = photo_item.pixmap().width()
    H = photo_item.pixmap().height()

    image = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    scene_rect = photo_item.sceneBoundingRect()
    scene.render(painter, QRectF(0, 0, W, H), scene_rect)
    painter.end()
    return image


def _export_single_photo(parent, scene, photo_item, path):
    _save_image(parent, _render_single_photo(scene, photo_item), path)


def _render_dual_photo(scene, left_item, right_item) -> QImage:
    # On the canvas both panels share the LEFT image's display height (the right
    # image is scaled to match). Reproduce that layout so the export matches the
    # canvas — composite at the left image's native vertical resolution.
    lh_disp = float(left_item.display_h) or 1.0
    scale = (float(left_item.pixmap().height()) or lh_disp) / lh_disp
    H  = max(1, round(lh_disp * scale))
    LW = max(1, round(float(left_item.display_w) * scale))
    RW = max(1, round(float(right_item.display_w) * scale))
    W  = LW + RW

    image = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    # Both panels render to the SAME height H so they stay aligned.
    scene.render(painter, QRectF(0, 0, LW, H), left_item.sceneBoundingRect())
    scene.render(painter, QRectF(LW, 0, RW, H), right_item.sceneBoundingRect())

    painter.end()
    return image


# 保存对话框的格式过滤器，与扩展名映射
SAVE_FILTERS = "PNG (*.png);;JPEG (*.jpg *.jpeg);;WebP (*.webp)"
_FILTER_EXT = {"PNG": ".png", "JPEG": ".jpg", "WebP": ".webp"}


def _save_dialog(parent, title: str, default_stem: str) -> str:
    """选格式 + 选路径，并让扩展名跟随所选格式。

    Qt 保存对话框的文件名默认是 .png。用户在下拉里选了 JPEG 却没改文件名时，
    过去会静默存成 PNG —— 这里按所选过滤器把扩展名纠正过来。
    """
    path, chosen = file_dialogs.save_file(
        parent, title, f"{default_stem}.png", SAVE_FILTERS)
    if not path:
        return ""
    want = _FILTER_EXT.get((chosen or "PNG").split(" ")[0], ".png")
    root, ext = os.path.splitext(path)
    ext_l = ext.lower()
    matches = (
        (want == ".jpg" and ext_l in (".jpg", ".jpeg"))
        or (want == ".png" and ext_l == ".png")
        or (want == ".webp" and ext_l == ".webp")
    )
    if not matches:
        path = root + want
    return path


def _save_image(parent, image: QImage, path: str):
    ext = os.path.splitext(path)[1].lower()
    fmt = {".jpg": "JPEG", ".jpeg": "JPEG",
           ".webp": "WEBP", ".png": "PNG"}.get(ext, "PNG")
    if fmt == "JPEG":
        # JPEG 不支持透明：先垫一层白底，否则半透明/空白区域会变黑
        flat = QImage(image.size(), QImage.Format.Format_RGB32)
        flat.fill(Qt.GlobalColor.white)
        painter = QPainter(flat)
        painter.drawImage(0, 0, image)
        painter.end()
        ok = flat.save(path, fmt, 95)
    elif fmt == "WEBP":
        ok = image.save(path, fmt, 90)
    else:
        ok = image.save(path, fmt)
    if ok:
        QMessageBox.information(parent, "导出", f"已保存到：\n{path}")
    else:
        QMessageBox.critical(parent, "导出", f"保存失败：\n{path}")


def export_manga_photo(parent, scene):
    """Export the complete Comic Maker page at its native page resolution."""
    if not getattr(scene, "is_manga_mode", lambda: False)():
        QMessageBox.warning(parent, "导出", "漫画制作器未启用。")
        return

    from manga_maker import PAGE_HEIGHT, PAGE_WIDTH

    selected = list(scene.selectedItems())
    scene.clearSelection()  # selection outlines are editing UI, not page art
    scene.set_manga_guides_visible(False)
    QApplication.processEvents()

    image = QImage(int(PAGE_WIDTH), int(PAGE_HEIGHT),
                   QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    scene.render(painter, QRectF(0, 0, PAGE_WIDTH, PAGE_HEIGHT), scene.sceneRect())
    painter.end()

    for item in selected:
        if item.scene() is scene:
            item.setSelected(True)
    scene.set_manga_guides_visible(True)

    from frame_dialog import FrameDialog
    from frames import apply_frame
    dlg = FrameDialog(image, parent)
    if not dlg.exec():
        return
    image = apply_frame(image, dlg.settings())
    scale = dlg.scale()
    if scale < 1.0:
        image = image.scaled(
            max(1, int(image.width() * scale)), max(1, int(image.height() * scale)),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = _save_dialog(parent, "导出漫画页面", f"comic-page-{timestamp}")
    if path:
        _save_image(parent, image, path)


def export_collage_photo(parent, scene):
    """Export the complete Photo Collage page at its configured aspect ratio."""
    if not getattr(scene, "is_collage_mode", lambda: False)():
        QMessageBox.warning(parent, "导出", "照片拼贴未启用。")
        return

    source = scene.sceneRect()
    width = max(1, int(round(source.width())))
    height = max(1, int(round(source.height())))
    selected = list(scene.selectedItems())
    scene.clearSelection()
    scene.set_manga_guides_visible(False)
    QApplication.processEvents()

    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    scene.render(painter, QRectF(0, 0, width, height), source)
    painter.end()

    for item in selected:
        if item.scene() is scene:
            item.setSelected(True)
    scene.set_manga_guides_visible(True)

    from frame_dialog import FrameDialog
    from frames import apply_frame
    dlg = FrameDialog(image, parent)
    if not dlg.exec():
        return
    image = apply_frame(image, dlg.settings())
    scale = dlg.scale()
    if scale < 1.0:
        image = image.scaled(
            max(1, int(image.width() * scale)), max(1, int(image.height() * scale)),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = _save_dialog(parent, "导出照片拼贴", f"photo-collage-{timestamp}")
    if path:
        _save_image(parent, image, path)


# ---------------------------------------------------------------------------
# Video export
# ---------------------------------------------------------------------------

def export_video(parent, scene, photo_item, player: VideoPlayer,
                 right_photo_item=None, right_player: VideoPlayer | None = None,
                 is_dual=False):
    """
    Export the current video with speech bubbles rendered on each frame.
    Uses OpenCV for frame rendering and FFmpeg for audio muxing.
    """
    # At least one player must be loaded
    active = player if (player and player.is_loaded()) else right_player
    if active is None or not active.is_loaded():
        QMessageBox.warning(parent, "导出", "未加载视频。")
        return

    src_path = active.path
    base = os.path.splitext(os.path.basename(src_path))[0]
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    default_name = f"{base}-{timestamp}.mp4"

    out_path, _ = file_dialogs.save_file(
        parent, "导出视频", default_name,
        "MP4 (*.mp4);;AVI (*.avi);;MKV (*.mkv)"
    )
    if not out_path:
        return

    # Determine the "driver" player (the one that provides frame count / fps)
    driver = player if (player and player.is_loaded()) else right_player

    if is_dual and right_player and right_player.is_loaded():
        _export_dual_video(parent, scene, photo_item, player,
                           right_photo_item, right_player, out_path)
    elif driver and driver.is_loaded():
        _export_single_video(parent, scene, photo_item, driver, out_path)
    else:
        QMessageBox.warning(parent, "导出", "没有可用的视频播放器。")
        return


def _prerender_bubble_overlay(scene, photo_item, W: int, H: int):
    """
    Render the bubble layer ONCE to a BGRA numpy array (H × W × 4, BGRA order).

    Bubbles are static — they don't change between video frames — so we render
    them a single time and reuse the result for every frame instead of calling
    QPainter+scene.render for every frame.
    """
    import numpy as np
    photo_item.setVisible(False)

    overlay = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
    overlay.fill(0)
    painter = QPainter(overlay)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    scene.render(painter, QRectF(0, 0, W, H), photo_item.sceneBoundingRect())
    painter.end()

    photo_item.setVisible(True)

    overlay = overlay.convertToFormat(QImage.Format.Format_ARGB32)
    ptr = overlay.bits()
    ptr.setsize(H * W * 4)
    return np.frombuffer(ptr, dtype=np.uint8).reshape((H, W, 4)).copy()


def _composite(frame_bgr, overlay_bgra):
    """Alpha-composite a pre-rendered bubble overlay onto a BGR video frame."""
    import numpy as np
    alpha       = overlay_bgra[:, :, 3:4] / 255.0
    overlay_bgr = overlay_bgra[:, :, :3].astype(np.float32)
    base_bgr    = frame_bgr.astype(np.float32)
    return (base_bgr * (1 - alpha) + overlay_bgr * alpha).clip(0, 255).astype(np.uint8)


def _export_single_video(parent, scene, photo_item, player: VideoPlayer, out_path: str):
    import cv2
    frames = player.get_export_frames()
    if not frames:
        QMessageBox.warning(parent, "导出", "No frames to export after trimming/cuts.")
        return

    # Use native video dimensions for full-resolution export.
    # Ensure codec-friendly even dimensions.
    W   = player.width
    H   = player.height
    W   = W if W % 2 == 0 else W + 1
    H   = H if H % 2 == 0 else H + 1
    fps = player.playback_fps

    # Pause background decode workers so they don't race the export loop.
    scene.pause_decode_workers()

    # Pre-render bubble overlay once — bubbles are static across all frames.
    bubble_overlay = _prerender_bubble_overlay(scene, photo_item, W, H)

    progress = QProgressDialog("正在导出视频…", "取消", 0, len(frames), parent)
    progress.setWindowTitle("正在导出")
    progress.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress.setMinimumDuration(0)
    progress.setValue(0)

    tmp_video = out_path + ".tmp_noaudio.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(tmp_video, fourcc, fps, (W, H))

    cancelled = False
    try:
        for i, frame_idx in enumerate(frames):
            if progress.wasCanceled():
                cancelled = True
                break

            frame = player.get_frame_ndarray(frame_idx)
            if frame is not None:
                if frame.shape[1] != W or frame.shape[0] != H:
                    frame = cv2.resize(frame, (W, H))
                writer.write(_composite(frame, bubble_overlay))

            progress.setValue(i + 1)
            QApplication.processEvents()
    finally:
        writer.release()
        progress.close()
        scene.resume_decode_workers()

    if cancelled:
        _safe_remove(tmp_video)
        return

    _finish_video_audio(player, tmp_video, out_path, frames)
    _safe_remove(tmp_video)

    QMessageBox.information(parent, "导出", f"视频已保存到：\n{out_path}")


def _pixmap_to_bgr(pixmap, w: int, h: int):
    """
    Scale a QPixmap to (w × h) and return as a BGR numpy array.
    Used when one side is a static photo during dual video export.
    """
    import numpy as np
    img = pixmap.scaled(w, h,
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                        ).toImage()
    img = img.convertToFormat(QImage.Format.Format_RGB888)
    ptr = img.bits()
    ptr.setsize(h * w * 3)
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 3)).copy()
    return arr[:, :, ::-1]  # RGB → BGR


def _export_dual_video(parent, scene, left_item, left_player: VideoPlayer,
                       right_item, right_player: VideoPlayer, out_path: str):
    """
    Dual video export.  Either side may be a static photo (player=None).
    The video side (or left if both are video) drives the frame sequence.
    """
    import cv2
    import numpy as np
    left_has_video  = left_player is not None and left_player.is_loaded()
    right_has_video = right_player is not None and right_player.is_loaded()

    # Pick the driver: prefer left video, fall back to right video
    driver = left_player if left_has_video else right_player
    if driver is None or not driver.is_loaded():
        QMessageBox.warning(parent, "导出", "未找到可用于双联导出的视频。")
        return

    frames = driver.get_export_frames()
    if not frames:
        QMessageBox.warning(parent, "导出", "没有可导出的帧。")
        return

    # Use native video dimensions for full-resolution export.
    LW  = left_player.width  if left_has_video  else left_item.pixmap().width()
    LH  = left_player.height if left_has_video  else left_item.pixmap().height()
    LW  = LW if LW % 2 == 0 else LW + 1
    LH  = LH if LH % 2 == 0 else LH + 1
    fps = driver.playback_fps

    # Determine output dimensions for the right panel at native resolution
    if right_has_video:
        RH_src = right_player.height
        RW_src = right_player.width
    if right_item is not None and not right_has_video:
        RW_out = right_item.pixmap().width()
        RH_out = right_item.pixmap().height()
        # Scale right photo to match left panel height
        scale  = LH / RH_out if RH_out else 1.0
        RW_out = max(1, int(RW_out * scale))
        RW_out = RW_out if RW_out % 2 == 0 else RW_out + 1
    elif right_has_video:
        scale  = LH / RH_src if RH_src else 1.0
        RW_out = max(1, int(RW_src * scale))
        RW_out = RW_out if RW_out % 2 == 0 else RW_out + 1
    else:
        RW_out = LW  # fallback

    W, H = LW + RW_out, LH

    # Pause background decode workers before accessing players directly.
    scene.pause_decode_workers()

    # Pre-render static sides once (photo stays the same every frame)
    static_left_bgr  = None if left_has_video  else _pixmap_to_bgr(left_item.pixmap(),  LW, LH)
    static_right_bgr = None
    if not right_has_video and right_item is not None:
        raw = _pixmap_to_bgr(right_item.pixmap(),
                             right_item.pixmap().width(),
                             right_item.pixmap().height())
        static_right_bgr = cv2.resize(raw, (RW_out, LH))

    # Pre-render bubble overlay for the left panel once (bubbles are static).
    left_overlay = _prerender_bubble_overlay(scene, left_item, LW, LH)

    progress = QProgressDialog("正在导出双联视频…", "取消", 0, len(frames), parent)
    progress.setWindowTitle("正在导出")
    progress.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress.setMinimumDuration(0)
    progress.setValue(0)

    tmp_video = out_path + ".tmp_noaudio.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(tmp_video, fourcc, fps, (W, H))

    right_total = right_player.frame_count if right_has_video else 0

    cancelled = False
    try:
        for i, frame_idx in enumerate(frames):
            if progress.wasCanceled():
                cancelled = True
                break

            # --- Left panel ---
            if left_has_video:
                left_frame = left_player.get_frame_ndarray(frame_idx)
                if left_frame is None:
                    left_frame = np.zeros((LH, LW, 3), dtype=np.uint8)
                if left_frame.shape[1] != LW or left_frame.shape[0] != LH:
                    left_frame = cv2.resize(left_frame, (LW, LH))
                left_rendered = _composite(left_frame, left_overlay)
            else:
                left_rendered = _composite(static_left_bgr.copy(), left_overlay)

            # --- Right panel ---
            if right_has_video:
                right_idx   = min(frame_idx, right_total - 1)
                right_frame = right_player.get_frame_ndarray(right_idx)
                if right_frame is None:
                    right_frame = np.zeros((RH_src, RW_src, 3), dtype=np.uint8)
                right_scaled = cv2.resize(right_frame, (RW_out, LH))
            elif static_right_bgr is not None:
                right_scaled = static_right_bgr
            else:
                right_scaled = np.zeros((LH, RW_out, 3), dtype=np.uint8)

            writer.write(np.hstack([left_rendered, right_scaled]))
            progress.setValue(i + 1)
            QApplication.processEvents()
    finally:
        writer.release()
        progress.close()
        scene.resume_decode_workers()

    if cancelled:
        _safe_remove(tmp_video)
        return

    _finish_video_audio(driver, tmp_video, out_path, frames)
    _safe_remove(tmp_video)

    QMessageBox.information(parent, "导出", f"双格视频已保存到：\n{out_path}")


# ---------------------------------------------------------------------------
# FFmpeg audio muxing
# ---------------------------------------------------------------------------

def _finish_video_audio(player: VideoPlayer, rendered_video: str, out_path: str,
                        export_frames: list[int]):
    """Move or mux the rendered no-audio video according to the player audio setting."""
    if player.audio_muted:
        shutil.move(rendered_video, out_path)
        return
    _mux_audio(player.path, rendered_video, out_path, export_frames,
               player.fps, player.speed_factor)


def _mux_audio(src_video: str, rendered_video: str, out_path: str,
               export_frames: list[int], source_fps: float, speed_factor: float = 1.0):
    """
    Attempt to mux audio from src_video into rendered_video → out_path.
    Falls back to just renaming rendered_video if FFmpeg is unavailable or fails.
    """
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        shutil.move(rendered_video, out_path)
        return

    # Calculate start time offset based on first export frame
    start_frame = export_frames[0] if export_frames else 0
    start_time = start_frame / source_fps if source_fps else 0.0

    # Scale timeout: 120 s base + 1 s per export frame, minimum 120 s.
    timeout_s = max(120, 120 + len(export_frames))

    cmd = [
        ffmpeg, "-y",
        "-i", rendered_video,
        "-ss", str(start_time),
        "-i", src_video,
        "-map", "0:v:0",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
    ]
    if speed_factor < 0.999:
        cmd += [
            "-filter_complex",
            f"[1:a:0]{_atempo_chain(speed_factor)}[a]",
            "-map", "[a]",
            "-c:a", "aac",
        ]
    else:
        cmd += [
            "-map", "1:a:0?",
            "-c:a", "aac",
        ]
    cmd += ["-shortest", out_path]
    try:
        subprocess.run(cmd, check=True, timeout=timeout_s,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # FFmpeg failed or timed out — use the video without audio.
        # Remove any partial output FFmpeg may have created before falling back.
        _safe_remove(out_path)
        shutil.move(rendered_video, out_path)


def _atempo_chain(speed_factor: float) -> str:
    """Build an FFmpeg atempo chain. atempo supports 0.5..100 per filter."""
    speed = max(0.10, min(1.0, float(speed_factor)))
    parts = []
    while speed < 0.5:
        parts.append("atempo=0.5")
        speed /= 0.5
    parts.append(f"atempo={speed:.4f}")
    return ",".join(parts)


def _safe_remove(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
