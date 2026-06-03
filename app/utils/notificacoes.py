"""
Utilitários de notificação (WhatsApp, e-mail, etc.).

Atualmente simulado via logging — substitua pelo SDK real quando necessário.
Para WhatsApp real: Twilio, Z-API, Evolution API, etc.
"""

import logging

logger = logging.getLogger(__name__)


def enviar_pedido_whatsapp(pedido_id: int) -> None:
    """
    Gera e loga o resumo do pedido no formato WhatsApp.
    Para integração real, substitua o logger.info pela chamada à API de mensagens.
    """
    try:
        from app.repositories import pedido_repository

        pedido = pedido_repository.buscar_por_id(pedido_id)
        if not pedido:
            logger.warning("[WhatsApp] Pedido #%s não encontrado", pedido_id)
            return

        itens = pedido_repository.buscar_itens(pedido_id)
        resumo_itens = "\n".join(
            f"- {i['quantidade']}x {i['produto_nome']}" for i in itens
        )

        mensagem = (
            f"🔔 *NOVO PEDIDO #{pedido_id}*\n\n"
            f"👤 *Cliente:* {pedido['cliente_nome']}\n"
            f"📍 *Endereço:* {pedido['endereco']}\n"
            f"💳 *Método:* {pedido['metodo_pagamento']}\n"
            f"--------------------------\n"
            f"🛒 *Itens:*\n{resumo_itens}\n"
            f"--------------------------\n"
            f"💰 *Total:* R$ {pedido['total_geral']:.2f}\n"
            f"🆔 *Cód. Pedido:* #{pedido_id}"
        )

        # TODO: substitua este log pela chamada real à API de WhatsApp
        logger.info("[WhatsApp] Mensagem para pedido #%s:\n%s", pedido_id, mensagem)

    except Exception as e:
        logger.error("[WhatsApp] Erro ao processar pedido #%s: %s", pedido_id, e)
