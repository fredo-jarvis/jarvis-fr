@echo off
title JARVIS (Mark LV - version francaise)
cd /d "%~dp0"
echo Lancement de JARVIS...
.venv\Scripts\python.exe main.py
if errorlevel 1 (
  echo.
  echo Une erreur est survenue - voir le message ci-dessus.
  pause
)
