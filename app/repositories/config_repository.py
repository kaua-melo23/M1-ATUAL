"""
Repository de Configurações, Categorias e Menu Admin.

Melhorias:
- Cache em memória para configurações, categorias e menu (dados raramente alterados)
- Usa get_db() para reutilizar conexão da requisição
- SELECT explícito (sem SELECT *)
- Invalidação de cache ao escrever
"""

from app.repositories.db import get_db
from app.utils.cache import cache

_TTL_CONFIG = 300   # 5 minutos
_TTL_CAT    = 180   # 3 minutos
_TTL_MENU   = 300   # 5 minutos


# ── Configurações ──────────────────────────────────────────────────────

@cache.cached(ttl=_TTL_CONFIG, key="config:configuracoes")
def buscar_configuracoes() -> dict:
    conn = get_db()
    rows = conn.execute("SELECT chave, valor FROM configuracoes").fetchall()
    return {r["chave"]: r["valor"] for r in rows}


def salvar_configuracoes(dados: dict):
    conn = get_db()
    conn.executemany(
        "INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?)",
        list(dados.items()),
    )
    conn.commit()
    cache.invalidar("config:configuracoes")


# ── Categorias do cliente ──────────────────────────────────────────────

@cache.cached(ttl=_TTL_CAT, key="config:categorias_ativas")
def buscar_categorias(apenas_ativas: bool = False) -> list[dict]:
    conn = get_db()
    sql = "SELECT id, nome, emoji, ordem, ativo FROM categorias_cliente"
    if apenas_ativas:
        sql += " WHERE ativo=1"
    sql += " ORDER BY ordem ASC"
    rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


def inserir_categoria(nome: str, emoji: str):
    conn = get_db()
    proxima = conn.execute(
        "SELECT COALESCE(MAX(ordem), 0) + 1 FROM categorias_cliente"
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO categorias_cliente (nome, emoji, ordem, ativo) VALUES (?, ?, ?, 1)",
        (nome, emoji, proxima),
    )
    conn.commit()
    _invalidar_cache_categorias()


def atualizar_categoria(cat_id: int, nome: str, emoji: str, ativo: int):
    conn = get_db()
    conn.execute(
        "UPDATE categorias_cliente SET nome=?, emoji=?, ativo=? WHERE id=?",
        (nome, emoji, ativo, cat_id),
    )
    conn.commit()
    _invalidar_cache_categorias()


def deletar_categoria(cat_id: int):
    conn = get_db()
    conn.execute("DELETE FROM categorias_cliente WHERE id=?", (cat_id,))
    conn.commit()
    _invalidar_cache_categorias()


def reordenar_categorias(ids_ordenados: list[int]):
    conn = get_db()
    conn.executemany(
        "UPDATE categorias_cliente SET ordem=? WHERE id=?",
        [(i, cat_id) for i, cat_id in enumerate(ids_ordenados)],
    )
    conn.commit()
    _invalidar_cache_categorias()


def _invalidar_cache_categorias():
    cache.invalidar("config:categorias_ativas")


# ── Menu Admin ─────────────────────────────────────────────────────────

@cache.cached(ttl=_TTL_MENU, key="config:menu_admin")
def buscar_menu_admin(apenas_visiveis: bool = False) -> list[dict]:
    conn = get_db()
    sql = "SELECT id, label, url, emoji, ordem, visivel FROM menu_admin"
    if apenas_visiveis:
        sql += " WHERE visivel=1"
    sql += " ORDER BY ordem ASC"
    rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


def atualizar_item_menu(item_id: int, label: str, emoji: str, visivel: int):
    conn = get_db()
    conn.execute(
        "UPDATE menu_admin SET label=?, emoji=?, visivel=? WHERE id=?",
        (label, emoji, visivel, item_id),
    )
    conn.commit()
    cache.invalidar("config:menu_admin")


def reordenar_menu_admin(ids_ordenados: list[int]):
    conn = get_db()
    conn.executemany(
        "UPDATE menu_admin SET ordem=? WHERE id=?",
        [(i, item_id) for i, item_id in enumerate(ids_ordenados)],
    )
    conn.commit()
    cache.invalidar("config:menu_admin")


# ── Taxas de Entrega ───────────────────────────────────────────────────

@cache.cached(ttl=_TTL_CONFIG, key="config:taxas")
def buscar_taxas() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT id, bairro, taxa FROM taxas_entrega ORDER BY bairro ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def salvar_taxa(bairro: str, valor: float):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO taxas_entrega (bairro, taxa) VALUES (?, ?)",
        (bairro, valor),
    )
    conn.commit()
    cache.invalidar("config:taxas")


def deletar_taxa(taxa_id: int):
    conn = get_db()
    conn.execute("DELETE FROM taxas_entrega WHERE id = ?", (taxa_id,))
    conn.commit()
    cache.invalidar("config:taxas")
