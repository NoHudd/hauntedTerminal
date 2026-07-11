@echo off
setlocal

:: Always run from the folder this .bat lives in (double-click, shortcut,
:: "Run as administrator" all give different working directories otherwise).
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

:: --- Find a working Python by actually RUNNING each candidate.
:: --- (The Microsoft Store "python" stub fails this test; PATH quirks too.)
set "PY_CMD="
py -3 -c "pass" >nul 2>&1 && set "PY_CMD=py -3"
if defined PY_CMD goto python_found
python -c "pass" >nul 2>&1 && set "PY_CMD=python"
if defined PY_CMD goto python_found
python3 -c "pass" >nul 2>&1 && set "PY_CMD=python3"
if defined PY_CMD goto python_found

echo [X] Could not find a working Python on this computer.
echo.
echo [!] Install Python 3.10 or newer from https://www.python.org/downloads/
echo [!] IMPORTANT: tick "Add python.exe to PATH" during install,
echo     then run this launcher again.
echo.
echo [i] Diagnostics (screenshot this if you need help):
where py python python3 2>nul
echo.
pause
exit /b 1

:python_found
%PY_CMD% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [X] Your Python is too old. The game needs Python 3.10 or newer.
    echo [!] Install the latest from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('%PY_CMD% --version') do set "PYTHON_VERSION=%%i"
echo [OK] Python %PYTHON_VERSION% found

:: --- Virtual environment
if exist "venv\Scripts\python.exe" goto venv_ready
echo [*] First time setup: creating a private Python environment...
%PY_CMD% -m venv venv
if errorlevel 1 (
    echo [X] Failed to create the environment.
    echo.
    pause
    exit /b 1
)
echo [OK] Environment created
goto venv_done
:venv_ready
echo [OK] Environment found
:venv_done

:: --- Dependencies: probe EVERYTHING the game imports, not just one package,
:: --- so an environment from an older version self-heals.
echo [*] Checking game components...
venv\Scripts\python.exe -c "import rich, textual, rich_pixels, PIL, yaml, pydantic" >nul 2>&1
if not errorlevel 1 goto deps_ready
echo [*] Installing game components - first run can take a minute...
venv\Scripts\python.exe -m pip install --quiet --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [X] Component install failed. Check your internet connection
    echo     and re-run this launcher. The messages above say what broke.
    echo.
    pause
    exit /b 1
)
echo [OK] Components installed
goto deps_done
:deps_ready
echo [OK] All components ready
:deps_done

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
set "GAME_EXIT=%errorlevel%"

popd

:: Clean exit: close the window with the game. Crash: keep it open readable.
if not "%GAME_EXIT%"=="0" (
    echo.
    echo [X] The game closed unexpectedly (code %GAME_EXIT%^). The messages
    echo     above may say why - a screenshot of this window helps a lot.
    echo.
    pause
)
endlocal
