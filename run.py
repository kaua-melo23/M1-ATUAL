"""
Ponto de entrada da aplicacao.

Uso:
    Desenvolvimento : python run.py
    Producao local  : python run.py  (Waitress e sempre usado)

O servidor de desenvolvimento Flask (app.run) nunca e chamado aqui.
"""

import os
import logging

from dotenv import load_dotenv
load_dotenv()

_timezone = os.getenv("TIMEZONE", "America/Recife")
os.environ["TZ"] = _timezone

from config.settings import Config, validar_config
from app import create_app


def main() -> None:
    from waitress import serve

    app = create_app(Config)
    logger = logging.getLogger("run")

    validar_config(Config)

    with app.app_context():
        from app.utils.diagnostico import realizar_testes_iniciais
        realizar_testes_iniciais()

    logger.info(
        "Servidor iniciando -- http://%s:%s (Waitress)",
        Config.HOST, Config.PORT,
    )
    logger.info("Timezone: %s", _timezone)

    serve(
        app,
        host=Config.HOST,
        port=Config.PORT,
        threads=4,
        channel_timeout=120,
    )


if __name__ == "__main__":
    main()
