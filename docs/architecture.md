# Architecture — App_Orcamentos_V2

> Documentação completa da arquitetura do sistema baseada no código real.

---

## 1. Stack Tecnológica

| Camada | Tecnologia | Versão |
|--------|-----------|--------|
| Linguagem | Python | 3.11 |
| Framework Web | Flask | 3.x |
| ORM | Flask-SQLAlchemy | — |
| Migrações | Flask-Migrate (Alembic) | — |
| Autenticação | Flask-Login | — |
| CSRF | Flask-WTF | — |
| Frontend | Jinja2 Templates | — |
| CSS | Tailwind CSS | 3.x (via binário) |
| JS | Alpine.js + Chart.js | — |
| Ícones | Font Awesome 6 | — |
| PDF | ReportLab (platypus) | — |
| Tradução | deep-translator (Google Translate) | — |
| Banco Dev | SQLite | 3 |
| Banco Prod | PostgreSQL | — |
| Servidor Prod | Gunicorn | — |
| Plataforma | Render | — |

---

## 2. Padrão Arquitetural

### 2.1 Application Factory

O app é criado via factory function `create_app()` em [`app/__init__.py`](../app/__init__.py):

```python
def create_app(config_name=None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    register_blueprints(app)
    # ... pragmas, security headers, upload folder, Jinja filters ...
    return app
```

O entry point [`app_v2.py`](../app_v2.py) chama `create_app()` e aplica migrações pendentes automaticamente.

### 2.2 Camadas

```
┌──────────────────────────────────────────────────┐
│  Blueprints (rotas)                              │
│  18 módulos em app/blueprints/                   │
│  Responsabilidade: HTTP, validação de formulário, │
│  autorização, redirecionamento                    │
├──────────────────────────────────────────────────┤
│  Services (lógica de negócio)                    │
│  12 módulos em app/services/                     │
│  Responsabilidade: regras de negócio, transições  │
│  de status, cálculos, geração de PDF              │
├──────────────────────────────────────────────────┤
│  Models (dados)                                  │
│  26 classes em app/models/                       │
│  Responsabilidade: mapeamento ORM, validação,     │
│  relacionamentos                                  │
├──────────────────────────────────────────────────┤
│  Database                                        │
│  SQLite (dev) / PostgreSQL (prod)                │
└──────────────────────────────────────────────────┘
```

---

## 3. Estrutura de Diretórios

