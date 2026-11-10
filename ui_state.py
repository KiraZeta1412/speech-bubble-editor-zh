"""ui_state.py —— 记住界面上的样式参数，重开软件后还在。

之前这些参数是硬编码在 canvas 里的（`_manga_style` / `_collage_style` /
`_collage_layout_settings`），每次启动都回到出厂值 —— 用户改过的背景色、
画框颜色、圆角、间距、外距、照片数量、布局类型全部丢失。

这里把它们统一存进 QSettings：
- QColor 序列化成 `#AARRGGBB` 字符串（带 alpha，能原样还原）
- int / float / str 按工厂值的类型还原，读坏了就退回工厂值

分组：
    ui/manga_style      漫画页样式
    ui/collage_style    拼贴样式
    ui/collage_layout   拼贴布局（照片数 / 布局类型 / 比例 / 间距 / 外距）
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QColor

ORG = "Long Weekend Labs"
APP = "Speech Bubble Editor"

GROUP_MANGA_STYLE = "ui/manga_style"
GROUP_COLLAGE_STYLE = "ui/collage_style"
GROUP_COLLAGE_LAYOUT = "ui/collage_layout"

# 测试用开关：设 SBE_NO_UI_STATE=1 时完全不读写配置。
# 自动化测试会在同一进程里反复新建 MainWindow，全局持久化会让前一个用例
# 留下的布局串到后一个用例（例如留下「斜切 · 2 块」导致只有 2 个分格）。
# 真实运行只有一个窗口，不存在这个问题。
_DISABLE_ENV = "SBE_NO_UI_STATE"


def _disabled() -> bool:
    return os.environ.get(_DISABLE_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def _settings() -> QSettings:
    return QSettings(ORG, APP)


def _encode(value):
    if isinstance(value, QColor):
        return value.name(QColor.NameFormat.HexArgb)
    return value


def _decode(raw, factory_value):
    """按工厂值的类型还原；类型不对就退回工厂值。"""
    try:
        if isinstance(factory_value, QColor):
            color = QColor(str(raw))
            return color if color.isValid() else QColor(factory_value)
        if isinstance(factory_value, bool):
            return str(raw) in ("true", "True", "1")
        if isinstance(factory_value, int):
            return int(raw)
        if isinstance(factory_value, float):
            return float(raw)
        return str(raw)
    except (TypeError, ValueError):
        return QColor(factory_value) if isinstance(factory_value, QColor) \
            else factory_value


def load_dict(group: str, factory: dict) -> dict:
    """读回保存过的值，工厂值兜底。返回新字典，不改动 factory。"""
    def _factory_copy() -> dict:
        return {k: (QColor(v) if isinstance(v, QColor) else v)
                for k, v in factory.items()}

    if _disabled():
        return _factory_copy()
    settings = _settings()
    settings.beginGroup(group)
    out: dict = {}
    try:
        for key, factory_value in factory.items():
            if settings.contains(key):
                out[key] = _decode(settings.value(key), factory_value)
            else:
                out[key] = QColor(factory_value) \
                    if isinstance(factory_value, QColor) else factory_value
    finally:
        settings.endGroup()
    return out


def save_value(group: str, key: str, value) -> None:
    """保存单个键。每次改一个参数就写一个，不做批量。"""
    if _disabled():
        return
    settings = _settings()
    settings.beginGroup(group)
    try:
        if isinstance(value, QColor):
            settings.setValue(key, value.name(QColor.NameFormat.HexArgb))
        else:
            settings.setValue(key, value)
    finally:
        settings.endGroup()
    settings.sync()


def save_dict(group: str, values: dict) -> None:
    if _disabled():
        return
    settings = _settings()
    settings.beginGroup(group)
    try:
        for key, value in values.items():
            settings.setValue(key, _encode(value))
    finally:
        settings.endGroup()
    settings.sync()


def clear_group(group: str) -> None:
    settings = _settings()
    settings.beginGroup(group)
    try:
        settings.remove("")
    finally:
        settings.endGroup()
    settings.sync()
