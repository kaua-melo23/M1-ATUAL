"""
Camada de infraestrutura — conexão e inicialização do banco de dados.

Melhorias aplicadas:
- WAL mode: leituras e escritas simultâneas sem bloqueio total
- Índices nos campos mais consultados (status, data_hora, produto_id, etc.)
- PRAGMA cache_size e temp_store para melhor uso de memória
- Conexão única por requisição via g (padrão Flask correto)
- init_db idempotente e sem queries repetitivas no startup
"""

import sqlite3
import os
import logging
from flask import current_app, g

logger = logging.getLogger(__name__)


def get_db_path() -> str:
    try:
        return current_app.config["DB_PATH"]
    except RuntimeError:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        return os.path.join(base, "database", "lanchonete.db")


def _configurar_conexao(conn: sqlite3.Connection) -> None:
    """Aplica PRAGMAs de performance em cada conexão nova."""
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-8000")   # ~8MB de cache
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA foreign_keys=ON")


def conectar() -> sqlite3.Connection:
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    _configurar_conexao(conn)
    return conn


def get_db() -> sqlite3.Connection:
    """
    Retorna conexão vinculada ao contexto da requisição Flask (g).
    Uma única conexão por requisição — sem overhead de reconexão.
    """
    if "db" not in g:
        g.db = conectar()
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ── Schema ─────────────────────────────────────────────────────────────

_DDL_TABELAS = """
CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    preco REAL NOT NULL,
    categoria TEXT,
    imagem TEXT,
    ingredientes TEXT,
    visivel INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS taxas_entrega (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bairro TEXT UNIQUE NOT NULL,
    taxa REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cliente_nome TEXT,
    cliente_telefone TEXT,
    bairro TEXT,
    endereco TEXT,
    total_produtos REAL,
    taxa_entrega REAL,
    total_geral REAL,
    metodo_pagamento TEXT,
    status TEXT DEFAULT 'Pendente',
    id_pagamento_mp TEXT,
    lancado_por INTEGER,
    valor_pago REAL DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS itens_pedido (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER,
    produto_nome TEXT,
    quantidade INTEGER,
    preco_unitario REAL,
    FOREIGN KEY (pedido_id) REFERENCES pedidos (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS insumos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    unidade_base TEXT NOT NULL,
    estoque_minimo REAL DEFAULT 0,
    tipo TEXT DEFAULT 'bruto',
    validade_padrao DATE
);

CREATE TABLE IF NOT EXISTS lotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insumo_id INTEGER,
    quantidade_inicial REAL,
    quantidade_atual REAL,
    validade DATE,
    custo_lote REAL,
    data_entrada DATE,
    FOREIGN KEY (insumo_id) REFERENCES insumos (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS receitas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insumo_fabricado_id INTEGER NOT NULL,
    insumo_bruto_id INTEGER NOT NULL,
    quantidade REAL NOT NULL,
    FOREIGN KEY (insumo_fabricado_id) REFERENCES insumos (id) ON DELETE CASCADE,
    FOREIGN KEY (insumo_bruto_id) REFERENCES insumos (id)
);

CREATE TABLE IF NOT EXISTS produto_insumo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_id INTEGER NOT NULL,
    insumo_id INTEGER NOT NULL,
    quantidade REAL NOT NULL DEFAULT 1,
    FOREIGN KEY (produto_id) REFERENCES produtos (id) ON DELETE CASCADE,
    FOREIGN KEY (insumo_id) REFERENCES insumos (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS configuracoes (
    chave TEXT PRIMARY KEY,
    valor TEXT
);

CREATE TABLE IF NOT EXISTS categorias_cliente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    emoji TEXT DEFAULT '🍽️',
    ordem INTEGER DEFAULT 0,
    ativo INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS menu_admin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    url TEXT NOT NULL,
    emoji TEXT DEFAULT '📄',
    ordem INTEGER DEFAULT 0,
    visivel INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS ia_analises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT NOT NULL,
    role TEXT NOT NULL,
    tipo_analise TEXT DEFAULT 'completa',
    tokens_usados INTEGER DEFAULT 0,
    duracao_ms INTEGER DEFAULT 0,
    data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ia_sugestoes_aplicadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analise_id INTEGER NOT NULL,
    sugestao_texto TEXT NOT NULL,
    usuario TEXT NOT NULL,
    categoria TEXT DEFAULT 'recomendacao',
    data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (analise_id) REFERENCES ia_analises(id) ON DELETE CASCADE
);
"""

