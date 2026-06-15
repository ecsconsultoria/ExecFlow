# CODEBASE_INDEX.md — App_Orcamentos_V2

> **Mapeamento completo de todos os arquivos do projeto com responsabilidades.**
> **Data:** 05/06/2026 (atualizado após remoção do Booking e reestruturação do menu)

---

## 1. Entry Points & Config (Raiz)

| Arquivo | Responsabilidade |
|---------|-----------------|
| `app_v2.py` | Entry point. Cria app via factory, aplica migrações pendentes, otimiza memória em produção. |
| `config.py` | Classes de configuração: `Config` (base), `DevelopmentConfig`, `ProductionConfig`, `TestingConfig`. Variáveis de ambiente. |
| `.env.example` | Template de variáveis de ambiente (DB, SMTP, PIX, PayPal, taxas). |
| `requirements.txt` | Dependências produção: Flask, SQLAlchemy, Flask-Login, Flask-WTF, gunicorn, psycopg2, reportlab, openpyxl, deep-translator. |
| `requirements-dev.txt` | Dependências dev: requirements.txt + pytest, pytest-flask, pytest-cov. |
| `pytest.ini` | Config pytest: paths de teste, filtros. |
| `Procfile` | Render: `web: gunicorn app_v2:app`. |
| `tailwind.config.js` | Tailwind CSS: cores da marca (brand dark, gold, light). |

---

## 2. App Factory & Extensions

| Arquivo | Responsabilidade |
|---------|-----------------|
| `app/__init__.py` | `create_app()` — Factory do Flask. Inicializa extensões, registra blueprints, configura headers, upload folder, Jinja filters, context processors, seed data, schema patches. |
| `app/extensions.py` | Instâncias globais: `db` (SQLAlchemy), `migrate` (Flask-Migrate), `login_manager` (Flask-Login), `csrf` (Flask-WTF CSRF). |

---

## 3. Models (23 arquivos, 26 classes)

### 3.1 Base

| Arquivo | Classes/Mixins | Responsabilidade |
|---------|---------------|-----------------|
| `models/base.py` | `TimestampMixin`, `SoftDeleteMixin` | Campos comuns: `created_at`, `updated_at`, `deleted_at`, `is_deleted`, `soft_delete()`. |

### 3.2 Core (Multi-Tenant)

| Arquivo | Classe(s) | Tabela | Responsabilidade |
|---------|-----------|--------|-----------------|
| `models/company.py` | `Company` | `companies` | Empresa (tenant). Dados cadastrais, plano, logo, settings JSON. |
| `models/user.py` | `User` | `users` | Usuário. Autenticação (Flask-Login UserMixin), RBAC dual (legado + M:N), `user_loader`. |
| `models/client.py` | `Client` | `clients` | Cliente. Soft delete. Dados de contato, billing. |
| `models/driver.py` | `Driver` | `drivers` | Motorista. Soft delete. CNH, idioma, status. |
| `models/vehicle.py` | `Vehicle`, `VehicleCategory` | `vehicles`, `vehicle_categories` | Veículo e Categoria. Placa, modelo, ano, capacidade. 18 categorias fixas. |
| `models/supplier.py` | `Supplier` | `suppliers` | Fornecedor. Soft delete. Terceirização de serviços. |
| `models/service.py` | `Service`, `ServicePricing`, `State` | `services`, `service_pricing`, `states` | Serviço, Precificação, Estado. 6 flags booleanas (`is_operational`, `requires_route`, ...), preços por categoria + tipo motorista. |

### 3.3 RBAC

| Arquivo | Classe(s) | Tabela | Responsabilidade |
|---------|-----------|--------|-----------------|
| `models/rbac.py` | `Permission`, `Role` | `permissions`, `roles`, `role_permissions`, `user_roles` | RBAC M:N. User ↔ Role ↔ Permission. |

### 3.4 Transacional

| Arquivo | Classe(s) | Tabela | Responsabilidade |
|---------|-----------|--------|-----------------|
| `models/quote.py` | `Quote`, `QuoteItem`, `QuoteInclusion` | `quotes`, `quote_items`, `quote_inclusions` | Orçamento. Itens, inclusões, status flow, pagamento, aprovação/rejeição. |
| `models/order.py` | `Order`, `OrderItem`, `OrderPayment` | `orders`, `order_items`, `order_payments` | Pedido de Venda (SO). Itens, parcelas, `computed_total`, 6 status timestamps + users. |
| `models/purchase_order.py` | `PurchaseOrder`, `POItem`, `POPayment` | `purchase_orders`, `po_items`, `po_payments` | Ordem de Compra. Itens, parcelas, `computed_total`, 5 status timestamps. |
| `models/service_order.py` | `ServiceOrder` | `service_orders` | Ordem de Serviço. Despacho, atribuição, eventos, custos, receitas, margem. Soft delete. |
| ~~`models/booking.py`~~ | ~~`Booking`~~ | — | **REMOVIDO em 05/06/2026.** Substituído pelo fluxo Order → ServiceOrder. |

