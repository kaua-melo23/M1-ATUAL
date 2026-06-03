"""
Repository de Produtos — acesso a dados da tabela `produtos`.

Melhorias:
- Sem SELECT * — colunas explícitas
- Usa get_db() em vez de conectar() — reutiliza conexão da requisição
- Cache em memória para buscar_visiveis (cardápio público, dado estático)
- Invalidação de cache ao escrever
"""

from app.repositories.db import get_db, conectar
from app.utils.cache import cache

_TTL_PRODUTOS = 120  # 2 minutos — cardápio muda raramente

_COLUNAS = "id, nome, preco, categoria, imagem, ingredientes, visivel"


def buscar_todos() -> list[dict]:
    """Admin: retorna todos os produtos sem cache."""
    conn = get_db()
    rows = conn.execute(
        f"SELECT {_COLUNAS} FROM produtos ORDER BY categoria, nome"
    ).fetchall()
    return [dict(r) for r in rows]


@cache.cached(ttl=_TTL_PRODUTOS, key="produtos:visiveis")
def buscar_visiveis() -> list[dict]:
    """Cardápio público — cacheado, usando conexão isolada (pode ser chamado fora de requisição)."""
    conn = conectar()
    rows = conn.execute(
        f"SELECT {_COLUNAS} FROM produtos WHERE visivel = 1 ORDER BY categoria, nome"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def buscar_por_id(produto_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute(
        f"SELECT {_COLUNAS} FROM produtos WHERE id = ?", (produto_id,)
    ).fetchone()
    return dict(row) if row else None


def buscar_por_nome(nome: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT id, nome FROM produtos WHERE nome = ?", (nome,)
    ).fetchone()
    return dict(row) if row else None


def inserir(nome: str, preco: float, categoria: str, imagem: str, ingredientes: str) -> int:
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO produtos (nome, preco, categoria, imagem, ingredientes, visivel) VALUES (?, ?, ?, ?, ?, 1)",
        (nome, preco, categoria, imagem, ingredientes),
    )
    conn.commit()
    _invalidar_cache()
    return cur.lastrowid


def atualizar(
    produto_id: int,
    nome: str,
    preco: float,
    categoria: str,
    imagem: str | None,
    ingredientes: str,
    visivel: int,
):
    conn = get_db()
    if imagem:
        conn.execute(
            "UPDATE produtos SET nome=?, preco=?, categoria=?, imagem=?, ingredientes=?, visivel=? WHERE id=?",
            (nome, preco, categoria, imagem, ingredientes, visivel, produto_id),
        )
    else:
        conn.execute(
            "UPDATE produtos SET nome=?, preco=?, categoria=?, ingredientes=?, visivel=? WHERE id=?",
            (nome, preco, categoria, ingredientes, visivel, produto_id),
        )
    conn.commit()
    _invalidar_cache()


def deletar(produto_id: int):
    conn = get_db()
    conn.execute("DELETE FROM produtos WHERE id = ?", (produto_id,))
    conn.commit()
    _invalidar_cache()


def _invalidar_cache():
    cache.invalidar("produtos:visiveis")
