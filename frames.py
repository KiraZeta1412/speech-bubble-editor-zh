"""
frames.py — Export frames and captions (Balloon+ "Save / Share" screen).

A frame is drawn around the finished image at export time: a border of one of
six styles in a chosen colour, optionally two-tone, with an optional caption
strip above or below the photo.

`FrameSettings` holds the choices; `apply_frame()` turns a rendered QImage into
the framed one. Nothing here touches the scene, so photo and video export can
share it.
"""

from dataclasses import dataclass, field

from PyQt6.QtGui import QImage, QPainter, QColor, QFont, QFontMetrics
from PyQt6.QtCore import Qt, QRect

# (key, label, outer border %, inner border %, tooltip)
# Percentages are of the image's short side, so a frame looks the same on any
# resolution.
FRAME_STYLES = (
    ("none",    "None",   0.000, 0.000, "无画框"),
    ("thin",    "细线",   0.012, 0.000, "细边框"),
    ("thick",   "粗线",  0.045, 0.000, "粗边框"),
    ("inner",   "内线",  0.045, 0.008, "带内描线的粗边框"),
    ("double",  "双层", 0.055, 0.016, "双色双边框"),
    ("polaroid","照片",  0.040, 0.000, "冲印风格：加宽底边用于说明文字"),
)

FRAME_COLORS = (
    "#ffffff", "#000000", "#c9b79c", "#2f5fd0",
    "#f6cfe0", "#b8d4c2", "#c62828",
)

CAPTION_POSITIONS = ("bottom", "top")


@dataclass
class FrameSettings:
    style: str = "none"
    color: str = "#ffffff"
    two_tone: bool = False
    accent: str = "#000000"      # second tone (inner keyline / double border)
    caption: str = ""
    caption_position: str = "bottom"
    caption_font: str = "Inter"
    caption_size: int = 10       # 1-30, relative; scaled to image size
    caption_color: str = ""      # blank = auto (contrast against frame)

    def is_active(self) -> bool:
        return self.style != "none" or bool(self.caption.strip())

    def copy(self) -> "FrameSettings":
        return FrameSettings(**self.__dict__)


def _style_def(key: str):
    for entry in FRAME_STYLES:
        if entry[0] == key:
            return entry
    return FRAME_STYLES[0]


def _contrast_text(bg: QColor) -> QColor:
    """Black or white, whichever is readable on `bg`."""
    lum = 0.299 * bg.red() + 0.587 * bg.green() + 0.114 * bg.blue()
    return QColor("#111111") if lum > 140 else QColor("#f2f2f2")


def apply_frame(image: QImage, cfg: FrameSettings) -> QImage:
    """Return a new image with the frame and caption drawn around `image`."""
    if cfg is None or not cfg.is_active():
        return image

    key, _label, outer_f, inner_f, _tip = _style_def(cfg.style)
    short = min(image.width(), image.height())
    border = int(round(short * outer_f))
    inner = int(round(short * inner_f))

    frame_color = QColor(cfg.color)
    accent_color = QColor(cfg.accent) if cfg.two_tone else frame_color

    caption = cfg.caption.strip()
    caption_h = 0
    font = QFont(cfg.caption_font)
    if caption:
        # Caption size is relative (1-30) so it holds up at any resolution.
        px = max(8, int(short * cfg.caption_size / 300.0))
        font.setPixelSize(px)
        font.setBold(True)
        caption_h = int(px * 2.1)
    # A photo-print frame always leaves a wide base, caption or not.
    base_extra = int(short * 0.075) if key == "polaroid" else 0

    top_pad = border + (caption_h if caption and cfg.caption_position == "top" else 0)
    bottom_pad = border + base_extra + (
        caption_h if caption and cfg.caption_position == "bottom" else 0)

    out_w = image.width() + border * 2
    out_h = image.height() + top_pad + bottom_pad
    out = QImage(out_w, out_h, QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(frame_color)

    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    photo_rect = QRect(border, top_pad, image.width(), image.height())

    # Inner keyline / second tone, drawn as a band hugging the photo.
    if inner > 0:
        painter.fillRect(
            QRect(photo_rect.left() - inner, photo_rect.top() - inner,
                  photo_rect.width() + inner * 2, photo_rect.height() + inner * 2),
            accent_color)
    elif cfg.two_tone and border > 0:
        # Two-tone on a plain border: outer half in the accent colour.
        half = max(1, border // 2)
        painter.fillRect(QRect(0, 0, out_w, half), accent_color)
        painter.fillRect(QRect(0, out_h - half, out_w, half), accent_color)
        painter.fillRect(QRect(0, 0, half, out_h), accent_color)
        painter.fillRect(QRect(out_w - half, 0, half, out_h), accent_color)

    painter.drawImage(photo_rect, image)

    if caption:
        painter.setFont(font)
        color = QColor(cfg.caption_color) if cfg.caption_color \
            else _contrast_text(frame_color)
        painter.setPen(color)
        if cfg.caption_position == "top":
            band = QRect(border, 0, image.width(), top_pad)
        else:
            band = QRect(border, photo_rect.bottom() + 1,
                         image.width(), out_h - photo_rect.bottom() - 1)
        painter.drawText(
            band,
            int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextWordWrap),
            caption)

    painter.end()
    return out