```
App_Orcamentos_V2/
│
├── app_v2.py                    # Entry point Flask
├── config.py                    # Config classes (Dev/Prod/Test)
├── requirements.txt             # Dependências produção
├── requirements-dev.txt         # Dependências dev/teste
├── pytest.ini                   # Config pytest
├── Procfile                     # Render: gunicorn
├── tailwind.config.js           # Tailwind config (cores marca)
│
├── app/
│   ├── __init__.py              # create_app() factory
│   ├── extensions.py            # db, migrate, login_manager, csrf
│   │
│   ├── models/                  # SQLAlchemy models (23 arquivos)
│   │   ├── __init__.py          # Re-exports
│   │   ├── base.py              # TimestampMixin, SoftDeleteMixin
│   │   ├── user.py              # User (Flask-Login UserMixin)
│   │   ├── rbac.py              # Permission, Role, user_roles, role_permissions
│   │   ├── company.py           # Company (tenant)
│   │   ├── client.py            # Client (soft delete)
│   │   ├── driver.py            # Driver (soft delete)
│   │   ├── vehicle.py           # Vehicle, VehicleCategory
│   │   ├── supplier.py          # Supplier (soft delete)
│   │   ├── service.py           # Service, ServicePricing, State
│   │   ├── quote.py             # Quote, QuoteItem, QuoteInclusion
│   │   ├── order.py             # Order, OrderItem, OrderPayment
│   │   ├── purchase_order.py    # PurchaseOrder, POItem, POPayment
│   │   ├── service_order.py     # ServiceOrder (soft delete)
│   │   ├── booking.py           # REMOVIDO em 05/06/2026
│   │   ├── financial.py         # FinancialRecord, AccountReceivable (legacy)
│   │   ├── financial_entry.py   # FinancialEntry (V4)
│   │   ├── revenue_entry.py     # RevenueEntry (V4)
│   │   ├── operation_cost.py    # OperationCost (V4)
│   │   ├── supplier_payment.py  # SupplierPayment (V4)
│   │   ├── audit.py / audit_log.py    # AuditLog
│   │   ├── service_order_assignment.py # ServiceOrderAssignment
│   │   └── service_order_event.py     # ServiceOrderEvent
│   │
│   ├── blueprints/              # Rotas (18 módulos)
│   │   ├── __init__.py          # register_blueprints()
│   │   ├── auth/routes.py       # Login, logout, change password
│   │   ├── dashboard/routes.py  # Dashboard, settings, reset endpoints
│   │   ├── quotes/routes.py     # CRUD orçamentos + aprovar/rejeitar
│   │   ├── orders/routes.py     # CRUD pedidos + status + pagamentos
│   │   ├── purchase_orders/routes.py # CRUD POs + status + pagamentos
│   │   ├── dispatch/routes.py   # Despacho (service orders)
│   │   ├── bookings/routes.py   # REMOVIDO em 05/06/2026
│   │   ├── clients/routes.py    # CRUD clientes
│   │   ├── drivers/routes.py    # CRUD motoristas
│   │   ├── vehicles/routes.py   # CRUD veículos
│   │   ├── suppliers/routes.py  # CRUD fornecedores
│   │   ├── services/routes.py   # Catálogo de serviços + precificação
│   │   ├── categories/routes.py # Categorias de veículos
│   │   ├── financial/routes.py  # Registros financeiros
│   │   ├── reports/routes.py    # Relatórios mensais
│   │   ├── users/routes.py      # CRUD usuários
│   │   ├── roles/routes.py      # Visualização de roles/permissões
│   │   └── audit/routes.py      # Log de auditoria
│   │
│   ├── services/                # Lógica de negócio (12 módulos)
│   │   ├── quote_service.py     # Criação/edição de orçamentos
│   │   ├── order_service.py     # Gestão de pedidos
│   │   ├── order_pdf.py         # PDF de pedido
│   │   ├── purchase_order_service.py # Gestão de POs
│   │   ├── purchase_order_pdf.py     # PDF de PO
│   │   ├── service_order_service.py  # Gestão de OS
│   │   ├── booking_service.py   # REMOVIDO em 05/06/2026
│   │   ├── dispatch_service.py  # Consultas de despacho
│   │   ├── financial_service.py # (dead code) Registros financeiros
│   │   ├── margin_service.py    # Cálculo de margem
│   │   ├── numbering_service.py # Numeração sequencial
│   │   └── quote_pdf.py         # PDF de orçamento + traduções
│   │
│   ├── utils/                   # Utilitários (7 módulos)
│   │   ├── __init__.py          # now_br(), utc_to_br(), make_client_token()
│   │   ├── audit.py             # log_activity()
│   │   ├── decorators.py        # @require_permission, @require_role, @tenant_required
│   │   ├── helpers.py           # format_currency(), parse_brl(), format_date(), status_badge_*()
│   │   ├── permissions.py       # Catálogo de permissões + matriz role-permissão
│   │   ├── security.py          # LoginRateLimiter, register_security_headers()
│   │   └── translate.py         # translate_obs() via Google Translate
│   │
│   ├── templates/               # 32 templates Jinja2
│   │   ├── base.html            # Layout base (navbar, sidebar)
│   │   ├── auth/                # Login, change password
│   │   ├── dashboard/           # Dashboard, settings
│   │   ├── quotes/              # Lista, detalhe, novo orçamento
│   │   ├── orders/              # Lista, detalhe
│   │   ├── purchase_orders/     # Lista, detalhe
│   │   ├── dispatch/            # Despacho + _os_card.html partial
│   │   ├── bookings/            # REMOVIDO em 05/06/2026
│   │   ├── clients/             # Lista, formulário
│   │   ├── drivers/             # Lista, formulário
│   │   ├── vehicles/            # Lista, formulário
│   │   ├── suppliers/           # Lista, formulário
│   │   ├── services/            # Catálogo
│   │   ├── categories/          # Categorias
│   │   ├── financial/           # Lista, formulário
│   │   ├── reports/             # Relatórios
│   │   ├── users/               # Lista, formulário
│   │   ├── roles/               # Roles e permissões
│   │   └── audit/               # Log de auditoria
│   │
│   └── static/
│       ├── css/
│       │   ├── tailwind.css     # Compilado
│       │   ├── tailwind.src.css # Fonte Tailwind
│       │   └── main.css         # CSS customizado
│       ├── js/
│       │   └── main.js          # JavaScript customizado
│       ├── vendor/              # alpine.min.js, chartjs.min.js, tailwind.js, fontawesome/
│       └── uploads/             # Logos e arquivos enviados
│
├── migrations/                  # Alembic
│   ├── alembic.ini
│   ├── env.py
│   ├── script.py.mako
│   └── versions/                # 11 migrações
│
├── tests/                       # Testes (6 arquivos, 85 testes)
│   ├── conftest.py
│   ├── test_decorators_and_audit.py
│   ├── test_permissions_catalog.py
│   ├── test_rbac_routes.py
│   ├── test_security_hardening.py
│   └── test_tenant_isolation.py
│
├── tools/
│   ├── tailwindcss.exe          # Tailwind CLI (40 MB)
│   └── smoke_rbac_phase2b.py   # Smoke test RBAC
│
└── instance/                    # SQLite runtime (dev)
    └── DB_V2.db
```

