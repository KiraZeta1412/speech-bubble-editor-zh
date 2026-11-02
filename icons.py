"""
icons.py — SVG icon helpers for Speech Bubble Editor v4 UI.

All icons are rendered as QIcon via QSvgRenderer so they scale cleanly
at any DPI. Use make_icon(SVG_STRING, size) to get a QIcon.

Colour is injected at render time via {color} format placeholder so
the same SVG path can be used in both normal and accent states.
"""

from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtCore import QByteArray


# Night-desk palette: warm proofing orange against cool ink-blue chrome.
ACCENT  = "#ff7a45"
FG      = "#e7edf5"
MUTED   = "#8c9aad"
DANGER  = "#ff6b7a"


def make_icon(svg_body: str, size: int = 20, color: str = FG) -> QIcon:
    """
    Wrap svg_body in a full SVG envelope, inject {color}, render to QIcon.
    svg_body should contain only the inner elements (paths, rects, etc.)
    """
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
        f'{svg_body.format(color=color)}'
        f'</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()
    return QIcon(pix)


def make_icon_pair(svg_body: str, size: int = 20) -> tuple[QIcon, QIcon]:
    """Returns (normal_icon, accent_icon) pair for checkable buttons."""
    return make_icon(svg_body, size, MUTED), make_icon(svg_body, size, ACCENT)


# ── SVG bodies (20×20 viewBox) ─────────────────────────────────────────────

# Top bar
ICON_OPEN = """
<path d="M3 13V5a1 1 0 0 1 1-1h4l1.5 1.5H16a1 1 0 0 1 1 1V13"
  stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
<path d="M1 10h18l-1.5 7H2.5L1 10z"
  fill="{color}" opacity="0.2" stroke="{color}" stroke-width="1.5" stroke-linejoin="round"/>
"""

ICON_EXPORT = """
<path d="M10 2v11" stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>
<path d="M6 6l4-4 4 4" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
<path d="M3 14v2a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2"
  stroke="{color}" stroke-width="1.5" stroke-linecap="round" fill="none"/>
"""

ICON_UNDO = """
<path d="M8.2 4.2L3.2 9.2L8.2 14.2"
  stroke="{color}" stroke-width="2.0" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
<path d="M3.8 9.2H13.2C16.0 9.2 17.8 11.0 17.8 13.6C17.8 16.2 16.0 18.0 13.2 18.0H11.2"
  stroke="{color}" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
"""

ICON_REDO = """
<path d="M11.8 4.2L16.8 9.2L11.8 14.2"
  stroke="{color}" stroke-width="2.0" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
<path d="M16.2 9.2H6.8C4.0 9.2 2.2 11.0 2.2 13.6C2.2 16.2 4.0 18.0 6.8 18.0H8.8"
  stroke="{color}" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
"""

ICON_RESET = """
<circle cx="10" cy="10" r="6.5"
  stroke="{color}" stroke-width="1.7" fill="none"/>
<path d="M7.2 7.2L12.8 12.8M12.8 7.2L7.2 12.8"
  stroke="{color}" stroke-width="1.85" stroke-linecap="round"/>
"""

ICON_ZOOM = """
<circle cx="9" cy="9" r="6" stroke="{color}" stroke-width="1.6" fill="none"/>
<path d="M18 18l-4-4" stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>
"""

ICON_SUN = """
<circle cx="10" cy="10" r="3.5" stroke="{color}" stroke-width="1.5" fill="none"/>
<path d="M10 1v2M10 17v2M1 10h2M17 10h2M3.5 3.5l1.5 1.5M15 15l1.5 1.5
         M3.5 16.5l1.5-1.5M15 5l1.5-1.5"
  stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
"""

ICON_GEAR = """
<circle cx="10" cy="10" r="2.5" stroke="{color}" stroke-width="1.4" fill="none"/>
<path d="M10 1.5A8.5 8.5 0 0 1 13 2.3l.5 1.5a6 6 0 0 1 2.7 2.7l1.5.5A8.5 8.5 0 0 1 18.5 10
         a8.5 8.5 0 0 1-.8 3l-1.5.5a6 6 0 0 1-2.7 2.7l-.5 1.5A8.5 8.5 0 0 1 10 18.5
         a8.5 8.5 0 0 1-3-.8l-.5-1.5a6 6 0 0 1-2.7-2.7l-1.5-.5A8.5 8.5 0 0 1 1.5 10
         a8.5 8.5 0 0 1 .8-3l1.5-.5a6 6 0 0 1 2.7-2.7l.5-1.5A8.5 8.5 0 0 1 10 1.5z"
  stroke="{color}" stroke-width="1.4" fill="none"/>
"""

