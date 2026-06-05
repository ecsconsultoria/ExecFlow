# AGENTS.md — Guia para Agentes de IA

> **Objetivo:** Este documento é o ponto de entrada para qualquer agente de IA (Claude Code, Copilot, etc.) trabalhar neste projeto. Siga estas regras **obrigatoriamente**.

---

## 1. Visão Geral

**App_Orcamentos_V2** é um ERP web para gestão de orçamentos e operações de transporte executivo (empresa: Executive Car SP). Stack:

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.11 + Flask 3.x |
| ORM | Flask-SQLAlchemy |
| Autenticação | Flask-Login (sessão em cookies) |
| Autorização | RBAC customizado (Permission ↔ Role M:N) |
| Frontend | Jinja2 + Tailwind CSS + Alpine.js + Chart.js |
| PDF | ReportLab (platypus) |
| Banco Dev | SQLite (`instance/DB_V2.db`) |
| Banco Prod | PostgreSQL (Render) |
| Deploy | Gunicorn no Render (Procfile) |
| Migrações | Alembic / Flask-Migrate |

---

## 2. Estrutura de Diretórios

```
App_Orcamentos_V2/
├── app_v2.py                 # Entry point — cria app, roda migrações
├── config.py                 # Config classes: Dev / Prod / Test
├── requirements.txt          # Dependências de produção
├── requirements-dev.txt      # Dependências de dev + teste
├── pytest.ini                # Config pytest
├── Procfile                  # Render: gunicorn
│
├── app/
│   ├── __init__.py           # Factory: create_app()
│   ├── extensions.py         # db, migrate, login_manager, csrf
│   ├── models/               # 23 arquivos, 26 classes SQLAlchemy
│   ├── blueprints/           # 18 módulos de rotas (~120 endpoints)
│   ├── services/             # 12 módulos de lógica de negócio
│   ├── utils/                # 7 módulos utilitários
│   ├── templates/            # 32 templates Jinja2
│   └── static/               # CSS, JS, fontes, uploads
│
├── migrations/               # Alembic (11 versões)
├── tests/                    # 6 arquivos de teste (85 testes)
├── tools/                    # tailwindcss.exe, smoke tests
├── instance/                 # DB_V2.db (SQLite runtime)
└── docs/                     # Documentação detalhada
```

---

## 3. Padrões Obrigatórios (NUNCA VIOLAR)

### 3.1 Multi-Tenant: `company_id`

**TODA query de dados de empresa DEVE filtrar por `company_id`.** Usuários só podem ver/editar dados da sua própria empresa.

```python
# ✅ CORRETO
Order.query.filter_by(company_id=current_user.company_id).all()
Client.query.filter(Client.company_id == current_user.company_id).all()

# ❌ ERRADO — vazamento de dados entre tenants
Order.query.all()
Client.query.filter_by(is_active=True).all()
```

**Exceção:** Tabelas globais como `Permission`, `State`, `VehicleCategory` podem ser acessadas sem filtro.

### 3.2 RBAC: Controle de Acesso

Toda rota sensível DEVE usar decorators de permissão:

```python
# ✅ CORRETO
@require_permission("so.view")       # Permissão exata
@require_any_permission("so.edit", "so.create")  # Pelo menos uma
@require_role("ADMIN", "MANAGER")    # Por role

# ❌ ERRADO — apenas @login_required sem verificar permissão
```

**IMPORTANTE:** `{% if has_perm(...) %}` nos templates é **apenas UX**. A segurança real é server-side com os decorators.

### 3.3 Soft Delete

Clientes, Fornecedores, Motoristas, Veículos e ServiceOrders usam soft delete (`deleted_at`). **Nunca use `db.session.delete()` diretamente nestes modelos.** Use `obj.soft_delete()`.

```python
# ✅ CORRETO
client.soft_delete()

# ❌ ERRADO
db.session.delete(client)
```

### 3.4 Auditoria

