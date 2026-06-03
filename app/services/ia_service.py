"""
Service de IA — coleta dados do sistema, monta payload e consulta a API da Anthropic.

Regras importantes:
  • A IA NUNCA altera dados — apenas analisa e sugere.
  • Este service não conhece Flask nem HTTP diretamente.
  • Toda comunicação com o banco passa pelos repositories.
"""

import json
import os
import time
from datetime import datetime, timedelta

import requests

# ── Constantes ────────────────────────────────────────────────────────

GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)
TIMEOUT_SEGUNDOS = 60

from app.repositories import (
    pedido_repository,
    produto_repository,
    estoque_repository,
)
from app.repositories.db import conectar


# ── Constantes ────────────────────────────────────────────────────────

TIMEOUT_SEGUNDOS = 60

_SYSTEM_PROMPT = """Você é um assistente analítico especializado em negócios de alimentação (restaurantes, lanchonetes, açaiterias).

Você recebe dados reais do sistema e deve:
1. Analisar o desempenho de vendas, custos e estoque
2. Identificar problemas e riscos
3. Apontar oportunidades de melhora
4. Fazer previsões baseadas nos dados fornecidos
5. Sugerir ações práticas e concretas

REGRAS OBRIGATÓRIAS:
- Responda APENAS com JSON válido, sem texto antes ou depois, sem blocos de código markdown
- Não invente dados — baseie-se apenas no que foi fornecido
- Seja objetivo e direto — as sugestões devem ser acionáveis
- Quando o estoque está crítico, priorize isso nos problemas
- Calcule dias de estoque restante quando possível
- Identifique produtos com alta margem e baixo volume (oportunidade de empurrar)
- Se não houver dados suficientes para uma seção, retorne array vazio

FORMATO DE RESPOSTA (JSON estrito):
{
  "resumo": "string com visão geral do negócio em 2-3 frases",
  "score_saude": número de 0 a 100 indicando saúde geral do negócio,
  "problemas": [
    {"titulo": "string curto", "descricao": "detalhe", "urgencia": "alta|media|baixa"}
  ],
  "oportunidades": [
    {"titulo": "string curto", "descricao": "detalhe", "impacto": "alto|medio|baixo"}
  ],
  "previsoes": [
    {"titulo": "string curto", "descricao": "detalhe"}
  ],
  "recomendacoes": [
    {
      "texto": "ação prática e específica",
      "categoria": "estoque|vendas|custo|produto|operacional",
      "prioridade": "alta|media|baixa"
    }
  ]
}"""


# ── Coleta de Dados ───────────────────────────────────────────────────

def _coletar_dados_vendas(dias: int = 30) -> dict:
    """Coleta resumo de vendas dos últimos N dias."""
    dt_inicio = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d 00:00:00")
    pedidos = pedido_repository.buscar_pedidos(dt_inicio=dt_inicio)

    if not pedidos:
        return {
            "periodo_dias": dias,
            "total_faturamento": 0,
            "total_pedidos": 0,
            "ticket_medio": 0,
            "por_metodo_pagamento": {},
            "top_produtos": [],
            "pedidos_por_dia": {},
        }

    total_faturamento = sum(p.get("total_geral") or 0 for p in pedidos)
    total_pedidos = len(pedidos)
    ticket_medio = round(total_faturamento / total_pedidos, 2) if total_pedidos else 0

    # Contagem por método de pagamento
    por_metodo: dict[str, dict] = {}
    for p in pedidos:
        metodo = (p.get("metodo_pagamento") or "DESCONHECIDO").upper()
        por_metodo.setdefault(metodo, {"pedidos": 0, "faturamento": 0.0})
        por_metodo[metodo]["pedidos"] += 1
        por_metodo[metodo]["faturamento"] += p.get("total_geral") or 0

    # Top produtos
    contagem_produtos: dict[str, dict] = {}
    for p in pedidos:
        for item in p.get("itens", []):
            nome = item.get("produto_nome", "?")
            qtd = item.get("quantidade", 0)
            preco = item.get("preco_unitario", 0)
            contagem_produtos.setdefault(nome, {"quantidade_vendida": 0, "faturamento": 0.0})
            contagem_produtos[nome]["quantidade_vendida"] += qtd
            contagem_produtos[nome]["faturamento"] += qtd * preco

    top_produtos = sorted(
        [{"nome": k, **v} for k, v in contagem_produtos.items()],
        key=lambda x: x["faturamento"],
        reverse=True,
    )[:10]

    # Pedidos por dia (últimos 7 dias)
    por_dia: dict[str, int] = {}
    for p in pedidos:
        data = str(p.get("data_hora", ""))[:10]
        por_dia[data] = por_dia.get(data, 0) + 1

    return {
        "periodo_dias": dias,
        "total_faturamento": round(total_faturamento, 2),
        "total_pedidos": total_pedidos,
        "ticket_medio": ticket_medio,
        "por_metodo_pagamento": por_metodo,
        "top_produtos": top_produtos,
        "pedidos_por_dia": dict(sorted(por_dia.items())[-7:]),
    }


