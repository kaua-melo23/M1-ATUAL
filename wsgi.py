"""
Ponto de entrada WSGI para deploy em cloud (Gunicorn, Railway, Render, etc.).

Uso:
    gunicorn "wsgi:app" --workers 2 --bind 0.0.0.0:$PORT

Não use este arquivo localmente — use run.py (Waitress).
"""

from dotenv import load_dotenv
load_dotenv()

from config.settings import Config
from app import create_app

app = create_app(Config)
