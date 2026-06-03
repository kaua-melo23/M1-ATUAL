"""
Repository de Auditoria — persiste e consulta o log de ações do sistema.

Timestamps salvos em horário local (sem depender do fuso do SO).
"""

from datetime import datetime, timezone, timedelta
from app.repositories.db import conectar

# UTC-3 (Brasília / Recife — sem horário de verão)
BRT = timezone(timedelta(hours=-3))


def _agora_brt() -> str:
    """Retorna o timestamp atual no fuso BRT como string ISO."""
    return datetime.now(BRT).strftime("%Y-%m-%d %H:%M:%S")


def registrar(usuario: str, role: str, acao: str, detalhes: str = "") -> None:
    """Grava uma entrada de auditoria. Nunca lança exceção — apenas loga."""
    try:
        conn = conectar()
        conn.execute(
            "INSERT INTO auditoria (usuario, role, acao, detalhes, data_hora) VALUES (?, ?, ?, ?, ?)",
            (usuario, role, acao, detalhes, _agora_brt()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Auditoria] ERRO ao registrar: {e}")


def buscar(
    dt_inicio: str | None = None,
    dt_fim: str | None = None,
    usuario: str | None = None,
    acao: str | None = None,
    limite: int = 200,
) -> list[dict]:
    conn = conectar()
    filtros = []
    params: list = []

    if dt_inicio:
        filtros.append("date(data_hora) >= date(?)")
        params.append(dt_inicio)
    if dt_fim:
        filtros.append("date(data_hora) <= date(?)")
        params.append(dt_fim)
    if usuario:
        filtros.append("LOWER(usuario) LIKE ?")
        params.append(f"%{usuario.lower()}%")
    if acao:
        filtros.append("LOWER(acao) LIKE ?")
        params.append(f"%{acao.lower()}%")

    where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    params.append(limite)

    rows = conn.execute(
        f"SELECT * FROM auditoria {where} ORDER BY data_hora DESC LIMIT ?",
        params,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def listar_usuarios_distintos() -> list[str]:
    conn = conectar()
    rows = conn.execute(
        "SELECT DISTINCT usuario FROM auditoria ORDER BY usuario"
    ).fetchall()
    conn.close()
    return [r["usuario"] for r in rows]
