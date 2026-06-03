"""
Controller Admin — rotas do painel administrativo.

Melhorias:
- /admin/diagnostico usa get_db() em vez de abrir conexão avulsa
- Logging em vez de prints
- Validação de entrada na criação de produto
- Imports organizados
"""

import logging
from flask import Blueprint, request, jsonify, session, render_template

from app.middleware.auth import login_required, permissao_required
from app.repositories import (
    produto_repository,
    config_repository,
    estoque_repository,
    pedido_repository,
)
from app.repositories.db import get_db
from app.services import estoque_service
from app.utils.uploads import salvar_imagem

admin_bp = Blueprint("admin_bp", __name__)
logger = logging.getLogger(__name__)

CAMPOS_CONFIG_PERMITIDOS = {
    "nome_lanchonete", "slogan", "cor_primaria", "cor_texto_header",
    "logo_url", "hora_abertura", "hora_fechamento", "offset_fuso",
}

# ── Páginas ───────────────────────────────────────────────────────────

@admin_bp.route("/admin")
@login_required
@permissao_required("pg_dashboard", "acesso_admin")
def dashboard():
    return render_template("admin/dashboard.html")


@admin_bp.route("/admin/complementos")
@login_required
@permissao_required("pg_complementos", "acesso_admin")
def admin_complementos():
    return render_template("admin/complementos.html")


@admin_bp.route("/admin/produtos")
@login_required
@permissao_required("pg_produtos", "acesso_admin")
def admin_produtos():
    return render_template("admin/produtos.html")


@admin_bp.route("/admin/pedidos")
@login_required
@permissao_required("pg_pedidos", "acesso_admin")
def admin_pedidos():
    return render_template("admin/pedidos.html")


@admin_bp.route("/admin/diagnostico-pedidos")
@login_required
@permissao_required("pg_diagnostico", "acesso_admin")
def admin_diagnostico():
    return render_template("admin/diagnostico.html")


@admin_bp.route("/admin/taxas")
@login_required
@permissao_required("pg_taxas", "acesso_admin")
def admin_taxas():
    return render_template("admin/taxas.html")


@admin_bp.route("/admin/estoque")
@login_required
@permissao_required("pg_estoque", "acesso_admin")
def admin_estoque():
    return render_template("admin/estoque.html")


@admin_bp.route("/admin/aparencia")
@login_required
@permissao_required("pg_aparencia", "acesso_admin")
def admin_aparencia():
    configs = config_repository.buscar_configuracoes()
    return render_template("admin/aparencia.html", configs=configs)


@admin_bp.route("/admin/navegacao")
@login_required
@permissao_required("pg_navegacao", "acesso_admin")
def admin_navegacao():
    return render_template(
        "admin/navegacao.html",
        categorias=config_repository.buscar_categorias(),
        menu_admin=config_repository.buscar_menu_admin(),
    )


# ── API: Diagnóstico ──────────────────────────────────────────────────

@admin_bp.route("/admin/diagnostico")
@login_required
def diagnostico():
    conn = get_db()
    pedidos = conn.execute(
        "SELECT id, cliente_nome, status, data_hora, total_geral FROM pedidos ORDER BY id DESC LIMIT 10"
    ).fetchall()
    itens_count = conn.execute("SELECT COUNT(*) FROM itens_pedido").fetchone()[0]
    return jsonify({
        "total_pedidos": len(pedidos),
        "total_itens_no_banco": itens_count,
        "sessao_ativa": bool(session.get("logado")),
        "ultimos_pedidos": [dict(p) for p in pedidos],
    })


# ── API: Configurações ────────────────────────────────────────────────

@admin_bp.route("/api/configuracoes", methods=["GET"])
def api_get_configuracoes():
    return jsonify(config_repository.buscar_configuracoes())


@admin_bp.route("/api/configuracoes", methods=["POST"])
@login_required
def api_salvar_configuracoes():
    dados = request.get_json() or {}
    dados_filtrados = {k: v for k, v in dados.items() if k in CAMPOS_CONFIG_PERMITIDOS}
    config_repository.salvar_configuracoes(dados_filtrados)
    return jsonify({"status": "sucesso"})


