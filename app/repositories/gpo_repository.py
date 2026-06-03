"""
Repository de GPO (Gestão de Pessoas e Organização).
Gerencia usuários, grupos e políticas de permissão.
"""

import hashlib
import json
import sqlite3

from app.repositories.db import conectar

# ── Constantes do domínio ─────────────────────────────────────────────

# Permissões agrupadas por categoria
PERMISSOES_SISTEMA = {
    # ── Páginas (acesso de visualização) ──────────────────────────────
    "pg_dashboard":    "Página: Dashboard",
    "pg_pedidos":      "Página: Pedidos",
    "pg_produtos":     "Página: Produtos",
    "pg_complementos": "Página: Complementos",
    "pg_estoque":      "Página: Estoque",
    "pg_taxas":        "Página: Taxas de entrega",
    "pg_relatorios":   "Página: Relatórios",
    "pg_aparencia":    "Página: Aparência",
    "pg_navegacao":    "Página: Navegação",
    "pg_ia":           "Página: Inteligência Artificial",
    "pg_impressora":   "Página: Impressora",
    "pg_auditoria":    "Página: Auditoria",
    "pg_diagnostico":  "Página: Diagnóstico de pedidos",
    "pg_gpo":          "Página: GPO (apenas admin)",
    # ── Operações ─────────────────────────────────────────────────────
    "lancar_pedidos":    "Op: Lançar pedidos do balcão",
    "ver_pedidos":       "Op: Visualizar pedidos",
    "aceitar_pedidos":   "Op: Aceitar pedidos (Pendente → Preparando)",
    "preparar_pedidos":  "Op: Marcar pedido como Preparado",
    "despachar_pedidos": "Op: Despachar pedidos (A Caminho)",
    "finalizar_pedidos": "Op: Finalizar pedidos",
    "ver_cardapio":      "Op: Ver produtos do cardápio",
    "ver_relatorios":    "Op: Acessar relatórios",
    "editar_produtos":   "Op: Criar/editar produtos",
    "editar_taxas":      "Op: Gerenciar taxas de entrega",
    "gerenciar_estoque": "Op: Gerenciar estoque",
    "acesso_admin":      "Op: Acesso completo ao painel admin",
}

# Mapeamento página → permissão necessária (para proteção de rotas e sidebar)
PAGINAS_PERMISSAO = {
    "/admin":                   "pg_dashboard",
    "/admin/pedidos":           "pg_pedidos",
    "/admin/produtos":          "pg_produtos",
    "/admin/complementos":      "pg_complementos",
    "/admin/estoque":           "pg_estoque",
    "/admin/taxas":             "pg_taxas",
    "/admin/relatorios":        "pg_relatorios",
    "/admin/aparencia":         "pg_aparencia",
    "/admin/navegacao":         "pg_navegacao",
    "/admin/ia":                "pg_ia",
    "/admin/impressora":        "pg_impressora",
    "/admin/auditoria":         "pg_auditoria",
    "/admin/diagnostico-pedidos": "pg_diagnostico",
    "/admin/gpo":               None,  # apenas admin
}

ROLES_SISTEMA = ["admin", "atendente", "cozinha", "caixa", "entregador"]


def _hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()