---

## 4. Modelos de Dados

### 4.1 Hierarquia de Mixins

```
TimestampMixin              SoftDeleteMixin
├── created_at             ├── deleted_at
├── updated_at             ├── is_deleted (property)
└── (now_br default)       └── soft_delete()
```

### 4.2 Entidades Principais

#### Core (Multi-Tenant)

| Modelo | Tabela | Soft Delete | Descrição |
|--------|--------|-------------|-----------|
| Company | companies | Não | Empresa (tenant) |
| User | users | Não | Usuário com RBAC |
| Client | clients | Sim | Cliente |
| Driver | drivers | Sim | Motorista |
| Vehicle | vehicles | Não | Veículo |
| VehicleCategory | vehicle_categories | Não | Categoria (sedan, van, etc.) |
| Supplier | suppliers | Sim | Fornecedor |
| Service | services | Não | Serviço (transfer, diária, etc.) |
| ServicePricing | service_pricing | Não | Preço por categoria + motorista |
| State | states | Não | Estado (SP, RJ) |

#### Transacional

| Modelo | Tabela | Numeração | Status |
|--------|--------|-----------|--------|
| Quote | quotes | `RFQ-` + YYMMDD + seq | pendente, aprovado, reprovado, reserva_confirmada |
| QuoteItem | quote_items | — | — |
| QuoteInclusion | quote_inclusions | — | — |
| Order | orders | `SO-` + YYMMDD + seq | novo, aberto, faturado, concluido, cancelado |
| OrderItem | order_items | — | — |
| OrderPayment | order_payments | — | — |
| PurchaseOrder | purchase_orders | `PO-` + YYMMDD + seq | rascunho, aberto, enviado, aprovado, em_execucao, concluido, cancelado |
| POItem | po_items | — | — |
| POPayment | po_payments | — | — |
| ServiceOrder | service_orders | `OS-` + YYMMDD + seq | criado, agendado, atribuido, confirmado_cliente, em_execucao, finalizado, cancelado |
| ~~Booking~~ | ~~bookings~~ | **REMOVIDO 05/06/2026** |