@admin_bp.route("/api/upload/logo", methods=["POST"])
@login_required
def api_upload_logo():
    """Recebe um arquivo de imagem e salva como logo da lanchonete."""
    arquivo = request.files.get("logo")
    nome = salvar_imagem(arquivo)
    if not nome:
        return jsonify({"erro": "Arquivo inválido ou extensão não permitida."}), 400

    url_relativa = f"/static/uploads/{nome}"
    config_repository.salvar_configuracoes({"logo_url": url_relativa})
    return jsonify({"status": "sucesso", "logo_url": url_relativa})


# ── API: Categorias ───────────────────────────────────────────────────

@admin_bp.route("/api/categorias", methods=["GET"])
def api_listar_categorias():
    return jsonify(config_repository.buscar_categorias())


@admin_bp.route("/api/categorias", methods=["POST"])
@login_required
def api_criar_categoria():
    dados = request.get_json() or {}
    config_repository.inserir_categoria(dados.get("nome", ""), dados.get("emoji", "🍽️"))
    return jsonify({"status": "sucesso"})


@admin_bp.route("/api/categorias/<int:cat_id>", methods=["PUT"])
@login_required
def api_atualizar_categoria(cat_id):
    dados = request.get_json() or {}
    config_repository.atualizar_categoria(
        cat_id, dados.get("nome", ""), dados.get("emoji", "🍽️"), dados.get("ativo", 1)
    )
    return jsonify({"status": "sucesso"})


@admin_bp.route("/api/categorias/<int:cat_id>", methods=["DELETE"])
@login_required
def api_deletar_categoria(cat_id):
    config_repository.deletar_categoria(cat_id)
    return jsonify({"status": "sucesso"})


@admin_bp.route("/api/categorias/reordenar", methods=["POST"])
@login_required
def api_reordenar_categorias():
    dados = request.get_json() or {}
    config_repository.reordenar_categorias(dados.get("ids", []))
    return jsonify({"status": "sucesso"})


# ── API: Menu Admin ───────────────────────────────────────────────────

@admin_bp.route("/api/menu-admin", methods=["GET"])
@login_required
def api_listar_menu_admin():
    return jsonify(config_repository.buscar_menu_admin())


@admin_bp.route("/api/menu-admin/<int:item_id>", methods=["PUT"])
@login_required
def api_atualizar_item_menu(item_id):
    dados = request.get_json() or {}
    config_repository.atualizar_item_menu(
        item_id, dados.get("label", ""), dados.get("emoji", "📄"), dados.get("visivel", 1)
    )
    return jsonify({"status": "sucesso"})


@admin_bp.route("/api/menu-admin/reordenar", methods=["POST"])
@login_required
def api_reordenar_menu_admin():
    dados = request.get_json() or {}
    config_repository.reordenar_menu_admin(dados.get("ids", []))
    return jsonify({"status": "sucesso"})


# ── API: Produtos ─────────────────────────────────────────────────────

@admin_bp.route("/api/produtos", methods=["GET"])
@login_required
def api_listar_produtos():
    return jsonify(produto_repository.buscar_todos())


@admin_bp.route("/api/produtos", methods=["POST"])
@login_required
def api_criar_produto():
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        return jsonify({"status": "erro", "msg": "Nome é obrigatório"}), 400
    try:
        preco = float(request.form.get("preco", 0))
    except ValueError:
        return jsonify({"status": "erro", "msg": "Preço inválido"}), 400

    categoria = request.form.get("categoria", "")
    ingredientes = request.form.get("ingredientes", "")
    nome_foto = salvar_imagem(request.files.get("foto")) or "default.jpg"

    produto_repository.inserir(nome, preco, categoria, nome_foto, ingredientes)
    return jsonify({"status": "sucesso"})


