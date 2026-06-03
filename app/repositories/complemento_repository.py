"""
Repository de Complementos — grupos, itens e vínculos produto→grupo.

Modelo de dados:
  grupos_complemento   → ex: "Frutas", "Adicionais Premium"
  itens_complemento    → granola, banana, morango... (com insumo_id e preço)
  produto_grupo_complemento → qual grupo pertence a qual produto e se é INCLUSO ou PAGO
  pedido_complementos  → complementos escolhidos em cada item do pedido
"""

from app.repositories.db import conectar


# ── Schema ────────────────────────────────────────────────────────────

DDL_COMPLEMENTOS = """
CREATE TABLE IF NOT EXISTS grupos_complemento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    descricao TEXT DEFAULT '',
    ativo INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS itens_complemento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grupo_id INTEGER NOT NULL,
    nome TEXT NOT NULL,
    preco_adicional REAL DEFAULT 0,
    insumo_id INTEGER,
    disponivel INTEGER DEFAULT 1,
    FOREIGN KEY (grupo_id) REFERENCES grupos_complemento(id) ON DELETE CASCADE,
    FOREIGN KEY (insumo_id) REFERENCES insumos(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS produto_grupo_complemento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_id INTEGER NOT NULL,
    grupo_id INTEGER NOT NULL,
    tipo TEXT NOT NULL CHECK(tipo IN ('incluso','adicional')),
    obrigatorio INTEGER DEFAULT 0,
    UNIQUE(produto_id, grupo_id),
    FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE CASCADE,
    FOREIGN KEY (grupo_id) REFERENCES grupos_complemento(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pedido_complementos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER NOT NULL,
    item_pedido_id INTEGER,
    item_complemento_id INTEGER NOT NULL,
    quantidade INTEGER DEFAULT 1,
    preco_unitario REAL DEFAULT 0,
    FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE,
    FOREIGN KEY (item_complemento_id) REFERENCES itens_complemento(id)
);
"""


def init_complementos():
    """Cria as tabelas de complementos se ainda não existirem."""
    conn = conectar()
    conn.executescript(DDL_COMPLEMENTOS)
    conn.commit()
    conn.close()


# ── Grupos ────────────────────────────────────────────────────────────

