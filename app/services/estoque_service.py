"""
Service de Estoque — regras de negócio para fabricação, transformação e baixa de estoque.

Melhorias:
- logging em vez de print()
- get_db() via repositories (sem abrir conexão direta aqui)
"""

import logging

from app.repositories import estoque_repository as repo
from app.repositories import produto_repository as prod_repo

logger = logging.getLogger(__name__)


def registrar_entrada_lote(
    insumo_id: int,
    quantidade: float,
    fator_conversao: float,
    validade: str,
    custo: float,
) -> bool:
    """Converte a quantidade pelo fator e grava o lote."""
    quantidade_final = quantidade * fator_conversao
    try:
        repo.inserir_lote(insumo_id, quantidade_final, validade, custo)
        return True
    except Exception as e:
        logger.error("Erro ao registrar lote para insumo %s: %s", insumo_id, e)
        return False


def fabricar_lote(insumo_fabricado_id: int, quantidade_produzida: float, validade: str) -> dict:
    """Desconta brutos conforme receita (PVPS) e gera lote do fabricado."""
    ingredientes = repo.buscar_ingredientes_receita(insumo_fabricado_id, quantidade_produzida)

    if not ingredientes:
        return {"status": "erro", "msg": "Este insumo não tem receita cadastrada."}

    # Valida estoque antes de qualquer desconto
    for ing in ingredientes:
        disponivel = repo.estoque_disponivel(ing["insumo_bruto_id"])
        if disponivel < ing["qtd_necessaria"]:
            return {
                "status": "erro",
                "msg": (
                    f"Estoque insuficiente de '{ing['nome']}'. "
                    f"Necessário: {ing['qtd_necessaria']}, Disponível: {round(disponivel, 2)}"
                ),
            }

    for ing in ingredientes:
        _descontar_pvps(ing["insumo_bruto_id"], ing["qtd_necessaria"])

    repo.inserir_lote(insumo_fabricado_id, quantidade_produzida, validade)
    return {"status": "sucesso", "msg": f"{quantidade_produzida} unidade(s) fabricada(s) com sucesso!"}


def transformar_insumo(pai_id: int, filho_id: int, qtd_pai: float, qtd_filho: float) -> dict:
    """Transforma um insumo em outro (ex.: kg → porções)."""
    lotes = repo.buscar_lotes_ativos(pai_id)

    if not lotes:
        return {"status": "erro", "msg": "Sem estoque disponível ou vencido"}

    primeiro_lote = lotes[0]
    if primeiro_lote["quantidade_atual"] < qtd_pai:
        return {"status": "erro", "msg": "Quantidade insuficiente no lote atual"}

    repo.descontar_lote(primeiro_lote["id"], qtd_pai)
    repo.inserir_lote(filho_id, qtd_filho, primeiro_lote["validade"])
    return {"status": "sucesso", "msg": "Transformação concluída"}


def baixar_estoque_por_produto(nome_produto: str, quantidade_vendida: float):
    """Abate insumos vinculados ao produto. Segue PVPS."""
    produto = prod_repo.buscar_por_nome(nome_produto)
    if not produto:
        return

    vinculos = repo.buscar_vinculos_por_produto_id(produto["id"], quantidade_vendida)

    # Fallback legado: tenta pelo nome do insumo igual ao produto
    if not vinculos:
        insumo = repo.buscar_insumo_por_nome(nome_produto)
        if insumo:
            vinculos = [{"insumo_id": insumo["id"], "qtd_descontar": quantidade_vendida}]

    for v in vinculos:
        _descontar_pvps(v["insumo_id"], v["qtd_descontar"])


# ── Helpers privados ──────────────────────────────────────────────────

def _descontar_pvps(insumo_id: int, quantidade: float):
    """Desconta `quantidade` de um insumo seguindo PVPS."""
    lotes = repo.buscar_lotes_ativos(insumo_id)
    restante = quantidade
    for lote in lotes:
        if restante <= 0:
            break
        desconto = min(restante, lote["quantidade_atual"])
        repo.descontar_lote(lote["id"], desconto)
        restante -= desconto
