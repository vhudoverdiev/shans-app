@echo off
setlocal

cd /d "%~dp0"

if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" -m unittest discover -s tests -v
    exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 -m unittest discover -s tests -v
    exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python -m unittest discover -s tests -v
    exit /b %ERRORLEVEL%
)

echo Python was not found. Create venv or add Python to PATH.
exit /b 1
