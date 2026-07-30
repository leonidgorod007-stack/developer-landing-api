@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

REM ============================================================
REM  Developer Landing API - one-click launcher
REM  Works from any folder (anchors to its own directory).
REM  Optional pip proxy: set PIP_PROXY=http://host:port before
REM  running, or edit the line below.
REM ============================================================

REM Anchor to the script's own directory so it runs from anywhere.
cd /d "%~dp0"
title Developer Landing API

echo ============================================================
echo   Developer Landing API - launcher
echo ============================================================
echo.

REM --- optional pip proxy -------------------------------------
if not "%PIP_PROXY%"=="" (
    set "PIP_ARGS=--proxy %PIP_PROXY%"
    echo [info] Using pip proxy: %PIP_PROXY%
) else (
    set "PIP_ARGS="
)

set "VENV_PY=%~dp0.venv\Scripts\python.exe"

REM --- create the virtual environment if missing --------------
if not exist "%VENV_PY%" (
    echo [setup] Virtual environment not found - creating it...
    set "PY="
    where py     >nul 2>nul && set "PY=py -3"
    if not defined PY ( where python >nul 2>nul && set "PY=python" )
    if not defined PY (
        echo.
        echo [ERROR] Python 3.9+ was not found on this system.
        echo         Install it from https://www.python.org/downloads/
        echo         ^(tick "Add python.exe to PATH"^), then run this file again.
        echo.
        pause
        exit /b 1
    )
    !PY! -m venv ".venv"
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

REM --- install dependencies once ------------------------------
if not exist "%~dp0.venv\.installed" (
    echo [setup] Installing dependencies ^(first run only^)...
    "%VENV_PY%" -m pip install --upgrade pip %PIP_ARGS%
    "%VENV_PY%" -m pip install %PIP_ARGS% -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Dependency installation failed.
        echo         If you are behind a proxy, set it and retry, e.g.:
        echo             set PIP_PROXY=http://host:port
        echo             %~nx0
        echo.
        pause
        exit /b 1
    )
    echo installed> "%~dp0.venv\.installed"
)

REM --- create .env from template if missing -------------------
if not exist "%~dp0.env" (
    echo [setup] Creating .env from template...
    copy /y ".env.example" ".env" >nul
    echo [note] For live AI, open .env and set ANTHROPIC_API_KEY
    echo        ^(and ANTHROPIC_BASE_URL if you use a proxy/gateway^).
)

echo.
echo [run] Starting server. Press Ctrl+C to stop.
echo       Landing:  http://localhost:8000/
echo       Swagger:  http://localhost:8000/docs
echo       Health:   http://localhost:8000/api/health
echo.

REM --- open the browser a few seconds after start -------------
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://localhost:8000/'" >nul 2>&1

REM --- run the server (local bind, no reload) -----------------
set "HOST=127.0.0.1"
set "RELOAD=false"
"%VENV_PY%" run.py

echo.
echo [stopped] Server stopped.
pause
