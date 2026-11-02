# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 单文件打包配置 —— 汉化版。

与上游 speech_bubble.spec 的差异：
  1. onefile：binaries/datas 直接进 EXE，不生成 COLLECT 目录
  2. ffmpeg 可选：找得到就打包（视频功能可用），找不到就跳过（仅图片功能）
     —— 上游是 raise RuntimeError 直接中断，没装 ffmpeg 的机器根本打不了包
  3. 排除用不到的 Qt 模块，压体积

用法（在仓库根目录）：
    python -m PyInstaller --noconfirm --clean --distpath dist --workpath build \
        sbe_zh_onefile.spec
产物：dist/漫画气泡编辑器.exe
"""
import os
import shutil

_app_dir = os.path.dirname(os.path.abspath(SPEC))

# ffmpeg 可选：环境变量 SBE_FFMPEG 指定，或 PATH 里能找到
_ffmpeg_bin = os.environ.get("SBE_FFMPEG") or shutil.which("ffmpeg")
if _ffmpeg_bin and not os.path.isfile(_ffmpeg_bin):
    _ffmpeg_bin = None
_binaries = [(_ffmpeg_bin, ".")] if _ffmpeg_bin else []

a = Analysis(
    [os.path.join(_app_dir, "main.py")],
    pathex=[_app_dir],
    binaries=_binaries,
    datas=[(os.path.join(_app_dir, n), n) for n in ("fonts", "icons", "theme")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PIL.ImageQt", "PyQt6.QtQml", "PyQt6.QtQuick"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="漫画气泡编辑器",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(_app_dir, "icons", "icon.ico"),
)
