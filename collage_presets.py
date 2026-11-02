"""Persistent named presets for the Photo Collage workspace."""

import json

from PyQt6.QtCore import QSettings


ORG = "Long Weekend Labs"
APP = "Speech Bubble Editor"
FACTORY_NAME = "午夜"
FACTORY_PRESET = {
    "layout": {
        "photo_count": 4,
        "layout_type": "马赛克",
        "aspect_ratio": "竖版 · 4:5",
        "margin": 28,
        "gap": 18,
    },
    "style": {
        "page_color": "#111318",
        "border_color": "#111318",
        "border_width": 0.0,
        "corner_radius": 24.0,
        "image_background": "blur",
    },
}


def _settings():
    return QSettings(ORG, APP)


def load_all() -> dict[str, dict]:
    raw = _settings().value("collage_presets/items", "{}")
    try:
        values = json.loads(str(raw))
        return values if isinstance(values, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _write(values: dict[str, dict]):
    settings = _settings()
    settings.setValue("collage_presets/items", json.dumps(values))
    settings.sync()


def save(name: str, preset: dict):
    name = str(name).strip()
    if not name:
        return
    values = load_all()
    values[name] = preset
    _write(values)


def delete(name: str):
    values = load_all()
    values.pop(str(name), None)
    _write(values)
    if default_name() == name:
        set_default("")


def rename(old_name: str, new_name: str):
    old_name, new_name = str(old_name), str(new_name).strip()
    values = load_all()
    if not new_name or old_name not in values:
        return
    preset = values.pop(old_name)
    values[new_name] = preset
    _write(values)
    if default_name() == old_name:
        set_default(new_name)


def default_name() -> str:
    return str(_settings().value("collage_presets/default", ""))


def set_default(name: str):
    settings = _settings()
    settings.setValue("collage_presets/default", str(name))
    settings.sync()


def default_preset() -> dict:
    name = default_name()
    saved = load_all()
    return saved.get(name, FACTORY_PRESET)
