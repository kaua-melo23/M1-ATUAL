"""
Controller de IA — rotas da seção "Inteligência do Negócio".

Acesso restrito a: admin e gerente.
A IA apenas analisa e sugere — NUNCA altera dados automaticamente.
"""

from flask import Blueprint, jsonify, render_template, request, session

from app.middleware.auth import login_required, permissao_required
from app.repositories import ia_repository
from app.services import ia_service

ia_bp = Blueprint("ia_bp", __name__)


# ── Guard de permissão ─────────────────────────────────────────────────

def _tem_acesso_ia() -> bool:
    """Retorna True para admin e gerente."""
    return session.get("role") in ("admin", "gerente")


def _usuario_atual() -> str:
    return session.get("username") or session.get("nome") or "desconhecido"


def _role_atual() -> str:
    return session.get("role", "")


# ── Página principal ──────────────────────────────────────────────────

@ia_bp.route("/admin/ia")
@login_required
@permissao_required("pg_ia", "acesso_admin")
def ia_index():
    return render_template("admin/ia.html", acesso_negado=False)


# ── API: Executar análise ─────────────────────────────────────────────

@ia_bp.route("/api/ia/analise", methods=["POST"])
@login_required
def api_executar_analise():
    """
    Coleta dados do sistema, chama a IA e registra auditoria.

    Body JSON (opcional):
        tipo_analise: str  — "completa" | "estoque" | "vendas" | "custos"
        dias_vendas:  int  — padrão 30
    """
    if not _tem_acesso_ia():
        return jsonify({"ok": False, "erro": "Acesso negado. Apenas admin e gerente."}), 403

    dados = request.get_json(silent=True) or {}
    tipo_analise = dados.get("tipo_analise", "completa")
    dias_vendas = int(dados.get("dias_vendas", 30))

    resultado = ia_service.executar_analise(tipo_analise, dias_vendas)

    # Auditoria — sempre registra a tentativa
    try:
        ia_repository.registrar_analise(
            usuario=_usuario_atual(),
            role=_role_atual(),
            tipo_analise=tipo_analise,
            tokens_usados=resultado.get("tokens_usados", 0),
            duracao_ms=resultado.get("duracao_ms", 0),
        )
    except Exception as e:
        # Auditoria nunca deve derrubar a resposta principal
        print(f"[IAController] Aviso: falha ao registrar auditoria: {e}")

    # Remove payload do response (pode ser grande) — fica só no log interno
    resultado.pop("payload", None)

    status_code = 200 if resultado.get("ok") else 500
    return jsonify(resultado), status_code


# ── API: Aplicar sugestão ─────────────────────────────────────────────

@ia_bp.route("/api/ia/sugestao/aplicar", methods=["POST"])
@login_required
def api_aplicar_sugestao():
    """
    Registra que o usuário reconheceu/encaminhou uma sugestão da IA.

    A IA NUNCA executa ações automáticas. Este endpoint apenas:
    1. Salva o registro de auditoria
    2. Retorna a URL de destino para redirecionar o usuário

    Body JSON:
        analise_id:     int    — ID da análise que originou a sugestão
        sugestao_texto: str    — Texto da sugestão
        categoria:      str    — "estoque" | "vendas" | "custo" | "produto" | "operacional"
    """
    if not _tem_acesso_ia():
        return jsonify({"ok": False, "erro": "Acesso negado."}), 403

    dados = request.get_json(silent=True) or {}
    analise_id = dados.get("analise_id")
    sugestao_texto = dados.get("sugestao_texto", "")
    categoria = dados.get("categoria", "recomendacao")

    if not analise_id or not sugestao_texto:
        return jsonify({"ok": False, "erro": "analise_id e sugestao_texto são obrigatórios"}), 400

    ia_repository.registrar_sugestao_aplicada(
        analise_id=int(analise_id),
        sugestao_texto=sugestao_texto,
        usuario=_usuario_atual(),
        categoria=categoria,
    )

    # Mapeia categoria para URL de destino
    _urls_destino = {
        "estoque":      "/admin/estoque",
        "produto":      "/admin/produtos",
        "vendas":       "/admin/relatorios",
        "custo":        "/admin/relatorios",
        "operacional":  "/admin",
    }
    url_destino = _urls_destino.get(categoria, "/admin")

    return jsonify({
        "ok": True,
        "mensagem": "Sugestão registrada. Você será direcionado para a área correspondente.",
        "url_destino": url_destino,
    })


# ── API: Histórico de análises ────────────────────────────────────────

@ia_bp.route("/api/ia/historico", methods=["GET"])
@login_required
def api_historico():
    """Retorna o histórico de análises realizadas."""
    if not _tem_acesso_ia():
        return jsonify({"ok": False, "erro": "Acesso negado."}), 403

    limite = int(request.args.get("limite", 20))
    historico = ia_repository.buscar_historico(limite)
    return jsonify({"ok": True, "historico": historico})


# ── API: Configurar chave de API ──────────────────────────────────────

@ia_bp.route("/api/ia/configurar-chave", methods=["POST"])
@login_required
def api_configurar_chave():
    """Salva a chave da API do Gemini no banco de dados (apenas admin)."""
    if session.get("role") != "admin":
        return jsonify({"ok": False, "erro": "Apenas admin pode configurar a chave da API."}), 403

    dados = request.get_json(silent=True) or {}
    chave = (dados.get("api_key") or "").strip()

    if not chave:
        return jsonify({"ok": False, "erro": "Chave não pode ser vazia."}), 400

    if not chave.startswith("AIza"):
        return jsonify({"ok": False, "erro": "Formato inválido. A chave do Gemini começa com 'AIza'"}), 400

    from app.repositories.db import conectar
    conn = conectar()
    conn.execute(
        "INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES ('gemini_api_key', ?)",
        (chave,),
    )
    conn.commit()
    conn.close()

    ia_repository.registrar_analise(
        usuario=_usuario_atual(),
        role=_role_atual(),
        tipo_analise="configurar_chave_api",
        tokens_usados=0,
        duracao_ms=0,
    )

    return jsonify({"ok": True, "mensagem": "Chave do Gemini salva com sucesso."})