Toda operação de criação/edição/exclusão de dados financeiros ou operacionais DEVE chamar `log_activity()`:

```python
from app.utils.audit import log_activity

log_activity("order", order.id, current_user.company_id,
             "Pedido faturado", current_user.id)
```

### 3.5 Parsing Monetário

Use **exclusivamente** `parse_brl()` para converter strings monetárias em float:

```python
from app.utils.helpers import parse_brl

valor = parse_brl("1.500,50")  # → 1500.5
valor = parse_brl("1500.50")   # → 1500.5
```

**Nunca use `float(str.replace(...))` manualmente.**

---

## 4. Fluxo de Negócio Principal

```
Quote (Orçamento)
  ├── status: pendente → aprovado → reserva_confirmada
  │                              ↘ reprovado
  │
  └── Order (Pedido de Venda / Sales Order)
        ├── status: novo → aberto → faturado → concluido
        │                           ↘ cancelado
        ├── ServiceOrder (Ordem de Serviço — despacho)
        │     status: criado → agendado → atribuido → em_execucao → finalizado
        │                                                ↘ cancelado
        └── PurchaseOrder (Ordem de Compra — fornecedor)
              status: rascunho → aberto → enviado → aprovado → em_execucao → concluido
                                                                    ↘ cancelado
```

**Entidades financeiras associadas:**
- `OrderPayment` — Parcelas a receber (vinculadas à Order)
- `POPayment` — Parcelas a pagar (vinculadas à PurchaseOrder)
- `RevenueEntry` — Receitas (vinculadas à ServiceOrder)
- `OperationCost` — Custos operacionais (vinculados à ServiceOrder)
- `SupplierPayment` — Pagamentos a fornecedores (vinculados à ServiceOrder)
- `FinancialEntry` — Lançamentos financeiros genéricos (V4)

---

## 5. Restrições de Banco de Dados

### 5.1 Nunca usar Raw SQL sem Whitelist

```python
# ✅ CORRETO — ORM
Order.query.filter_by(company_id=cid).all()

# ❌ ERRADO — SQL injection risk
db.session.execute(f"SELECT * FROM orders WHERE company_id = {cid}")
```

Raw SQL só é permitido para:
- Migrações de schema (`_ensure_schema_columns()`)
- Resets de dados de desenvolvimento (com nomes de tabela hardcoded)
- Agregações complexas que o ORM não suporta (ex: `func.sum` + `GROUP BY`)

### 5.2 Cuidado com `db.session.commit()`

Alguns serviços chamam `commit()` internamente, outros não. Isso é inconsistente (dívida técnica conhecida). Ao modificar serviços:

1. **NÃO adicione novos `commit()` dentro de serviços** — siga o padrão de delegar ao controller
2. Se precisar garantir atomicidade, use `db.session.begin_nested()` (savepoint)

---

## 6. Restrições de Código

### 6.1 NÃO usar `lazy="joined"` em novos relacionamentos

O projeto sofre de sobrecarga de JOINs (20+ relacionamentos com eager loading forçado). Novos relacionamentos devem usar `lazy="select"` (padrão SQLAlchemy).

### 6.2 NÃO duplicar lógica entre arquivos

Antes de implementar algo novo, verifique se já existe em:
- `app/services/` — lógica de negócio
- `app/utils/helpers.py` — funções de formatação
- `app/utils/decorators.py` — decorators de autorização

### 6.3 Campos de Status

Use as tuplas de constantes definidas nos modelos (ex: `ORDER_STATUSES`, `PO_STATUSES`). Não hardcode strings de status.

---

## 7. Como Analisar Código Antes de Modificar

> **Regra de ouro:** Nunca modifique sem antes compreender. Este é um ERP em produção — alterações impensadas podem causar prejuízo financeiro real.

### 7.1 Procedimento de Análise (OBRIGATÓRIO)

Para qualquer tarefa (bug, feature, refatoração), execute nesta ordem:

