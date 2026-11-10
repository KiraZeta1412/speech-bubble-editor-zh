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

import os
import sys

from PyQt6.QtCore import QSettings, QLibraryInfo, QTranslator
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QColorDialog

import i18n
import ui_state

GROUP = "ui/custom_colors"
SLOTS = 16          # QColorDialog 的自定义色块数量
RECENT_MAX = 12     # 调色板弹窗里「最近使用」最多显示几个

_qt_translator: QTranslator | None = None


def _translations_dir() -> str:
    """打包后翻译在 _MEIPASS/translations，开发时用 PyQt6 自带目录。"""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        local = os.path.join(bundle, "translations")
        if os.path.isdir(local):
            return local
    return QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)


def _ensure_qt_translation() -> None:
    """让 Qt 自绘的对话框跟着界面语言走。

    Qt 内置对话框里那些按钮和分组标题（Basic colors / OK / Cancel…）
    不在软件的汉化表里，而是来自 Qt 自己的翻译文件。改非原生的起因是要
    读写自定义色块 —— 但原生对话框是跟着系统语言走的，换成 Qt 自绘之后
    不加载中文翻译就会变成英文界面。
    """
    global _qt_translator
    if _qt_translator is not None:
        return
    if i18n.language() != "zh":
        _qt_translator = QTranslator()      # 占位，避免反复尝试
        return
    translator = QTranslator()
    path = _translations_dir()
    if translator.load("qtbase_zh_CN", path):
        app = QApplication.instance()
        if app is not None:
            app.installTranslator(translator)
            _qt_translator = translator
            return
    _qt_translator = translator


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
    """和 QColorDialog.getColor 用法一样，但会记住自定义颜色。"""
    _ensure_qt_translation()
    dialog = QColorDialog(QColor(initial) if initial else QColor("#ffffff"),
                          parent)
    dialog.setWindowTitle(title)
    # 必须用 Qt 自绘对话框：原生对话框的自定义色块 Qt 访问不到
    dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
    dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel,
                     bool(allow_alpha))
    for index, color in enumerate(load_custom_colors()[:SLOTS]):
        dialog.setCustomColor(index, color)

    accepted = dialog.exec() == QColorDialog.DialogCode.Accepted
    if not accepted:
        return None

    # 对话框把用户新加的色块也放在同样的槽位里，读回来存下
    captured: list[QColor] = []
    for index in range(SLOTS):
        color = dialog.customColor(index)
        if color.isValid():
            captured.append(color)
    chosen = dialog.currentColor()
    if chosen.isValid():
        key = chosen.name(QColor.NameFormat.HexArgb)
        captured = [c for c in captured
                    if c.name(QColor.NameFormat.HexArgb) != key]
        captured.insert(0, QColor(chosen))
    save_custom_colors(captured[:SLOTS])
    return chosen if chosen.isValid() else None
