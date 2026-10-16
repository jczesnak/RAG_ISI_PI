@echo off
rem Instaluje wszystko, co potrzebne do uruchomienia projektu (szczegoly: scripts\install.ps1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