ICON_KEYBOARD = """
<rect x="2.5" y="5" width="15" height="10" rx="2"
  stroke="{color}" stroke-width="1.6" fill="none"/>
<path d="M5.5 8h1M8.5 8h1M11.5 8h1M14.5 8h1
         M5.5 10.5h1M8.5 10.5h1M11.5 10.5h1M14.5 10.5h1"
  stroke="{color}" stroke-width="1.7" stroke-linecap="round"/>
<path d="M7 13h6" stroke="{color}" stroke-width="1.7" stroke-linecap="round"/>
"""

ICON_MORE = """
<circle cx="10" cy="4" r="1.5" fill="{color}"/>
<circle cx="10" cy="10" r="1.5" fill="{color}"/>
<circle cx="10" cy="16" r="1.5" fill="{color}"/>
"""

# Tool sidebar
ICON_SELECT = """
<path d="M4 2L4 16L8 12L10.5 18L13 17L10.5 11L16 11L4 2Z"
  fill="{color}" stroke="{color}" stroke-width="0.5" stroke-linejoin="round"/>
"""

ICON_MOVE = """
<path d="M10 2v16M2 10h16" stroke="{color}" stroke-width="1.6" stroke-linecap="round"/>
<path d="M10 2L8 5M10 2L12 5" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
<path d="M10 18L8 15M10 18L12 15" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
<path d="M2 10L5 8M2 10L5 12" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
<path d="M18 10L15 8M18 10L15 12" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
"""

ICON_BUBBLE = """
<ellipse cx="10" cy="8" rx="8" ry="5.5" fill="{color}" opacity="0.15" stroke="{color}" stroke-width="1.5"/>
<path d="M7 13L5 17.5L9.5 14" fill="{color}" stroke="{color}" stroke-width="1.5" stroke-linejoin="round"/>
"""

ICON_CAPTION = """
<rect x="1.5" y="5" width="17" height="10" rx="3" fill="{color}" opacity="0.12" stroke="{color}" stroke-width="1.5"/>
<line x1="5" y1="8.5" x2="15" y2="8.5" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
<line x1="5" y1="11.5" x2="12" y2="11.5" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
"""

ICON_TEXT = """
<path d="M3 4.5H17M10 4.5V16" stroke="{color}" stroke-width="2" stroke-linecap="round"/>
<line x1="7" y1="16" x2="13" y2="16" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
"""

ICON_LAYERS = """
<path d="M2 14l8 4 8-4M2 10l8 4 8-4M2 6l8-4 8 4-8 4-8-4z"
  stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
"""

ICON_MEME = """
<rect x="2" y="2" width="16" height="16" rx="1.5" fill="{color}" opacity="0.1" stroke="{color}" stroke-width="1.5"/>
<line x1="5" y1="5.5" x2="15" y2="5.5" stroke="{color}" stroke-width="2.2" stroke-linecap="round"/>
<line x1="6.5" y1="8" x2="13.5" y2="8" stroke="{color}" stroke-width="1.4" stroke-linecap="round" opacity="0.6"/>
<line x1="5" y1="14.5" x2="15" y2="14.5" stroke="{color}" stroke-width="2.2" stroke-linecap="round"/>
<line x1="6.5" y1="12" x2="13.5" y2="12" stroke="{color}" stroke-width="1.4" stroke-linecap="round" opacity="0.6"/>
"""

ICON_DUAL = """
<rect x="1.5" y="3.5" width="7" height="13" rx="1" fill="{color}" opacity="0.12" stroke="{color}" stroke-width="1.5"/>
<rect x="11.5" y="3.5" width="7" height="13" rx="1" fill="{color}" opacity="0.12" stroke="{color}" stroke-width="1.5"/>
"""

