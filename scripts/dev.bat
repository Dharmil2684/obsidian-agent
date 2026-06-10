@echo off
setlocal

echo ============================================
echo   Obsidian Agent - Phase 2 Dev Mode
echo   System Tray + Floating Window
echo ============================================
echo.
echo   Ctrl+Shift+Space  = toggle window
echo   Left-click tray   = toggle window
echo   Right-click tray  = context menu
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from python.org
    pause & exit /b 1
)

REM Check Node
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Install from nodejs.org
    pause & exit /b 1
)

REM Install Python deps if needed
if not exist ".venv" (
    echo [setup] Creating Python virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q

REM Install Node deps if needed
if not exist "node_modules" (
    echo [setup] Installing root Node deps...
    npm install --silent
)
if not exist "renderer\node_modules" (
    echo [setup] Installing renderer Node deps...
    npm --prefix renderer install --silent
)

echo.
echo [1/3] Starting FastAPI backend on http://localhost:8000
start "FastAPI Backend" cmd /k "call .venv\Scripts\activate.bat && python -m uvicorn backend.main:app --host localhost --port 8000 --reload"

echo [2/3] Starting Vite dev server on http://localhost:5173
start "Vite Dev Server" cmd /k "npm --prefix renderer run dev"

echo [3/3] Waiting for Vite then launching Electron...
timeout /t 4 /nobreak >nul

set NODE_ENV=development
npm run electron

endlocal
