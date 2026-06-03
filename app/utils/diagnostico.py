"""
Utilitários de diagnóstico executados na inicialização do servidor.
"""

import logging
import os

from flask import current_app

logger = logging.getLogger(__name__)


def realizar_testes_iniciais() -> None:
    """Valida conexões e estrutura de diretórios na inicialização."""
    logger.info("=" * 50)
    logger.info("DIAGNÓSTICO DE INICIALIZAÇÃO")
    logger.info("=" * 50)

    # ── Pastas necessárias ────────────────────────────────────────────────────
    pastas = [
        current_app.config.get("UPLOAD_FOLDER", "static/uploads"),
        os.path.dirname(current_app.config.get("DB_PATH", "database/lanchonete.db")),
        current_app.config.get("LOG_DIR", "logs"),
    ]
    for pasta in pastas:
        if not os.path.exists(pasta):
            os.makedirs(pasta, exist_ok=True)
            logger.info("Pasta criada: %s", pasta)
        else:
            logger.debug("Pasta OK: %s", pasta)

    # ── Admin configurado ─────────────────────────────────────────────────────
    admin_user = current_app.config.get("ADMIN_USER", "")
    if admin_user:
        logger.info("Admin configurado: %s", admin_user)
    else:
        logger.warning("ADMIN_USER não definido no .env — login admin desabilitado")

    # ── Mercado Pago ──────────────────────────────────────────────────────────
    try:
        from app.services.pagamento_service import validar_conexao
        resultado = validar_conexao()
        if resultado["ok"]:
            logger.info("Mercado Pago: %s", resultado["msg"])
        else:
            logger.warning("Mercado Pago: %s", resultado["msg"])
    except Exception as e:
        logger.warning("Mercado Pago: erro ao validar — %s", e)

    # ── Anthropic ─────────────────────────────────────────────────────────────
    anthropic_key = current_app.config.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        logger.info("Anthropic API Key: configurada")
    else:
        logger.warning("Anthropic API Key: não configurada (IA desabilitada)")

    logger.info("=" * 50)
