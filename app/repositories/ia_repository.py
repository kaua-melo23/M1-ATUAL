"""
Repository de IA — persiste histórico de análises e sugestões aplicadas.

Responsabilidade única: SQL de leitura/escrita nas tabelas de auditoria de IA.
Nenhuma regra de negócio aqui.
"""

from app.repositories.db import conectar


# ── Análises ──────────────────────────────────────────────────────────

def registrar_analise(
    usuario: str,
    role: str,
    tipo_analise: str,
    tokens_usados: int,
    duracao_ms: int,
) -> int:
    """Registra uma análise realizada. Retorna o ID gerado."""
    conn = conectar()
    cur = conn.execute(
        """INSERT INTO ia_analises (usuario, role, tipo_analise, tokens_usados, duracao_ms)
           VALUES (?, ?, ?, ?, ?)""",
        (usuario, role, tipo_analise, tokens_usados, duracao_ms),
    )
    conn.commit()
    analise_id = cur.lastrowid
    conn.close()
    return analise_id


def buscar_historico(limite: int = 30) -> list[dict]:
    """Retorna as análises mais recentes, com contagem de sugestões aplicadas."""
    conn = conectar()
    rows = conn.execute(
        """SELECT a.*,
                  COUNT(s.id) AS sugestoes_aplicadas
           FROM ia_analises a
           LEFT JOIN ia_sugestoes_aplicadas s ON a.id = s.analise_id
           GROUP BY a.id
           ORDER BY a.data_hora DESC
           LIMIT ?""",
        (limite,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Sugestões Aplicadas ───────────────────────────────────────────────

def registrar_sugestao_aplicada(
    analise_id: int,
    sugestao_texto: str,
    usuario: str,
    categoria: str = "recomendacao",
) -> int:
    """Registra que o usuário reconheceu/encaminhou uma sugestão da IA."""
    conn = conectar()
    cur = conn.execute(
        """INSERT INTO ia_sugestoes_aplicadas (analise_id, sugestao_texto, usuario, categoria)
           VALUES (?, ?, ?, ?)""",
        (analise_id, sugestao_texto, usuario, categoria),
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def buscar_sugestoes_aplicadas(analise_id: int) -> list[dict]:
    conn = conectar()
    rows = conn.execute(
        """SELECT * FROM ia_sugestoes_aplicadas
           WHERE analise_id = ?
           ORDER BY data_hora DESC""",
        (analise_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