```
1. MAPEIE o fluxo de dados
2. IDENTIFIQUE os pontos de impacto
3. RASTREIE os callers e callees
4. VERIFIQUE as restrições do sistema
5. PROJETE a solução
6. VALIDE o impacto cruzado
7. IMPLEMENTE com segurança
8. TESTE com cobertura
```

### 7.2 Passo 1: Mapear o Fluxo de Dados

```bash
# 1. Identifique a rota de entrada
grep -rn "def.*rota.*" app/blueprints/

# 2. Siga o caminho completo
#    Rota (blueprints/) → Serviço (services/) → Modelo (models/)
#    Exemplo:
#    POST /orders/<id>/faturar
#      → orders/routes.py:faturar()
#        → order_service.faturar()
#          → Order.status = 'faturado'
#          → OrderPayment (geração de parcelas)
#          → margin_service.recalculate_order()

# 3. Liste todos os arquivos no fluxo
grep -rn "nome_da_funcao" app/

# 4. Verifique imports cruzados
grep -rn "from.*import.*nome_do_modulo" app/
```

### 7.3 Passo 2: Identificar Pontos de Impacto

Antes de modificar qualquer arquivo, verifique:

| O que verificar | Comando/Ferramenta |
|-----------------|-------------------|
| Quem chama esta função? | `grep -rn "nome_funcao(" app/` |
| Quais modelos são afetados? | Leia o serviço e veja os imports |
| Existem rotas que dependem disto? | `grep -rn "nome_funcao" app/blueprints/` |
| Há templates que usam o resultado? | `grep -rn "atributo_afetado" app/templates/` |
| Há testes cobrindo este código? | `grep -rn "nome_funcao" tests/` |

### 7.4 Passo 3: Rastrear Callers e Callees

Crie uma árvore mental de dependências:

```
Controller (rota)
  └── service.funcao_principal()
        ├── model.query.filter(...)      # Leitura
        ├── model.atributo = valor       # Escrita
        ├── db.session.flush()           # Persistência parcial
        ├── outro_service.funcao()       # Sub-chamada
        │     └── model2.query...
        └── margin_service.calculo()     # Impacto financeiro
```

**IMPORTANTE:** Se a função chama `db.session.commit()`, identifique TODAS as alterações pendentes na sessão que serão commitadas juntas.

---

## 8. Como Propor Mudanças

### 8.1 Antes de Implementar

1. **Escreva um mini-plano** no formato:
   ```
   ARQUIVOS AFETADOS:
   - app/models/X.py (adicionar campo Y)
   - app/services/X_service.py (nova função Z)
   - app/blueprints/X/routes.py (nova rota W)

   IMPACTO MULTI-TENANT:
   - O campo Y tem company_id? [Sim/Não — justifique]
   - A query filtra por company_id? [Sim/Não — justifique]

   IMPACTO RBAC:
   - Nova rota requer qual permissão?
   - Permissão existe no catálogo? [Sim/Não — qual?]

   IMPACTO FINANCEIRO:
   - Altera cálculos de margem, receita ou custo? [Sim/Não]
   - Altera transições de status? [Sim/Não — quais?]

   IMPACTO NO BANCO:
   - Requer migração? [Sim/Não]
   - Altera dados existentes? [Sim/Não — como?]
   ```

2. **Apresente o plano para aprovação** antes de escrever código

### 8.2 Durante a Implementação

- Siga os padrões obrigatórios da §3
- Não introduza `lazy="joined"`
- Não duplique lógica existente (§6.2)
- Não adicione `commit()` dentro de serviços (§5.2)
- Use `parse_brl()` para qualquer valor monetário (§3.5)

### 8.3 Após a Implementação

- Execute `pytest tests/ -v` (todos os 85 testes devem passar)
- Execute validação multi-tenant (§9)
- Execute validação RBAC (§10)
- Execute validação financeira (§11)
- Se aplicável, execute validação de deploy (§12)

