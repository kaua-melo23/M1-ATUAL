@echo off
:: ─────────────────────────────────────────────────────────────────────────────
:: setup.bat — Configura o ambiente pela primeira vez
:: Execute este script UMA VEZ após clonar o projeto.
:: ─────────────────────────────────────────────────────────────────────────────

cd /d "%~dp0.."

echo.
echo ============================================================
echo  SETUP — Lanchonete
echo ============================================================

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Instale em: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Cria .env se não existir
if not exist ".env" (
    copy ".env.example" ".env"
    echo [OK] .env criado a partir do .env.example
    echo      Abra o arquivo .env e preencha as variaveis antes de continuar.
) else (
    echo [OK] .env ja existe.
)

:: Cria ambiente virtual
if not exist "venv" (
    echo Criando ambiente virtual...
    python -m venv venv
    echo [OK] venv criado.
)

:: Instala dependências
echo Instalando dependencias...
call venv\Scripts\activate.bat
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo [OK] Dependencias instaladas.

:: Cria pastas necessárias
if not exist "logs" mkdir logs
if not exist "database" mkdir database
if not exist "static\uploads" mkdir static\uploads
if not exist "cloudflare" mkdir cloudflare

echo.
echo ============================================================
echo  Setup concluido!
echo  Proximo passo: edite o arquivo .env e execute start.bat
echo ============================================================
echo.
pause
