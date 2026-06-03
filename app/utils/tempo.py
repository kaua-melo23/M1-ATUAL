"""
Utilitário de tempo — retorna data/hora no fuso configurado pelo admin.
"""

from datetime import datetime, timezone, timedelta


def get_agora_str() -> str:
    """
    Retorna data/hora atual no fuso horário configurado em 'configuracoes' (offset_fuso).
    Padrão: -3 (America/Recife, Fortaleza, etc.)
    """
    from app.repositories.config_repository import buscar_configuracoes
    try:
        configs = buscar_configuracoes()
        offset = int(configs.get("offset_fuso", -3))
    except Exception:
        offset = -3

    tz = timezone(timedelta(hours=offset))
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


def get_offset_fuso() -> int:
    """Retorna o offset do fuso configurado (ex: -3 para Recife)."""
    from app.repositories.config_repository import buscar_configuracoes
    try:
        return int(buscar_configuracoes().get("offset_fuso", -3))
    except Exception:
        return -3
