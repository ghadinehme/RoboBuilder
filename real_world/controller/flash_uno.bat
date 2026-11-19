@echo off
rem Windows: double-click if the board does not answer in the controller ("no IR bridge answer").
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0flash_uno.ps1"
pause
