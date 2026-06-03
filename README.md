# 🍔 Cardápio Digital — Sistema de Gestão para Lanchonetes

> Aplicação web full-stack para gestão completa de lanchonetes, desenvolvida em Python/Flask. Cobre todo o ciclo operacional: cardápio digital com carrinho, pagamento via PIX, gestão de pedidos, controle de estoque, controle de acesso e insights com IA.

<br>

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat-square&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)
![Waitress](https://img.shields.io/badge/WSGI-Waitress-4B8BBE?style=flat-square)
![Cloudflare](https://img.shields.io/badge/Tunnel-Cloudflare-F38020?style=flat-square&logo=cloudflare&logoColor=white)

---

## ✨ Funcionalidades

### 🛒 Vitrine do Cliente
- **Cardápio digital** com categorias, imagens e carrinho
- **Pagamento via PIX** integrado ao Mercado Pago SDK
- Layout responsivo otimizado para pedidos pelo celular

### 📋 Gestão de Pedidos
- **Quadro Kanban** com atualização automática em tempo real
- Pedidos filtrados por função — atendentes veem apenas seus próprios pedidos
- Rastreamento `lancado_por`: registra qual atendente abriu cada pedido
- Presets de filtro salvos por usuário
- Filtragem por janela de turno com timestamps corretos por fuso horário

### 🏪 Painel Administrativo
- **Dashboard** com visão geral das vendas
- Navegação dinâmica com reordenação por arrastar e soltar
- Aparência da vitrine configurável pelo admin (cores, logo, banner)
- **Log de auditoria** para todas as operações críticas

### 📦 Controle de Estoque
- **Interface com 4 abas**: Insumos Brutos · Insumos Fabricados · Receitas · Alertas
- **Lógica PVPS** (Primeiro a Vencer, Primeiro a Sair) no consumo de lotes
- Alertas de estoque mínimo configuráveis por insumo
- **Contagem física diária**: lançamento manual do inventário no final do dia
- Lista de compras gerada automaticamente a partir dos itens em baixa
- Custo unitário por insumo com histórico

### 💰 Financeiro
- Custo de produção por produto (visível apenas no admin)
- Margem de lucro calculada automaticamente no card de cada produto
- Custo estimado de reposição na lista de compras

### 🔐 Controle de Acesso (GPO)
- Usuários, Grupos e Políticas — sistema de permissões granular
- Renderização de interface baseada em função (admin / atendente / caixa)
- Gerenciamento de sessão com TTL configurável

### 🤖 Insights com IA
- Análise de negócio via **API da Anthropic (Claude)**
- Analisa pedidos, estoque e padrões de venda
- Sugestões exibidas no painel administrativo
- A IA nunca altera dados — camada exclusivamente de leitura e análise

### 🖨️ Impressora Térmica
- Suporte a ESC/POS via `python-escpos`
- Modos de conexão: USB, Rede e Serial
- Fila de impressão em background com retry automático
- Página de configuração no painel admin

### 🌐 Infraestrutura
- Servidor WSGI de produção: **Waitress**
- **Cloudflare Tunnel** com autenticação por token — sem necessidade de abrir portas
- Scripts `.bat` de inicialização para deploy no Windows
- Logs rotativos com estrutura padronizada
- Rate limiting via Flask-Limiter (proteção contra DDoS e brute-force)
- Seletor de fuso horário configurável pelo admin

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                  Aplicação Flask                         │
│               (Application Factory)                     │
├────────────┬────────────────────┬───────────────────────┤
│ Controllers│     Services       │    Repositories       │
│ (Blueprints│  (Regras de negócio│  (Acesso a dados)     │
├────────────┼────────────────────┼───────────────────────┤
│ auth       │ pedido_service     │ produto_repository    │
│ admin      │ estoque_service    │ pedido_repository     │
│ vendas     │ pagamento_service  │ estoque_repository    │
│ atendente  │ ia_service         │ config_repository     │
│ gpo        │ auditoria_service  │ gpo_repository        │
│ impressora │ complemento_service│ auditoria_repository  │
│ ia         │                    │                       │
└────────────┴────────────────────┴───────────────────────┘
                         │
                  SQLite (SQL puro)
```

**Hierarquia de templates** — sistema Jinja2 em 4 camadas:
```
base.html  →  page.html  →  components/  →  partials/
```

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12+, Flask 3.0 |
| Banco de dados | SQLite (SQL puro, sem ORM) |
| Frontend | Jinja2, Tailwind CSS, JavaScript puro (fetch API) |
| WSGI | Waitress |
| Pagamentos | Mercado Pago SDK |
| Inteligência Artificial | API da Anthropic (Claude) |
| Impressão | python-escpos (ESC/POS) |
| Tunelamento | Cloudflare Tunnel |
| Proteção | Flask-Limiter |

---

## 🚀 Como Executar

### Pré-requisitos

- Python 3.12+
- pip

### Instalação

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/cardapio-refatorado.git
cd cardapio-refatorado

# Crie e ative o ambiente virtual
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

# Instale as dependências
pip install -r requirements.txt

# Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env com suas chaves (veja a seção de Configuração)

# Execute
python run.py
```

### Configuração (`.env`)

```env
SECRET_KEY=sua-chave-secreta

# Mercado Pago
MP_ACCESS_TOKEN=seu-token-mp

# Anthropic (Insights com IA)
ANTHROPIC_API_KEY=sua-chave-anthropic

# Cloudflare Tunnel (opcional)
CF_TUNNEL_TOKEN=seu-token-tunnel

# Fuso horário
APP_TIMEZONE=America/Recife
```

---

## 📁 Estrutura do Projeto

```
cardapio-refatorado/
├── app/
│   ├── __init__.py              # Application Factory
│   ├── controllers/             # Blueprints Flask (camada HTTP)
│   │   ├── admin_controller.py
│   │   ├── vendas_controller.py
│   │   ├── atendente_controller.py
│   │   ├── gpo_controller.py
│   │   ├── impressora_controller.py
│   │   └── ia_controller.py
│   ├── services/                # Regras de negócio
│   │   ├── pedido_service.py
│   │   ├── estoque_service.py
│   │   ├── pagamento_service.py
│   │   └── ia_service.py
│   ├── repositories/            # Acesso a dados
│   │   ├── db.py                # Schema e migrações
│   │   ├── produto_repository.py
│   │   ├── pedido_repository.py
│   │   └── estoque_repository.py
│   └── utils/
├── templates/
│   ├── base.html
│   ├── admin/
│   │   ├── dashboard.html
│   │   ├── estoque.html
│   │   ├── pedidos.html
│   │   └── ...
│   └── components/
├── static/
├── config/
│   └── settings.py
├── run.py
├── wsgi.py
└── requirements.txt
```

---

## 📸 Screenshots

> *(Adicione capturas de tela do painel admin, kanban e cardápio do cliente aqui)*

---

## 🔑 Decisões de Arquitetura

**SQL puro sem ORM** — Todas as queries usam colunas explícitas, sem `SELECT *`. Isso mantém as consultas transparentes e evita problemas de N+1 que ORMs podem mascarar.

**Separação estrita de responsabilidades** — Controllers tratam apenas HTTP (request/response). Regras de negócio ficam exclusivamente nos services. Repositories concentram todo o SQL.

**IA como conselheira somente-leitura** — O `ia_service` tem acesso aos repositories mas nunca escreve no banco. Essa fronteira arquitetural garante que sugestões da IA nunca possam corromper dados operacionais.

**Baixa de estoque configurável** — A baixa automática ao confirmar venda pode ser ligada ou desligada nas configurações do admin. Quando desligada, o dono faz a contagem física manual no final do dia.

**Deploy sem infraestrutura complexa** — Cloudflare Tunnel elimina a necessidade de IP fixo, configuração de roteador ou servidor dedicado. O sistema roda em qualquer máquina Windows da lanchonete.

---

## 👨‍💻 Sobre

Desenvolvido por **Kauã** como projeto full-stack real durante a transição de Suporte de TI para Engenharia Backend/DevOps. O sistema está em uso ativo em produção por um cliente real.

---

## 📄 Licença

Este projeto está licenciado sob a licença MIT.
