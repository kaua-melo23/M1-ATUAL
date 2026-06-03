"""
Utilitário de upload de imagens.
"""

import os
import uuid
import logging
from werkzeug.utils import secure_filename
from flask import current_app

logger = logging.getLogger(__name__)


def _extensao_permitida(filename: str) -> bool:
    permitidas = current_app.config.get("ALLOWED_EXTENSIONS", {"png", "jpg", "jpeg", "gif", "webp", "avif"})
    return "." in filename and filename.rsplit(".", 1)[1].lower() in permitidas


def salvar_imagem(arquivo) -> str | None:
    """
    Salva o arquivo de imagem enviado via form e retorna o nome do arquivo salvo.
    Retorna None se nenhum arquivo válido for enviado.
    """
    if not arquivo or not getattr(arquivo, "filename", None):
        return None

    if not _extensao_permitida(arquivo.filename):
        logger.warning("Extensão não permitida: %s", arquivo.filename)
        return None

    ext = arquivo.filename.rsplit(".", 1)[1].lower()
    nome_unico = f"{uuid.uuid4().hex}.{ext}"
    nome_seguro = secure_filename(nome_unico)

    pasta = current_app.config.get("UPLOAD_FOLDER", "static/uploads")
    os.makedirs(pasta, exist_ok=True)

    caminho = os.path.join(pasta, nome_seguro)
    arquivo.save(caminho)
    logger.debug("Imagem salva: %s", caminho)
    return nome_seguro
