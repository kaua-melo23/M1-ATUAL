"""
Controller da impressora — rotas usadas pelo template impressora.html

  GET  /admin/impressora                → página
  GET  /api/impressora/windows          → lista impressoras Windows instaladas
  POST /api/impressora/config           → salva configuração
  GET  /api/impressora/teste            → imprime página de teste
"""
from flask import Blueprint, jsonify, render_template, request
from app.middleware.auth import login_required, permissao_required
from app.printer.service import (
    carregar_config,
    salvar_config,
    testar_impressora,
    listar_impressoras_windows,
)

# strict_slashes=False faz o Blueprint aceitar /rota e /rota/ sem 404
impressora_bp = Blueprint("impressora", __name__, url_prefix="")
impressora_bp.url_value_preprocessor  # garante compatibilidade


@impressora_bp.get("/admin/impressora")
@impressora_bp.get("/admin/impressora/")
@login_required
@permissao_required("pg_impressora", "acesso_admin")
def pagina():
    config = carregar_config()
    return render_template("admin/impressora.html", config=config)


@impressora_bp.get("/api/impressora/windows")
@impressora_bp.get("/api/impressora/windows/")
def listar_windows():
    """Retorna as impressoras instaladas no Windows para popular o dropdown."""
    nomes = listar_impressoras_windows()
    atual = carregar_config().get("nome_windows")
    return jsonify({"impressoras": nomes, "selecionada": atual})


@impressora_bp.post("/api/impressora/config")
@impressora_bp.post("/api/impressora/config/")
def salvar():
    dados = request.get_json(force=True) or {}
    campos = {"tipo", "modo", "nome_windows", "vendor_id", "product_id",
              "ip", "porta", "com", "baudrate", "cortar_papel"}
    payload = {k: v for k, v in dados.items() if k in campos}
    if not payload:
        return jsonify({"status": "erro", "mensagem": "Nenhum campo válido."}), 400
    salvar_config(payload)
    return jsonify({"status": "sucesso"})


@impressora_bp.get("/api/impressora/teste")
@impressora_bp.get("/api/impressora/teste/")
def teste():
    resultado = testar_impressora()
    status = 200 if resultado["ok"] else 500
    return jsonify(resultado), status