@admin_bp.route("/api/produtos/editar/<int:produto_id>", methods=["POST"])
@login_required
def api_editar_produto(produto_id):
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        return jsonify({"status": "erro", "msg": "Nome é obrigatório"}), 400
    try:
        preco = float(request.form.get("preco", 0))
    except ValueError:
        return jsonify({"status": "erro", "msg": "Preço inválido"}), 400

    categoria = request.form.get("categoria", "")
    ingredientes = request.form.get("ingredientes", "")
    visivel = int(request.form.get("visivel", 1))
    nome_foto = salvar_imagem(request.files.get("foto"))

    produto_repository.atualizar(produto_id, nome, preco, categoria, nome_foto, ingredientes, visivel)
    return jsonify({"status": "sucesso"})


@admin_bp.route("/api/produtos/<int:produto_id>", methods=["DELETE"])
@login_required
def api_deletar_produto(produto_id):
    produto_repository.deletar(produto_id)
    return jsonify({"status": "sucesso"})


# ── API: Insumos e Estoque ────────────────────────────────────────────

@admin_bp.route("/api/insumos", methods=["GET"])
@login_required
def api_listar_insumos():
    tipo = request.args.get("tipo")
    return jsonify(estoque_repository.buscar_insumos(tipo))


@admin_bp.route("/api/insumos", methods=["POST"])
@login_required
def api_criar_insumo():
    dados = request.get_json() or {}
    novo_id = estoque_repository.inserir_insumo(
        nome=dados.get("nome"),
        unidade_base=dados.get("unidade_base"),
        estoque_minimo=float(dados.get("estoque_minimo", 0)),
        tipo=dados.get("tipo", "bruto"),
        validade_padrao=dados.get("validade_padrao"),
    )
    return jsonify({"status": "sucesso", "id": novo_id})


@admin_bp.route("/api/insumos/<int:insumo_id>", methods=["PUT"])
@login_required
def api_atualizar_insumo(insumo_id):
    dados = request.get_json() or {}
    estoque_repository.atualizar_insumo(
        insumo_id, dados.get("nome"), dados.get("unidade_base"),
        float(dados.get("estoque_minimo", 0)), dados.get("validade_padrao"),
    )
    return jsonify({"status": "sucesso"})


@admin_bp.route("/api/insumos/<int:insumo_id>", methods=["DELETE"])
@login_required
def api_deletar_insumo(insumo_id):
    estoque_repository.deletar_insumo(insumo_id)
    return jsonify({"status": "sucesso"})


@admin_bp.route("/api/insumos/<int:insumo_id>/lotes", methods=["GET"])
@login_required
def api_lotes_insumo(insumo_id):
    return jsonify(estoque_repository.buscar_lotes(insumo_id))


@admin_bp.route("/api/insumos/entrada", methods=["POST"])
@login_required
def api_entrada_estoque():
    dados = request.get_json() or {}
    sucesso = estoque_service.registrar_entrada_lote(
        insumo_id=dados.get("insumo_id"),
        quantidade=float(dados.get("quantidade")),
        fator_conversao=float(dados.get("fator_conversao", 1)),
        validade=dados.get("validade"),
        custo=float(dados.get("custo", 0)),
    )
    return jsonify({"status": "sucesso" if sucesso else "erro"})


@admin_bp.route("/api/insumos/fabricar", methods=["POST"])
@login_required
def api_fabricar():
    dados = request.get_json() or {}
    resultado = estoque_service.fabricar_lote(
        insumo_fabricado_id=int(dados.get("insumo_fabricado_id")),
        quantidade_produzida=float(dados.get("quantidade")),
        validade=dados.get("validade"),
    )
    return jsonify(resultado)


@admin_bp.route("/api/insumos/transformar", methods=["POST"])
@login_required
def api_transformar_insumo():
    dados = request.get_json() or {}
    resultado = estoque_service.transformar_insumo(
        pai_id=dados.get("insumo_pai_id"),
        filho_id=dados.get("insumo_filho_id"),
        qtd_pai=float(dados.get("qtd_pai_gasta")),
        qtd_filho=float(dados.get("qtd_filho_gerada")),
    )
    return jsonify(resultado)