ICON_MANGA = """
<rect x="2" y="1.5" width="16" height="17" rx="1.3"
  fill="{color}" opacity="0.10" stroke="{color}" stroke-width="1.5"/>
<path d="M2.5 7.2h15M2.5 13.2h15M8.2 1.8v5.1M11.8 7.5v5.4M7 13.5v4.7"
  stroke="{color}" stroke-width="1.35" stroke-linecap="square"/>
"""

ICON_COLLAGE = """
<rect x="2" y="2" width="7" height="7" rx="1"
  fill="{color}" opacity="0.16" stroke="{color}" stroke-width="1.4"/>
<rect x="11" y="2" width="7" height="11" rx="1"
  fill="{color}" opacity="0.10" stroke="{color}" stroke-width="1.4"/>
<rect x="2" y="11" width="7" height="7" rx="1"
  fill="{color}" opacity="0.10" stroke="{color}" stroke-width="1.4"/>
<rect x="11" y="15" width="7" height="3" rx="1"
  fill="{color}" opacity="0.18" stroke="{color}" stroke-width="1.4"/>
"""

ICON_BLUR = """
<rect x="3" y="3" width="14" height="14" rx="3.5" fill="{color}" opacity="0.12" stroke="{color}" stroke-width="1.5"/>
<circle cx="7.6" cy="7.6" r="1.4" fill="{color}" opacity="0.95"/>
<circle cx="12.4" cy="7.6" r="1.4" fill="{color}" opacity="0.55"/>
<circle cx="7.6" cy="12.4" r="1.4" fill="{color}" opacity="0.55"/>
<circle cx="12.4" cy="12.4" r="1.4" fill="{color}" opacity="0.3"/>
"""

ICON_PIXELATE = """
<rect x="3" y="3" width="14" height="14" rx="2" fill="none" stroke="{color}" stroke-width="1.5"/>
<rect x="5" y="5" width="3.3" height="3.3" fill="{color}" opacity="0.9"/>
<rect x="11.7" y="5" width="3.3" height="3.3" fill="{color}" opacity="0.5"/>
<rect x="5" y="11.7" width="3.3" height="3.3" fill="{color}" opacity="0.5"/>
<rect x="11.7" y="11.7" width="3.3" height="3.3" fill="{color}" opacity="0.9"/>
"""

ICON_CROP = """
<path d="M5.5 1.5v11a2 2 0 0 0 2 2h11"
  stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
<path d="M1.5 5.5h11a2 2 0 0 1 2 2v11"
  stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
"""

ICON_ROTATE = """
<path d="M3.2 10a6.8 6.8 0 1 1 2.0 4.8"
  stroke="{color}" stroke-width="1.8" stroke-linecap="round" fill="none"/>
<path d="M3.2 5.2v4.6h4.6"
  stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
"""

ICON_SPEEDLINES = """
<line x1="2" y1="2" x2="7.4" y2="7.4" stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>
<line x1="18" y1="2" x2="12.6" y2="7.4" stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>
<line x1="2" y1="18" x2="7.4" y2="12.6" stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>
<line x1="18" y1="18" x2="12.6" y2="12.6" stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>
<line x1="10" y1="1" x2="10" y2="5.6" stroke="{color}" stroke-width="1.5" stroke-linecap="round" opacity="0.7"/>
<line x1="10" y1="19" x2="10" y2="14.4" stroke="{color}" stroke-width="1.5" stroke-linecap="round" opacity="0.7"/>
<line x1="1" y1="10" x2="5.6" y2="10" stroke="{color}" stroke-width="1.5" stroke-linecap="round" opacity="0.7"/>
<line x1="19" y1="10" x2="14.4" y2="10" stroke="{color}" stroke-width="1.5" stroke-linecap="round" opacity="0.7"/>
"""

# Context toolbar
ICON_ALIGN_LEFT = """
<rect x="3" y="3" width="2" height="14" rx="1" fill="{color}"/>
<rect x="7" y="5" width="9" height="2.5" rx="1.2" fill="{color}"/>
<rect x="7" y="9" width="6" height="2.5" rx="1.2" fill="{color}"/>
<rect x="7" y="13" width="9" height="2.5" rx="1.2" fill="{color}"/>
"""

ICON_ALIGN_HCENTER = """
<rect x="9" y="3" width="2" height="14" rx="1" fill="{color}" opacity="0.75"/>
<rect x="5" y="5" width="10" height="2.5" rx="1.2" fill="{color}"/>
<rect x="7" y="9" width="6" height="2.5" rx="1.2" fill="{color}"/>
<rect x="5" y="13" width="10" height="2.5" rx="1.2" fill="{color}"/>
"""

