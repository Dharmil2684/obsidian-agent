@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   Obsidian Agent — First-Time Setup
echo ============================================
echo.

REM ---- Prerequisites check ---------------------------------------------------
python --version >nul 2>&1
if errorlevel 1 ( echo [ERROR] Python 3.11+ required. Get it at python.org & pause & exit /b 1 )

node --version >nul 2>&1
if errorlevel 1 ( echo [ERROR] Node.js 20+ required. Get it at nodejs.org & pause & exit /b 1 )

ollama --version >nul 2>&1
if errorlevel 1 ( echo [WARN] Ollama not found. Get it at ollama.ai for local LLM support. )

REM ---- Vault path ------------------------------------------------------------
if "%~1"=="" (
    set /p VAULT_PATH="Enter your Obsidian vault path (e.g. C:\Users\You\ObsidianVault): "
) else (
    set VAULT_PATH=%~1
    if /I "!VAULT_PATH:~0,7!"=="--vault" set VAULT_PATH=%~2
)

if "!VAULT_PATH!"=="" (
    echo [ERROR] No vault path provided.
    pause & exit /b 1
)

REM ---- Groq API key ----------------------------------------------------------
set /p GROQ_KEY="Enter your Groq API key (free at console.groq.com, press Enter to skip): "

REM ---- Write .env ------------------------------------------------------------
(
    echo VAULT_PATH=!VAULT_PATH!
    echo LOCAL_MODEL=nous-hermes3
    echo FALLBACK_MODEL=phi3-mini
    echo OLLAMA_BASE_URL=http://localhost:11434
    echo GROQ_API_KEY=!GROQ_KEY!
    echo GROQ_MODEL=llama-3.3-70b-versatile
    echo API_HOST=localhost
    echo API_PORT=8000
    echo MAX_BACKUPS=3
) > .env
echo [ok] .env written

REM ---- Python venv + deps ---------------------------------------------------
echo.
echo [1/5] Installing Python dependencies...
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q
echo [ok] Python deps installed

REM ---- Node deps ------------------------------------------------------------
echo [2/5] Installing Node dependencies...
npm install --silent
npm --prefix renderer install --silent
echo [ok] Node deps installed

REM ---- Ollama models --------------------------------------------------------
echo [3/5] Pulling Ollama models (nous-hermes3 is ~5GB, this may take a while)...
ollama pull nous-hermes3 2>nul || echo [skip] Ollama pull skipped (not installed or offline)
ollama pull nomic-embed-text 2>nul || echo [skip] nomic-embed-text skipped
echo [ok] Models ready

REM ---- Generate vault context -----------------------------------------------
echo [4/5] Generating agent context from vault...
python scripts\generate_context.py "!VAULT_PATH!" 2>nul || echo [skip] Context generation skipped

REM ---- Run tests ------------------------------------------------------------
echo [5/5] Running tests...
pytest tests\ -q
if errorlevel 1 (
    echo [WARN] Some tests failed. Check output above.
) else (
    echo [ok] All tests passed
)

echo.
echo ============================================
echo   Setup complete! Run: scripts\dev.bat
echo ============================================
pause
endlocal
