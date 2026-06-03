"""
Controller de Complementos — APIs para admin e cardápio público.
"""

from flask import Blueprint, request, jsonify

from app.middleware.auth import login_required
from app.repositories import complemento_repository as repo
from app.repositories import produto_repository

complemento_bp = Blueprint("complemento_bp", __name__)


# ══════════════════════════════════════════════════════════════════════
# APIs PÚBLICAS (cardápio do cliente)
# ══════════════════════════════════════════════════════════════════════

@complemento_bp.route("/api/complementos/produto/<int:produto_id>")
def api_complementos_produto(produto_id):
    """Retorna grupos e itens disponíveis de um produto (para o modal do cliente)."""
    grupos = repo.buscar_grupos_do_produto(produto_id, apenas_ativos=True)
    return jsonify(grupos)


@complemento_bp.route("/api/complementos/produtos/bulk")
def api_complementos_bulk():
    """
    Retorna complementos de vários produtos de uma vez.
    Usado no carregamento do cardápio para evitar N+1 requests.
    Query param: ids=1,2,3
    """
    ids_str = request.args.get("ids", "")
    try:
        ids = [int(x) for x in ids_str.split(",") if x.strip()]
    except ValueError:
        return jsonify({}), 400

    resultado = repo.buscar_complementos_por_produto_ids(ids)
    return jsonify(resultado)


# ══════════════════════════════════════════════════════════════════════
# ADMIN — Grupos
# ══════════════════════════════════════════════════════════════════════

@complemento_bp.route("/api/admin/complementos/produtos-montaveis", methods=["GET"])
@login_required
def api_produtos_montaveis():
    """Retorna produtos com grupos de complemento vinculados (fluxo montável)."""
    return jsonify(repo.buscar_produtos_montaveis())


@complemento_bp.route("/api/admin/complementos/grupos", methods=["GET"])
@login_required
def api_listar_grupos():
    grupos = repo.buscar_grupos()
    # Inclui contagem de itens em cada grupo
    for g in grupos:
        g["itens"] = repo.buscar_itens_do_grupo(g["id"])
    return jsonify(grupos)


@complemento_bp.route("/api/admin/complementos/grupos", methods=["POST"])
@login_required
def api_criar_grupo():
    d = request.get_json()
    nome = (d.get("nome") or "").strip()
    if not nome:
        return jsonify({"ok": False, "erro": "Nome obrigatório"}), 400
    novo_id = repo.inserir_grupo(nome, d.get("descricao", ""))
    return jsonify({"ok": True, "id": novo_id})


@complemento_bp.route("/api/admin/complementos/grupos/<int:grupo_id>", methods=["PUT"])
@login_required
def api_atualizar_grupo(grupo_id):
    d = request.get_json()
    repo.atualizar_grupo(
        grupo_id,
        d.get("nome", ""),
        d.get("descricao", ""),
        int(d.get("ativo", 1)),
    )
    return jsonify({"ok": True})


@complemento_bp.route("/api/admin/complementos/grupos/<int:grupo_id>", methods=["DELETE"])
@login_required
def api_deletar_grupo(grupo_id):
    repo.deletar_grupo(grupo_id)
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════════
# ADMIN — Itens dentro de um grupo
# ══════════════════════════════════════════════════════════════════════

@complemento_bp.route("/api/admin/complementos/grupos/<int:grupo_id>/itens", methods=["GET"])
@login_required
def api_listar_itens(grupo_id):
    return jsonify(repo.buscar_itens_do_grupo(grupo_id))


@complemento_bp.route("/api/admin/complementos/grupos/<int:grupo_id>/itens", methods=["POST"])
@login_required
def api_criar_item(grupo_id):
    d = request.get_json()
    nome = (d.get("nome") or "").strip()
    if not nome:
        return jsonify({"ok": False, "erro": "Nome obrigatório"}), 400
    novo_id = repo.inserir_item(
        grupo_id,
        nome,
        float(d.get("preco_adicional", 0)),
        d.get("insumo_id") or None,
    )
    return jsonify({"ok": True, "id": novo_id})


@complemento_bp.route("/api/admin/complementos/itens/<int:item_id>", methods=["PUT"])
@login_required
def api_atualizar_item(item_id):
    d = request.get_json()
    repo.atualizar_item(
        item_id,
        d.get("nome", ""),
        float(d.get("preco_adicional", 0)),
        d.get("insumo_id") or None,
        int(d.get("disponivel", 1)),
    )
    return jsonify({"ok": True})


@complemento_bp.route("/api/admin/complementos/itens/<int:item_id>", methods=["DELETE"])
@login_required
def api_deletar_item(item_id):
    repo.deletar_item(item_id)
    return jsonify({"ok": True})


@complemento_bp.route("/api/admin/complementos/itens/<int:item_id>/disponibilidade", methods=["POST"])
@login_required
def api_toggle_disponibilidade(item_id):
    """Liga/desliga disponibilidade de um item no cardápio."""
    novo_valor = repo.alternar_disponibilidade(item_id)
    return jsonify({"ok": True, "disponivel": novo_valor})


# ══════════════════════════════════════════════════════════════════════
# ADMIN — Vínculo Produto ↔ Grupo
# ══════════════════════════════════════════════════════════════════════

@complemento_bp.route("/api/admin/complementos/produto/<int:produto_id>/grupos", methods=["GET"])
@login_required
def api_grupos_do_produto(produto_id):
    return jsonify(repo.buscar_grupos_do_produto(produto_id))


@complemento_bp.route("/api/admin/complementos/produto/<int:produto_id>/grupos", methods=["POST"])
@login_required
def api_vincular_grupo(produto_id):
    d = request.get_json()
    grupo_id = d.get("grupo_id")
    tipo = d.get("tipo", "incluso")  # 'incluso' ou 'adicional'
    obrigatorio = int(d.get("obrigatorio", 0))

    if tipo not in ("incluso", "adicional"):
        return jsonify({"ok": False, "erro": "tipo deve ser 'incluso' ou 'adicional'"}), 400

    repo.vincular_grupo_produto(produto_id, grupo_id, tipo, obrigatorio)
    return jsonify({"ok": True})


@complemento_bp.route("/api/admin/complementos/produto/<int:produto_id>/grupos/<int:grupo_id>", methods=["DELETE"])
@login_required
def api_desvincular_grupo(produto_id, grupo_id):
    repo.desvincular_grupo_produto(produto_id, grupo_id)
    return jsonify({"ok": True})
