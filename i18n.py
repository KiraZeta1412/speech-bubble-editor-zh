# -*- coding: utf-8 -*-
"""i18n.py —— 运行时中英切换。

本项目的界面文案直接写在源码里（中文）。要支持运行时切换，这里做两件事：

1. `tr(text)`：给需要显式取词的调用点用，返回当前语言下的文案。
2. `apply_language(root)`：遍历已有控件树，把已显示的文本换到目标语言。
3. `install(app)`：装一个事件过滤器，凡是新创建/首次显示的控件也自动翻一遍。
   否则切换语言后，后续重建的属性面板会退回源码里的中文。

词典在 translations_data.py。查不到的文本一律原样保留
（字体族名、用户输入内容、动态拼接串都靠这个规则天然不受影响）。
"""

from __future__ import annotations

import re

from PyQt6.QtCore import QEvent, QObject, QSettings
from PyQt6.QtWidgets import (
    QAbstractButton, QComboBox, QLabel, QLineEdit, QListWidget, QPlainTextEdit,
    QStatusBar, QTabBar, QTextEdit, QWidget,
)

from translations_data import EN_TO_ZH, ZH_TO_EN

# 动态文案靠规则处理（词典里无法穷举带数字/变量的串）。
# 每条是 (正则, 处理函数)，函数收到 match 返回译文。
def _rule_title_en(m):
    return "Speech Bubble Editor · " + m.group(2)


def _rule_title_zh(m):
    return "漫画气泡编辑器 · " + m.group(1)


def _rule_photos_en(m):
    return f"{m.group(1)} photos"


def _rule_photos_zh(m):
    return f"{m.group(1)} 张照片"


def _rule_startup_en(m):
    name = m.group(1)
    return "Startup preset: " + ZH_TO_EN.get(name, name)


def _rule_startup_zh(m):
    name = m.group(1)
    return "启动预设：" + EN_TO_ZH.get(name, name)


_RULES_EN = [   # 中文 -> 英文
    (re.compile(r"^(漫画气泡编辑器|对话气泡编辑器) · (.+)$"), _rule_title_en),
    (re.compile(r"^(\d+) 张照片$"), _rule_photos_en),
    (re.compile(r"^启动预设：\s*(.*)$"), _rule_startup_en),
]
_RULES_ZH = [   # 英文 -> 中文
    (re.compile(r"^Speech Bubble Editor · (.+)$"), _rule_title_zh),
    (re.compile(r"^(\d+) photos$"), _rule_photos_zh),
    (re.compile(r"^Startup preset:\s*(.*)$"), _rule_startup_zh),
]

# 「4 张照片  ·  马赛克  ·  竖版 · 4:5」这类分段拼接串：按双空格分隔符拆开逐段翻
_SEGMENT_SEP = "  ·  "

_ORG = "LongWeekendLabs"
_APP = "SpeechBubbleEditor"
_KEY = "ui/language"

# 不参与翻译的控件（objectName 黑名单）
_SKIP_OBJECTS = {"LangToggle"}

_lang = "zh"          # 当前语言：zh / en
_app = None


def _settings() -> QSettings:
    return QSettings(_ORG, _APP)


def language() -> str:
    return _lang


def set_language(lang: str) -> None:
    global _lang
    _lang = "en" if str(lang).lower().startswith("en") else "zh"
    _settings().setValue(_KEY, _lang)


def load_language() -> str:
    """启动时读取上次选择（默认中文）。"""
    global _lang
    value = _settings().value(_KEY, "zh", type=str)
    _lang = "en" if str(value).lower().startswith("en") else "zh"
    return _lang


def tr(text: str) -> str:
    """按当前语言取词。

    走 _swap 而不是直接查词典 —— 这样 tr() 也能享受多行拼接、正则规则、
    分段拼接串那几层处理（例如自绘的多行占位文字）。
    """
    return _swap(text)


