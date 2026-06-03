"""
Configuracoes centralizadas da aplicacao.

Todas as variaveis sensiveis vem do .env -- nunca hardcode valores de producao aqui.
Para gerar uma SECRET_KEY segura:
    python -c "import secrets; print(secrets.token_hex(32))"
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Config:
    # ── Flask ──────────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    DEBUG: bool = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # ── Servidor (Waitress) ────────────────────────────────────────────────────
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", 5000))

    # ── Timezone ───────────────────────────────────────────────────────────────
    TIMEZONE: str = os.getenv("TIMEZONE", "America/Recife")

    # ── Cloudflare Tunnel ──────────────────────────────────────────────────────
    CLOUDFLARE_TOKEN: str = os.getenv("CLOUDFLARE_TOKEN", "")

    # ── Sessao / Cookies ───────────────────────────────────────────────────────
    # COOKIE_SECURE=true  → acesso via Cloudflare Tunnel (HTTPS)
    # COOKIE_SECURE=false → acesso direto por IP local na rede interna
    SESSION_COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "true").lower() == "true"
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"

    # ── Banco de Dados ─────────────────────────────────────────────────────────
    DB_PATH: str = os.path.join(BASE_DIR, "database", "lanchonete.db")

    # ── Uploads ────────────────────────────────────────────────────────────────
    UPLOAD_FOLDER: str = os.path.join(BASE_DIR, "static", "uploads")
    ALLOWED_EXTENSIONS: set = {"png", "jpg", "jpeg", "gif", "webp", "avif"}

    # ── Admin padrao ───────────────────────────────────────────────────────────
    ADMIN_USER: str = os.getenv("ADMIN_USER", "")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")

    # ── Mercado Pago ───────────────────────────────────────────────────────────
    MP_ACCESS_TOKEN: str = os.getenv("MP_ACCESS_TOKEN", "")

    # ── Anthropic (IA) ─────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # ── Logging ────────────────────────────────────────────────────────────────
    LOG_LEVEL: int = logging.DEBUG if DEBUG else logging.INFO
    LOG_DIR: str = os.path.join(BASE_DIR, "logs")


def validar_config(config: Config) -> None:
    """
    Valida variaveis criticas no startup e emite avisos claros.
    Nao encerra a aplicacao -- permite rodar em modo degradado para desenvolvimento.
    """
    logger = logging.getLogger("config")
    avisos = []

    if not config.SECRET_KEY:
        avisos.append(
            "SECRET_KEY nao definida no .env! "
            "Sessions sao inseguras. Gere uma chave com: "
            "python -c \"import secrets; print(secrets.token_hex(32))\""
        )

    if not config.ADMIN_USER or not config.ADMIN_PASSWORD:
        avisos.append(
            "ADMIN_USER ou ADMIN_PASSWORD nao definidos no .env! "
            "Login de administrador pode estar desabilitado."
        )

    if not config.CLOUDFLARE_TOKEN:
        avisos.append(
            "CLOUDFLARE_TOKEN nao definido. "
            "O tunnel nao sera iniciado pelo start_tunnel.bat."
        )

    if not config.SESSION_COOKIE_SECURE:
        logger.warning(
            "COOKIE_SECURE=false -- login via Cloudflare Tunnel pode falhar. "
            "Use apenas para acesso local direto."
        )

    for aviso in avisos:
        logger.warning("CONFIG: %s", aviso)
