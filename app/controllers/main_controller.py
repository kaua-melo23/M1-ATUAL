"""
Controller principal — rotas públicas do cardápio.

Melhorias:
- Dados do cardápio público servidos via cache (produto_repository já cacheia)
- Menos queries por requisição na rota index
"""

from flask import Blueprint, render_template, session, redirect, url_for

from app.repositories import produto_repository, config_repository
from app.middleware.auth import login_required, permissao_required

main_bp = Blueprint("main_bp", __name__)


@main_bp.route("/")
def index():
    """Cardápio público — dados cacheados em memória."""
    produtos = produto_repository.buscar_visiveis()        # cache 2min
    configs = config_repository.buscar_configuracoes()     # cache 5min
    categorias = config_repository.buscar_categorias(apenas_ativas=True)  # cache 3min
    return render_template("index.html", produtos=produtos, configs=configs, categorias=categorias)


@main_bp.route("/revisar")
def revisar():
    configs = config_repository.buscar_configuracoes()
    return render_template("revisar.html", configs=configs)


@main_bp.route("/admin_dashboard")
@login_required
def admin_page():
    return render_template("admin/dashboard.html")


@main_bp.route("/admin/relatorios")
@login_required
@permissao_required("pg_relatorios", "acesso_admin")
def admin_relatorios():
    return render_template("admin/relatorios.html")