def buscar_grupos(apenas_ativos: bool = False) -> list[dict]:
    conn = conectar()
    sql = "SELECT * FROM grupos_complemento"
    if apenas_ativos:
        sql += " WHERE ativo = 1"
    sql += " ORDER BY nome ASC"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def buscar_grupo_por_id(grupo_id: int) -> dict | None:
    conn = conectar()
    row = conn.execute("SELECT * FROM grupos_complemento WHERE id = ?", (grupo_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def inserir_grupo(nome: str, descricao: str = "") -> int:
    conn = conectar()
    cur = conn.execute(
        "INSERT INTO grupos_complemento (nome, descricao) VALUES (?, ?)", (nome, descricao)
    )
    conn.commit()
    novo_id = cur.lastrowid
    conn.close()
    return novo_id


def atualizar_grupo(grupo_id: int, nome: str, descricao: str, ativo: int):
    conn = conectar()
    conn.execute(
        "UPDATE grupos_complemento SET nome=?, descricao=?, ativo=? WHERE id=?",
        (nome, descricao, ativo, grupo_id),
    )
    conn.commit()
    conn.close()


def deletar_grupo(grupo_id: int):
    conn = conectar()
    conn.execute("DELETE FROM grupos_complemento WHERE id=?", (grupo_id,))
    conn.commit()
    conn.close()


# ── Itens de Complemento ──────────────────────────────────────────────

def buscar_itens_do_grupo(grupo_id: int, apenas_disponiveis: bool = False) -> list[dict]:
    conn = conectar()
    sql = """
        SELECT ic.*, i.nome AS nome_insumo
        FROM itens_complemento ic
        LEFT JOIN insumos i ON ic.insumo_id = i.id
        WHERE ic.grupo_id = ?
    """
    if apenas_disponiveis:
        sql += " AND ic.disponivel = 1"
    sql += " ORDER BY ic.nome ASC"
    rows = conn.execute(sql, (grupo_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def buscar_item_por_id(item_id: int) -> dict | None:
    conn = conectar()
    row = conn.execute("SELECT * FROM itens_complemento WHERE id=?", (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def inserir_item(grupo_id: int, nome: str, preco_adicional: float, insumo_id) -> int:
    conn = conectar()
    cur = conn.execute(
        "INSERT INTO itens_complemento (grupo_id, nome, preco_adicional, insumo_id) VALUES (?, ?, ?, ?)",
        (grupo_id, nome, preco_adicional, insumo_id or None),
    )
    conn.commit()
    novo_id = cur.lastrowid
    conn.close()
    return novo_id


def atualizar_item(item_id: int, nome: str, preco_adicional: float, insumo_id, disponivel: int):
    conn = conectar()
    conn.execute(
        "UPDATE itens_complemento SET nome=?, preco_adicional=?, insumo_id=?, disponivel=? WHERE id=?",
        (nome, preco_adicional, insumo_id or None, disponivel, item_id),
    )
    conn.commit()
    conn.close()


def deletar_item(item_id: int):
    conn = conectar()
    conn.execute("DELETE FROM itens_complemento WHERE id=?", (item_id,))
    conn.commit()
    conn.close()


def alternar_disponibilidade(item_id: int) -> int:
    """Toggle disponível/indisponível. Retorna o novo valor."""
    conn = conectar()
    conn.execute(
        "UPDATE itens_complemento SET disponivel = CASE WHEN disponivel=1 THEN 0 ELSE 1 END WHERE id=?",
        (item_id,),
    )
    conn.commit()
    row = conn.execute("SELECT disponivel FROM itens_complemento WHERE id=?", (item_id,)).fetchone()
    conn.close()
    return row["disponivel"] if row else 0


# ── Vínculo Produto → Grupo ───────────────────────────────────────────

def buscar_grupos_do_produto(produto_id: int, apenas_ativos: bool = False) -> list[dict]:
    """Retorna grupos vinculados ao produto com seus itens aninhados."""
    conn = conectar()
    sql = """
        SELECT pgc.id AS vinculo_id, pgc.tipo, pgc.obrigatorio,
               gc.id AS grupo_id, gc.nome AS grupo_nome, gc.ativo AS grupo_ativo
        FROM produto_grupo_complemento pgc
        JOIN grupos_complemento gc ON pgc.grupo_id = gc.id
        WHERE pgc.produto_id = ?
    """
    if apenas_ativos:
        sql += " AND gc.ativo = 1"
    rows = conn.execute(sql, (produto_id,)).fetchall()

    grupos = []
    for r in rows:
        g = dict(r)
        # Busca itens do grupo (só disponíveis se for exibição ao cliente)
        itens_sql = """
            SELECT ic.id, ic.nome, ic.preco_adicional, ic.disponivel, ic.insumo_id
            FROM itens_complemento ic
            WHERE ic.grupo_id = ?
        """
        if apenas_ativos:
            itens_sql += " AND ic.disponivel = 1"
        itens_sql += " ORDER BY ic.nome ASC"
        itens = conn.execute(itens_sql, (g["grupo_id"],)).fetchall()
        g["itens"] = [dict(i) for i in itens]
        grupos.append(g)

    conn.close()
    return grupos


def vincular_grupo_produto(produto_id: int, grupo_id: int, tipo: str, obrigatorio: int = 0):
    conn = conectar()
    conn.execute(
        """INSERT INTO produto_grupo_complemento (produto_id, grupo_id, tipo, obrigatorio)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(produto_id, grupo_id) DO UPDATE SET tipo=excluded.tipo, obrigatorio=excluded.obrigatorio""",
        (produto_id, grupo_id, tipo, obrigatorio),
    )
    conn.commit()
    conn.close()


def desvincular_grupo_produto(produto_id: int, grupo_id: int):
    conn = conectar()
    conn.execute(
        "DELETE FROM produto_grupo_complemento WHERE produto_id=? AND grupo_id=?",
        (produto_id, grupo_id),
    )
    conn.commit()
    conn.close()


# ── Complementos do Pedido ────────────────────────────────────────────

def salvar_complementos_pedido(pedido_id: int, complementos: list[dict]):
    """
    complementos = [
      { item_complemento_id, quantidade, preco_unitario, item_pedido_id? }
    ]
    """
    if not complementos:
        return
    conn = conectar()
    conn.executemany(
        """INSERT INTO pedido_complementos
           (pedido_id, item_pedido_id, item_complemento_id, quantidade, preco_unitario)
           VALUES (?, ?, ?, ?, ?)""",
        [
            (
                pedido_id,
                c.get("item_pedido_id"),
                c["item_complemento_id"],
                c.get("quantidade", 1),
                c.get("preco_unitario", 0),
            )
            for c in complementos
        ],
    )
    conn.commit()
    conn.close()


def buscar_complementos_pedido(pedido_id: int) -> list[dict]:
    conn = conectar()
    rows = conn.execute(
        """SELECT pc.*, ic.nome AS complemento_nome
           FROM pedido_complementos pc
           JOIN itens_complemento ic ON pc.item_complemento_id = ic.id
           WHERE pc.pedido_id = ?""",
        (pedido_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Consulta pública (cardápio) ───────────────────────────────────────

def buscar_complementos_por_produto_ids(produto_ids: list[int]) -> dict:
    """
    Retorna dict { produto_id: [grupos_com_itens] }
    Usado para carregar todos os complementos do cardápio de uma vez (1 query).
    """
    if not produto_ids:
        return {}
    placeholders = ",".join("?" * len(produto_ids))
    conn = conectar()
    rows = conn.execute(
        f"""SELECT pgc.produto_id, pgc.tipo, pgc.obrigatorio,
                   gc.id AS grupo_id, gc.nome AS grupo_nome,
                   ic.id AS item_id, ic.nome AS item_nome,
                   ic.preco_adicional, ic.disponivel
            FROM produto_grupo_complemento pgc
            JOIN grupos_complemento gc ON pgc.grupo_id = gc.id AND gc.ativo = 1
            JOIN itens_complemento ic ON ic.grupo_id = gc.id AND ic.disponivel = 1
            WHERE pgc.produto_id IN ({placeholders})
            ORDER BY pgc.produto_id, gc.nome, ic.nome""",
        produto_ids,
    ).fetchall()
    conn.close()

    resultado: dict = {}
    for r in rows:
        pid = r["produto_id"]
        if pid not in resultado:
            resultado[pid] = []

        # Encontra ou cria o grupo dentro desse produto
        grupo = next((g for g in resultado[pid] if g["grupo_id"] == r["grupo_id"]), None)
        if not grupo:
            grupo = {
                "grupo_id": r["grupo_id"],
                "grupo_nome": r["grupo_nome"],
                "tipo": r["tipo"],
                "obrigatorio": r["obrigatorio"],
                "itens": [],
            }
            resultado[pid].append(grupo)

        grupo["itens"].append({
            "id": r["item_id"],
            "nome": r["item_nome"],
            "preco_adicional": r["preco_adicional"],
        })

    return resultado


# ── Fluxo Montável ────────────────────────────────────────────────────

def buscar_produtos_montaveis() -> list[dict]:
    """
    Retorna todos os produtos que possuem ao menos um grupo de complemento
    vinculado, com seus grupos e itens aninhados (itens separados por taxa).
    """
    conn = conectar()
    rows = conn.execute("""
        SELECT
            p.id   AS produto_id,
            p.nome AS produto_nome,
            pgc.grupo_id,
            pgc.tipo,
            pgc.obrigatorio,
            gc.nome  AS grupo_nome,
            gc.ativo AS grupo_ativo,
            ic.id              AS item_id,
            ic.nome            AS item_nome,
            ic.preco_adicional,
            ic.disponivel
        FROM produtos p
        JOIN produto_grupo_complemento pgc ON pgc.produto_id = p.id
        JOIN grupos_complemento gc ON gc.id = pgc.grupo_id
        LEFT JOIN itens_complemento ic ON ic.grupo_id = gc.id
        ORDER BY p.nome ASC, gc.nome ASC, ic.nome ASC
    """).fetchall()
    conn.close()

    produtos: dict = {}
    for r in rows:
        pid = r["produto_id"]
        if pid not in produtos:
            produtos[pid] = {
                "produto_id":   pid,
                "produto_nome": r["produto_nome"],
                "grupos": {},
            }

        gid = r["grupo_id"]
        if gid not in produtos[pid]["grupos"]:
            produtos[pid]["grupos"][gid] = {
                "grupo_id":   gid,
                "grupo_nome": r["grupo_nome"],
                "tipo":       r["tipo"],
                "obrigatorio": r["obrigatorio"],
                "itens_sem_taxa": [],
                "itens_com_taxa": [],
            }

        if r["item_id"] is not None:
            item = {
                "id":             r["item_id"],
                "nome":           r["item_nome"],
                "preco_adicional": r["preco_adicional"],
                "disponivel":     r["disponivel"],
            }
            if r["preco_adicional"] and r["preco_adicional"] > 0:
                produtos[pid]["grupos"][gid]["itens_com_taxa"].append(item)
            else:
                produtos[pid]["grupos"][gid]["itens_sem_taxa"].append(item)

    # Converte dicts internos para listas
    resultado = []
    for p in produtos.values():
        p["grupos"] = list(p["grupos"].values())
        resultado.append(p)
    return resultado
