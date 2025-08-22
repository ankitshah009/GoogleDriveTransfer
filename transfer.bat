@echo off
REM Google Drive Transfer Tool - Windows Batch Script

echo 🚀 Google Drive Transfer Tool
echo =============================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    echo    Please install Python 3.7 or higher
    pause
    exit /b 1
)

REM Check if required files exist
if not exist "credentials.json" (
    echo ❌ credentials.json not found!
    echo    Please run setup.py first to configure your credentials.
    pause
    exit /b 1
)

if not exist "drive_transfer.py" (
    echo ❌ drive_transfer.py not found!
    pause
    exit /b 1
)

REM Run the transfer tool with all passed arguments
python drive_transfer.py %*

REM Pause to see output
echo.
echo Press any key to exit...
pause >nul
