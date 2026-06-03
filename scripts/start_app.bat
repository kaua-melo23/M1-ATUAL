@echo off
:: ─────────────────────────────────────────────────────────────────────────────
:: start_app.bat — Inicia apenas o servidor Flask (Waitress)
:: ─────────────────────────────────────────────────────────────────────────────

cd /d "%~dp0.."

if not exist "venv\Scripts\activate.bat" (
    echo [ERRO] Ambiente virtual nao encontrado. Execute scripts\setup.bat primeiro.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [ERRO] Arquivo .env nao encontrado. Execute scripts\setup.bat primeiro.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo.
echo ============================================================
echo  Iniciando Lanchonete (Waitress)...
echo ============================================================
echo.

python run.py

pause
