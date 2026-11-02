@echo off
rem Speech Bubble Editor - debug launcher (keeps the console open)
setlocal
set "HERE=%~dp0"
set "PYTHONIOENCODING=utf-8"
set "PY=D:\learn\dsh\py311\python.exe"
if not exist "%PY%" set "PY=python"

echo === starting Speech Bubble Editor (debug) ===
"%PY%" "%HERE%start_zh.py"
echo.
echo === exited with code %ERRORLEVEL% ===
pause
endlocal
