@echo off
rem Speech Bubble Editor - Chinese localised build
rem Double-click to launch. No console window.
rem NOTE: keep this file ASCII-only; cmd.exe misparses UTF-8 Chinese paths.
setlocal
set "HERE=%~dp0"

rem Prefer the bundled Python that already has PyQt6 installed.
set "PY=D:\learn\dsh\py311\pythonw.exe"
if not exist "%PY%" set "PY=pythonw"

start "" "%PY%" "%HERE%start_zh.py"
endlocal
