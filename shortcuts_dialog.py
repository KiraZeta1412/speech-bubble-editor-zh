"""
shortcuts_dialog.py — Keyboard shortcuts reference dialog.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QWidget,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt


SHORTCUT_GROUPS = [
    (
        "项目",
        [
            ("打开媒体", "Ctrl+O"),
            ("导出", "Ctrl+E"),
            ("重置项目", "Ctrl+N"),
            ("显示键盘快捷键", "Ctrl+/"),
        ],
    ),
    (
        "编辑",
        [
            ("撤销", "Ctrl+Z"),
            ("重做", "Ctrl+Y 或 Ctrl+Shift+Z"),
            ("添加对话气泡", "Ctrl+B"),
            ("添加文字", "T"),
            ("添加图片或视频图层", "Ctrl+L"),
            ("删除选中项", "删除"),
        ],
    ),
    (
        "工具",
        [
            ("选择工具", "V"),
            ("移动工具", "M"),
        ],
    ),
    (
        "视频",
        [
            ("播放或暂停", "空格键"),
            ("后退一帧", "左方向键"),
            ("前进一帧", "右方向键"),
            ("跳到第一帧", "Home"),
            ("跳到最后一帧", "End"),
            ("设置入点", "["),
            ("设置出点", "]"),
            ("切换全屏窗口", "F"),
        ],
    ),
]


class ShortcutsDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("键盘快捷键")
        self.setFixedWidth(640)
        self.setModal(True)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        title = QLabel("键盘快捷键")
        font = QFont()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)

        subtitle = QLabel("编辑时可用的快捷操作。")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        subtitle.setStyleSheet("color: #9a9a9a; font-size: 11px;")
        layout.addWidget(subtitle)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

        groups = QGridLayout()
        groups.setContentsMargins(0, 0, 0, 0)
        groups.setHorizontalSpacing(24)
        groups.setVerticalSpacing(14)
        for index, (group_name, rows) in enumerate(SHORTCUT_GROUPS):
            groups.addWidget(
                self._group_widget(group_name, rows),
                index // 2,
                index % 2,
            )
        layout.addLayout(groups)

        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(100)
        close_btn.setToolTip("关闭键盘快捷键")
        close_btn.clicked.connect(self.accept)

        h = QHBoxLayout()
        h.addStretch()
        h.addWidget(close_btn)
        h.addStretch()
        layout.addLayout(h)

    def _group_widget(self, group_name: str, rows: list[tuple[str, str]]) -> QWidget:
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(7)

        group_label = QLabel(group_name.upper())
        group_label.setObjectName("ShortcutsGroupLabel")
        group_label.setStyleSheet(
            "color: #9fb0cf; font-size: 10px; font-weight: 700; "
            "letter-spacing: 1px;"
        )
        panel_layout.addWidget(group_label)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(7)

        for row, (action, keys) in enumerate(rows):
            action_label = QLabel(action)
            action_label.setStyleSheet("color: #d8deea;")
            key_label = QLabel(keys)
            key_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            key_label.setStyleSheet(
                "color: #ff8a3d; font-weight: 700; "
                "font-family: monospace;"
            )
            grid.addWidget(action_label, row, 0)
            grid.addWidget(key_label, row, 1)

        grid.setColumnStretch(0, 1)
        panel_layout.addLayout(grid)
        panel_layout.addStretch()
        return panel
