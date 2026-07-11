@echo off
setlocal enabledelayedexpansion

:: Always run from the folder this .bat lives in (double-click, shortcut,
:: "Run as administrator" — all give different working directories otherwise).
pushd "%~dp0"

:: UTF-8 so the game's box-drawing and sprites render instead of garbage.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

title Haunted Terminal
color 0D

cls
echo.
echo ===============================================================
echo.
echo                  H A U N T E D   T E R M I N A L
echo           Learn command-line skills through adventure!
echo.
echo ===============================================================
echo.
echo [Launcher] Initializing...
echo.

:: --- Find Python: prefer the "py" launcher (installed even when PATH is not
:: --- set), fall back to "python". The Microsoft Store stub fails the probe.
set "PY_CMD="
py -3 --version >nul 2>&1
if %errorlevel% equ 0 set "PY_CMD=py -3"
if not defined PY_CMD (
    python --version >nul 2>&1
    if !errorlevel! equ 0 set "PY_CMD=python"
)
if not defined PY_CMD (
    echo [X] Python was not found on this computer.
    echo [!] Install Python 3.10 or newer from https://www.python.org/downloads/
    echo [!] IMPORTANT: tick "Add python.exe to PATH" during install.
    echo.
    pause
    exit /b 1
)

:: --- Require Python 3.10+ (the game's UI framework needs it).
%PY_CMD% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Your Python is too old. The game needs Python 3.10 or newer.
    echo [!] Install the latest from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('%PY_CMD% --version') do set PYTHON_VERSION=%%i
echo [OK] Python %PYTHON_VERSION% found

:: --- Virtual environment
if not exist "venv\Scripts\python.exe" (
    echo [*] First time setup: creating a private Python environment...
    %PY_CMD% -m venv venv
    if !errorlevel! neq 0 (
        echo [X] Failed to create the environment.
        echo.
        pause
        exit /b 1
    )
    echo [OK] Environment created
) else (
    echo [OK] Environment found
)

:: --- Dependencies: probe EVERYTHING the game imports, not just one package,
:: --- so an environment from an older version self-heals.
echo [*] Checking game components...
venv\Scripts\python.exe -c "import rich, textual, rich_pixels, PIL, yaml, pydantic" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Installing game components — first run can take a minute...
    venv\Scripts\python.exe -m pip install --quiet --upgrade pip
    venv\Scripts\python.exe -m pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo.
        echo [X] Component install failed. Check your internet connection
        echo     and re-run this launcher. The messages above say what broke.
        echo.
        pause
        exit /b 1
    )
    echo [OK] Components installed
) else (
    echo [OK] All components ready
)

:: --- Folders + default config
if not exist "saves\" mkdir saves
if not exist "config\settings.py" (
    if exist "config\settings.example.py" copy config\settings.example.py config\settings.py >nul
)

echo.
echo ===============================================================
echo               Launching Haunted Terminal...
echo ===============================================================
timeout /t 1 /nobreak >nul

venv\Scripts\python.exe main.py
set GAME_EXIT=%errorlevel%

popd

:: Clean exit: close the window with the game (no "press any key").
:: Crash: keep the window open so the error is readable.
if %GAME_EXIT% neq 0 (
    echo.
    echo [X] The game closed unexpectedly (code %GAME_EXIT%^). The messages
    echo     above may say why — a screenshot of this window helps a lot.
    echo.
    pause
)
endlocal
