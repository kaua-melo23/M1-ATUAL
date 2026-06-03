"""
Repository de Estoque — insumos, lotes, receitas e vínculos produto→insumo.

Melhorias:
- get_db() para requisições Flask, conectar() para contextos externos
- SELECT explícito (sem SELECT *)
- Logging em vez de print()
- Queries de lotes otimizadas
"""

import logging
from app.repositories.db import get_db, conectar

logger = logging.getLogger(__name__)


# ── Insumos ───────────────────────────────────────────────────────────

def buscar_insumos(tipo: str | None = None) -> list[dict]:
    conn = get_db()
    sql = """
        SELECT i.id, i.nome, i.unidade_base, i.estoque_minimo, i.tipo, i.validade_padrao,
               COALESCE(SUM(CASE WHEN l.validade >= date('now') THEN l.quantidade_atual ELSE 0 END), 0) AS total_estoque,
               MIN(CASE WHEN l.validade >= date('now') AND l.quantidade_atual > 0 THEN l.validade END) AS proxima_validade
        FROM insumos i
        LEFT JOIN lotes l ON i.id = l.insumo_id
    """
    params = ()
    if tipo:
        sql += " WHERE i.tipo = ?"
        params = (tipo,)
    sql += " GROUP BY i.id ORDER BY i.nome"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def inserir_insumo(nome: str, unidade_base: str, estoque_minimo: float, tipo: str, validade_padrao) -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO insumos (nome, unidade_base, estoque_minimo, tipo, validade_padrao) VALUES (?, ?, ?, ?, ?)",
        (nome, unidade_base, estoque_minimo, tipo, validade_padrao),
    )
    conn.commit()
    return cur.lastrowid


def atualizar_insumo(insumo_id: int, nome: str, unidade_base: str, estoque_minimo: float, validade_padrao):
    conn = get_db()
    conn.execute(
        "UPDATE insumos SET nome=?, unidade_base=?, estoque_minimo=?, validade_padrao=? WHERE id=?",
        (nome, unidade_base, estoque_minimo, validade_padrao, insumo_id),
    )
    conn.commit()


def deletar_insumo(insumo_id: int):
    conn = get_db()
    conn.execute("DELETE FROM insumos WHERE id=?", (insumo_id,))
    conn.commit()