#### Financeiro (V4)

| Modelo | Tabela | Descrição |
|--------|--------|-----------|
| RevenueEntry | revenue_entries | Receitas vinculadas à ServiceOrder |
| OperationCost | operation_costs | Custos operacionais |
| SupplierPayment | supplier_payments | Pagamentos a fornecedores |
| FinancialEntry | financial_entries | Lançamentos financeiros genéricos |

#### Financeiro (Legado)

| Modelo | Tabela | Descrição |
|--------|--------|-----------|
| FinancialRecord | financial_records | Registros financeiros (booking) |
| AccountReceivable | accounts_receivable | Contas a receber |

#### RBAC e Auditoria

| Modelo | Tabela | Descrição |
|--------|--------|-----------|
| Permission | permissions | Permissão individual |
| Role | roles | Papel (grupo de permissões) |
| role_permissions | role_permissions | M:N Role ↔ Permission |
| user_roles | user_roles | M:N User ↔ Role |
| AuditLog | audit_logs | Log de auditoria |
| ServiceOrderAssignment | service_order_assignments | Atribuições de motorista/fornecedor |
| ServiceOrderEvent | service_order_events | Timeline de eventos da OS |

### 4.3 Relacionamentos Chave

```
Company (1) ────── (N) User
Company (1) ────── (N) Client
Company (1) ────── (N) Driver
Company (1) ────── (N) Vehicle
Company (1) ────── (N) Supplier
Company (1) ────── (N) Quote
Company (1) ────── (N) Order
Company (1) ────── (N) ServiceOrder

Quote (1) ────── (N) QuoteItem
Quote (1) ────── (N) QuoteInclusion
Quote (1) ────── (N) Order

Order (1) ────── (N) OrderItem
Order (1) ────── (N) OrderPayment
Order (1) ────── (N) PurchaseOrder

PurchaseOrder (1) ────── (N) POItem
PurchaseOrder (1) ────── (N) POPayment

ServiceOrder (1) ────── (N) ServiceOrderAssignment
ServiceOrder (1) ────── (N) ServiceOrderEvent
ServiceOrder (1) ────── (N) OperationCost
ServiceOrder (1) ────── (N) RevenueEntry
ServiceOrder (1) ────── (N) SupplierPayment
ServiceOrder (1) ────── (N) FinancialEntry

Service (1) ────── (N) ServicePricing
ServicePricing (N) ────── (1) VehicleCategory
Service (N) ────── (1) State

User (N) ────── (M) Role
Role (N) ────── (M) Permission
```

---

## 5. Extensões Flask

Definidas em [`app/extensions.py`](../app/extensions.py):

| Extensão | Objeto | Finalidade |
|----------|--------|-----------|
| Flask-SQLAlchemy | `db` | ORM, session management |
| Flask-Migrate | `migrate` | Migrações Alembic |
| Flask-Login | `login_manager` | Sessão de usuário, `current_user` |
| Flask-WTF CSRF | `csrf` | Proteção CSRF em POST/PUT/DELETE |

`login_manager.login_view = "auth.login"` — redireciona para login quando não autenticado.

---

## 6. Sistema de Autorização (RBAC)

### 6.1 Estrutura

```
User ──M:N── Role ──M:N── Permission
```

- **Permission:** Unidade atômica (ex: `so.view`, `financial.manage`)
- **Role:** Grupo de permissões (ex: ADMIN, MANAGER, FINANCIAL, OPERATIONAL, VIEWER)
- **User:** Pode ter múltiplas roles

### 6.2 Catálogo de Permissões

Definido em [`app/utils/permissions.py`](../app/utils/permissions.py):

- `PERMISSION_CATALOG` — ~50 permissões com código, categoria, label, descrição
- `SYSTEM_ROLES` — 5 roles fixas
- `ROLE_PERMISSION_MATRIX` — mapeamento role → conjunto de permissões
- `LEGACY_ROLE_MAP` — migração de roles legadas