@admin_bp.route("/api/receitas/<int:insumo_id>", methods=["GET"])
@login_required
def api_get_receita(insumo_id):
    return jsonify(estoque_repository.buscar_receita(insumo_id))


@admin_bp.route("/api/receitas/<int:insumo_id>", methods=["POST"])
@login_required
def api_salvar_receita(insumo_id):
    dados = request.get_json() or {}
    estoque_repository.salvar_receita(insumo_id, dados.get("ingredientes", []))
    return jsonify({"status": "sucesso"})


@admin_bp.route("/api/produto_insumos/<int:produto_id>", methods=["GET"])
@login_required
def api_get_produto_insumos(produto_id):
    return jsonify(estoque_repository.buscar_vinculos_produto(produto_id))


@admin_bp.route("/api/produto_insumos/<int:produto_id>", methods=["POST"])
@login_required
def api_salvar_produto_insumos(produto_id):
    dados = request.get_json() or {}
    estoque_repository.salvar_vinculos_produto(produto_id, dados.get("insumos", []))
    return jsonify({"status": "sucesso"})


@admin_bp.route("/api/estoque/alertas", methods=["GET"])
@login_required
def api_alertas_estoque():
    return jsonify(estoque_repository.buscar_alertas_estoque())


# ── API: Pedidos ──────────────────────────────────────────────────────

@admin_bp.route("/api/listar_pedidos")
@login_required
def api_listar_pedidos():
    hora_inicio = request.args.get("hora_inicio", type=int)
    dt_inicio = request.args.get("dt_inicio")
    dt_fim = request.args.get("dt_fim")
    pedidos = pedido_repository.buscar_pedidos(
        hora_inicio=hora_inicio, dt_inicio=dt_inicio, dt_fim=dt_fim
    )
    return jsonify(pedidos)


@admin_bp.route("/api/excluir_pedido/<int:pedido_id>", methods=["DELETE"])
@login_required
def api_excluir_pedido(pedido_id):
    try:
        pedido_repository.deletar(pedido_id)
        return jsonify({"success": True})
    except Exception as e:
        logger.error("Erro ao excluir pedido #%s: %s", pedido_id, e)
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/api/pedido_status/<int:pedido_id>", methods=["POST"])
@login_required
def api_alterar_status(pedido_id):
    dados = request.get_json() or {}
    pedido_repository.atualizar_status(pedido_id, dados.get("status"))
    return jsonify({"success": True})


# ── API: Taxas ────────────────────────────────────────────────────────

@admin_bp.route("/api/taxas", methods=["GET", "POST"])
@login_required
def api_gerenciar_taxas():
    if request.method == "POST":
        bairro = (request.form.get("bairro") or "").strip()
        if not bairro:
            return jsonify({"status": "erro", "msg": "Bairro é obrigatório"}), 400
        try:
            taxa = float(request.form.get("taxa", 0))
        except ValueError:
            return jsonify({"status": "erro", "msg": "Taxa inválida"}), 400
        config_repository.salvar_taxa(bairro, taxa)
        return jsonify({"status": "sucesso"})
    return jsonify(config_repository.buscar_taxas())


@admin_bp.route("/api/taxas/<int:taxa_id>", methods=["DELETE"])
@login_required
def api_deletar_taxa(taxa_id):
    config_repository.deletar_taxa(taxa_id)
    return jsonify({"status": "sucesso"})


# ── API: Cache (admin only) ───────────────────────────────────────────

@admin_bp.route("/api/cache/stats", methods=["GET"])
@login_required
def api_cache_stats():
    """Informações sobre o cache em memória."""
    from app.utils.cache import cache
    return jsonify(cache.stats())


@admin_bp.route("/api/cache/limpar", methods=["POST"])
@login_required
def api_cache_limpar():
    """Limpa todo o cache em memória (útil após alterações em massa)."""
    from app.utils.cache import cache
    cache.limpar()
    logger.info("Cache limpo manualmente por %s", session.get("nome"))
    return jsonify({"status": "sucesso", "msg": "Cache limpo."})