def buscar_insumo_por_nome(nome: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT id FROM insumos WHERE nome = ?", (nome,)).fetchone()
    return dict(row) if row else None


# ── Lotes ─────────────────────────────────────────────────────────────

def buscar_lotes(insumo_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        """SELECT id, insumo_id, quantidade_inicial, quantidade_atual, validade, custo_lote, data_entrada,
                  CASE WHEN validade < date('now') THEN 1 ELSE 0 END AS vencido,
                  CASE WHEN validade <= date('now', '+7 days') AND validade >= date('now') THEN 1 ELSE 0 END AS vence_em_breve
           FROM lotes WHERE insumo_id = ? ORDER BY validade ASC""",
        (insumo_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def buscar_lotes_ativos(insumo_id: int) -> list[dict]:
    """Lotes válidos com estoque, ordenados por PVPS (primeiro que vence primeiro sai)."""
    conn = get_db()
    rows = conn.execute(
        """SELECT id, quantidade_atual, validade FROM lotes
           WHERE insumo_id = ? AND validade >= date('now') AND quantidade_atual > 0
           ORDER BY validade ASC""",
        (insumo_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def inserir_lote(insumo_id: int, quantidade: float, validade: str, custo: float = 0) -> int:
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO lotes (insumo_id, quantidade_inicial, quantidade_atual, validade, custo_lote, data_entrada)
           VALUES (?, ?, ?, ?, ?, date('now'))""",
        (insumo_id, quantidade, quantidade, validade, custo),
    )
    conn.commit()
    return cur.lastrowid


def descontar_lote(lote_id: int, quantidade: float):
    conn = get_db()
    conn.execute(
        "UPDATE lotes SET quantidade_atual = MAX(0, quantidade_atual - ?) WHERE id = ?",
        (quantidade, lote_id),
    )
    conn.commit()


def estoque_disponivel(insumo_id: int) -> float:
    conn = get_db()
    row = conn.execute(
        """SELECT COALESCE(SUM(quantidade_atual), 0) FROM lotes
           WHERE insumo_id = ? AND validade >= date('now')""",
        (insumo_id,),
    ).fetchone()
    return row[0] if row else 0.0


# ── Receitas ──────────────────────────────────────────────────────────

def buscar_receita(insumo_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        """SELECT r.id, r.insumo_bruto_id, r.quantidade, i.nome, i.unidade_base
           FROM receitas r
           JOIN insumos i ON i.id = r.insumo_bruto_id
           WHERE r.insumo_fabricado_id = ?""",
        (insumo_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def buscar_ingredientes_receita(insumo_fabricado_id: int, quantidade_produzida: float) -> list[dict]:
    """Retorna ingredientes com a quantidade necessária proporcional."""
    conn = get_db()
    rows = conn.execute(
        """SELECT r.insumo_bruto_id, i.nome, r.quantidade * ? AS qtd_necessaria
           FROM receitas r
           JOIN insumos i ON i.id = r.insumo_bruto_id
           WHERE r.insumo_fabricado_id = ?""",
        (quantidade_produzida, insumo_fabricado_id),
    ).fetchall()
    return [dict(r) for r in rows]


def salvar_receita(insumo_id: int, ingredientes: list[dict]):
    conn = get_db()
    conn.execute("DELETE FROM receitas WHERE insumo_fabricado_id = ?", (insumo_id,))
    conn.executemany(
        "INSERT INTO receitas (insumo_fabricado_id, insumo_bruto_id, quantidade) VALUES (?, ?, ?)",
        [(insumo_id, ing["insumo_id"], ing["quantidade"]) for ing in ingredientes],
    )
    conn.commit()


# ── Vínculos produto → insumo ─────────────────────────────────────────

def buscar_vinculos_produto(produto_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        """SELECT pi.id, pi.produto_id, pi.insumo_id, pi.quantidade, i.nome, i.unidade_base
           FROM produto_insumo pi
           JOIN insumos i ON i.id = pi.insumo_id
           WHERE pi.produto_id = ?""",
        (produto_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def buscar_vinculos_por_produto_id(produto_id: int, quantidade_vendida: float) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT insumo_id, quantidade * ? AS qtd_descontar FROM produto_insumo WHERE produto_id = ?",
        (quantidade_vendida, produto_id),
    ).fetchall()
    return [dict(r) for r in rows]


def salvar_vinculos_produto(produto_id: int, insumos: list[dict]):
    conn = get_db()
    conn.execute("DELETE FROM produto_insumo WHERE produto_id = ?", (produto_id,))
    conn.executemany(
        "INSERT INTO produto_insumo (produto_id, insumo_id, quantidade) VALUES (?, ?, ?)",
        [(produto_id, ins["insumo_id"], ins["quantidade"]) for ins in insumos],
    )
    conn.commit()


# ── Alertas de estoque ────────────────────────────────────────────────

def buscar_alertas_estoque() -> list[dict]:
    """Retorna insumos abaixo do estoque mínimo em uma única query."""
    conn = get_db()
    rows = conn.execute(
        """SELECT i.id, i.nome, i.unidade_base, i.estoque_minimo,
                  COALESCE(SUM(CASE WHEN l.validade >= date('now') THEN l.quantidade_atual ELSE 0 END), 0) AS total_estoque
           FROM insumos i
           LEFT JOIN lotes l ON l.insumo_id = i.id
           GROUP BY i.id
           HAVING total_estoque < i.estoque_minimo
           ORDER BY i.nome"""
    ).fetchall()
    return [dict(r) for r in rows]
