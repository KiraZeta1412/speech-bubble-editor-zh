"""
Native file dialog helpers.

Qt falls back to its own QFileDialog when native dialogs are disabled or no
platform portal is available. Keep the calls centralized so open/import flows
all ask for the OS file picker first — and so they all remember the last folder
the user browsed to.
"""

import os
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtCore import QSettings

_SETTINGS_ORG = "LongWeekendLabs"
_SETTINGS_APP = "SpeechBubbleEditor"
_LAST_DIR_KEY = "dialogs/last_open_dir"
_LAST_SAVE_KEY = "dialogs/last_save_dir"


def _settings() -> QSettings:
    return QSettings(_SETTINGS_ORG, _SETTINGS_APP)


def _last_dir() -> str:
    d = _settings().value(_LAST_DIR_KEY, "", type=str)
    return d if d and os.path.isdir(d) else ""


def _remember_dir(path: str) -> None:
    if path:
        _settings().setValue(_LAST_DIR_KEY, os.path.dirname(path))


def _last_save_dir() -> str:
    d = _settings().value(_LAST_SAVE_KEY, "", type=str)
    return d if d and os.path.isdir(d) else ""


def open_file(parent, title: str, file_filter: str, directory: str = "") -> str:
    options = QFileDialog.Option(0)
    options &= ~QFileDialog.Option.DontUseNativeDialog
    # Fall back to the last folder the user opened from when no explicit
    # directory is given, so the picker doesn't reset every time.
    start_dir = directory or _last_dir()
    path, _ = QFileDialog.getOpenFileName(
        parent,
        title,
        start_dir,
        file_filter,
        options=options,
    )
    _remember_dir(path)
    return path


def save_file(parent, title: str, default_name: str,
              file_filter: str) -> tuple[str, str]:
    """保存对话框：默认落在上次保存过的文件夹，并把这次的目录记下来。

    返回 (路径, 用户选择的格式过滤器)，调用方可据此校正扩展名。
    """
    options = QFileDialog.Option(0)
    options &= ~QFileDialog.Option.DontUseNativeDialog
    start_dir = _last_save_dir()
    suggested = (os.path.join(start_dir, default_name)
                 if start_dir else default_name)
    path, chosen = QFileDialog.getSaveFileName(
        parent, title, suggested, file_filter, options=options)
    if path:
        _settings().setValue(_LAST_SAVE_KEY, os.path.dirname(path))
    return path, chosen

