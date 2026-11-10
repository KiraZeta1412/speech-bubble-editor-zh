"""colorpicker.py —— 取色对话框，并记住「自定义颜色」。

问题：Qt 在 Windows 上默认用系统原生颜色对话框，原生对话框底部的
「自定义颜色」色块由系统管理，Qt 既读不到也写不进 —— 所以用户加进去的颜色
换次启动就没了。

做法：
1. 改成 Qt 自绘对话框（DontUseNativeDialog），这样能读写那 16 个自定义色块
2. 把这些色块存进 QSettings（`ui/custom_colors`，颜色用 #AARRGGBB 保留 alpha）
3. 软件自己的调色板弹窗也读同一份数据，显示成「最近使用」一行

两个地方共用一份记录，用户在哪里选的自定义色都能再找回来。
"""

from __future__ import annotations

from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QColorDialog

import ui_state

GROUP = "ui/custom_colors"
SLOTS = 16          # 保留位数（和原生对话框的色块数量对齐）
RECENT_MAX = 12     # 调色板弹窗里「最近使用」最多显示几个


def _settings() -> QSettings:
    return QSettings(ui_state.ORG, ui_state.APP)


def load_custom_colors() -> list[QColor]:
    """按对话框色块顺序读回自定义颜色（跳过空槽）。"""
    if ui_state._disabled():
        return []
    settings = _settings()
    settings.beginGroup(GROUP)
    out: list[QColor] = []
    try:
        for index in range(SLOTS):
            key = f"slot{index}"
            if not settings.contains(key):
                continue
            color = QColor(str(settings.value(key)))
            if color.isValid():
                out.append(color)
    finally:
        settings.endGroup()
    return out


def save_custom_colors(colors: list[QColor]) -> None:
    if ui_state._disabled():
        return
    settings = _settings()
    settings.beginGroup(GROUP)
    try:
        settings.remove("")
        for index, color in enumerate(colors[:SLOTS]):
            if color.isValid():
                settings.setValue(f"slot{index}",
                                  color.name(QColor.NameFormat.HexArgb))
    finally:
        settings.endGroup()
    settings.sync()


def push_recent(color: QColor) -> None:
    """把刚用过的颜色挪到最前面（去重），并保存。"""
    if not color.isValid():
        return
    key = color.name(QColor.NameFormat.HexArgb)
    colors = [c for c in load_custom_colors()
              if c.name(QColor.NameFormat.HexArgb) != key]
    colors.insert(0, QColor(color))
    save_custom_colors(colors[:SLOTS])


def pick_color_dialog(initial: QColor, parent=None, title: str = "选取颜色",
                      allow_alpha: bool = True) -> QColor | None:
    """用系统原生取色对话框（界面语言跟随系统，中文系统就是中文）。

    原生对话框底部的「自定义颜色」色块由系统管理，Qt 读写不到，所以那里
    存的东西不归我们管 —— 但用户选过的颜色都会被 push_recent 记下来，
    下次在软件的调色板弹窗「最近使用」里直接能点。
    """
    options = (QColorDialog.ColorDialogOption.ShowAlphaChannel
               if allow_alpha else QColorDialog.ColorDialogOption(0))
    color = QColorDialog.getColor(QColor(initial) if initial else QColor("#ffffff"),
                                  parent, title, options)
    if color is not None and color.isValid():
        push_recent(color)
        return color
    return None
