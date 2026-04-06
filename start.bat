@echo off
setlocal enabledelayedexpansion

:: Set console colors and title
title HFSE - Haunted Filesystem Experience
color 0D

cls
echo.
echo ===============================================================
echo.
echo    ██╗  ██╗███████╗███████╗███████╗
echo    ██║  ██║██╔════╝██╔════╝██╔════╝
echo    ███████║█████╗  ███████╗█████╗
echo    ██╔══██║██╔══╝  ╚════██║██╔══╝
echo    ██║  ██║██║     ███████║███████╗
echo    ╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝
echo.
echo         Haunted Filesystem Experience
echo         Learn command-line skills through adventure!
echo.
echo ===============================================================
echo.
echo [HFSE Launcher] Initializing...
echo.

:: Check Python installation
echo [*] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] Python is not installed or not in PATH!
    echo [!] Please install Python 3.7 or higher from https://www.python.org/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [√] Python %PYTHON_VERSION% found

:: Check if virtual environment exists
if not exist "venv\" (
    echo [*] First time setup detected!
    echo [*] Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [X] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [√] Virtual environment created
) else (
    echo [√] Virtual environment found
)

:: Activate virtual environment
echo [*] Activating virtual environment...
call venv\Scripts\activate.bat

:: Check if dependencies are installed
echo [*] Checking dependencies...
python -c "import rich" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Installing required packages...
    echo [*] This may take a moment...
    pip install -q -r requirements.txt
    if %errorlevel% neq 0 (
        echo [X] Failed to install dependencies
        pause
        exit /b 1
    )
    echo [√] All dependencies installed successfully
) else (
    echo [√] All dependencies satisfied
)

:: Create necessary directories
if not exist "saves\" mkdir saves
if not exist "config\" mkdir config

:: Check for config file
if not exist "config\settings.py" (
    echo [*] Setting up configuration...
    if exist "config\settings.example.py" (
        copy config\settings.example.py config\settings.py >nul
        echo [√] Configuration file created
    )
)

:: Launch the game
echo.
echo ===============================================================
echo          🎮 Launching Haunted Filesystem Experience! 🎮
echo ===============================================================
echo.
timeout /t 1 /nobreak >nul

python main.py

:: Deactivate virtual environment on exit
call venv\Scripts\deactivate.bat

endlocal
pause