---

## 9. Como Validar Impacto Multi-Tenant

### 9.1 Checklist de Validação Multi-Tenant

Para **qualquer alteração** que envolva modelos, queries ou rotas:

- [ ] **Toda nova query tem `company_id`?**
  ```python
  # Procure por queries sem company_id
  grep -rn "query.filter" app/ | grep -v "company_id"
  grep -rn "query.filter_by" app/ | grep -v "company_id"
  grep -rn "\.all()" app/blueprints/ | grep -v "company_id"
  ```

- [ ] **Toda nova rota tem escopo de tenant?**
  ```python
  # Verifique se a rota filtra por current_user.company_id
  # Padrão correto:
  items = Model.query.filter_by(company_id=current_user.company_id).all()
  ```

- [ ] **Novas tabelas globais são intencionalmente globais?**
  Se um modelo NÃO tem `company_id`, ele precisa estar na lista de exceções:
  `Permission`, `Role`, `role_permissions`, `user_roles`, `State`, `VehicleCategory`

- [ ] **Relações entre tenants são impossíveis?**
  ```python
  # ❌ PERIGO: um usuário da empresa A vinculando recursos da empresa B
  order.client_id = client_de_outra_empresa.id  # SEMPRE valide antes!
  ```

### 9.2 Teste de Isolamento Multi-Tenant

```python
# Padrão para teste de tenant isolation:
def test_cross_tenant_access_blocked(client, app):
    """Usuário da Empresa A NÃO pode ver dados da Empresa B."""
    # Criar empresa A e B
    # Autenticar como usuário da empresa A
    # Tentar acessar recurso da empresa B
    # Deve retornar 403 ou 404
    resp = client.get(f'/orders/{order_da_empresa_b}')
    assert resp.status_code in (403, 404)
```

### 9.3 Auditoria de Queries Existentes

Execute antes de modificar queries existentes:

```bash
# Liste todas as queries que NÃO filtram por company_id
grep -rn "\.query\.\|\.filter\|\.filter_by" app/blueprints/ | grep -v "company_id" | grep -v "Permission\|Role\|State\|VehicleCategory"
```

---

## 10. Como Validar RBAC

### 10.1 Checklist de Validação RBAC

Para **toda nova rota** ou **alteração de rota existente**:

- [ ] **A rota tem decorator de autorização?**
  ```python
  # ✅ Correto
  @login_required
  @require_permission("so.view")
  def minha_rota(): ...

  # ❌ Errado — apenas login_required não basta
  @login_required
  def minha_rota(): ...
  ```

- [ ] **A permissão correta foi escolhida?**
  | Operação | Decorator |
  |----------|-----------|
  | Visualização (GET lista/detalhe) | `@require_permission("modulo.view")` |
  | Criação (POST new) | `@require_permission("modulo.create")` ou `@require_any_permission("modulo.create", "modulo.edit")` |
  | Edição (POST edit) | `@require_permission("modulo.edit")` |
  | Exclusão | `@require_permission("modulo.delete")` |
  | Operação financeira | `@require_permission("financial.manage")` |

- [ ] **A permissão existe no catálogo?**
  Verifique `app/utils/permissions.py` → `PERMISSION_CATALOG`. Se for nova, adicione.

- [ ] **A permissão está na matriz de roles?**
  Verifique `app/utils/permissions.py` → `ROLE_PERMISSION_MATRIX`. Toda permissão nova precisa ser atribuída a pelo menos uma role.

- [ ] **O template esconde elementos não autorizados?**
  ```html
  {% if has_perm('so.edit') %}
    <button>Editar</button>
  {% endif %}
  ```

### 10.2 Teste de RBAC