### 6.3 Decorators

```python
@require_permission("so.view")           # Permissão exata
@require_any_permission("a", "b")       # Pelo menos uma
@require_role("ADMIN", "MANAGER")       # Por role
@tenant_required                         # Exige company_id
```

### 6.4 Contexto de Template

`has_perm(code)` e `has_any_perm(*codes)` injetados via context processor para controle de UI (não substituem segurança server-side).

---

## 7. Sistema de Eventos (ServiceOrder)

`ServiceOrderEvent` implementa um padrão de event sourcing para ordens de serviço:

| Evento | Ícone |
|--------|-------|
| created | 📋 |
| status_changed | 🔄 |
| driver_assigned | 🧑‍✈️ |
| supplier_assigned | 🏢 |
| cost_added | 💰 |
| cost_removed | 🗑️ |
| note_added | 📝 |
| driver_info_sent | 📤 |
| executed | ▶️ |
| closed | ✅ |
| reopened | 🔓 |
| cancelled | ❌ |
| invoice_generated | 🧾 |
| invoice_cancelled | 🗙️ |
| quote_approved | ✅ |

---

## 8. PDF Generation

Três geradores de PDF usando ReportLab (platypus):

| Gerador | Arquivo | Entrada | Saída |
|---------|---------|---------|-------|
| Quote PDF | `services/quote_pdf.py` | Quote | Orçamento (PT/EN) |
| Order PDF | `services/order_pdf.py` | Order | Pedido (PT/EN) |
| PO PDF | `services/purchase_order_pdf.py` | PurchaseOrder | Ordem de Compra (PT/EN) |

Cada PDF inclui:
- Header com logo da empresa
- Dados do cliente
- Tabela de itens/serviços
- Resumo financeiro
- Parcelas (quando aplicável)
- Observações e dados operacionais
- Tradução PT→EN via `deep-translator` (Google Translate)

**Dívida técnica:** Os 3 geradores compartilham ~70% do código (header, footer, estilos). Uma classe base `BasePDFGenerator` reduziria a duplicação.

---

## 9. Sistema de Numeração

Definido em [`app/services/numbering_service.py`](../app/services/numbering_service.py):

| Entidade | Formato | Exemplo |
|----------|---------|---------|
| Quote | `RFQ-YYMMDD-NNN` | `RFQ-250604-001` |
| Order | `SO-YYMMDD-NNN` | `SO-250604-001` |
| ServiceOrder | `OS-YYMMDD-NNN` | `OS-250604-001` |
| PurchaseOrder | `PO-YYMMDD-NNN` | `PO-250604-001` |
| Booking | `RES-YYYY-NNNN` | `RES-2026-0001` |

**Limitação conhecida:** O algoritmo usa `LIKE` query + `max()` sem lock, podendo gerar duplicatas em concorrência. Em produção multi-worker, considerar sequências nativas do PostgreSQL.

---

## 10. Segurança

### 10.1 Headers

Aplicados via `register_security_headers()` em [`app/utils/security.py`](../app/utils/security.py):

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- `Strict-Transport-Security` (produção, 1 ano)

### 10.2 Rate Limiting

`LoginRateLimiter` — 5 tentativas / 15 minutos por IP/email. In-memory (não compartilhado entre workers Gunicorn).

### 10.3 Senhas

Hash com `werkzeug.security.generate_password_hash` (pbkdf2:sha256 com salt).

---

## 11. Dependências entre Camadas

```
blueprints/auth ──── utils/decorators
blueprints/* ────── utils/audit
blueprints/* ────── utils/helpers (Jinja filters)
blueprints/* ────── services/*
services/* ──────── models/*
services/* ──────── utils (now_br)
models/* ────────── utils (now_br, base mixins)
app/__init__.py ─── utils/security (headers)
app/__init__.py ─── utils/permissions (RBAC seed)
```
