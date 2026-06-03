"""
Controller de Vendas — geração de PIX, webhook e pedidos presenciais.

Melhorias:
- logging em vez de print()
- Tratamento de erro mais explícito no webhook
"""

import logging
from flask import Blueprint, request, jsonify

from app.services import pedido_service, pagamento_service
from app.repositories import pedido_repository

vendas_bp = Blueprint("vendas_bp", __name__)
logger = logging.getLogger(__name__)


@vendas_bp.route("/api/pagamento/gerar_pix", methods=["POST"])
def gerar_pix():
    """Gera o PIX com validade de 4 minutos. O pedido NÃO é salvo aqui."""
    try:
        dados = request.get_json() or {}
        total = float(dados.get("total", 0))
        resultado = pagamento_service.gerar_pix(total, dados)
        if "erro" in resultado:
            return jsonify(resultado), 400
        return jsonify(resultado)
    except Exception as e:
        logger.error("Erro ao gerar PIX: %s", e)
        return jsonify({"error": str(e)}), 500


@vendas_bp.route("/api/webhook", methods=["POST"])
def webhook():
    """Webhook do Mercado Pago. Pedido só é registrado se aprovado."""
    try:
        body = request.get_json(silent=True, force=True) or {}
        id_recurso = request.args.get("data.id") or body.get("data", {}).get("id")

        if not id_recurso:
            return jsonify({"status": "ok"}), 200

        pagamento = pagamento_service.consultar_pagamento(id_recurso)
        if not pagamento:
            return jsonify({"status": "ok"}), 200

        if pagamento.get("status") == "approved":
            dados_originais = pagamento.get("metadata", {}).get("dados_pedido")
            if dados_originais:
                pedido_service.processar_pedido_pago(dados_originais, id_recurso)

    except Exception as e:
        logger.error("Erro no webhook: %s", e)

    return jsonify({"status": "ok"}), 200


@vendas_bp.route("/api/pedidos/presencial", methods=["POST"])
def pedido_presencial():
    """Rota para pagamentos em Dinheiro ou Cartão."""
    try:
        dados = request.get_json() or {}
        pedido_id = pedido_service.processar_pedido_presencial(dados)
        if pedido_id:
            return jsonify({"status": "success", "id": pedido_id})
        return jsonify({"error": "Erro ao salvar pedido"}), 500
    except Exception as e:
        logger.error("Erro ao registrar pedido presencial: %s", e)
        return jsonify({"error": str(e)}), 500


@vendas_bp.route("/api/pagamento/status/<id_mp>")
def checar_status_pix(id_mp):
    """O frontend chama para verificar se o PIX foi pago."""
    try:
        pedido = pedido_repository.buscar_por_id_mp(id_mp)
        if pedido:
            return jsonify({"pago": True, "pedido_id": pedido["id"], "status": pedido["status"]})
        return jsonify({"pago": False})
    except Exception as e:
        logger.error("Erro ao checar status PIX %s: %s", id_mp, e)
        return jsonify({"error": str(e)}), 500