def _swap(text: str) -> str:
    """把一段当前文本换到目标语言；查不到就原样返回。"""
    if not text:
        return text
    table = ZH_TO_EN if _lang == "en" else EN_TO_ZH
    hit = table.get(text)
    if hit is not None:
        return hit
    # 多行文案：词典里存的是分行片段（界面用 \n 拼起来），整串查不到时逐行翻
    if "\n" in text:
        changed = False
        out = []
        for line in text.split("\n"):
            new = table.get(line)
            if new is not None and new != line:
                out.append(new)
                changed = True
            else:
                out.append(line)
        if changed:
            return "\n".join(out)
    # 带数字/变量的动态文案交给规则
    for pattern, handler in (_RULES_EN if _lang == "en" else _RULES_ZH):
        if pattern.match(text):
            return handler(pattern.match(text))
    # 分段拼接串（"4 张照片  ·  马赛克  ·  竖版 · 4:5"）：拆开逐段翻再拼回去
    if _SEGMENT_SEP in text:
        parts = text.split(_SEGMENT_SEP)
        swapped = [_swap(p) for p in parts]
        if swapped != parts:
            return _SEGMENT_SEP.join(swapped)
    return text


def _translate_widget(widget: QWidget, shallow: bool = False) -> None:
    """翻译单个控件自身的文本（不含子控件）。"""
    if widget is None or widget.objectName() in _SKIP_OBJECTS:
        return

    # 窗口标题（只对顶层窗口有意义，但设了也无妨）
    title = widget.windowTitle()
    if title:
        new = _swap(title)
        if new != title:
            widget.setWindowTitle(new)

    tip = widget.toolTip()
    if tip:
        new = _swap(tip)
        if new != tip:
            widget.setToolTip(new)

    status_tip = widget.statusTip()
    if status_tip:
        new = _swap(status_tip)
        if new != status_tip:
            widget.setStatusTip(new)

    if isinstance(widget, QStatusBar):
        # 状态栏的"就绪"这类常驻消息不是控件 text()，单独处理
        msg = widget.currentMessage()
        if msg:
            new = _swap(msg)
            if new != msg:
                widget.showMessage(new)
    elif isinstance(widget, QLineEdit):
        # 只动占位符，绝不动用户输入内容
        ph = widget.placeholderText()
        if ph:
            new = _swap(ph)
            if new != ph:
                widget.setPlaceholderText(new)
    elif isinstance(widget, (QTextEdit, QPlainTextEdit)):
        ph = widget.placeholderText()
        if ph:
            new = _swap(ph)
            if new != ph:
                widget.setPlaceholderText(new)
    elif isinstance(widget, (QLabel, QAbstractButton)):
        text = widget.text()
        if text:
            new = _swap(text)
            if new != text:
                widget.setText(new)

    if isinstance(widget, QTabBar):
        for i in range(widget.count()):
            text = widget.tabText(i)
            new = _swap(text)
            if new != text:
                widget.setTabText(i, new)
    elif isinstance(widget, QComboBox):
        for i in range(widget.count()):
            text = widget.itemText(i)
            new = _swap(text)
            if new != text:
                widget.setItemText(i, new)
    elif isinstance(widget, QListWidget):
        for i in range(widget.count()):
            item = widget.item(i)
            if item is not None:
                new = _swap(item.text())
                if new != item.text():
                    item.setText(new)

    # 挂在这个控件上的 QAction（工具栏、菜单）
    for action in widget.actions():
        if action is None:
            continue
        text = action.text()
        if text:
            new = _swap(text)
            if new != text:
                action.setText(new)
        tip = action.toolTip()
        if tip:
            new = _swap(tip)
            if new != tip:
                action.setToolTip(new)
        status_tip = action.statusTip()
        if status_tip:
            new = _swap(status_tip)
            if new != status_tip:
                action.setStatusTip(new)

    if not shallow:
        for child in widget.findChildren(QWidget):
            _translate_widget(child, shallow=True)


def apply_language(root: QWidget | None) -> None:
    """把整棵控件树切到当前语言（对已经显示的界面立即可见）。"""
    if root is None:
        return
    _translate_widget(root)


class _AutoTranslate(QObject):
    """新控件首次显示时也翻一下，避免重建出来的面板退回中文。"""

    def eventFilter(self, obj, event):  # noqa: N802 (Qt 命名)
        if _lang != "en":
            return False
        etype = event.type()
        if etype in (QEvent.Type.Polish, QEvent.Type.Show) and isinstance(obj, QWidget):
            try:
                _translate_widget(obj, shallow=True)
            except Exception:
                pass
        return False


_filter = None


def install(app) -> None:
    """装上自动翻译过滤器（只需调用一次）。"""
    global _app, _filter
    _app = app
    if _filter is None:
        _filter = _AutoTranslate()
        app.installEventFilter(_filter)
