"""自定义拼贴布局的存取。

用户在设计器里画出来的布局存成「归一化矩形」：每个矩形的 x/y/w/h 都是 0..1
的页面相对坐标，跟具体页面尺寸无关。应用时按当前页面比例缩放即可，
所以同一套自定义布局在竖版和方形页面上都能用。

存储走 QSettings（和 collage_presets 一致），不额外落文件。
"""

from __future__ import annotations

import json

from PyQt6.QtCore import QSettings

ORG = "Long Weekend Labs"
APP = "Speech Bubble Editor"
KEY = "collage_custom_layouts"

# 布局类型名用这个前缀标记「这是自定义布局」
CUSTOM_PREFIX = "自定义 · "


def _settings() -> QSettings:
    return QSettings(ORG, APP)


def is_custom(layout_type: str) -> bool:
    return str(layout_type or "").startswith(CUSTOM_PREFIX)


def custom_name(layout_type: str) -> str:
    text = str(layout_type or "")
    return text[len(CUSTOM_PREFIX):] if text.startswith(CUSTOM_PREFIX) else text


def make_type(name: str) -> str:
    return f"{CUSTOM_PREFIX}{str(name).strip()}"


def load_all() -> dict[str, list[list[float]]]:
    raw = _settings().value(KEY, "{}")
    try:
        values = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(values, dict):
        return {}
    out: dict[str, list[list[float]]] = {}
    for name, rects in values.items():
        clean = _clean_rects(rects)
        if clean:
            out[str(name)] = clean
    return out


def _clean_rects(rects) -> list[list[float]]:
    """校验并夹紧：每个矩形必须是 4 个 0..1 的数，且宽高为正。"""
    if not isinstance(rects, (list, tuple)):
        return []
    out: list[list[float]] = []
    for item in rects:
        if not isinstance(item, (list, tuple)) or len(item) != 4:
            continue
        try:
            x, y, w, h = (float(v) for v in item)
        except (TypeError, ValueError):
            continue
        x = min(max(x, 0.0), 1.0)
        y = min(max(y, 0.0), 1.0)
        w = min(max(w, 0.01), 1.0 - x)
        h = min(max(h, 0.01), 1.0 - y)
        if w > 0 and h > 0:
            out.append([round(x, 6), round(y, 6), round(w, 6), round(h, 6)])
    return out


def _write(values: dict[str, list[list[float]]]):
    settings = _settings()
    settings.setValue(KEY, json.dumps(values, ensure_ascii=False))
    settings.sync()


def save(name: str, rects) -> bool:
    name = str(name).strip()
    clean = _clean_rects(rects)
    if not name or not clean:
        return False
    values = load_all()
    values[name] = clean
    _write(values)
    return True


def delete(name: str):
    values = load_all()
    if values.pop(str(name).strip(), None) is not None:
        _write(values)


def rename(old: str, new: str) -> bool:
    old, new = str(old).strip(), str(new).strip()
    if not new or old == new:
        return False
    values = load_all()
    if old not in values:
        return False
    values[new] = values.pop(old)
    _write(values)
    return True


def get(name: str) -> list[list[float]]:
    return load_all().get(str(name).strip(), [])


def names() -> list[str]:
    return sorted(load_all().keys())
