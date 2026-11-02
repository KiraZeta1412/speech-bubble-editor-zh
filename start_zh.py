# -*- coding: utf-8 -*-
"""Launcher for the Chinese-localised Speech Bubble Editor.

Why this file exists: the project imports sibling modules flat
(`from main_window import MainWindow`), but some embedded/portable Python
builds (those driven by a `python3xx._pth` file) never add the script
directory to sys.path. This wrapper adds it, then runs main.py with the
original argv, so behaviour matches running main.py directly.

Usage:
    python start_zh.py
    python start_zh.py --smoke-test report.json
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
os.chdir(HERE)

MAIN = os.path.join(HERE, "main.py")
sys.argv[0] = MAIN
runpy.run_path(MAIN, run_name="__main__")