def init_gpo():
    """Cria tabelas de GPO no banco se ainda não existirem."""
    conn = conectar()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS grupos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            descricao TEXT DEFAULT '',
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS politicas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            descricao TEXT DEFAULT '',
            permissoes TEXT DEFAULT '[]',
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS grupo_politicas (
            grupo_id INTEGER,
            politica_id INTEGER,
            PRIMARY KEY (grupo_id, politica_id),
            FOREIGN KEY (grupo_id) REFERENCES grupos(id) ON DELETE CASCADE,
            FOREIGN KEY (politica_id) REFERENCES politicas(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nome TEXT NOT NULL,
            role TEXT DEFAULT 'atendente',
            grupo_id INTEGER,
            ativo INTEGER DEFAULT 1,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (grupo_id) REFERENCES grupos(id) ON DELETE SET NULL
        );
    """)
    conn.commit()
    conn.close()


# ── Usuários ──────────────────────────────────────────────────────────

def buscar_usuarios() -> list[dict]:
    conn = conectar()
    rows = conn.execute(
        "SELECT u.*, g.nome AS grupo_nome FROM usuarios u LEFT JOIN grupos g ON u.grupo_id = g.id ORDER BY u.nome"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def verificar_login(username: str, senha: str) -> dict | None:
    conn = conectar()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE username=? AND password_hash=? AND ativo=1",
        (username, _hash_senha(senha)),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def inserir_usuario(username: str, senha: str, nome: str, role: str, grupo_id) -> dict:
    conn = conectar()
    try:
        conn.execute(
            "INSERT INTO usuarios (username, password_hash, nome, role, grupo_id) VALUES (?, ?, ?, ?, ?)",
            (username, _hash_senha(senha), nome, role, grupo_id),
        )
        conn.commit()
        return {"ok": True}
    except sqlite3.IntegrityError:
        return {"ok": False, "erro": "Usuário já existe"}
    finally:
        conn.close()


def atualizar_usuario(user_id: int, nome: str, role: str, grupo_id, ativo: int, senha: str | None = None):
    conn = conectar()
    if senha:
        conn.execute(
            "UPDATE usuarios SET nome=?, role=?, grupo_id=?, ativo=?, password_hash=? WHERE id=?",
            (nome, role, grupo_id, ativo, _hash_senha(senha), user_id),
        )
    else:
        conn.execute(
            "UPDATE usuarios SET nome=?, role=?, grupo_id=?, ativo=? WHERE id=?",
            (nome, role, grupo_id, ativo, user_id),
        )
    conn.commit()
    conn.close()


def deletar_usuario(user_id: int):
    conn = conectar()
    conn.execute("DELETE FROM usuarios WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


def obter_permissoes_usuario(user_id: int) -> set:
    conn = conectar()
    u = conn.execute("SELECT role, grupo_id FROM usuarios WHERE id=?", (user_id,)).fetchone()
    if not u:
        conn.close()
        return set()

    if u["role"] == "admin":
        conn.close()
        return set(PERMISSOES_SISTEMA.keys())

    if not u["grupo_id"]:
        conn.close()
        return set()

    rows = conn.execute(
        "SELECT p.permissoes FROM politicas p JOIN grupo_politicas gp ON gp.politica_id = p.id WHERE gp.grupo_id = ?",
        (u["grupo_id"],),
    ).fetchall()
    conn.close()

    perms: set = set()
    for r in rows:
        try:
            perms.update(json.loads(r["permissoes"]))
        except Exception:
            pass
    return perms


# ── Grupos ────────────────────────────────────────────────────────────

def buscar_grupos() -> list[dict]:
    conn = conectar()
    rows = conn.execute(
        """SELECT g.*,
                  COUNT(DISTINCT u.id) AS total_usuarios,
                  COUNT(DISTINCT gp.politica_id) AS total_politicas
           FROM grupos g
           LEFT JOIN usuarios u ON u.grupo_id = g.id
           LEFT JOIN grupo_politicas gp ON gp.grupo_id = g.id
           GROUP BY g.id ORDER BY g.nome"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def inserir_grupo(nome: str, descricao: str = "") -> dict:
    conn = conectar()
    try:
        conn.execute("INSERT INTO grupos (nome, descricao) VALUES (?, ?)", (nome, descricao))
        conn.commit()
        return {"ok": True}
    except sqlite3.IntegrityError:
        return {"ok": False, "erro": "Grupo já existe"}
    finally:
        conn.close()


def atualizar_grupo(grupo_id: int, nome: str, descricao: str):
    conn = conectar()
    conn.execute("UPDATE grupos SET nome=?, descricao=? WHERE id=?", (nome, descricao, grupo_id))
    conn.commit()
    conn.close()


def deletar_grupo(grupo_id: int):
    conn = conectar()
    conn.execute("DELETE FROM grupos WHERE id=?", (grupo_id,))
    conn.commit()
    conn.close()


def sincronizar_politicas_grupo(grupo_id: int, politicas_ids: list[int]):
    conn = conectar()
    conn.execute("DELETE FROM grupo_politicas WHERE grupo_id=?", (grupo_id,))
    conn.executemany(
        "INSERT OR IGNORE INTO grupo_politicas (grupo_id, politica_id) VALUES (?, ?)",
        [(grupo_id, pid) for pid in politicas_ids],
    )
    conn.commit()
    conn.close()


def buscar_politicas_do_grupo(grupo_id: int) -> list[dict]:
    conn = conectar()
    rows = conn.execute(
        "SELECT p.* FROM politicas p JOIN grupo_politicas gp ON gp.politica_id = p.id WHERE gp.grupo_id = ?",
        (grupo_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Políticas ─────────────────────────────────────────────────────────

def buscar_politicas() -> list[dict]:
    conn = conectar()
    rows = conn.execute(
        """SELECT p.*, COUNT(DISTINCT gp.grupo_id) AS grupos_aplicados
           FROM politicas p
           LEFT JOIN grupo_politicas gp ON gp.politica_id = p.id
           GROUP BY p.id ORDER BY p.nome"""
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["permissoes"] = json.loads(d["permissoes"])
        except Exception:
            d["permissoes"] = []
        result.append(d)
    return result


def inserir_politica(nome: str, descricao: str, permissoes: list) -> dict:
    conn = conectar()
    try:
        conn.execute(
            "INSERT INTO politicas (nome, descricao, permissoes) VALUES (?, ?, ?)",
            (nome, descricao, json.dumps(permissoes)),
        )
        conn.commit()
        return {"ok": True}
    except sqlite3.IntegrityError:
        return {"ok": False, "erro": "Política já existe"}
    finally:
        conn.close()


def atualizar_politica(pol_id: int, nome: str, descricao: str, permissoes: list):
    conn = conectar()
    conn.execute(
        "UPDATE politicas SET nome=?, descricao=?, permissoes=? WHERE id=?",
        (nome, descricao, json.dumps(permissoes), pol_id),
    )
    conn.commit()
    conn.close()


def deletar_politica(pol_id: int):
    conn = conectar()
    conn.execute("DELETE FROM politicas WHERE id=?", (pol_id,))
    conn.commit()
    conn.close()