def _coletar_dados_produtos() -> list[dict]:
    """Retorna produtos com preço, custo estimado e margem."""
    produtos = produto_repository.buscar_todos()
    resultado = []
    conn = conectar()

    for prod in produtos:
        if not prod.get("visivel"):
            continue

        # Calcula custo estimado via produto_insumo + lotes
        custo_estimado = _calcular_cmv_produto(conn, prod["id"])

        resultado.append({
            "id": prod["id"],
            "nome": prod["nome"],
            "categoria": prod.get("categoria", ""),
            "preco_venda": prod.get("preco", 0),
            "custo_estimado": round(custo_estimado, 4),
            "margem_percentual": round(
                ((prod.get("preco", 0) - custo_estimado) / prod.get("preco", 1)) * 100, 1
            ) if prod.get("preco") else 0,
        })

    conn.close()
    return resultado


def _calcular_cmv_produto(conn, produto_id: int) -> float:
    """Soma custo dos insumos vinculados ao produto (custo médio por unidade)."""
    rows = conn.execute(
        """SELECT pi.quantidade,
                  COALESCE(
                      (SELECT SUM(l.custo_lote) / NULLIF(SUM(l.quantidade_inicial), 0)
                       FROM lotes l
                       WHERE l.insumo_id = pi.insumo_id
                         AND l.validade >= date('now')
                         AND l.quantidade_inicial > 0),
                      0
                  ) AS custo_unitario_insumo
           FROM produto_insumo pi
           WHERE pi.produto_id = ?""",
        (produto_id,),
    ).fetchall()
    return sum(r["quantidade"] * r["custo_unitario_insumo"] for r in rows)


def _coletar_dados_estoque() -> dict:
    """Coleta status do estoque: alertas, validades e consumo estimado."""
    insumos = estoque_repository.buscar_insumos()
    alertas = estoque_repository.buscar_alertas_estoque()

    # Detecta vencimentos próximos (7 dias)
    conn = conectar()
    vencimentos = conn.execute(
        """SELECT i.nome, l.validade, l.quantidade_atual, l.id AS lote_id
           FROM lotes l
           JOIN insumos i ON i.id = l.insumo_id
           WHERE l.validade BETWEEN date('now') AND date('now', '+7 days')
             AND l.quantidade_atual > 0
           ORDER BY l.validade ASC""",
    ).fetchall()
    conn.close()

    resumo = []
    for ins in insumos:
        resumo.append({
            "nome": ins["nome"],
            "unidade": ins.get("unidade_base", ""),
            "tipo": ins.get("tipo", "bruto"),
            "estoque_atual": round(ins.get("total_estoque", 0), 2),
            "estoque_minimo": ins.get("estoque_minimo", 0),
            "proxima_validade": ins.get("proxima_validade"),
            "status": (
                "critico" if ins.get("total_estoque", 0) == 0
                else "alerta" if ins.get("total_estoque", 0) <= ins.get("estoque_minimo", 0)
                else "ok"
            ),
        })

    return {
        "total_insumos": len(insumos),
        "alertas_estoque_minimo": [
            {
                "nome": a["nome"],
                "estoque_atual": a.get("total_estoque", 0),
                "estoque_minimo": a.get("estoque_minimo", 0),
                "unidade": a.get("unidade_base", ""),
            }
            for a in alertas
        ],
        "vencimentos_proximos": [
            {
                "nome": v["nome"],
                "validade": v["validade"],
                "quantidade": round(v["quantidade_atual"], 2),
            }
            for v in vencimentos
        ],
        "insumos": resumo,
    }


def _coletar_custos_operacionais() -> dict:
    """Coleta custos a partir de configurações e estoque."""
    conn = conectar()
    row = conn.execute("SELECT valor FROM configuracoes WHERE chave = 'custo_fixo_mensal'").fetchone()
    custo_fixo = float(row["valor"]) if row else 0.0

    row2 = conn.execute("SELECT valor FROM configuracoes WHERE chave = 'custo_operacional_mensal'").fetchone()
    custo_op = float(row2["valor"]) if row2 else 0.0

    # Valor total do estoque (custo de reposição)
    row3 = conn.execute(
        """SELECT COALESCE(SUM(l.quantidade_atual *
              (l.custo_lote / NULLIF(l.quantidade_inicial, 0))), 0) AS valor_estoque
           FROM lotes l
           WHERE l.validade >= date('now') AND l.quantidade_atual > 0"""
    ).fetchone()
    valor_estoque = round(float(row3["valor_estoque"]) if row3 else 0.0, 2)

    conn.close()
    return {
        "fixos_mensais": custo_fixo,
        "operacionais_mensais": custo_op,
        "valor_estoque_atual": valor_estoque,
    }