_DDL_INDICES = """
CREATE INDEX IF NOT EXISTS idx_pedidos_status ON pedidos(status);
CREATE INDEX IF NOT EXISTS idx_pedidos_data_hora ON pedidos(data_hora);
CREATE INDEX IF NOT EXISTS idx_pedidos_lancado_por ON pedidos(lancado_por);
CREATE INDEX IF NOT EXISTS idx_pedidos_id_mp ON pedidos(id_pagamento_mp);
CREATE INDEX IF NOT EXISTS idx_itens_pedido_id ON itens_pedido(pedido_id);
CREATE INDEX IF NOT EXISTS idx_produtos_visivel ON produtos(visivel);
CREATE INDEX IF NOT EXISTS idx_produtos_categoria ON produtos(categoria);
CREATE INDEX IF NOT EXISTS idx_lotes_insumo ON lotes(insumo_id);
CREATE INDEX IF NOT EXISTS idx_lotes_validade ON lotes(validade);
CREATE INDEX IF NOT EXISTS idx_produto_insumo_produto ON produto_insumo(produto_id);
CREATE INDEX IF NOT EXISTS idx_produto_insumo_insumo ON produto_insumo(insumo_id);
CREATE INDEX IF NOT EXISTS idx_insumos_nome ON insumos(nome);
"""

_CONFIGS_PADRAO = [
    ("nome_lanchonete", "Lanchonete Express"),
    ("slogan", "O melhor sabor da região"),
    ("cor_primaria", "#dc2626"),
    ("cor_texto_header", "#ffffff"),
    ("logo_url", ""),
    ("hora_abertura", "18:00"),
    ("hora_fechamento", "23:00"),
    ("offset_fuso", "-3"),
]

_CATEGORIAS_PADRAO = [
    ("Lanches", "🍔", 0),
    ("Bebidas", "🥤", 1),
    ("Porções", "🍟", 2),
    ("Sobremesas", "🍨", 3),
]

_MENU_ADMIN_PADRAO = [
    ("Dashboard",    "/admin",               "📊", 0),
    ("Relatórios",   "/admin/relatorios",    "📈", 1),
    ("Estoque",      "/admin/estoque",       "📦", 2),
    ("Produtos",     "/admin/produtos",      "🍔", 3),
    ("Complementos", "/admin/complementos",  "🍓", 4),
    ("Pedidos",      "/admin/pedidos",       "🛵", 5),
    ("Taxas",        "/admin/taxas",         "📍", 6),
    ("Aparência",    "/admin/aparencia",     "🎨", 7),
    ("Navegação",    "/admin/navegacao",     "🗂️", 8),
    ("GPO",          "/admin/gpo",           "👥", 9),
    ("Impressora",   "/admin/impressora",    "🖨️", 10),
    ("IA / Insights","/admin/ia",            "🤖", 11),
]

_MIGRACOES = [
    ("ALTER TABLE produtos ADD COLUMN ingredientes TEXT", None),
    ("ALTER TABLE produtos ADD COLUMN visivel INTEGER DEFAULT 1",
     "UPDATE produtos SET visivel = 1 WHERE visivel IS NULL"),
    ("ALTER TABLE insumos ADD COLUMN tipo TEXT DEFAULT 'bruto'",
     "UPDATE insumos SET tipo = 'bruto' WHERE tipo IS NULL"),
    ("ALTER TABLE insumos ADD COLUMN validade_padrao DATE", None),
    ("ALTER TABLE pedidos ADD COLUMN lancado_por INTEGER", None),
    ("ALTER TABLE pedidos ADD COLUMN cliente_telefone TEXT", None),
    ("ALTER TABLE pedidos ADD COLUMN valor_pago REAL", None),
]


def init_db():
    """Cria tabelas, índices, valores padrão e executa migrações."""
    conn = conectar()
    cur = conn.cursor()

    cur.executescript(_DDL_TABELAS)
    cur.executescript(_DDL_INDICES)

    # Configs padrão (INSERT OR IGNORE — idempotente)
    cur.executemany(
        "INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES (?, ?)",
        _CONFIGS_PADRAO,
    )

    # Categorias padrão (só se tabela vazia)
    if cur.execute("SELECT COUNT(*) FROM categorias_cliente").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO categorias_cliente (nome, emoji, ordem, ativo) VALUES (?, ?, ?, 1)",
            _CATEGORIAS_PADRAO,
        )

    # Menu admin — inserção idempotente por URL (sem SELECT antes de cada INSERT)
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_menu_admin_url ON menu_admin(url)")
    for label, url, emoji, ordem in _MENU_ADMIN_PADRAO:
        cur.execute(
            "INSERT OR IGNORE INTO menu_admin (label, url, emoji, ordem, visivel) VALUES (?, ?, ?, ?, 1)",
            (label, url, emoji, ordem),
        )

    conn.commit()

    # Migrações incrementais
    for sql, followup in _MIGRACOES:
        try:
            cur.execute(sql)
            if followup:
                cur.execute(followup)
            conn.commit()
        except Exception:
            pass  # Coluna já existe — erro esperado e ignorado

    conn.close()
    logger.info("Banco de dados inicializado.")
