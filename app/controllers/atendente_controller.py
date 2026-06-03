"""
Controller do Atendente — painel de pedidos do balcão.

Melhorias:
- logging em vez de print()
- Uso de permissao_required onde aplicável
"""

import logging
from flask import Blueprint, render_template, request, jsonify, session, redirect

from app.middleware.auth import login_required, permissao_required
from app.repositories import produto_repository, pedido_repository
from app.services.pedido_service import registrar_pedido_completo

atendente_bp = Blueprint("atendente_bp", __name__)
logger = logging.getLogger(__name__)

_MAPA_PERMISSAO_STATUS = {
    "Preparando": "aceitar_pedidos",
    "Preparado":  "preparar_pedidos",
    "A Caminho":  "despachar_pedidos",
    "Finalizado": "finalizar_pedidos",
}


def _tem_acesso_atendente() -> bool:
    if not session.get("logado"):
        return False
    if session.get("role") == "admin":
        return True
    perms = set(session.get("permissoes", []))
    return bool(perms.intersection({"lancar_pedidos", "ver_pedidos"}))


@atendente_bp.route("/atendente")
def atendente_index():
    if not _tem_acesso_atendente():
        return redirect("/login")
    return render_template(
        "atendente/index.html",
        usuario_nome=session.get("nome", "Atendente"),
        role=session.get("role", ""),
        permissoes=session.get("permissoes", []),
    )


@atendente_bp.route("/api/atendente/produtos")
def api_produtos_atendente():
    if not _tem_acesso_atendente():
        return jsonify({"erro": "Não autorizado"}), 401
    return jsonify(produto_repository.buscar_visiveis())  # cache aplicado


@atendente_bp.route("/api/atendente/pedido", methods=["POST"])
def api_lancar_pedido():
    if not _tem_acesso_atendente():
        return jsonify({"erro": "Não autorizado"}), 401

    role = session.get("role", "")
    perms = session.get("permissoes", [])
    if role != "admin" and "lancar_pedidos" not in perms:
        return jsonify({"erro": "Sem permissão para lançar pedidos"}), 403

    data = request.get_json() or {}
    itens = data.get("itens", [])
    if not itens:
        return jsonify({"erro": "Pedido sem itens"}), 400

    total_itens = sum(i["preco"] * i["quantidade"] for i in itens)
    valor_pago = data.get("valor_pago")  # informado pelo frontend quando pagamento em dinheiro
    pedido = {
        "nome": data.get("cliente_nome", "Balcão"),
        "bairro": "Balcão",
        "endereco": "Retirada no Local",
        "total_itens": total_itens,
        "taxa": 0.0,
        "total_geral": total_itens,
        "metodo": data.get("metodo_pagamento", "Dinheiro"),
        "lancado_por": session.get("user_id"),
        "valor_pago": float(valor_pago) if valor_pago is not None else None,
    }

    pedido_id = registrar_pedido_completo(pedido, itens)
    if not pedido_id:
        return jsonify({"erro": "Erro ao registrar pedido"}), 500

    if data.get("aceitar_automatico"):
        pedido_repository.atualizar_status(pedido_id, "Preparando")

    try:
        from app.services.pedido_service import _tentar_imprimir
        _tentar_imprimir(pedido_id)
    except Exception as exc:
        logger.warning("Erro ao enfileirar impressao (balcao) #%s: %s", pedido_id, exc)

    return jsonify({"ok": True, "pedido_id": pedido_id})


@atendente_bp.route("/api/atendente/pedidos")
def api_pedidos_atendente():
    if not _tem_acesso_atendente():
        return jsonify({"erro": "Não autorizado"}), 401

    role = session.get("role", "")
    perms = set(session.get("permissoes", []))
    user_id = session.get("user_id")

    if role == "admin" or "ver_pedidos" in perms:
        pedidos = pedido_repository.buscar_pedidos()
    else:
        pedidos = pedido_repository.buscar_pedidos(lancado_por=user_id)

    return jsonify(pedidos)


@atendente_bp.route("/api/atendente/pedido/<int:pid>/status", methods=["POST"])
def api_status_atendente(pid):
    if not _tem_acesso_atendente():
        return jsonify({"erro": "Não autorizado"}), 401

    data = request.get_json() or {}
    novo_status = data.get("status", "")
    role = session.get("role", "")
    perms = session.get("permissoes", [])

    perm_necessaria = _MAPA_PERMISSAO_STATUS.get(novo_status)
    if role != "admin" and perm_necessaria and perm_necessaria not in perms:
        return jsonify({"erro": f"Sem permissão: {perm_necessaria}"}), 403

    pedido_repository.atualizar_status(pid, novo_status)

    if novo_status == "Preparando":
        try:
            from app.services.pedido_service import _tentar_imprimir
            _tentar_imprimir(pid)
        except Exception as e:
            logger.warning("Erro ao enfileirar impressão: %s", e)

    return jsonify({"ok": True})
