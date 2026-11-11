@echo off
title Installation du cerveau local de Jarvis
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer-cerveau-local.ps1"
pause
