@echo off
title Installation de Jarvis
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -Raw -Encoding UTF8 '%~dp0installer.ps1' | Invoke-Expression"
pause
