"""
Controller de autenticação — login e logout.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, current_app

from app.repositories import gpo_repository

auth_bp = Blueprint("auth_bp", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    erro = None

    if request.method == "POST":
        usuario = request.form.get("username", "").strip()
        senha = request.form.get("password", "")  # NÃO strip — deve bater com o cadastro

        # 1. Admin via variáveis de ambiente (backward compat)
        if usuario == current_app.config["ADMIN_USER"] and senha == current_app.config["ADMIN_PASSWORD"]:
            _iniciar_sessao(user_id=0, role="admin", nome="Administrador", permissoes=[])
            return redirect(url_for("main_bp.admin_page"))

        # 2. Usuários do banco
        user = gpo_repository.verificar_login(usuario, senha)
        if user:
            perms = list(gpo_repository.obter_permissoes_usuario(user["id"]))
            _iniciar_sessao(user["id"], user["role"], user["nome"], perms)

            if user["role"] == "admin" or "acesso_admin" in perms:
                return redirect(url_for("main_bp.admin_page"))
            return redirect("/atendente")

        erro = "Usuário ou senha incorretos."

    return render_template("login.html", erro=erro)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth_bp.login"))


def _iniciar_sessao(user_id: int, role: str, nome: str, permissoes: list):
    session.clear()
    session["logado"] = True
    session["role"] = role
    session["nome"] = nome
    session["user_id"] = user_id
    session["permissoes"] = permissoes
