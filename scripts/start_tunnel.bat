@echo off
:: ─────────────────────────────────────────────────────────────────────────────
:: start_tunnel.bat -- Inicia o Cloudflare Tunnel via token
:: Requer: cloudflared instalado (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
:: ─────────────────────────────────────────────────────────────────────────────

cd /d "%~dp0.."

:: Le CLOUDFLARE_TOKEN do .env
for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
    if "%%A"=="CLOUDFLARE_TOKEN" set CLOUDFLARE_TOKEN=%%B
)

if "%CLOUDFLARE_TOKEN%"=="" (
    echo [ERRO] CLOUDFLARE_TOKEN nao definido no .env
    echo        Acesse: Zero Trust ^> Networks ^> Tunnels ^> seu tunnel ^> Configure ^> Install connector
    pause
    exit /b 1
)

if "%CLOUDFLARE_TOKEN%"=="cole-seu-token-aqui" (
    echo [ERRO] CLOUDFLARE_TOKEN ainda com valor de exemplo no .env
    echo        Substitua pelo token real do painel da Cloudflare.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Iniciando Cloudflare Tunnel...
echo ============================================================
echo.

cloudflared tunnel run --token %CLOUDFLARE_TOKEN%

pause
