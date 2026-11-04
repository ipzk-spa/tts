@echo off
REM Spag Voice Studio (SVS+) launcher — force UTF-8 console for Ukrainian text
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONLEGACYWINDOWSSTDIO=0
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false; $OutputEncoding = [Console]::OutputEncoding; & '%~dp0start_voice_studio.ps1'"
if errorlevel 1 pause
pause
