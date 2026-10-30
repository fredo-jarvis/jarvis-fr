@echo off
title Changer la cle Gemini de Jarvis
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File outils\cle_gemini.ps1
pause
