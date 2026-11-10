"""colorpicker.py —— 取色对话框，记住「自定义颜色」。

对话框用 Qt 自绘版本（DontUseNativeDialog），原因有两个：
1. 它带十六进制输入框（HTML 那一栏），Windows 原生对话框没有
2. 只有自绘版本才开放 setCustomColor / customColor，能把自定义色块存下来
   —— 原生对话框那 16 个色块由系统管，Qt 读写不到

自定义颜色存进 QSettings（`ui/custom_colors`，颜色用 #AARRGGBB 保留 alpha），
下次打开对话框自动填回；软件自己的调色板弹窗也读同一份数据，显示成
「最近使用」一行，两处共用一套记录。

注意：Qt 自绘对话框里的按钮和分组标题（基本颜色 / 确定 / 取消…）不在软件的
汉化表里，来自 Qt 自己的翻译文件，所以要加载 qtbase_zh_CN。
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


def _settings() -> QSettings:
    return QSettings(ui_state.ORG, ui_state.APP)


# ---------------------------------------------------------------------------
# Qt 自带翻译（对话框里的按钮和标题）
# ---------------------------------------------------------------------------

def _translations_dir() -> str:
    """打包后翻译在 _MEIPASS/translations，开发时用 PyQt6 自带目录。"""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        local = os.path.join(bundle, "translations")
        if os.path.isdir(local):
            return local
    return QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)


def _ensure_qt_translation() -> None:
    """按当前界面语言加载 Qt 中文翻译；英文界面不加载。"""
    global _qt_translator
    if _qt_translator is not None:
        return
    translator = QTranslator()
    if i18n.language() == "zh" and translator.load("qtbase_zh_CN",
                                                   _translations_dir()):
        app = QApplication.instance()
        if app is not None:
            app.installTranslator(translator)
    _qt_translator = translator


# ---------------------------------------------------------------------------
# 自定义颜色读写
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 取色
# ---------------------------------------------------------------------------

def pick_color_dialog(initial: QColor, parent=None, title: str = "选取颜色",
                      allow_alpha: bool = True) -> QColor | None:
    """打开取色对话框，并记住自定义颜色。

    用自绘版本：有十六进制输入框，且能读写自定义色块。
    """
    _ensure_qt_translation()

    dialog = QColorDialog(QColor(initial) if initial else QColor("#ffffff"),
                          parent)
    dialog.setWindowTitle(title)
    dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
    dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel,
                     bool(allow_alpha))
    for index, color in enumerate(load_custom_colors()[:SLOTS]):
        dialog.setCustomColor(index, color)

    if dialog.exec() != QColorDialog.DialogCode.Accepted:
        return None

    # 对话框会把用户新加的色块放进同样的槽位，读回来存下
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
