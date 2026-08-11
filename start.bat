@echo off
REM ELIS System Startup Script for Windows

echo Starting ELIS System...
echo.

if not exist ".venv" (
    echo Error: Virtual environment not found!
    echo Please create it first with: python -m venv .venv
    pause
    exit /b 1
)

if not exist ".env" (
    echo Warning: .env file not found!
    echo Please create .env file with your configuration
    echo.
)

echo Using Python from virtual environment (.venv)
echo Starting server on http://localhost:5001
echo Press Ctrl+C to stop the server
echo.

.venv\Scripts\python.exe run.py
