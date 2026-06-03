"""
Service de Pedidos — regras de negócio para criação e processamento de pedidos.

Melhorias:
- logging em vez de print()
- _tentar_imprimir busca pedido por ID direto (sem varrer lista inteira)
"""

import logging

from app.repositories import pedido_repository as repo
from app.services.estoque_service import baixar_estoque_por_produto
from app.services.complemento_service import (
    montar_complementos_para_salvar,
    baixar_estoque_complementos,
)
from app.repositories import complemento_repository as comp_repo
from app.utils.notificacoes import enviar_pedido_whatsapp

logger = logging.getLogger(__name__)


def registrar_pedido_completo(dados: dict, itens: list[dict]) -> int | bool:
    """Persiste o pedido e seus itens."""
    return repo.inserir_pedido(dados, itens)


def processar_pedido_pago(dados_originais: dict, id_mp: str) -> int | None:
    """
    Executa o fluxo completo após confirmação de pagamento PIX:
    1. Idempotência — evita duplicatas pelo id_mp
    2. Registra o pedido
    3. Vincula o ID do Mercado Pago
    4. Baixa estoque e complementos
    5. Atualiza status e notifica
    """
    if repo.buscar_por_id_mp(id_mp):
        return None

    dados_pedido = _mapear_dados_pedido(dados_originais, metodo="PIX")
    itens = dados_originais.get("itens_detalhados", [])

    pedido_id = repo.inserir_pedido(dados_pedido, itens)
    if not pedido_id:
        return None

    repo.vincular_id_mp(pedido_id, id_mp)
    _finalizar_pedido(pedido_id, itens, status="Pago")
    _tentar_imprimir(pedido_id)
    logger.info("Pedido #%s criado e aprovado via PIX.", pedido_id)
    return pedido_id


def processar_pedido_presencial(dados: dict) -> int | None:
    """Registra pedido pago presencialmente (dinheiro/cartão)."""
    dados_pedido = _mapear_dados_pedido(dados, metodo=dados.get("metodo", "DINHEIRO").upper())
    itens = dados.get("itens_detalhados", [])

    pedido_id = repo.inserir_pedido(dados_pedido, itens)
    if not pedido_id:
        return None

    _finalizar_pedido(pedido_id, itens, status="Confirmado")
    _tentar_imprimir(pedido_id)
    return pedido_id


def _mapear_dados_pedido(dados: dict, metodo: str) -> dict:
    return {
        "nome": dados.get("nome_cliente") or dados.get("cliente_nome") or "Cliente",
        "bairro": dados.get("bairro", ""),
        "endereco": dados.get("endereco", "Retirada"),
        "total_itens": float(dados.get("total_produtos", 0)),
        "taxa": float(dados.get("taxa_entrega", 0)),
        "total_geral": float(dados.get("total", 0)),
        "metodo": metodo,
        "valor_pago": dados.get("valor_pago"),  # None para PIX/cartao
    }


def _finalizar_pedido(pedido_id: int, itens: list[dict], status: str):
    """Baixa estoque, salva complementos, atualiza status e notifica."""
    for item in itens:
        baixar_estoque_por_produto(item.get("nome", ""), item.get("quantidade", 0))

    registros = montar_complementos_para_salvar(pedido_id, itens)
    if registros:
        comp_repo.salvar_complementos_pedido(pedido_id, registros)
    baixar_estoque_complementos(itens)

    repo.atualizar_status(pedido_id, status)
    enviar_pedido_whatsapp(pedido_id)


def _tentar_imprimir(pedido_id: int):
    """
    Verifica se deve imprimir e enfileira.
    Busca pedido diretamente por ID — sem varrer toda a lista.
    """
    try:
        from app.printer.service import enfileirar_impressao
        pedido = repo.buscar_por_id(pedido_id)
        if not pedido:
            logger.warning("Pedido #%s não encontrado para impressão.", pedido_id)
            return
        pedido["itens"] = repo.buscar_itens(pedido_id)
        enfileirar_impressao(pedido)
    except Exception as e:
        logger.warning("Erro ao enfileirar impressão para pedido #%s: %s", pedido_id, e)