```python
# Para cada nova rota, teste todos os níveis de acesso:
def test_rota_bloqueia_sem_permissao(client, viewer_user):
    """VIEWER não pode criar/editar/excluir."""
    client.post('/login', data={'email': 'viewer@test.com', 'password': 'test'})
    resp = client.post('/orders/new', data={...})
    assert resp.status_code == 403

def test_rota_permite_com_permissao(client, admin_user):
    """ADMIN pode criar/editar/excluir."""
    client.post('/login', data={'email': 'admin@test.com', 'password': 'test'})
    resp = client.post('/orders/new', data={...})
    assert resp.status_code in (200, 302)  # OK ou redirect
```

### 10.3 Validação de Consistência RBAC

```bash
# Verifique se todas as rotas têm decorators de permissão
grep -rn "@login_required" app/blueprints/ | while read line; do
  file=$(echo "$line" | cut -d: -f1)
  # Verifica se tem @require_ logo abaixo ou acima
  grep -A1 -B1 "@login_required" "$file" | grep -q "@require_"
  if [ $? -ne 0 ]; then
    echo "⚠️  Rota sem @require_permission em $file: $line"
  fi
done
```

---

## 11. Como Validar Impacto Financeiro

### 11.1 Quando Validar

Toda alteração que toca em **qualquer** destes arquivos exige validação financeira:

| Arquivo | Motivo |
|---------|--------|
| `models/order.py` | `computed_total`, `margin_amount`, `total_po_cost` |
| `models/purchase_order.py` | `computed_total` |
| `models/service_order.py` | `recalculate_margin()`, `revenue_amount` |
| `models/service.py` | `effective_price()` |
| `services/order_service.py` | `faturar()`, `baixa()`, `generate_payments()` |
| `services/purchase_order_service.py` | `faturar()`, `baixa()`, `generate_payments()` |
| `services/margin_service.py` | `calculate_order_margin()`, `recalculate_order()` |
| `services/quote_service.py` | `create_quote()`, cálculo de preços |
| `blueprints/orders/routes.py` | Todas as rotas de status e pagamento |
| `blueprints/purchase_orders/routes.py` | Todas as rotas de status e pagamento |
| `blueprints/financial/routes.py` | `baixa_record()` |
| `utils/helpers.py` | `parse_brl()` |

### 11.2 Checklist de Validação Financeira

Antes de concluir qualquer alteração nos arquivos acima:

- [ ] **Cálculo de `computed_total` permanece correto?**
  ```
  Fórmula: subtotal − desconto + frete + outros_custos
  Desconto %: subtotal * (discount_value / 100)
  Desconto R$: discount_value
  ```

- [ ] **Cálculo de margem permanece correto?**
  ```
  Order:  computed_total − sum(po.computed_total for non-cancelled POs)
  OS:     revenue_amount − total_cost_amount − supplier_amount
  ```

- [ ] **Precificação de serviços não foi alterada indevidamente?**
  ```
  recibo:    price_base
  nf:        price_base × 1.10
  cartao:    price_base × 1.065
  nf_cartao: price_base × 1.165
  ```

- [ ] **Transições de status não violam regras de negócio?**
  Verifique a máquina de estados em [docs/business_rules.md](docs/business_rules.md) §2.

- [ ] **Valores monetários usam `parse_brl()`?**
  ```bash
  grep -rn "replace.*\.\..*replace.*," app/ | grep -v "format_currency\|_fmt_brl\|helpers.py"
  # Não deve retornar NADA (todas as ocorrências devem ter sido migradas para parse_brl)
  ```

- [ ] **Pagamentos e baixas mantêm consistência?**
  - `paid_amount` ≤ `amount`?
  - `paid_date` é posterior a `due_date`?
  - `paid_by` está registrado?

### 11.3 Teste de Consistência Financeira