### 3.5 Financeiro (V4)

| Arquivo | Classe(s) | Tabela | Responsabilidade |
|---------|-----------|--------|-----------------|
| `models/financial_entry.py` | `FinancialEntry` | `financial_entries` | Lançamento financeiro genérico (V4). |
| `models/revenue_entry.py` | `RevenueEntry` | `revenue_entries` | Receita vinculada à ServiceOrder. |
| `models/operation_cost.py` | `OperationCost` | `operation_costs` | Custo operacional vinculado à ServiceOrder. |
| `models/supplier_payment.py` | `SupplierPayment` | `supplier_payments` | Pagamento a fornecedor vinculado à ServiceOrder. |

### 3.6 Financeiro (Legado)

| Arquivo | Classe(s) | Tabela | Responsabilidade |
|---------|-----------|--------|-----------------|
| `models/financial.py` | `FinancialRecord`, `AccountReceivable` | `financial_records`, `accounts_receivable` | Registros financeiros e contas a receber (legado). Mantidos por compatibilidade. |

### 3.7 Eventos e Auditoria

| Arquivo | Classe(s) | Tabela | Responsabilidade |
|---------|-----------|--------|-----------------|
| `models/audit.py` | `AuditLog` | `audit_logs` | Log de auditoria. Entidade, ação, IP, user_agent. |
| `models/audit_log.py` | (re-export) | — | `from .audit import AuditLog`. |
| `models/service_order_assignment.py` | `ServiceOrderAssignment` | `service_order_assignments` | Atribuição de motorista/fornecedor. `is_current`, histórico. |
| `models/service_order_event.py` | `ServiceOrderEvent` | `service_order_events` | Timeline de eventos da OS. Event sourcing com 15 tipos de evento. |

### 3.8 Init

| Arquivo | Responsabilidade |
|---------|-----------------|
| `models/__init__.py` | Re-exports de todos os modelos e constantes. Organizado em V3 (legado) e V4 (novo). |

---

## 4. Blueprints (18 módulos)

| Módulo | Arquivo | Rotas | Responsabilidade |
|--------|---------|-------|-----------------|
| `blueprints/__init__.py` | Registra todos os blueprints no app. | — | `register_blueprints(app)`. |
| `auth` | `auth/routes.py` | `/login`, `/logout`, `/change-password` | Autenticação. Rate limiter no login. |
| `dashboard` | `dashboard/routes.py` | `/`, `/settings`, `/settings/reset-*`, `/settings/rates` | Dashboard KPIs, configurações, reset endpoints. |
| `quotes` | `quotes/routes.py` | `/quotes/`, `/new`, `/<id>`, `/edit`, `/pdf/<lang>`, `/approve`, `/reject`, `/delete` | CRUD orçamentos. Aprovação/rejeição. PDF PT/EN. |
| `orders` | `orders/routes.py` | `/orders/`, `/new`, `/create/<qid>`, `/<id>`, `/<id>/open`, `/faturar`, `/fechar`, `/cancel`, `/reabrir`, `/payments/*`, `/items/*` | CRUD pedidos. Transições de status. Pagamentos. Itens. |
| `purchase_orders` | `purchase_orders/routes.py` | `/purchase-orders/`, `/new`, `/<id>`, `/<id>/pdf`, `/<id>/save`, `/<id>/open`, `/send`, `/approve`, `/start`, `/conclude`, `/faturar`, `/cancel`, `/payments/*`, `/items/*` | CRUD POs. Transições de status. Pagamentos. Itens. |
| `dispatch` | `dispatch/routes.py` | `/dispatch/` | Dashboard de despacho. OS do dia, pendentes, em execução. |
| ~~`bookings`~~ | — | — | **REMOVIDO em 05/06/2026.** |
| `clients` | `clients/routes.py` | `/clients/`, `/new`, `/<id>/edit`, `/<id>/delete`, `/api/new`, `/search` | CRUD clientes. API de busca. Soft delete. |
| `drivers` | `drivers/routes.py` | `/drivers/`, `/new`, `/<id>/edit`, `/<id>/delete` | CRUD motoristas. Soft delete. |
| `vehicles` | `vehicles/routes.py` | `/vehicles/`, `/new`, `/<id>/edit`, `/<id>/delete` | CRUD veículos. |
| `suppliers` | `suppliers/routes.py` | `/suppliers/`, `/new`, `/<id>/edit`, `/<id>/delete`, `/bulk-delete`, `/api/new` | CRUD fornecedores. Bulk delete. Soft delete. |
| `services` | `services/routes.py` | `/services/`, `/add`, `/edit/<pid>`, `/flags/<sid>`, `/delete`, `/delete-bulk`, `/import-excel`, `/export-excel` | Catálogo de serviços. Precificação. Import/export Excel. |
| `categories` | `categories/routes.py` | `/categories/` | Listagem de categorias de veículos. |
| `financial` | `financial/routes.py` | `/financial/`, `/record/new`, `/<rid>/edit`, `/<rid>/delete`, `/<rid>/baixa` | Registros financeiros. Baixa. Soft delete cascade. |
| `reports` | `reports/routes.py` | `/reports/` | Relatórios mensais (receita, custo, lucro). |
| `users` | `users/routes.py` | `/users/`, `/new`, `/<uid>/edit`, `/<uid>/toggle-active` | CRUD usuários. Ativação/desativação. Self-lockout protection. |
| `roles` | `roles/routes.py` | `/roles/` | Visualização de roles e permissões. |
| `audit` | `audit/routes.py` | `/audit/` | Log de auditoria com paginação. |