ICON_ALIGN_RIGHT = """
<rect x="15" y="3" width="2" height="14" rx="1" fill="{color}"/>
<rect x="4" y="5" width="9" height="2.5" rx="1.2" fill="{color}"/>
<rect x="7" y="9" width="6" height="2.5" rx="1.2" fill="{color}"/>
<rect x="4" y="13" width="9" height="2.5" rx="1.2" fill="{color}"/>
"""

ICON_ALIGN_TOP = """
<rect x="3" y="3" width="14" height="2" rx="1" fill="{color}"/>
<rect x="5" y="7" width="2.5" height="9" rx="1.2" fill="{color}"/>
<rect x="9" y="7" width="2.5" height="6" rx="1.2" fill="{color}"/>
<rect x="13" y="7" width="2.5" height="9" rx="1.2" fill="{color}"/>
"""

ICON_ALIGN_VCENTER = """
<rect x="3" y="9" width="14" height="2" rx="1" fill="{color}" opacity="0.75"/>
<rect x="5" y="5" width="2.5" height="10" rx="1.2" fill="{color}"/>
<rect x="9" y="7" width="2.5" height="6" rx="1.2" fill="{color}"/>
<rect x="13" y="5" width="2.5" height="10" rx="1.2" fill="{color}"/>
"""

ICON_ALIGN_BOTTOM = """
<rect x="3" y="15" width="14" height="2" rx="1" fill="{color}"/>
<rect x="5" y="4" width="2.5" height="9" rx="1.2" fill="{color}"/>
<rect x="9" y="7" width="2.5" height="6" rx="1.2" fill="{color}"/>
<rect x="13" y="4" width="2.5" height="9" rx="1.2" fill="{color}"/>
"""

ICON_TO_FRONT = """
<rect x="4" y="8" width="7" height="7" rx="1.4" stroke="{color}" stroke-width="1.7" fill="none" opacity="0.5"/>
<rect x="9" y="4" width="7" height="7" rx="1.4" fill="{color}"/>
<path d="M15 3.2l2.4 2.4l-2.4 2.4" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
"""

ICON_BRING_FWD = """
<rect x="4" y="8" width="7" height="7" rx="1.4" stroke="{color}" stroke-width="1.7" fill="none" opacity="0.5"/>
<rect x="9" y="4" width="7" height="7" rx="1.4" fill="{color}"/>
"""

ICON_SEND_BACK = """
<rect x="9" y="4" width="7" height="7" rx="1.4" stroke="{color}" stroke-width="1.7" fill="none" opacity="0.5"/>
<rect x="4" y="8" width="7" height="7" rx="1.4" fill="{color}"/>
"""

ICON_TO_BACK = """
<rect x="9" y="4" width="7" height="7" rx="1.4" stroke="{color}" stroke-width="1.7" fill="none" opacity="0.5"/>
<rect x="4" y="8" width="7" height="7" rx="1.4" fill="{color}"/>
<path d="M5 16.8l-2.4-2.4l2.4-2.4" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
"""

ICON_FLIP_H = """
<rect x="9.2" y="3" width="1.6" height="14" rx="0.8" fill="{color}" opacity="0.65"/>
<path d="M7.5 5.5L3.5 10l4 4.5zM12.5 5.5l4 4.5l-4 4.5z" fill="{color}"/>
"""

ICON_FLIP_V = """
<rect x="3" y="9.2" width="14" height="1.6" rx="0.8" fill="{color}" opacity="0.65"/>
<path d="M5.5 7.5L10 3.5l4.5 4zM5.5 12.5l4.5 4l4.5-4z" fill="{color}"/>
"""

ICON_DELETE = """
<path d="M4 6h12M8 6V4h4v2" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
<path d="M6.2 7.8h7.6l-.7 8.2H6.9z" fill="{color}"/>
<path d="M9 9.5v4.5M11 9.5v4.5" stroke="#111827" stroke-width="1.3" stroke-linecap="round" opacity="0.75"/>
"""

# Video transport
ICON_TO_START = """
<rect x="1" y="2" width="2" height="12" rx="1" fill="{color}"/>
<path d="M14 2.5L5 8l9 5.5V2.5z" fill="{color}"/>
"""

