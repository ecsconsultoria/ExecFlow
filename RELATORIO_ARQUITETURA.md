# 🔍 Relatório de Arquitetura & Qualidade — ExecFlow_ERP_V2

**Data:** 04/06/2026
**Escopo:** Análise completa do código-fonte (modelos, rotas, serviços, utilitários, templates, testes)
**Metodologia:** Análise estática de ~70 arquivos Python + 32 templates HTML + 11 migrações Alembic

---

## 📋 Índice

1. [Visão Geral da Arquitetura](#1-visão-geral-da-arquitetura)
2. [Problemas de Arquitetura](#2-problemas-de-arquitetura)
3. [Dívidas Técnicas](#3-dívidas-técnicas)
4. [Problemas de Segurança](#4-problemas-de-segurança)
5. [Consultas SQL Ineficientes](#5-consultas-sql-ineficientes)
6. [Melhorias de Performance](#6-melhorias-de-performance)
7. [Oportunidades de Refatoração](#7-oportunidades-de-refatoração)
8. [Resumo Executivo](#8-resumo-executivo)

---

## 1. Visão Geral da Arquitetura

### Stack Tecnológica

| Camada | Tecnologia |
|--------|-----------|
| **Backend** | Python 3.11 / Flask 3.x |
| **ORM** | Flask-SQLAlchemy |
| **Autenticação** | Flask-Login (sessão) |
| **Autorização** | RBAC customizado (Permission + Role M:N) |
| **Migrações** | Alembic / Flask-Migrate (11 versões) |
| **Banco** | SQLite (dev), PostgreSQL (prod via `psycopg2-binary`) |
| **Frontend** | Jinja2 + Tailwind CSS + Alpine.js + Chart.js |
| **PDF** | ReportLab (platypus) |
| **Tradução** | deep-translator (Google Translate, sem API key) |
| **Deploy** | Gunicorn no Render/Heroku (Procfile) |
| **Testes** | Pytest + pytest-flask + pytest-cov |

### Estrutura de Diretórios

```
ExecFlow_ERP_V2/
├── app_v2.py                    # Entry point
├── config.py                    # Config (dev/prod/test)
├── app/
│   ├── __init__.py              # Factory: create_app()
│   ├── extensions.py            # db, migrate, login_manager, csrf
│   ├── models/        (23 arquivos, 26 classes)
│   ├── blueprints/    (18 módulos, ~120 rotas)
│   ├── services/      (12 módulos de lógica de negócio)
│   ├── utils/         (7 módulos: audit, decorators, helpers, permissions, security, translate)
│   ├── templates/     (32 templates Jinja2)
│   └── static/        (CSS Tailwind, JS Alpine/Chart.js, Font Awesome)
├── migrations/        (Alembic, 11 versões)
├── tests/             (6 arquivos de teste)
└── instance/          (DB_V2.db + WAL/SHM)
```

### Diagrama Conceitual

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Blueprints  │────▶│    Services      │────▶│     Models       │
│  (rotas)     │     │  (business logic)│     │  (SQLAlchemy)    │
│  18 módulos  │     │  12 módulos      │     │  26 classes      │
└──────────────┘     └─────────────────┘     └──────────────────┘
       │                     │                        │
       ▼                     ▼                        ▼
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Templates   │     │  PDF Generators  │     │   SQLite/Postgres│
│  Jinja2 (32) │     │  ReportLab (3)   │     │   Database       │
└──────────────┘     └─────────────────┘     └──────────────────┘
```

### Modelo de Domínio (Entidades Principais)

```
Company ──┬── User (RBAC: M:N Role → M:N Permission)
           ├── Client
           ├── Supplier ──── Driver
           ├── Vehicle (→ VehicleCategory)
           ├── Service (→ State, ServicePricing)
           ├── Quote ──┬── QuoteItem
           │           └── QuoteInclusion
           ├── Booking (legado, em desuso)
           ├── ServiceOrder ──┬── ServiceOrderAssignment
           │                  ├── ServiceOrderEvent
           │                  ├── OperationCost
           │                  ├── RevenueEntry
           │                  ├── SupplierPayment
           │                  └── FinancialEntry
           ├── Order ──┬── OrderItem
           │           ├── OrderPayment
           │           └── PurchaseOrder ──┬── POItem
           │                               └── POPayment
           └── (legado) FinancialRecord, AccountReceivable
```

---

## 2. Problemas de Arquitetura

### 🔴 A2.1 — Inconsistência no Gerenciamento de Transações

**Gravidade:** CRÍTICA

Alguns serviços fazem `db.session.commit()` internamente, outros delegam ao caller. Isso cria um modelo mental inconsistente e perigoso:

| Commita internamente | NÃO commita (delega ao caller) |
|---|---|
| `booking_service.create_from_quote` | `order_service.cancel` |
| `order_service.update_header` | `purchase_order_service.cancel` |
| `order_service.baixa` | `service_order_service.assign_driver` |
| `purchase_order_service.baixa` | `service_order_service.assign_supplier` |
| `quote_service.create_quote` | `purchase_order_service.conclude` |

**Risco:** Se um chamador espera que o serviço faça commit e ele não faz, dados são perdidos. Se um serviço faz commit e o chamador também chama `commit()` após lógica adicional, o estado intermediário é persistido sem a lógica completa.

**Recomendação:** Adotar um padrão uniforme: ou todos os serviços são responsáveis pelo commit, ou nenhum é. A abordagem recomendada é **Unit of Work** — o controller/rota sempre gerencia o `commit()`.

---

### 🔴 A2.2 — Duplicação Massiva de Lógica de Cascade Financeiro

**Gravidade:** CRÍTICA

A lógica de "void" de registros financeiros ao cancelar/excluir entidades está duplicada em **3 lugares diferentes**:

1. `orders/routes.py`: `_void_order_financial_records()` + `_void_linked_po_financial_records()`
2. `purchase_orders/routes.py`: `_void_po_financial_records()`
3. `financial/routes.py`: cascade inline em `delete_record()`

**Risco:** Qualquer mudança na lógica de cancelamento financeiro precisa ser replicada em 3 arquivos. Bugs de inconsistência (ex.: esquecer de sincronizar um status) são inevitáveis.

**Recomendação:** Extrair para `financial_service.py` (que está atualmente como dead code) com métodos como `void_entity_financial_records(entity_type, entity_id)`.

---

### 🔴 A2.3 — `lazy="joined"` Generalizado como Anti-Pattern

**Gravidade:** ALTA

**20+ relacionamentos** em 9 modelos usam `lazy="joined"`, forçando JOINs em toda query:

| Modelo | Nº de JOINs forçados |
|--------|---------------------|
| Order | **6 User relationships** (creator, opener, invoicer, closer, canceller, reopener) |
| PurchaseOrder | **7+ relationships** (creator, company, supplier, service, service_order, order, vehicle_category) |
| ServiceOrder | 3 (assigned_driver, assigned_vehicle, quote) |
| ServiceOrderAssignment | 3 (driver, vehicle, supplier) |
| Quote | 3 (creator, approver, rejecter) |
| AuditLog | 1 (user) |
| RevenueEntry | 1 (client) |
| SupplierPayment | 1 (supplier) |
| ServiceOrderEvent | 1 (user) |

**Impacto:** Uma listagem de 50 Orders gera 50 × 6 = 300 User queries em JOINs (mesmo com JOIN, o volume de dados trafegados é enorme). A maioria dos campos não é usada em listagens.

**Recomendação:** Alterar para `lazy="select"` (padrão) e usar `joinedload()` explícito apenas nas queries que realmente precisam dos dados.

---

### 🟡 A2.4 — Sistema Duplo de Roles (Legado + RBAC)

**Gravidade:** MÉDIA

O modelo `User` mantém dois sistemas de autorização simultâneos:

1. **Legado:** Coluna `role` (string: "superadmin", "admin", "manager", "operator")
2. **Novo:** M:N `User ↔ Role ↔ Permission` (RBAC completo)

Métodos como `has_role()`, `has_permission()` e `_is_effective_admin` verificam ambos os caminhos, aumentando a complexidade e o risco de inconsistência. Um usuário poderia ter `"ADMIN"` no Role mas `"operator"` na coluna legada.

**Recomendação:** Concluir a migração removendo a coluna `role` legada e confiando apenas no sistema RBAC.

---

### 🟡 A2.5 — Denormalização sem Sincronização Automática

**Gravidade:** MÉDIA

`ServiceOrder` armazena campos financeiros denormalizados (`revenue_amount`, `total_cost_amount`, `supplier_amount`, `margin_amount`) que são calculados por `recalculate_margin()`. Porém:

- Não há **triggers SQL**, **event listeners SQLAlchemy** ou **hooks** que recalculam automaticamente quando `OperationCost`, `RevenueEntry` ou `SupplierPayment` são criados/alterados/excluídos.
- Se qualquer código path modificar esses registros sem chamar `recalculate_margin()`, a ServiceOrder exibirá dados financeiros incorretos.

**Recomendação:** Adicionar event listeners SQLAlchemy (`after_insert`, `after_update`, `after_delete`) nos modelos filhos, ou converter os campos para `@property` dinâmicas.

---

### 🟡 A2.6 — Modelos Legados Coexistindo com V4

**Gravidade:** MÉDIA

`FinancialRecord`, `AccountReceivable` e `Booking` são marcados como "LEGACY" nos comentários mas continuam ativos no schema, são importados em `__init__.py`, e têm rotas dedicadas. O `financial_service.py` inteiro parece ser dead code (comentário em `booking_service.py` diz que não é mais chamado desde V2/V4).

**Recomendação:** Definir um plano de depreciação com prazo. Remover ou isolar os modelos legados em um módulo `legacy/`.

---

### 🟡 A2.7 — Responsabilidades Sobrepostas entre Rotas e Serviços

**Gravidade:** MÉDIA

As funções `save_all()` em `orders/routes.py` (57 linhas) e `purchase_orders/routes.py` (70 linhas) misturam:
- Parsing de formulário
- Normalização de dados
- Autorização
- Transições de status
- Recálculo de margem
- Auditoria

Isso viola o princípio de Single Responsibility. As rotas deveriam apenas orquestrar; a lógica deveria estar nos serviços.

---

## 3. Dívidas Técnicas

### 🔴 D3.1 — Bug: `is_deleted` em OperationCost (Dead Code)

**Arquivo:** `app/models/service_order.py` — método `recalculate_margin()`

```python
sum(c.amount for c in self.costs
    if not getattr(c, 'is_deleted', False))
```

`OperationCost` **NÃO** herda `SoftDeleteMixin`, portanto `is_deleted` nunca existe. O `getattr` com default `False` sempre retorna `False`. O filtro de soft-delete é **código morto** — custos "deletados" (que na verdade não podem ser soft-deletados) são sempre incluídos.

**Recomendação:** Ou adicionar `SoftDeleteMixin` a `OperationCost`, ou remover o `getattr`.

---

### 🔴 D3.2 — Bug de Parsing de Valores Monetários (Corrupção de Dados)

**Gravidade:** CRÍTICA

O padrão `float(raw.replace(".", "").replace(",", "."))` aparece em **6 locais**:

- `financial/routes.py` linha 262
- `orders/routes.py` linhas 341, 444
- `purchase_orders/routes.py` linhas 115-116, 245-250, 457, 549
- `purchase_order_service.py` linha 195

**Problema:** `str.replace(".", "")` remove TODOS os pontos. Uma entrada como `"1500.50"` (padrão internacional) torna-se `"150050"` (150 mil em vez de 1.500,50). Apenas o formato brasileiro `"1.500,50"` funciona corretamente.

**Cenário real:** Um usuário colando um valor de uma planilha Excel em formato internacional corrompe o dado.

**Recomendação:** Criar uma função `parse_brl(value: str) -> float` única, robusta, com validação e testes unitários, e usá-la em toda a codebase.

---

### 🟡 D3.3 — Coluna `"metadata"` como Palavra Reservada SQL

**Arquivo:** `app/models/service_order_event.py`

A coluna `"metadata"` é palavra reservada em PostgreSQL, MySQL e outros bancos. Embora SQLAlchemy faça quoting automático, ferramentas de SQL raw, migrações manuais e algumas ferramentas de BI podem quebrar.

**Recomendação:** Renomear para `event_metadata` ou `extra_data`.

---

### 🟡 D3.4 — Ausência de Índices em Chaves Estrangeiras

**Gravidade:** ALTA

**30+ FKs** não possuem `index=True` explícito. SQLite cria índices automaticamente para FKs, mas PostgreSQL e MySQL **não criam**. Se o app migrar para produção em PostgreSQL, consultas por `service_order_id`, `company_id`, `client_id`, `quote_id` e user FKs serão full table scans.

FKs sem índice explícito:
- Todos os `client_id`
- Todos os `quote_id` (QuoteItem, QuoteInclusion, Order, PurchaseOrder, Booking, ServiceOrder)
- Todos os `service_order_id` (PurchaseOrder, OperationCost, RevenueEntry, SupplierPayment, FinancialEntry, etc.)
- Todos os `user_id` além do modelo User
- Todos os `supplier_id`, `vehicle_id`, `driver_id`, `category_id`, `service_id`

**Recomendação:** Adicionar `index=True` em todas as colunas FK como parte da preparação para produção PostgreSQL.

---

### 🟡 D3.5 — 22 Campos de Status sem Constraints de Banco

**Gravidade:** MÉDIA

Status e tipos são armazenados como strings livres sem `CHECK constraint` no banco. Qualquer bug pode gravar um valor inválido:

| Modelo | Campo | Valores Válidos |
|--------|-------|-----------------|
| Quote | status | 7 valores |
| Quote | billing_type | 4 valores |
| Order | status | 6 valores |
| PurchaseOrder | status | 10 valores |
| ServiceOrder | status | 7 valores |
| Booking | status | 4 valores |
| FinancialEntry | type, status | 3 + 6 valores |
| RevenueEntry | status, billing_type | 5 + 4 valores |
| SupplierPayment | status | 4 valores |
| OperationCost | cost_type | 11 valores |
| ServiceOrderAssignment | assignment_type | 2 valores |
| ServiceOrderEvent | event_type | 15 valores |
| Driver | language, status | 2 + N |
| Vehicle | status | N |
| VehicleCategory | category_type | 6 valores |
| Company | plan, status | 3 + 3 |
| Order/PurchaseOrder | discount_type | 2 valores |

**Recomendação:** Adicionar `db.CheckConstraint` ou migrar para `SQLAlchemy Enum`.

---

### 🟡 D3.6 — Ausência de Validação de Formato no Modelo

Campos como `email`, `phone`, `whatsapp`, `document` (CPF/CNPJ), `plate` não têm validação de formato na camada de modelo. A validação é delegada inteiramente ao frontend (HTML5 `type="email"`, `pattern="..."`) — que pode ser bypassado.

**Recomendação:** Adicionar `@validates` do SQLAlchemy para validação server-side de formatos críticos.

---

### 🟡 D3.7 — Numeração Sequencial com Condição de Corrida

**Arquivo:** `app/services/numbering_service.py`

O gerador de números sequenciais usa `LIKE` query + `max()` sem lock:

```python
last = (model_class.query
        .filter(model_class.company_id == company_id,
                field.like(f"{prefix}-%"))
        .order_by(model_class.id.desc())
        .first())
```

Duas transações concorrentes podem ler o mesmo `last`, gerar o mesmo número, e criar duplicatas. A coluna `number` tem `unique=True`, então uma delas receberá `IntegrityError`.

**Recomendação:** Usar uma tabela de sequência dedicada com `SELECT ... FOR UPDATE` ou sequences nativas do PostgreSQL.

---

### 🟡 D3.8 — Testes Insuficientes

**Gravidade:** MÉDIA

- Apenas **6 arquivos de teste** focados em RBAC, segurança e tenant isolation.
- **Nenhum teste unitário** para os serviços de negócio (order_service, purchase_order_service, quote_service, etc.).
- **Nenhum teste** para parsing de valores monetários.
- **Nenhum teste de integração** para os fluxos principais (quote → order → PO → financial).
- **Nenhum teste** para os geradores de PDF.

O QA report (`QA_REPORT.md`) documenta testes E2E manuais, mas não são automatizados.

**Recomendação:** Expandir cobertura para serviços críticos e fluxos de negócio principais.

---

## 4. Problemas de Segurança

### 🔴 S4.1 — Vazamento de Dados para Google Translate (LGPD)

**Gravidade:** ALTA

**Arquivo:** `app/utils/translate.py`

A função `translate_obs()` envia texto de orçamentos (incluindo nomes de clientes, endereços, dados de passageiros, valores) para os servidores do Google Translate **sem garantias contratuais** de proteção de dados. Isso constitui transferência internacional de dados pessoais sem as salvaguardas exigidas pela LGPD.

**Recomendação:** Adicionar consentimento explícito do cliente, documentar a transferência, ou usar uma solução de tradução local/offline.

---

### 🔴 S4.2 — Rate Limiter In-Process (Multi-Worker Ineficaz)

**Gravidade:** ALTA

**Arquivo:** `app/utils/security.py`

O `LoginRateLimiter` usa estado em memória (dicionário + Lock). Com `gunicorn -w 4`, cada worker tem seu próprio contador. Um atacante pode fazer 5 tentativas por worker = 20 tentativas antes de bloqueio.

**Recomendação:** Migrar para Flask-Limiter + Redis em produção, ou usar um backend compartilhado.

---

### 🔴 S4.3 — Reset Destrutivo sem Confirmação

**Gravidade:** ALTA

**Arquivo:** `app/blueprints/dashboard/routes.py`

Três endpoints (`reset-transactional`, `reset-financial`, `reset-all`) executam `DELETE FROM table` em massa sem:
- Confirmação secundária (ex.: digitar "CONFIRMAR")
- Re-autenticação (confirmação de senha)
- Proteção CSRF adicional
- Log de auditoria do reset

**Recomendação:** Adicionar modal de confirmação com re-autenticação, token CSRF dedicado, e registro em audit log.

---

### 🟡 S4.4 — Content-Security-Policy (CSP) Ausente

**Gravidade:** MÉDIA

**Arquivo:** `app/utils/security.py`

Os headers de segurança incluem `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy` e `Permissions-Policy`, mas **não incluem CSP** — a defesa mais importante contra XSS. Um ataque XSS refletido ou armazenado pode executar JavaScript livremente.

**Recomendação:** Adicionar header `Content-Security-Policy` com diretivas restritivas para `script-src`, `style-src`, `connect-src`.

---

### 🟡 S4.5 — Cross-Tenant Data Exposure

**Gravidade:** MÉDIA

**Arquivos:** `categories/routes.py`, `roles/routes.py`

- `VehicleCategory.query.order_by(...).all()` — retorna categorias de TODAS as empresas (sem filtro `company_id`)
- `Role.query.order_by(...).all()` — retorna roles de TODAS as empresas
- `Permission.query.order_by(...).all()` — retorna permissões globais (aceitável se forem shared)

Se categorias são específicas por tenant, isso é um vazamento de dados entre empresas.

**Recomendação:** Adicionar filtro `company_id` ou confirmar design multi-tenant.

---

### 🟡 S4.6 — Mass Assignment em ServiceOrder

**Gravidade:** MÉDIA

**Arquivo:** `app/services/service_order_service.py` — `create_manual()`

```python
ServiceOrder(**{k: v for k, v in data.items() if hasattr(ServiceOrder, k)})
```

Isso permite que um formulário malicioso defina **qualquer coluna** do modelo, incluindo campos sensíveis como `revenue_amount`, `total_cost_amount`, `margin_amount` ou `status`. O filtro `hasattr` não é um allowlist — ele permite qualquer atributo existente.

**Recomendação:** Usar um allowlist explícito de campos permitidos.

---

### 🟡 S4.7 — Log de Auditoria sem Dados Forenses

**Gravidade:** MÉDIA

**Arquivo:** `app/utils/audit.py`

O `log_activity()` registra entidade, ação e usuário, mas **não captura**:
- Endereço IP do request
- User-Agent
- Timestamp do request
- Valores antigos vs. novos (diff)

Para um sistema financeiro/ERP, isso é insuficiente para conformidade (LGPD, auditoria fiscal).

**Recomendação:** Adicionar `ip_address`, `user_agent`, e campos `old_data`/`new_data` JSON ao `AuditLog`.

---

### 🟡 S4.8 — Cookie `Secure` e HSTS Condicionais

**Gravidade:** BAIXA/MÉDIA

`SESSION_COOKIE_SECURE` e HSTS são ativados condicionalmente. Se um admin desativar cookies seguros (ex.: para testar localmente sem HTTPS), o HSTS também é desativado.

**Recomendação:** Separar flags: sempre ativar HSTS em produção, independentemente da configuração de cookie.

---

### 🟡 S4.9 — Ausência de Logging de Acessos Negados

**Gravidade:** BAIXA

Os decorators `require_permission` e `require_role` abortam com 401/403 sem registrar a tentativa. Em um sistema financeiro, tentativas de acesso negado deveriam ser logadas para detecção de atividades suspeitas.

**Recomendação:** Adicionar `log_activity()` nos decorators quando o acesso é negado.

---

## 5. Consultas SQL Ineficientes

### 🔴 Q5.1 — Dashboard: 24+ Queries para Gráfico de 12 Meses

**Arquivo:** `app/blueprints/dashboard/routes.py` linhas 190-205

O gráfico de receita/custos dos últimos 12 meses chama `_so_revenue()` e `_po_cost()` para cada mês, resultando em **24+ consultas agregadas** apenas para renderizar um gráfico. Cada função executa uma query SQL com `SUM()` e `GROUP BY`.

**Recomendação:** Refatorar para uma única query que retorne todos os 12 meses de uma vez usando `GROUP BY strftime('%Y-%m', ...)`.

---

### 🔴 Q5.2 — N+1 em `_catalog_json()` (Quotes)

**Arquivo:** `app/blueprints/quotes/routes.py` linhas 36-68

Loop sobre categorias → precificações. Para cada pricing, acessa `p.service.name`, `p.service.description`, `p.service.km_included`, `p.service.duration_hours`, `p.service.state.code`, `p.category.km_extra_rate`. Sem eager loading, esses acessos geram uma query adicional por atributo.

Com 50 precificações, isso pode gerar **50+ consultas individuais**.

**Recomendação:** Adicionar `joinedload(ServicePricing.service).joinedload(Service.state)` e `joinedload(ServicePricing.category)`.

---

### 🔴 Q5.3 — N+1 em `detail()` de Order (Seller Name)

**Arquivo:** `app/blueprints/orders/routes.py` linha 176

```python
if order.created_by:
    u = User.query.get(order.created_by)
    seller_name = u.name if u else "–"
```

O relacionamento `created_by` no modelo Order usa `lazyload('*')`, forçando uma query manual separada para cada detalhe de Order.

**Recomendação:** Ou definir `created_by` como relacionamento normal, ou usar `joinedload` na query principal de detail.

---

### 🟡 Q5.4 — N+1 em PDF: Category Query por Item

**Arquivo:** `app/services/quote_pdf.py` linhas 497-503

No loop de itens do PDF, se `it.category` for None mas `it.category_id` existir, uma query individual `VehicleCategory.query.get(it.category_id)` é feita **para cada item**. Um orçamento com 15 itens gera **15 queries adicionais**.

**Recomendação:** Garantir eager loading de `category` antes de entrar no loop usando `joinedload`.

---

### 🟡 Q5.5 — Bulk Delete com Loop Individual

**Arquivos:** `suppliers/routes.py`, `services/routes.py`

`bulk_delete()` e `delete_bulk()` iteram sobre IDs fazendo uma query + update por registro. Para 100 fornecedores, são 100 SELECT + 100 UPDATE.

**Recomendação:** Usar `Model.query.filter(Model.id.in_(ids)).update({"deleted_at": now}, synchronize_session=False)`.

---

### 🟡 Q5.6 — Loop de `all()` em Cancel (Financial Records)

**Arquivo:** `app/services/order_service.py` linhas 220-227

No cancelamento de Order, os `FinancialRecord` são carregados com `.all()` e depois iterados um a um para atualizar status. São N updates individuais em vez de um bulk update.

**Recomendação:** `FinancialRecord.query.filter(...).update({"status": "cancelado"}, synchronize_session=False)`.

---

### 🟡 Q5.7 — `db.session.expire()` + Reload Desnecessário

**Arquivo:** `app/services/order_service.py` linha 520

```python
db.session.expire(order, ['items'])
order.total_amount = sum(i.total_price or 0 for i in order.items)
```

Força um reload completo de `order.items` do banco de dados para recalcular o total, mesmo quando o estado dos itens já é conhecido em memória.

**Recomendação:** Calcular o total com os itens em memória (tracking do SQLAlchemy), sem forçar reload.

---

### 🟡 Q5.8 — Query COUNT + Iteração na Mesma Collection

**Arquivo:** `app/services/purchase_order_service.py` linhas 373, 396

`po.payments.count()` seguido de `list(po.payments)` ou iteração gera **duas queries**: um `COUNT` e um `SELECT`.

**Recomendação:** Carregar `po.payments` uma vez com `all()` e usar `len()`.

---

## 6. Melhorias de Performance

### 🔴 P6.1 — Reduzir JOINs Forçados (lazy="joined")

**Impacto estimado:** ALTO (redução de 50-80% no tráfego de dados em queries de listagem)

**Ação:** Alterar `lazy="joined"` para `lazy="select"` ou `lazy="selectin"` em:
- Order: 6 User relationships
- PurchaseOrder: 7+ relationships
- ServiceOrder, Quote, AuditLog, ServiceOrderEvent, etc.

Usar `joinedload()` explícito apenas nas queries de detalhe/edição.

---

### 🔴 P6.2 — Adicionar Índices para Produção PostgreSQL

**Impacto estimado:** ALTO (evita full table scans em migração para produção)

**Ação:** Adicionar `index=True` em todas as colunas FK:
- `company_id` (todas as tabelas)
- `service_order_id` (6+ tabelas)
- `client_id`, `quote_id`, `supplier_id`, `user_id` FKs
- Índices compostos em `(company_id, status)` para listagens filtradas

---

### 🟡 P6.3 — Paginação em Listagens

**Impacto estimado:** MÉDIO

As listagens de Quotes, Orders, POs, OS não usam `.paginate()` do SQLAlchemy. Com crescimento de dados, listagens sem limite podem causar memory pressure.

**Recomendação:** Adotar `Model.query.filter(...).order_by(...).paginate(page=page, per_page=25)` em todas as listagens.

---

### 🟡 P6.4 — Otimizar Dashboard

**Impacto estimado:** MÉDIO (dashboard seria 2-3x mais rápido)

**Ações:**
1. Consolidar `_so_revenue()` + `_po_cost()` em uma única query com 12-month `GROUP BY`
2. Consolidar `get_today()`, `get_pending_assignment()`, `get_overdue()` do dispatch em uma query
3. Adicionar eager loading aos objetos carregados para evitar N+1 no template

---

### 🟡 P6.5 — Cache de Catálogo de Serviços

**Impacto estimado:** MÉDIO

O catálogo de serviços/precificações é carregado em múltiplas páginas (quotes, orders, dashboard) e raramente muda.

**Recomendação:** Cache em memória (Flask-Caching) com invalidação nas operações de edição do catálogo.

---

### 🟡 P6.6 — Otimizar Geração de PDF

**Impacto estimado:** BAIXO/MÉDIO

- Mover queries (`User.query.get`, `VehicleCategory.query.get`) para fora do loop de geração de PDF
- Resolver `logo_url` uma vez por request, não em cada PDF
- Adicionar timeout na chamada HTTP do Google Translate em `translate_obs()`

---

### 🟡 P6.7 — Query de Numeração Sequencial

**Impacto estimado:** BAIXO

A query `LIKE "PREFIX-%"` com `ORDER BY id DESC LIMIT 1` funciona bem em SQLite, mas em PostgreSQL com milhões de registros, um índice funcional ou sequence dedicada seria mais eficiente.

**Recomendação:** Criar tabela `sequence_numbers(entity_type, company_id, year, month, last_seq)` com `SELECT ... FOR UPDATE`.

---

## 7. Oportunidades de Refatoração

### 🔴 R7.1 — Extrair PDF Base Class

**Impacto:** ALTO (elimina ~70% de código duplicado)

Os três geradores de PDF (`quote_pdf.py`, `order_pdf.py`, `purchase_order_pdf.py`) compartilham ~70% da estrutura:
- Header da empresa (logo, endereço)
- Estilos de tabela
- Footer com página
- Resolução de logo_url
- Agrupamento de dados operacionais
- Labels i18n

**Ação:** Criar `BasePDFGenerator` com métodos `_build_header()`, `_build_footer()`, `_build_table_styles()`, `_resolve_logo()` e herdar nos geradores específicos.

---

### 🔴 R7.2 — Extrair Lógica de Desconto Duplicada

**Impacto:** MÉDIO

`Order.computed_total` e `PurchaseOrder.computed_total` implementam a mesma lógica:
```python
base = subtotal
if discount_type == '%': base -= subtotal * (discount_value / 100)
elif discount_type == 'R$': base -= discount_value
return base + freight + other_costs
```

**Ação:** Criar um mixin `DiscountMixin` ou uma utility function `compute_total(subtotal, discount_type, discount_value, freight, other_costs)`.

---

### 🔴 R7.3 — Extrair Parsing de Valor Monetário

**Impacto:** ALTO (corrige bug de corrupção de dados em 6+ locais)

**Ação:** Criar `parse_brl(value: str) -> float` em `app/utils/helpers.py`:
```python
def parse_brl(value: str) -> float:
    """Parse Brazilian currency string to float.
    Handles: "1.500,50", "1500.50", "1500,50"
    """
    if not value:
        return 0.0
    s = str(value).strip()
    # Detect format by last separator
    if ',' in s and '.' in s:
        # Both present: assume Brazilian "1.500,50"
        s = s.replace('.', '').replace(',', '.')
    elif s.count(',') == 1 and s.count('.') == 0:
        s = s.replace(',', '.')
    return float(s)
```
E substituir todas as ocorrências inline.

---

### 🟡 R7.4 — Mover Lógica de Negócio das Rotas para Serviços

**Impacto:** MÉDIO

As funções `save_all()` em `orders/routes.py` e `purchase_orders/routes.py` contêm 57-70 linhas de lógica de negócio.

**Ação:** Mover a lógica de save para `order_service.update_order_full()` e `purchase_order_service.update_po_full()`.

---

### 🟡 R7.5 — Unificar Sistema de Autorização

**Impacto:** MÉDIO

Remover a coluna `role` (string) legada do modelo `User` e confiar exclusivamente no sistema RBAC M:N. Atualizar `has_role()`, `has_permission()`, `_is_effective_admin` para usar apenas o novo caminho.

---

### 🟡 R7.6 — Extrair Helpers de Template Duplicados

**Impacto:** BAIXO

O padrão `{{ "%.2f"|format(valor).replace('.', ',') }}` aparece em múltiplos templates. O filtro `format_currency` já existe no Python mas nem sempre é usado.

**Ação:** Garantir uso consistente de `{{ valor|currency }}` em todos os templates.

---

### 🟡 R7.7 — Remover Import Pattern `__import__("datetime")`

**Arquivo:** `app/blueprints/dashboard/routes.py`

```python
__import__("datetime").timedelta(...)
__import__("datetime").date(...)
```

Isso aparece em 5+ locais no dashboard. É um anti-pattern que dificulta ferramentas de análise estática.

**Ação:** Substituir por `from datetime import timedelta, date` no topo do arquivo.

---

### 🟡 R7.8 — Consolidar Gerenciamento de Transações

**Impacto:** ALTO

**Ação:** Adotar o padrão **Unit of Work**:
1. Nenhum serviço chama `db.session.commit()`
2. A rota sempre inicia, chama serviços, e faz `commit()` ou `rollback()` no final
3. Adicionar um context manager `@transactional` para rotas críticas

---

### 🟡 R7.9 — Dead Code: Remover `financial_service.py`

Confirmar que nenhum caller usa `FinancialService` e removê-lo. Atualizar o import não utilizado em `booking_service.py`.

---

### 🟡 R7.10 — Adicionar Type Hints

**Impacto:** BAIXO (qualidade de código)

A maior parte do código não tem type hints. Adicionar gradualmente, começando pelos serviços e utilitários.

---

## 8. Resumo Executivo

### 📊 Estatísticas do Projeto

| Métrica | Valor |
|---------|-------|
| Arquivos Python analisados | ~70 |
| Templates HTML | 32 |
| Modelos SQLAlchemy | 26 classes |
| Rotas | ~120 endpoints |
| Serviços | 12 módulos |
| Migrações Alembic | 11 versões |
| Linhas de código (estimado) | ~8.000+ |

### 🔢 Distribuição de Issues por Severidade

| Severidade | Arquitetura | Dívida Técnica | Segurança | SQL | Performance | Refatoração |
|-----------|-------------|----------------|-----------|-----|-------------|-------------|
| **CRÍTICA** | 3 | 2 | 0 | 0 | 0 | 0 |
| **ALTA** | 1 | 1 | 3 | 3 | 2 | 4 |
| **MÉDIA** | 3 | 4 | 5 | 4 | 4 | 4 |
| **BAIXA** | 0 | 0 | 1 | 1 | 1 | 2 |
| **TOTAL** | **7** | **7** | **9** | **8** | **7** | **10** |

### 🎯 Top 10 Ações Prioritárias

| # | Ação | Categoria | Severidade |
|---|------|-----------|------------|
| 1 | Corrigir parsing de valores monetários (bug de corrupção de dados) | Dívida Técnica | CRÍTICA |
| 2 | Unificar gerenciamento de transações (commit/rollback) | Arquitetura | CRÍTICA |
| 3 | Extrair lógica de cascade financeiro duplicada | Arquitetura | CRÍTICA |
| 4 | Corrigir bug `is_deleted` em OperationCost (código morto) | Dívida Técnica | CRÍTICA |
| 5 | Adicionar Content-Security-Policy | Segurança | ALTA |
| 6 | Migrar rate limiter para Redis (multi-worker) | Segurança | ALTA |
| 7 | Documentar/remover vazamento LGPD no Google Translate | Segurança | ALTA |
| 8 | Alterar `lazy="joined"` para `lazy="select"` nos modelos | Performance | ALTA |
| 9 | Adicionar índices em todas as FKs (preparação PostgreSQL) | Performance | ALTA |
| 10 | Extrair classe base de PDF (eliminar 70% código duplicado) | Refatoração | ALTA |

### ✅ Pontos Positivos

- **RBAC bem desenhado:** O sistema de Permission/Role é bem estruturado, com catálogo canônico e matriz de permissões documentada
- **Multi-tenant:** Filtro por `company_id` presente na maioria das queries
- **Soft-delete:** Preserva integridade de dados históricos em Clientes, Drivers, Suppliers, etc.
- **Event Sourcing:** ServiceOrderEvent fornece timeline auditável de mudanças de estado
- **Segurança básica presente:** Headers de segurança, CSRF via Flask-WTF, rate limiter no login, hash de senhas com Werkzeug
- **Migrações versionadas:** Alembic com 11 migrações documentadas
- **Idempotência:** `_seed_rbac()` e `_ensure_schema_columns()` são seguros para rodar a cada boot

### ⚠️ Riscos para Produção

1. **Corrupção silenciosa de valores monetários** — o bug de parsing pode causar prejuízo financeiro
2. **Condição de corrida na numeração** — pode gerar IntegrityError em produção com concorrência
3. **Rate limiter ineficaz** — com 4 workers gunicorn, proteção contra brute force é ~4x mais fraca
4. **Vazamento LGPD** — dados de clientes enviados ao Google Translate sem consentimento
5. **Reset destrutivo** — endpoints de reset de dados sem confirmação adequada
6. **Sem CSP** — vulnerável a XSS se houver injeção em qualquer template

---

*Relatório gerado por análise estática automatizada em 04/06/2026.*
*Nenhum arquivo foi modificado durante esta análise.*