def coletar_payload_completo(dias_vendas: int = 30) -> dict:
    """Monta o payload completo para envio à IA."""
    return {
        "contexto": {
            "data_analise": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "periodo_vendas_dias": dias_vendas,
        },
        "vendas": _coletar_dados_vendas(dias_vendas),
        "produtos": _coletar_dados_produtos(),
        "estoque": _coletar_dados_estoque(),
        "custos": _coletar_custos_operacionais(),
    }


# ── Chamada à API ─────────────────────────────────────────────────────

def _obter_api_key() -> str:
    """Lê a chave do Gemini do ambiente ou do banco de dados."""
    chave = os.getenv("GEMINI_API_KEY", "")
    if not chave:
        try:
            conn = conectar()
            row = conn.execute(
                "SELECT valor FROM configuracoes WHERE chave = 'gemini_api_key'"
            ).fetchone()
            conn.close()
            if row:
                chave = row["valor"]
        except Exception:
            pass
    return chave.strip()


def chamar_ia(payload: dict, tipo_analise: str = "completa") -> dict:
    """
    Envia o payload para o Gemini e retorna a análise estruturada.

    Retorna dict com:
        - ok: bool
        - analise: dict (quando ok=True)
        - erro: str (quando ok=False)
        - tokens_usados: int
        - duracao_ms: int
    """
    api_key = _obter_api_key()
    if not api_key:
        return {
            "ok": False,
            "erro": "GEMINI_API_KEY não configurada. Adicione ao .env ou em Configurações.",
            "tokens_usados": 0,
            "duracao_ms": 0,
        }

    mensagem_usuario = (
        f"Analise os dados do meu negócio e retorne o JSON conforme instruído.\n\n"
        f"Tipo de análise solicitada: {tipo_analise}\n\n"
        f"DADOS DO SISTEMA:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )

    corpo = {
        "system_instruction": {
            "parts": [{"text": _SYSTEM_PROMPT}]
        },
        "contents": [
            {"role": "user", "parts": [{"text": mensagem_usuario}]}
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "maxOutputTokens": 2000,
            "temperature": 0.3,
        },
    }

    inicio = time.time()
    try:
        resp = requests.post(
            GEMINI_API_URL,
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json=corpo,
            timeout=TIMEOUT_SEGUNDOS,
        )
        duracao_ms = int((time.time() - inicio) * 1000)

        if resp.status_code != 200:
            return {
                "ok": False,
                "erro": f"Gemini retornou HTTP {resp.status_code}: {resp.text[:300]}",
                "tokens_usados": 0,
                "duracao_ms": duracao_ms,
            }

        data = resp.json()

        # Extrai texto da resposta do Gemini
        try:
            texto_resposta = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError):
            return {
                "ok": False,
                "erro": "Resposta inesperada do Gemini. Tente novamente.",
                "tokens_usados": 0,
                "duracao_ms": duracao_ms,
            }

        tokens_usados = data.get("usageMetadata", {}).get("candidatesTokenCount", 0)

        # Remove blocos markdown caso a IA os inclua mesmo com response_mime_type
        if texto_resposta.startswith("```"):
            linhas = texto_resposta.splitlines()
            texto_resposta = "\n".join(
                l for l in linhas if not l.strip().startswith("```")
            ).strip()

        analise = json.loads(texto_resposta)

        return {
            "ok": True,
            "analise": analise,
            "tokens_usados": tokens_usados,
            "duracao_ms": duracao_ms,
        }

    except requests.Timeout:
        duracao_ms = int((time.time() - inicio) * 1000)
        return {
            "ok": False,
            "erro": f"Timeout após {TIMEOUT_SEGUNDOS}s. Tente novamente.",
            "tokens_usados": 0,
            "duracao_ms": duracao_ms,
        }
    except json.JSONDecodeError as e:
        duracao_ms = int((time.time() - inicio) * 1000)
        return {
            "ok": False,
            "erro": f"Gemini retornou resposta inválida (não é JSON): {e}",
            "tokens_usados": 0,
            "duracao_ms": duracao_ms,
        }
    except Exception as e:
        duracao_ms = int((time.time() - inicio) * 1000)
        return {
            "ok": False,
            "erro": f"Erro inesperado: {str(e)}",
            "tokens_usados": 0,
            "duracao_ms": duracao_ms,
        }


# ── Ponto de entrada principal ────────────────────────────────────────

def executar_analise(tipo_analise: str = "completa", dias_vendas: int = 30) -> dict:
    """
    Função principal: coleta dados → chama IA → retorna resultado completo.

    Retorna:
        ok: bool
        analise: dict (resumo, problemas, oportunidades, previsoes, recomendacoes)
        payload: dict (dados enviados, para debug)
        tokens_usados: int
        duracao_ms: int
        erro: str (se ok=False)
    """
    payload = coletar_payload_completo(dias_vendas)
    resultado = chamar_ia(payload, tipo_analise)
    resultado["payload"] = payload
    return resultado
