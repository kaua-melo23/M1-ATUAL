"""
Service de Complementos — regras de negócio para complementos.

Responsabilidades:
- Calcular preço extra dos adicionais pagos
- Dar baixa no estoque dos insumos vinculados aos complementos
- Montar o payload de complementos para salvar no pedido
"""

from app.repositories import complemento_repository as repo
from app.services.estoque_service import _descontar_pvps


def calcular_total_complementos(itens_escolhidos: list[dict]) -> float:
    """
    Soma o preço extra dos complementos selecionados.
    itens_escolhidos = [{ item_id, quantidade }]
    """
    total_extra = 0.0
    for escolha in itens_escolhidos:
        item = repo.buscar_item_por_id(escolha.get("item_id"))
        if item and item["preco_adicional"] > 0:
            total_extra += item["preco_adicional"] * escolha.get("quantidade", 1)
    return round(total_extra, 2)


def montar_complementos_para_salvar(
    pedido_id: int, itens_carrinho: list[dict]
) -> list[dict]:
    """
    Converte a lista de itens do carrinho (com complementos aninhados)
    para o formato flat do banco de dados.

    Cada item do carrinho pode ter:
      item["complementos"] = [{ item_id, quantidade, preco_unitario }]
    """
    registros = []
    for item in itens_carrinho:
        for comp in item.get("complementos", []):
            registros.append({
                "pedido_id": pedido_id,
                "item_complemento_id": comp["item_id"],
                "quantidade": comp.get("quantidade", 1),
                "preco_unitario": comp.get("preco_unitario", 0),
            })
    return registros


def baixar_estoque_complementos(itens_carrinho: list[dict]):
    """
    Desconta o estoque dos insumos vinculados aos complementos escolhidos.
    Segue a mesma lógica PVPS do restante do sistema.
    """
    for item in itens_carrinho:
        for comp in item.get("complementos", []):
            item_db = repo.buscar_item_por_id(comp.get("item_id"))
            if item_db and item_db.get("insumo_id"):
                quantidade = comp.get("quantidade", 1)
                _descontar_pvps(item_db["insumo_id"], quantidade)


def validar_complementos_obrigatorios(produto_id: int, itens_escolhidos: list[dict]) -> str | None:
    """
    Verifica se todos os grupos obrigatórios do produto foram preenchidos.
    Retorna mensagem de erro ou None se estiver tudo ok.
    """
    grupos = repo.buscar_grupos_do_produto(produto_id, apenas_ativos=True)
    ids_escolhidos = {c["item_id"] for c in itens_escolhidos}

    for grupo in grupos:
        if not grupo.get("obrigatorio"):
            continue
        ids_do_grupo = {i["id"] for i in grupo.get("itens", [])}
        if not ids_do_grupo.intersection(ids_escolhidos):
            return f"Escolha pelo menos um item de '{grupo['grupo_nome']}'"

    return None