```python
def test_margem_order_consistente(app, db):
    """Margem = receita - custo total dos POs."""
    order = criar_order_teste()
    po1 = criar_po_teste(order, amount=500)
    po2 = criar_po_teste(order, amount=300)
    db.session.commit()

    from app.services.margin_service import calculate_order_margin
    revenue, cost, margin = calculate_order_margin(order)

    assert cost == 800  # 500 + 300
    assert revenue == order.computed_total
    assert margin == revenue - cost

def test_parse_brl_todos_formatos():
    """Todos os formatos de entrada produzem o valor correto."""
    from app.utils.helpers import parse_brl
    assert parse_brl("1.500,50") == 1500.50
    assert parse_brl("1500,50") == 1500.50
    assert parse_brl("1500.50") == 1500.50
    assert parse_brl("R$ 1.500,50") == 1500.50
    assert parse_brl(1500.50) == 1500.50
```

---

## 12. Como Validar Deploy

### 12.1 Procedimento de Validação de Deploy

Use este procedimento **sempre** que uma alteração for destinada a produção:

```
FASE 1: PRÉ-DEPLOY (local)
  1. pytest tests/ -v                    # 85 testes devem passar
  2. Teste manual dos fluxos alterados
  3. Verifique migrações pendentes

FASE 2: STAGING (se disponível)
  4. Deploy em ambiente staging
  5. Smoke test dos fluxos críticos
  6. Verificação de logs

FASE 3: PRODUÇÃO
  7. Backup do banco (se migração destrutiva)
  8. Deploy
  9. Smoke test imediato
  10. Monitoramento por 30 min
```

### 12.2 Smoke Tests Obrigatórios Pós-Deploy

- [ ] Login com admin funciona
- [ ] Dashboard carrega sem erros
- [ ] Criar orçamento → PDF gerado
- [ ] Aprovar orçamento → Order criada
- [ ] Criar OS → Atribuir motorista
- [ ] Criar PO → Aprovar → Concluir
- [ ] Baixa financeira registrada
- [ ] Logout funciona

---

## 13. Como Trabalhar Neste Projeto (Passo a Passo)

### Para adicionar uma nova feature:

1. **Analise** o fluxo existente (§7)
2. **Proponha** o mini-plano (§8.1)
3. **Modele** a entidade em `app/models/` (herde de `TimestampMixin`, adicione `company_id`, `index=True` em FKs)
4. **Crie migração** com `flask db migrate -m "descrição"`
5. **Implemente serviço** em `app/services/` (regras de negócio, sem commit interno)
6. **Crie blueprint** em `app/blueprints/<modulo>/routes.py` (use decorators de permissão)
7. **Crie templates** em `app/templates/<modulo>/`
8. **Adicione permissões** em `app/utils/permissions.py` ao catálogo e matriz
9. **Valide multi-tenant** (§9)
10. **Valide RBAC** (§10)
11. **Valide impacto financeiro** (§11, se aplicável)
12. **Teste** com `pytest tests/ -v`

### Para corrigir um bug:

1. **Analise** o fluxo de dados completo (§7)
2. **Reproduza** o bug localmente
3. **Escreva um teste** que capture o bug (deve falhar antes da correção)
4. **Identifique a causa raiz** seguindo rota → serviço → modelo
5. **Verifique multi-tenant** — o bug pode ser falta de `company_id`
6. **Verifique RBAC** — pode ser permissão faltando
7. **Corrija com o mínimo de alterações necessárias**
8. **Execute todos os testes** — o novo teste deve passar, os 85 existentes não devem quebrar
9. **Execute validações** multi-tenant (§9) e financeira (§11)

---

## 14. Links para Documentação Detalhada

| Documento | Conteúdo |
|-----------|----------|
| [AGENTS_DEV.md](AGENTS_DEV.md) | Guia de desenvolvimento local + checklists operacionais |
| [AGENTS_PROD.md](AGENTS_PROD.md) | Guia de produção + regras rígidas + checklist de deploy |
| [docs/architecture.md](docs/architecture.md) | Arquitetura completa do sistema |
| [docs/business_rules.md](docs/business_rules.md) | Regras de negócio e fluxos |
| [docs/development.md](docs/development.md) | Guia de desenvolvimento local |
| [docs/production.md](docs/production.md) | Guia de ambiente de produção |
| [docs/deployment.md](docs/deployment.md) | Processo de deploy |

