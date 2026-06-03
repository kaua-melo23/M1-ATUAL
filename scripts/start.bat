@echo off
:: ─────────────────────────────────────────────────────────────────────────────
:: start.bat — Inicia o servidor e o tunnel em janelas separadas
:: ─────────────────────────────────────────────────────────────────────────────

cd /d "%~dp0.."

echo.
echo ============================================================
echo  Lanchonete — Iniciando ambiente completo
echo ============================================================
echo.

:: Abre o servidor em uma nova janela
start "Lanchonete - Servidor" cmd /k "scripts\start_app.bat"

:: Aguarda 5 segundos para o servidor iniciar antes do tunnel
timeout /t 5 /nobreak >nul

:: Abre o tunnel em outra janela
start "Lanchonete - Tunnel" cmd /k "scripts\start_tunnel.bat"

echo  Servidor e tunnel iniciados em janelas separadas.
echo  Feche as janelas para encerrar.
echo.
