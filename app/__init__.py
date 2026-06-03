"""
Application Factory — cria e configura a instância do Flask.
"""

import os
import logging
from datetime import timedelta

from flask import Flask

from config.settings import Config


def create_app(config_class=Config) -> Flask:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    template_dir = os.path.join(base_dir, "templates")
    static_dir = os.path.join(base_dir, "static")

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.config.from_object(config_class)

    # ── Logging ──────────────────────────────────────────────────────────────
    _configurar_logging(app)

    # ── Sessão ───────────────────────────────────────────────────────────────
    app.config.update(
        SESSION_PERMANENT=True,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
        SESSION_REFRESH_EACH_REQUEST=True,
    )

    # ── Banco de dados ────────────────────────────────────────────────────────
    from app.repositories.db import init_db, close_db
    from app.repositories.gpo_repository import init_gpo
    from app.repositories.complemento_repository import init_complementos

    init_db()
    init_gpo()
    init_complementos()
    app.teardown_appcontext(close_db)

    # ── Blueprints ────────────────────────────────────────────────────────────
    from app.controllers.auth_controller import auth_bp
    from app.controllers.admin_controller import admin_bp
    from app.controllers.vendas_controller import vendas_bp
    from app.controllers.atendente_controller import atendente_bp
    from app.controllers.gpo_controller import gpo_bp
    from app.controllers.main_controller import main_bp
    from app.controllers.complemento_controller import complemento_bp
    from app.controllers.impressora_controller import impressora_bp
    from app.controllers.ia_controller import ia_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(vendas_bp)
    app.register_blueprint(atendente_bp)
    app.register_blueprint(gpo_bp)
    app.register_blueprint(complemento_bp)
    app.register_blueprint(impressora_bp)
    app.register_blueprint(ia_bp)

    # ── Worker de impressão ───────────────────────────────────────────────────
    # Importação centralizada em app/printer/ (único local)
    from app.printer.service import iniciar_worker
    iniciar_worker()

    logger = logging.getLogger(__name__)
    logger.info("Aplicação inicializada — host=%s port=%s debug=%s",
                config_class.HOST, config_class.PORT, config_class.DEBUG)

    return app


def _configurar_logging(app: Flask) -> None:
    """Configura logging estruturado em arquivo e console."""
    import os

    log_dir = app.config.get("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_level = app.config.get("LOG_LEVEL", logging.INFO)
    log_file = os.path.join(log_dir, "app.log")

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler de arquivo (rotativo por tamanho)
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # Handler de console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # Configura o root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Evita handlers duplicados em reloads de desenvolvimento
    if not root_logger.handlers:
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

    # Silencia logs verbosos de libs externas
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("waitress").setLevel(logging.INFO)
