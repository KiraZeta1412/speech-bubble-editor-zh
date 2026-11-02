"""
about_dialog.py — About dialog for Speech Bubble Editor.
"""

import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt

from version import __version__, __app_name__, __org_name__, __copyright__


def _resource_path(relative: str) -> str:
    import sys
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)


class AboutDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"关于 {__app_name__}")
        self.setFixedWidth(440)
        self.setModal(True)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(12)

        # ── Logo ─────────────────────────────────────────────────────────
        logo_path = _resource_path(os.path.join("icons", "LongWeekendLabs.logo.jpg"))
        if os.path.exists(logo_path):
            logo_pm = QPixmap(logo_path).scaledToWidth(
                200, Qt.TransformationMode.SmoothTransformation)
            logo_label = QLabel()
            logo_label.setPixmap(logo_pm)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            layout.addWidget(logo_label)

        # ── App name ─────────────────────────────────────────────────────
        name_label = QLabel(__app_name__)
        f = QFont()
        f.setPointSize(18)
        f.setBold(True)
        name_label.setFont(f)
        name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(name_label)

        # ── Version ──────────────────────────────────────────────────────
        ver_label = QLabel(f"版本 {__version__}")
        f2 = QFont()
        f2.setPointSize(11)
        ver_label.setFont(f2)
        ver_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        ver_label.setStyleSheet("color: #888;")
        layout.addWidget(ver_label)

        # ── Org / copyright ──────────────────────────────────────────────
        org_label = QLabel(f"{__org_name__}\n{__copyright__}")
        org_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        org_label.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(org_label)

        # ── Divider ──────────────────────────────────────────────────────
        from PyQt6.QtWidgets import QFrame
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # ── Project links ────────────────────────────────────────────────
        links_label = QLabel(
            '<a href="https://longweekendlabs.github.io/speech-bubble-editor/">'
            'longweekendlabs.github.io/speech-bubble-editor</a><br>'
            '<a href="https://github.com/longweekendlabs/speech-bubble-editor">'
            'github.com/longweekendlabs/speech-bubble-editor</a>'
        )
        links_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        links_label.setOpenExternalLinks(True)
        links_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(links_label)

        # ── License ──────────────────────────────────────────────────────
        license_text = (
            "官方发行版：Windows x64 与 Linux x64。\n\n"
            "技术构成：Python · PyQt6 · OpenCV · FFmpeg · Pillow\n"
            f"{__copyright__}"
        )
        lic_label = QLabel(license_text)
        lic_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lic_label.setStyleSheet("color: #999; font-size: 10px;")
        lic_label.setWordWrap(True)
        layout.addWidget(lic_label)

        # ── Close button ─────────────────────────────────────────────────
        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(close_btn)
        h.addStretch()
        layout.addLayout(h)
