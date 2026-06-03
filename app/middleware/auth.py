"""
Middleware de autenticação e autorização.

Centraliza decoradores e helpers de verificação de sessão,
eliminando a repetição de `if not session.get('logado')` nas rotas.
"""

from functools import wraps

from flask import session, redirect, request, jsonify, render_template


def login_required(f):
    """Exige usuário autenticado. Para XHR retorna 401 JSON; para browser redireciona."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logado"):
            if _is_api_request():
                return jsonify({"erro": "nao_autenticado", "redirect": "/login"}), 401
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Exige role 'admin'."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logado") or session.get("role") != "admin":
            if _is_api_request():
                return jsonify({"erro": "Não autorizado"}), 401
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated


def permissao_required(*permissoes_necessarias: str):
    """
    Exige que o usuário possua ao menos uma das permissões listadas.
    Admin sempre passa. Para navegação de página (não-API) retorna 403.html.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get("logado"):
                if _is_api_request():
                    return jsonify({"erro": "nao_autenticado"}), 401
                return redirect("/login")

            role = session.get("role", "")
            if role == "admin":
                return f(*args, **kwargs)

            perms = set(session.get("permissoes", []))
            if not perms.intersection(permissoes_necessarias):
                if _is_api_request():
                    return jsonify({"erro": f"Sem permissão: {', '.join(permissoes_necessarias)}"}), 403
                return render_template("admin/403.html",
                                       permissoes_necessarias=permissoes_necessarias), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


def _is_api_request() -> bool:
    """True se a requisição é AJAX/API."""
    return (
        request.path.startswith("/api/")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )
