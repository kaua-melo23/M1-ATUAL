"""
Controller de Auditoria — rota /admin/auditoria (apenas admin).
"""

from flask import Blueprint, render_template, request, jsonify, session
from app.middleware.auth import admin_required
from app.repositories import auditoria_repository

auditoria_bp = Blueprint("auditoria_bp", __name__)


@auditoria_bp.route("/admin/auditoria")
@admin_required
def auditoria_index():
    return render_template("admin/auditoria.html")


@auditoria_bp.route("/api/auditoria", methods=["GET"])
@admin_required
def api_auditoria():
    eventos = auditoria_repository.buscar(
        dt_inicio=request.args.get("dt_inicio"),
        dt_fim=request.args.get("dt_fim"),
        usuario=request.args.get("usuario"),
        acao=request.args.get("acao"),
        limite=int(request.args.get("limite", 200)),
    )
    usuarios = auditoria_repository.listar_usuarios_distintos()
    return jsonify({"eventos": eventos, "usuarios": usuarios})
