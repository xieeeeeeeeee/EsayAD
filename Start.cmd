@echo off
cd /d "%~dp0"
if exist "%~dp0dist\LCSC-AD24-Assistant-0.3.1.exe" (
  start "" "%~dp0dist\LCSC-AD24-Assistant-0.3.1.exe"
  exit /b
)
if exist "%~dp0dist\LCSC-AD24-Assistant-0.2.2.exe" (
  start "" "%~dp0dist\LCSC-AD24-Assistant-0.2.2.exe"
  exit /b
)
if exist "%~dp0dist\LCSC-AD24-Assistant-0.2.1.exe" (
  start "" "%~dp0dist\LCSC-AD24-Assistant-0.2.1.exe"
  exit /b
)
if exist "%~dp0dist\LCSC-AD24-Assistant.exe" (
  start "" "%~dp0dist\LCSC-AD24-Assistant.exe"
) else (
  start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0launch.pyw"
)