---

## 5. Services (12 módulos)

| Arquivo | Responsabilidade | Status |
|---------|-----------------|--------|
| `services/__init__.py` | Re-exports de serviços públicos. | Ativo |
| `services/quote_service.py` | Criação/edição de orçamentos. Delete-and-reinsert de itens. População de client info. | Ativo |
| `services/order_service.py` | Gestão de pedidos: `create_manual`, `create_from_quote`, `update_header`, `update_adjustments`, `open_order`, `faturar`, `fechar`, `cancel`, `reabrir`, `generate_payments`, `add_payment`, `delete_payment`, `baixa`, `add_item`, `update_item`, `delete_item`. | Ativo |
| `services/order_pdf.py` | Geração de PDF de pedido (ReportLab). Dados operacionais, parcelas, itens. | Ativo |
| `services/purchase_order_service.py` | Gestão de POs: `create`, `create_from_order`, `create_from_service_order`, `open_po`, `send`, `approve`, `start_execution`, `conclude`, `faturar`, `cancel`, `generate_payments`, `update_payment_inline`, `delete_payment`, `baixa`, `add_item`, `update_item`, `delete_item`. | Ativo |
| `services/purchase_order_pdf.py` | Geração de PDF de PO (ReportLab). Fornecedor, itens, parcelas. | Ativo |
| `services/service_order_service.py` | Gestão de OS: `create_from_booking`, `create_manual`, `create_from_quote`, `assign_driver`, `assign_supplier`, `add_cost`, `recalculate_margin`, `update_status`, `add_event`, `close`, `send_driver_info`. | Ativo |
| ~~`services/booking_service.py`~~ | Criação de booking a partir de quote. | **REMOVIDO em 05/06/2026.** |
| `services/dispatch_service.py` | Consultas de despacho: `get_today`, `get_pending_assignment`, `get_in_progress`, `get_overdue`, `get_summary`. | Ativo |
| `services/financial_service.py` | Criação de `FinancialRecord` + `AccountReceivable` para booking. | **Dead code** — não chamado desde V2/V4 |
| `services/margin_service.py` | Cálculo de margem: `calculate_order_margin(revenue, cost, margin)`, `recalculate_order()` para write-back. | Ativo |
| `services/numbering_service.py` | Numeração sequencial: `next_rfq`, `next_order`, `next_os`, `next_po`. LIKE query + max(). | Ativo |

---

## 6. Utils (7 módulos)

| Arquivo | Responsabilidade |
|---------|-----------------|
| `utils/__init__.py` | `now_br()` (datetime Brasília UTC-3 naive), `utc_to_br()`, `make_client_token()` (HMAC-SHA256). |
| `utils/audit.py` | `log_activity(entity, entity_id, company_id, action, user_id)` — registra no `AuditLog`. Caller responsável pelo `commit()`. |
| `utils/decorators.py` | `@require_role(*codes)`, `@require_permission(code)`, `@require_any_permission(*codes)`, `@tenant_required`. Abortam 401/403. |
| `utils/helpers.py` | `parse_brl()` (parsing monetário canônico), `format_currency()`, `format_date()`, `format_datetime()`, `billing_label()`, `status_badge_class()`, `status_badge_style()`, `status_dot_color()`. |
| `utils/permissions.py` | Catálogo canônico: `PERMISSION_CATALOG` (~50 permissões), `SYSTEM_ROLES` (5 roles), `ROLE_PERMISSION_MATRIX`, `LEGACY_ROLE_MAP`. |
| `utils/security.py` | `LoginRateLimiter` (in-memory, janela deslizante 5/15min), `register_security_headers()` (X-Frame, nosniff, Referrer-Policy, Permissions-Policy, HSTS condicional). |
| `utils/translate.py` | `translate_obs(text, lang)` — tradução via `deep-translator` (Google Translate, sem API key). Silenciosa em falhas. |