---

## 15. Checklists por Tipo de Tarefa

### 15.1 Correção de Bug

- [ ] Analisei o fluxo completo (§7) — rota → serviço → modelo
- [ ] Reproduzi o bug localmente
- [ ] Escrevi teste que falha ANTES da correção
- [ ] Identifiquei a causa raiz
- [ ] Verifiquei se é problema de `company_id` (multi-tenant)
- [ ] Verifiquei se é problema de permissão (RBAC)
- [ ] Verifiquei se é problema de `parse_brl()` (valor monetário)
- [ ] Corrigi com alteração mínima
- [ ] Todos os 85 testes passam (`pytest tests/ -v`)
- [ ] Testei manualmente no browser
- [ ] Verifiquei se o bug não existe em arquivos similares (ex: mesmo padrão em purchase_orders e orders)
- [ ] `log_activity()` se for operação sensível

### 15.2 Nova Funcionalidade

- [ ] Analisei o fluxo existente (§7)
- [ ] Escrevi mini-plano (§8.1)
- [ ] Obtive aprovação do plano
- [ ] Modelo herda de `TimestampMixin`
- [ ] Modelo tem `company_id` com `index=True` (ou justificativa para ser global)
- [ ] FK têm `index=True`
- [ ] Relacionamentos usam `lazy="select"` (NÃO `lazy="joined"`)
- [ ] Migração criada com `flask db migrate`
- [ ] Serviço não chama `db.session.commit()` internamente
- [ ] Rota tem decorator `@require_permission` adequado
- [ ] Permissão adicionada ao `PERMISSION_CATALOG`
- [ ] Permissão adicionada ao `ROLE_PERMISSION_MATRIX`
- [ ] Template usa `{% if has_perm(...) %}` para controle de UI
- [ ] Valores monetários usam `parse_brl()`
- [ ] Operações sensíveis chamam `log_activity()`
- [ ] Soft delete para exclusões (se aplicável)
- [ ] Validei multi-tenant (§9)
- [ ] Validei RBAC (§10)
- [ ] Validei impacto financeiro (§11, se aplicável)
- [ ] Testes escritos (mínimo: acesso autorizado, acesso negado, tenant isolation)
- [ ] Todos os 85 testes passam

### 15.3 Refatoração

- [ ] Mapeei todos os callers da função a ser refatorada (§7.3)
- [ ] Mapeei todos os callees (§7.4)
- [ ] Identifiquei trechos duplicados que podem ser unificados
- [ ] A refatoração NÃO altera comportamento externo
- [ ] Não introduzi `lazy="joined"`
- [ ] Não mudei assinatura de funções públicas (ou atualizei todos os callers)
- [ ] Não alterei transações (commit/rollback permanecem equivalentes)
- [ ] Extraí lógica repetida para utility/services
- [ ] Todos os 85 testes passam sem modificação (ou testes atualizados justificadamente)
- [ ] Testei manualmente os fluxos afetados

---

## 16. Checklist Rápido (Resumo)

Antes de considerar qualquer tarefa concluída:

- [ ] Filtrei por `company_id`?
- [ ] Adicionei decorator de permissão na rota?
- [ ] Usei `parse_brl()` para valores monetários?
- [ ] Usei `log_activity()` para operações sensíveis?
- [ ] Testei com `pytest tests/ -v`?
- [ ] Não introduzi `lazy="joined"`?
- [ ] Não dupliquei lógica existente?
- [ ] Não usei raw SQL sem whitelist?
- [ ] Não adicionei `commit()` dentro de serviço?
- [ ] Verifiquei soft delete para exclusões?
- [ ] Verifiquei impacto multi-tenant (§9)?
- [ ] Verifiquei impacto RBAC (§10)?
- [ ] Verifiquei impacto financeiro (§11, se aplicável)?