ICON_STEP_BACK = """
<path d="M11 2.5L2 8l9 5.5V2.5z" fill="{color}"/>
<path d="M13 4l-4 4 4 4" stroke="{color}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none" opacity="0.5"/>
"""

ICON_PLAY = """
<path d="M3 2.5l14 7.5-14 7.5V2.5z" fill="{color}"/>
"""

ICON_PAUSE = """
<rect x="3" y="2" width="4" height="12" rx="1" fill="{color}"/>
<rect x="10" y="2" width="4" height="12" rx="1" fill="{color}"/>
"""

ICON_STEP_FWD = """
<path d="M5 2.5L14 8 5 13.5V2.5z" fill="{color}"/>
<path d="M7 4l4 4-4 4" stroke="{color}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none" opacity="0.5"/>
"""

ICON_TO_END = """
<rect x="13" y="2" width="2" height="12" rx="1" fill="{color}"/>
<path d="M2 2.5L11 8 2 13.5V2.5z" fill="{color}"/>
"""

ICON_VOLUME = """
<path d="M3 6H1v4h2l4 3V3L3 6z" fill="{color}"/>
<path d="M10 5c1 1 1.5 2.2 1.5 3.5S11 11 10 12" stroke="{color}" stroke-width="1.4" stroke-linecap="round" fill="none"/>
<path d="M12.5 3c1.7 1.5 2.5 3.4 2.5 5.5s-.8 4-2.5 5.5" stroke="{color}" stroke-width="1.4" stroke-linecap="round" fill="none"/>
"""

ICON_FULLSCREEN = """
<path d="M1 5V1h4M11 1h4v4M15 11v4h-4M5 15H1v-4"
  stroke="{color}" stroke-width="1.5" stroke-linecap="round" fill="none"/>
"""

ICON_SET_IN = """
<rect x="0" y="2" width="2" height="12" rx="1" fill="{color}"/>
<path d="M3 8h9" stroke="{color}" stroke-width="1.4" stroke-linecap="round"/>
<path d="M9 5l3 3-3 3" stroke="{color}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
"""

ICON_SET_OUT = """
<rect x="14" y="2" width="2" height="12" rx="1" fill="{color}"/>
<path d="M13 8H4" stroke="{color}" stroke-width="1.4" stroke-linecap="round"/>
<path d="M7 5L4 8l3 3" stroke="{color}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
"""

ICON_CUT = """
<circle cx="4" cy="4" r="2" stroke="{color}" stroke-width="1.4" fill="none"/>
<circle cx="4" cy="12" r="2" stroke="{color}" stroke-width="1.4" fill="none"/>
<path d="M6 5.5L14 9M6 10.5L14 7" stroke="{color}" stroke-width="1.4" stroke-linecap="round"/>
"""

ICON_MARKER = """
<path d="M8 1l1.8 5.5H16l-5 3.6 1.9 5.9L8 12.5l-4.9 3.5 1.9-5.9-5-3.6h6.2z"
  fill="{color}" opacity="0.9"/>
"""

ICON_REVERSE = """
<path d="M1 8h12" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
<path d="M4 4L1 8l3 4" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
<path d="M10 4l4 4-4 4" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none" opacity="0.5"/>
"""

# Text alignment
ICON_TEXT_LEFT = """
<line x1="1" y1="4" x2="15" y2="4" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
<line x1="1" y1="7.5" x2="10" y2="7.5" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
<line x1="1" y1="11" x2="13" y2="11" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
"""

ICON_TEXT_CENTER = """
<line x1="1" y1="4" x2="15" y2="4" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
<line x1="3.5" y1="7.5" x2="12.5" y2="7.5" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
<line x1="1.5" y1="11" x2="14.5" y2="11" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
"""

ICON_TEXT_RIGHT = """
<line x1="1" y1="4" x2="15" y2="4" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
<line x1="6" y1="7.5" x2="15" y2="7.5" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
<line x1="3" y1="11" x2="15" y2="11" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
"""

ICON_TEXT_JUSTIFY = """
<line x1="1" y1="4" x2="15" y2="4" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
<line x1="1" y1="7.5" x2="15" y2="7.5" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
<line x1="1" y1="11" x2="15" y2="11" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
"""