---

## 7. Templates (32 Jinja2)

### 7.1 Layout

| Arquivo | Responsabilidade |
|---------|-----------------|
| `templates/base.html` | Layout base: navbar, sidebar, Alpine.js init, CSRF token meta. |

### 7.2 Por Módulo

| Módulo | Templates |
|--------|-----------|
| `auth/` | `login.html` (formulário de login), `change_password.html` |
| `dashboard/` | `index.html` (KPIs + gráficos Chart.js), `settings.html` |
| `quotes/` | `index.html` (lista com filtros), `detail.html`, `new.html` |
| `orders/` | `index.html` (lista com filtros), `detail.html` (tabs: header, itens, pagamentos, POs, OS) |
| `purchase_orders/` | `index.html` (lista com filtros), `detail.html` |
| `dispatch/` | `index.html` (cards de OS por status), `_os_card.html` (partial) |
| ~~`bookings/`~~ | — | **REMOVIDO em 05/06/2026.** |
| `clients/` | `index.html`, `form.html` |
| `drivers/` | `index.html`, `form.html` |
| `vehicles/` | `index.html`, `form.html` |
| `suppliers/` | `index.html`, `form.html` |
| `services/` | `index.html` (catálogo com precificação) |
| `categories/` | `index.html` |
| `financial/` | `index.html` (lista com filtros), `form.html`, `payables.html` (painel Contas a Pagar) |
| `reports/` | `index.html` (métricas mensais) |
| `users/` | `index.html`, `form.html` |
| `roles/` | `index.html` (roles + permissões) |
| `audit/` | `index.html` (log com paginação) |

---

## 8. Static Assets

| Caminho | Descrição |
|---------|-----------|
| `static/css/tailwind.css` | Tailwind CSS compilado. |
| `static/css/tailwind.src.css` | Fonte Tailwind com diretivas `@tailwind`. |
| `static/css/main.css` | CSS customizado adicional. |
| `static/js/main.js` | JavaScript customizado para interações. |
| `static/vendor/alpine.min.js` | Alpine.js (reatividade frontend). |
| `static/vendor/chartjs.min.js` | Chart.js (gráficos do dashboard). |
| `static/vendor/tailwind.js` | Tailwind CSS JS (dev). |
| `static/vendor/fontawesome/` | Font Awesome 6 (ícones). |
| `static/uploads/` | Arquivos enviados (logos). |

---

## 9. Migrations

| Caminho | Descrição |
|---------|-----------|
| `migrations/alembic.ini` | Config Alembic. |
| `migrations/env.py` | Ambiente Alembic (online/offline). |
| `migrations/script.py.mako` | Template para novas migrações. |
| `migrations/versions/` | 11 migrações versionadas (discount fields, approved/rejected by, vehicle model, user tracking, PO items, is_operational, category_type, operational fields, PO payments, emission_date, faturado fields). |

---

## 10. Tests (6 arquivos, 85 testes)

| Arquivo | Testes | Escopo |
|---------|--------|--------|
| `tests/conftest.py` | — | Fixtures: `app`, `client`, `auth_user`, `db`. |
| `tests/test_decorators_and_audit.py` | 11 | Decorators de autorização e `log_activity`. |
| `tests/test_permissions_catalog.py` | 4 | Validação do catálogo de permissões. |
| `tests/test_rbac_routes.py` | 55 | Acesso a rotas com diferentes roles (ADMIN, MANAGER, OPERATIONAL, FINANCIAL, VIEWER). |
| `tests/test_security_hardening.py` | 11 | Rate limiter e headers de segurança. |
| `tests/test_tenant_isolation.py` | 4 | Isolamento multi-tenant. |

---

## 11. Tools & Data

| Caminho | Descrição |
|---------|-----------|
| `tools/tailwindcss.exe` | Tailwind CSS CLI (Windows, 40 MB). |
| `tools/smoke_rbac_phase2b.py` | Smoke test RBAC. |
| `build_css.bat` | Script para build de CSS. |
| `run_tests.ps1` | Script PowerShell para rodar testes. |
| `tabela_data.py` | Dados da tabela de precificação (importada pelo seed). |
| `update_db.py` | Script auxiliar de atualização de banco. |
| `reset_transactional.py` | Script auxiliar de reset de dados transacionais. |
| `qa_test_e2e.py` | Teste E2E automatizado. |
| `qa_results.json` | Resultados do QA automatizado. |
| `QA_REPORT.md` | Relatório de QA (18/05/2026): 97 testes, 94 pass, 2 falsos negativos. |
| `RELATORIO_ARQUITETURA.md` | Relatório de arquitetura e qualidade (04/06/2026). |
| `RELATORIO_PARSING_MONETARIO.md` | Relatório de risco de parsing monetário (04/06/2026). |
