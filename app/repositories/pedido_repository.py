"""
Repository de Pedidos.

Melhorias:
- buscar_pedidos: JOIN único em vez de N queries (N+1 eliminado)
- SELECT explícito (sem SELECT *)
- Logging em vez de print()
- Paginação opcional para relatórios grandes
"""

import logging
from app.repositories.db import get_db
from app.utils.tempo import get_agora_str

logger = logging.getLogger(__name__)

_COLUNAS_PEDIDO = (
    "id, data_hora, cliente_nome, cliente_telefone, bairro, endereco, "
    "total_produtos, taxa_entrega, total_geral, metodo_pagamento, status, "
    "id_pagamento_mp, lancado_por, valor_pago"
)


def inserir_pedido(p: dict, itens: list[dict]) -> int | bool:
    """Insere pedido e seus itens em uma única transação. Retorna o ID ou False."""
    conn = get_db()
    try:
        cur = conn.execute(
            """INSERT INTO pedidos
               (data_hora, cliente_nome, bairro, endereco, total_produtos, taxa_entrega,
                total_geral, metodo_pagamento, status, lancado_por, cliente_telefone, valor_pago)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                get_agora_str(),
                p.get("nome"),
                p.get("bairro"),
                p.get("endereco"),
                p.get("total_itens"),
                p.get("taxa"),
                p.get("total_geral"),
                p.get("metodo"),
                "Pendente",
                p.get("lancado_por"),
                p.get("telefone"),
                p.get("valor_pago"),
            ),
        )
        pedido_id = cur.lastrowid

        conn.executemany(
            "INSERT INTO itens_pedido (pedido_id, produto_nome, quantidade, preco_unitario) VALUES (?, ?, ?, ?)",
            [
                (pedido_id, item.get("nome"), item.get("quantidade"), item.get("preco"))
                for item in itens
            ],
        )
        conn.commit()
        return pedido_id
    except Exception as e:
        conn.rollback()
        logger.error("Erro ao inserir pedido: %s", e)
        return False


def buscar_pedidos(
    hora_inicio=None,
    dt_inicio=None,
    dt_fim=None,
    lancado_por=None,
    limite: int | None = None,
    offset: int = 0,
) -> list[dict]:
    """
    Retorna pedidos com seus itens em uma única query (JOIN).
    Elimina o problema N+1 de queries separadas por pedido.

    Paginação: use `limite` e `offset` para conjuntos grandes.
    """
    conn = get_db()

    filtros = []
    params = []

    if dt_inicio and dt_fim:
        filtros.append("p.data_hora >= ? AND p.data_hora <= ?")
        params += [dt_inicio, dt_fim]
    elif dt_inicio:
        filtros.append("p.data_hora >= ?")
        params.append(dt_inicio)
    elif dt_fim:
        filtros.append("p.data_hora <= ?")
        params.append(dt_fim)
    elif hora_inicio is not None:
        filtros.append("CAST(strftime('%H', p.data_hora) AS INTEGER) >= ?")
        params.append(hora_inicio)

    if lancado_por is not None:
        filtros.append("p.lancado_por = ?")
        params.append(lancado_por)

    where = ("WHERE " + " AND ".join(filtros)) if filtros else ""

    # ── Query com JOIN: busca pedidos e itens de uma vez ──────────────
    sql = f"""
        SELECT
            p.id, p.data_hora, p.cliente_nome, p.bairro, p.endereco,
            p.total_produtos, p.taxa_entrega, p.total_geral,
            p.metodo_pagamento, p.status, p.lancado_por,
            ip.produto_nome, ip.quantidade, ip.preco_unitario
        FROM pedidos p
        LEFT JOIN itens_pedido ip ON ip.pedido_id = p.id
        {where}
        ORDER BY p.id DESC
    """

    if limite:
        sql += " LIMIT ? OFFSET ?"
        params += [limite, offset]

    rows = conn.execute(sql, params).fetchall()

    # Agrupa itens por pedido em Python (evita queries extras)
    pedidos: dict[int, dict] = {}
    for row in rows:
        pid = row["id"]
        if pid not in pedidos:
            pedidos[pid] = {
                "id": pid,
                "data_hora": row["data_hora"],
                "data": row["data_hora"],           # compatibilidade
                "cliente_nome": row["cliente_nome"],
                "bairro": row["bairro"],
                "endereco": row["endereco"],
                "total_produtos": row["total_produtos"],
                "taxa_entrega": row["taxa_entrega"],
                "total_geral": row["total_geral"],
                "total": row["total_geral"],         # compatibilidade
                "metodo_pagamento": row["metodo_pagamento"],
                "metodo": row["metodo_pagamento"],   # compatibilidade
                "status": row["status"],
                "lancado_por": row["lancado_por"],
                "itens": [],
            }
        if row["produto_nome"]:
            pedidos[pid]["itens"].append({
                "produto_nome": row["produto_nome"],
                "quantidade": row["quantidade"],
                "preco_unitario": row["preco_unitario"],
                # compatibilidade com templates legados
                "nome": row["produto_nome"],
                "preco": row["preco_unitario"],
            })

    return list(pedidos.values())


def buscar_por_id(pedido_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute(
        f"SELECT {_COLUNAS_PEDIDO} FROM pedidos WHERE id = ?", (pedido_id,)
    ).fetchone()
    if not row:
        return None
    p = dict(row)
    p["data"] = p["data_hora"]
    p["total"] = p["total_geral"]
    p["metodo"] = p["metodo_pagamento"]
    return p


def buscar_por_id_mp(id_mp: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT id, status FROM pedidos WHERE id_pagamento_mp = ?", (str(id_mp),)
    ).fetchone()
    return dict(row) if row else None


def buscar_itens(pedido_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT produto_nome, quantidade, preco_unitario FROM itens_pedido WHERE pedido_id = ?",
        (pedido_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def atualizar_status(pedido_id: int, novo_status: str):
    conn = get_db()
    conn.execute("UPDATE pedidos SET status = ? WHERE id = ?", (novo_status, pedido_id))
    conn.commit()


def vincular_id_mp(pedido_id: int, id_mp: str):
    conn = get_db()
    conn.execute(
        "UPDATE pedidos SET id_pagamento_mp = ? WHERE id = ?", (str(id_mp), pedido_id)
    )
    conn.commit()


def deletar(pedido_id: int):
    conn = get_db()
    conn.execute("DELETE FROM pedidos WHERE id = ?", (pedido_id,))
    conn.commit()
