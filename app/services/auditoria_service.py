"""
Service de Auditoria — ponto central para registrar ações críticas.

Uso em qualquer controller:
    from app.services.auditoria_service import auditar
    auditar(session, "criou_produto", f"Produto '{nome}' id={id}")
"""

import json
from flask import session as flask_session
from app.repositories import auditoria_repository


def auditar(session: dict, acao: str, detalhes: str | dict = "") -> None:
    """
    Registra uma ação de auditoria.
    - session: dict-like (flask.session ou dict manual)
    - acao: string descritiva ex: 'criou_produto', 'editou_preco'
    - detalhes: string ou dict (será serializado para JSON se dict)
    """
    usuario = session.get("nome") or session.get("username") or "desconhecido"
    role = session.get("role", "")
    if isinstance(detalhes, dict):
        detalhes = json.dumps(detalhes, ensure_ascii=False)
    auditoria_repository.registrar(usuario, role, acao, str(detalhes))
