# BACKLOG.md — ExecFlow_ERP_V2

> **Data:** 05/06/2026 (atualizado)
> **Fonte:** RELATORIO_ARQUITETURA.md + análise completa do código
> **Total de itens:** 48 | **Concluídos:** 8 (Sprint 1) + Booking + Menu

---

## P0 — CRÍTICO (5 itens)

Itens que causam corrupção de dados, perda financeira ou falha total do sistema.

---

### P0-01 — Bug de Parsing de Valores Monetários (Corrupção de Dados)

| Campo | Valor |
|-------|-------|
| **Categoria** | Dívida Técnica |
| **Origem** | `RELATORIO_ARQUITETURA.md` D3.2 |
| **Impacto** | Valores financeiros corrompidos (100x maior). Prejuízo financeiro real. |
| **Risco** | Entrada `"1500.50"` (formato internacional) → armazenado como `150050.00` |
| **Esforço** | ✅ **CONCLUÍDO** — `parse_brl()` canônico implementado em `app/utils/helpers.py` |
| **Arquivos alterados** | `helpers.py`, `financial/routes.py`, `orders/routes.py`, `purchase_orders/routes.py`, `purchase_order_service.py`, `order_service.py` |
| **Dependências** | Nenhuma |

---

### P0-02 — Inconsistência no Gerenciamento de Transações

| Campo | Valor |
|-------|-------|
| **Categoria** | Arquitetura |
| **Origem** | `RELATORIO_ARQUITETURA.md` A2.1 |
| **Impacto** | Dados perdidos ou estado parcialmente persistido. Comportamento imprevisível entre serviços. |
| **Risco** | Serviços com `commit()` interno vs. delegado: `booking_service.create_from_quote` commita; `order_service.cancel` não commita. Caller não sabe o que esperar. |
| **Esforço** | Grande (8h-16h) — requer revisão de todos os serviços e controllers |
| **Arquivos envolvidos** | `booking_service.py`, `order_service.py`, `purchase_order_service.py`, `quote_service.py`, `service_order_service.py`, `orders/routes.py`, `purchase_orders/routes.py`, `financial/routes.py` |
| **Dependências** | R7.8 (Consolidar Unit of Work) |

---

### P0-03 — Duplicação Massiva de Lógica de Cascade Financeiro

| Campo | Valor |
|-------|-------|
| **Categoria** | Arquitetura |
| **Origem** | `RELATORIO_ARQUITETURA.md` A2.2 |
| **Impacto** | Bugs de inconsistência financeira ao cancelar/excluir entidades. Correção em um local não reflete nos outros. |
| **Risco** | 3 implementações divergentes da mesma lógica (`_void_order_financial_records`, `_void_po_financial_records`, cascade em `delete_record`) |
| **Esforço** | Médio (4h-6h) — extrair para serviço compartilhado |
| **Arquivos envolvidos** | `orders/routes.py`, `purchase_orders/routes.py`, `financial/routes.py`, `financial_service.py` (atualmente dead code) |
| **Dependências** | P0-02 (transações precisam estar consistentes antes de unificar cascade) |

---

### P0-04 — Bug `is_deleted` em OperationCost (Dead Code)

| Campo | Valor |
|-------|-------|
| **Categoria** | Dívida Técnica |
| **Origem** | `RELATORIO_ARQUITETURA.md` D3.1 |
| **Impacto** | Custos "deletados" são sempre incluídos no cálculo de margem. Dados financeiros incorretos. |
| **Risco** | `OperationCost` não herda `SoftDeleteMixin`, mas `recalculate_margin()` tenta filtrar por `is_deleted`. Filtro é código morto. |
| **Esforço** | Pequeno (1h) — adicionar `SoftDeleteMixin` ou remover o `getattr` |
| **Arquivos envolvidos** | `models/service_order.py`, `models/operation_cost.py` |
| **Dependências** | Nenhuma — correção isolada |

---

### P0-05 — Reset Destrutivo sem Confirmação

| Campo | Valor |
|-------|-------|
| **Categoria** | Segurança |
| **Origem** | `RELATORIO_ARQUITETURA.md` S4.3 |
| **Impacto** | Perda total de dados transacionais/financeiros por ação acidental ou maliciosa de admin. |
| **Risco** | 3 endpoints (`reset-transactional`, `reset-financial`, `reset-all`) executam `DELETE FROM` sem re-autenticação, confirmação, ou log de auditoria. |
| **Esforço** | Médio (3h-4h) — adicionar modal de confirmação + re-autenticação + audit log |
| **Arquivos envolvidos** | `dashboard/routes.py`, `templates/dashboard/settings.html`, `utils/audit.py` |
| **Dependências** | Nenhuma |

---

## P1 — IMPORTANTE (13 itens)

Itens que afetam segurança, performance em produção ou integridade arquitetural.

---

### P1-01 — Vazamento de Dados para Google Translate (LGPD)

| Campo | Valor |
|-------|-------|
| **Categoria** | Segurança |
| **Origem** | `RELATORIO_ARQUITETURA.md` S4.1 |
| **Impacto** | Violação LGPD. Transferência internacional de dados pessoais sem consentimento. |
| **Risco** | `translate_obs()` envia nomes, endereços, valores para Google. Sem consentimento documentado. |
| **Esforço** | Médio (4h-8h) — implementar tradução offline, ou adicionar consentimento + documentação |
| **Arquivos envolvidos** | `utils/translate.py`, `services/quote_pdf.py`, `services/order_pdf.py`, `services/purchase_order_pdf.py` |
| **Dependências** | Nenhuma |

---

### P1-02 — Rate Limiter In-Process (Multi-Worker Ineficaz)

| Campo | Valor |
|-------|-------|
| **Categoria** | Segurança |
| **Origem** | `RELATORIO_ARQUITETURA.md` S4.2 |
| **Impacto** | Proteção contra brute force ~4x mais fraca com múltiplos workers Gunicorn. |
| **Risco** | Atacante faz 5 tentativas por worker = 20 tentativas antes de bloqueio |
| **Esforço** | Médio (4h-6h) — migrar para Flask-Limiter + Redis |
| **Arquivos envolvidos** | `utils/security.py`, `blueprints/auth/routes.py`, `requirements.txt` |
| **Dependências** | Redis externo (infra) |

---

### P1-03 — `lazy="joined"` Generalizado (Performance)

| Campo | Valor |
|-------|-------|
| **Categoria** | Arquitetura / Performance |
| **Origem** | `RELATORIO_ARQUITETURA.md` A2.3, P6.1 |
| **Impacto** | 20+ JOINs forçados em toda query. Listagens com 50+ registros trafegam dados desnecessários de 6-7 tabelas extras. |
| **Risco** | Degradação progressiva com crescimento de dados. Listagem de Orders carrega 6 User objects via JOIN. |
| **Esforço** | Grande (8h-12h) — alterar 9 modelos, testar todas as queries afetadas |
| **Arquivos envolvidos** | `models/order.py`, `models/purchase_order.py`, `models/service_order.py`, `models/quote.py`, `models/audit.py`, `models/revenue_entry.py`, `models/supplier_payment.py`, `models/service_order_assignment.py`, `models/service_order_event.py` |
| **Dependências** | P0-02 (transações devem ser compreendidas antes de alterar modelos) |

---

### P1-04 — Ausência de Índices em Chaves Estrangeiras

| Campo | Valor |
|-------|-------|
| **Categoria** | Performance / Produção |
| **Origem** | `RELATORIO_ARQUITETURA.md` D3.4, P6.2 |
| **Impacto** | Full table scans em PostgreSQL. Degradação severa com volume de dados. |
| **Risco** | 30+ FKs sem `index=True`. SQLite cria automaticamente; PostgreSQL não. |
| **Esforço** | Grande (8h-12h) — adicionar índices em 20+ modelos, criar migração, testar em staging PostgreSQL |
| **Arquivos envolvidos** | Todos os 20+ arquivos de modelo com FK |
| **Dependências** | Ambiente PostgreSQL para teste |

---

### P1-05 — Numeração Sequencial com Condição de Corrida

| Campo | Valor |
|-------|-------|
| **Categoria** | Dívida Técnica |
| **Origem** | `RELATORIO_ARQUITETURA.md` D3.7 |
| **Impacto** | `IntegrityError` em produção com concorrência. Duas transações podem gerar o mesmo número. |
| **Risco** | `LIKE` query + `max()` sem lock. `unique=True` impede duplicata mas causa erro 500. |
| **Esforço** | Médio (4h-6h) — implementar tabela de sequência ou usar PostgreSQL `SEQUENCE` |
| **Arquivos envolvidos** | `services/numbering_service.py`, migrations/ |
| **Dependências** | PostgreSQL (sequências nativas) ou SQLite (tabela dedicada com lock) |

---

### P1-06 — Dashboard: 24+ Queries para Gráfico

| Campo | Valor |
|-------|-------|
| **Categoria** | SQL Ineficiente |
| **Origem** | `RELATORIO_ARQUITETURA.md` Q5.1 |
| **Impacto** | Dashboard lento. 24+ consultas agregadas apenas para o gráfico de 12 meses. |
| **Risco** | Cada requisição ao dashboard gera 24+ queries separadas. Tempo de resposta degradado. |
| **Esforço** | Médio (3h-4h) — consolidar em query única com `GROUP BY` mensal |
| **Arquivos envolvidos** | `dashboard/routes.py` |
| **Dependências** | Nenhuma |

---

### P1-07 — N+1 em `_catalog_json()` (Quotes)

| Campo | Valor |
|-------|-------|
| **Categoria** | SQL Ineficiente |
| **Origem** | `RELATORIO_ARQUITETURA.md` Q5.2 |
| **Impacto** | Página de novo orçamento lenta. 50+ queries em catálogo com muitas precificações. |
| **Risco** | Loop sobre categorias → precificações acessa relacionamentos sem eager loading |
| **Esforço** | Pequeno (1h-2h) — adicionar `joinedload` para `service`, `state`, `category` |
| **Arquivos envolvidos** | `quotes/routes.py` |
| **Dependências** | Nenhuma |

---

### P1-08 — N+1 em `detail()` de Order (Seller Name)

| Campo | Valor |
|-------|-------|
| **Categoria** | SQL Ineficiente |
| **Origem** | `RELATORIO_ARQUITETURA.md` Q5.3 |
| **Impacto** | Query extra para cada visualização de detalhe de Order. |
| **Risco** | `User.query.get(order.created_by)` manual porque relacionamento usa `lazyload('*')` |
| **Esforço** | Pequeno (1h) — usar `joinedload` na query de detail |
| **Arquivos envolvidos** | `orders/routes.py`, `models/order.py` |
| **Dependências** | P1-03 (relacionado a `lazy="joined"`) |

---

### P1-09 — Extrair PDF Base Class (Refatoração)

| Campo | Valor |
|-------|-------|
| **Categoria** | Refatoração |
| **Origem** | `RELATORIO_ARQUITETURA.md` R7.1 |
| **Impacto** | ~70% de código duplicado entre 3 geradores de PDF. Manutenção tripla. |
| **Risco** | Mudanças de layout precisam ser replicadas manualmente em 3 arquivos. |
| **Esforço** | Grande (8h-12h) — criar `BasePDFGenerator`, migrar 3 geradores, testar output |
| **Arquivos envolvidos** | `services/quote_pdf.py`, `services/order_pdf.py`, `services/purchase_order_pdf.py`, novo `services/base_pdf.py` |
| **Dependências** | Testes de regressão de PDF (comparação visual) |

---

### P1-10 — Adicionar Content-Security-Policy (CSP)

| Campo | Valor |
|-------|-------|
| **Categoria** | Segurança |
| **Origem** | `RELATORIO_ARQUITETURA.md` S4.4 |
| **Impacto** | Defesa principal contra XSS ausente. Templates vulneráveis a injeção. |
| **Risco** | Sem CSP, XSS refletido ou armazenado executa JavaScript livremente. |
| **Esforço** | Médio (3h-5h) — definir diretivas CSP, testar todos os templates, ajustar inline scripts |
| **Arquivos envolvidos** | `utils/security.py`, múltiplos templates (para ajustar inline scripts com nonce/hash) |
| **Dependências** | Testes em todos os templates |

---

### P1-11 — Mass Assignment em ServiceOrder

| Campo | Valor |
|-------|-------|
| **Categoria** | Segurança |
| **Origem** | `RELATORIO_ARQUITETURA.md` S4.6 |
| **Impacto** | Atacante pode definir campos sensíveis via formulário manipulado. |
| **Risco** | `create_manual()` aceita qualquer atributo do modelo via `hasattr`. |
| **Esforço** | Pequeno (1h-2h) — substituir `hasattr` por allowlist explícita |
| **Arquivos envolvidos** | `services/service_order_service.py` |
| **Dependências** | Nenhuma |

---

### P1-12 — Cross-Tenant Data Exposure (Categories/Roles)

| Campo | Valor |
|-------|-------|
| **Categoria** | Segurança |
| **Origem** | `RELATORIO_ARQUITETURA.md` S4.5 |
| **Impacto** | Dados de categorias e roles visíveis entre empresas. |
| **Risco** | `VehicleCategory.query.all()` e `Role.query.all()` sem filtro `company_id` |
| **Esforço** | Pequeno (1h-2h) — adicionar filtro `company_id` ou confirmar que são tabelas globais |
| **Arquivos envolvidos** | `categories/routes.py`, `roles/routes.py` |
| **Dependências** | Confirmação de design multi-tenant |

---

### P1-13 — Testes Insuficientes

| Campo | Valor |
|-------|-------|
| **Categoria** | Dívida Técnica |
| **Origem** | `RELATORIO_ARQUITETURA.md` D3.8 |
| **Impacto** | Regressões não detectadas. Sem cobertura de serviços de negócio e fluxos financeiros. |
| **Risco** | Bugs em `order_service`, `purchase_order_service`, `margin_service` não são capturados. |
| **Esforço** | Grande (16h-24h) — testes unitários para 12 serviços, testes de integração para fluxos principais |
| **Arquivos envolvidos** | `tests/` (todos), 12 serviços |
| **Dependências** | P0-02 (testes dependem de comportamento estável) |

---

## P2 — MELHORIA (18 itens)

Itens que melhoram qualidade, manutenibilidade e robustez.

---

### P2-01 — Sistema Duplo de Roles (Legado + RBAC)

| Campo | Valor |
|-------|-------|
| **Categoria** | Arquitetura |
| **Origem** | RELATÓRIO A2.4 |
| **Impacto** | Complexidade desnecessária. Risco de inconsistência entre role legada e RBAC. |
| **Esforço** | Médio (6h-8h) — remover coluna `role`, migrar lógica, testar todos os níveis de acesso |
| **Arquivos** | `models/user.py`, `utils/permissions.py`, `blueprints/auth/routes.py`, `blueprints/users/routes.py`, migrations/ |
| **Dependências** | Testes RBAC existentes |

---

### P2-02 — Denormalização sem Sincronização Automática

| Campo | Valor |
|-------|-------|
| **Categoria** | Arquitetura |
| **Origem** | RELATÓRIO A2.5 |
| **Impacto** | Dados financeiros inconsistentes se `recalculate_margin()` não for chamado. |
| **Esforço** | Médio (3h-5h) — adicionar event listeners SQLAlchemy ou converter para `@property` |
| **Arquivos** | `models/service_order.py`, `models/operation_cost.py`, `models/revenue_entry.py`, `models/supplier_payment.py` |
| **Dependências** | Nenhuma |

---

### P2-03 — Modelos Legados Coexistindo com V4

| Campo | Valor |
|-------|-------|
| **Categoria** | Arquitetura |
| **Origem** | RELATÓRIO A2.6 |
| **Impacto** | Código morto ou semi-ativo poluindo codebase. Manutenção desnecessária. |
| **Esforço** | Médio (4h-6h) — definir plano de depreciação, isolar em `legacy/` ou remover |
| **Arquivos** | `models/financial.py`, `models/booking.py`, `services/financial_service.py`, `blueprints/bookings/`, `blueprints/financial/` |
| **Dependências** | Confirmação de que não há dependentes ativos |

---

### P2-04 — Responsabilidades Sobrepostas entre Rotas e Serviços

| Campo | Valor |
|-------|-------|
| **Categoria** | Arquitetura |
| **Origem** | RELATÓRIO A2.7 |
| **Impacto** | `save_all()` com 57-70 linhas misturando parsing, validação, autorização, status, margem e auditoria. |
| **Esforço** | Médio (4h-6h) — extrair lógica para `order_service.update_full()` e `purchase_order_service.update_full()` |
| **Arquivos** | `orders/routes.py`, `purchase_orders/routes.py`, `services/order_service.py`, `services/purchase_order_service.py` |
| **Dependências** | P0-02 |

---

### P2-05 — Coluna `"metadata"` como Palavra Reservada SQL

| Campo | Valor |
|-------|-------|
| **Categoria** | Dívida Técnica |
| **Origem** | RELATÓRIO D3.3 |
| **Impacto** | Quebra em ferramentas SQL raw, migrações manuais, BI. |
| **Esforço** | Pequeno (1h-2h) — renomear coluna + migração |
| **Arquivos** | `models/service_order_event.py`, migrations/ |
| **Dependências** | Migração com rename column |

---

### P2-06 — 22 Campos de Status sem Constraints de Banco

| Campo | Valor |
|-------|-------|
| **Categoria** | Dívida Técnica |
| **Origem** | RELATÓRIO D3.5 |
| **Impacto** | Qualquer bug pode gravar status inválido. Dados inconsistentes. |
| **Esforço** | Médio (4h-6h) — adicionar `CheckConstraint` ou `Enum` em 22 campos, criar migrações |
| **Arquivos** | 15+ modelos |
| **Dependências** | Nenhuma |

---

### P2-07 — Ausência de Validação de Formato no Modelo

| Campo | Valor |
|-------|-------|
| **Categoria** | Dívida Técnica |
| **Origem** | RELATÓRIO D3.6 |
| **Impacto** | Emails, telefones, documentos inválidos no banco. Validação apenas no frontend (bypassável). |
| **Esforço** | Médio (3h-5h) — adicionar `@validates` SQLAlchemy para formatos críticos |
| **Arquivos** | `models/user.py`, `models/client.py`, `models/driver.py`, `models/supplier.py`, `models/vehicle.py`, `models/company.py` |
| **Dependências** | Nenhuma |

---

### P2-08 — Log de Auditoria sem Dados Forenses

| Campo | Valor |
|-------|-------|
| **Categoria** | Segurança |
| **Origem** | RELATÓRIO S4.7 |
| **Impacto** | Insuficiente para conformidade LGPD e auditoria fiscal. |
| **Esforço** | Médio (4h-6h) — adicionar `ip_address`, `user_agent`, `old_data`, `new_data` ao modelo e função |
| **Arquivos** | `models/audit.py`, `utils/audit.py` |
| **Dependências** | Migração para novas colunas |

---

### P2-09 — N+1 em PDF: Category Query por Item

| Campo | Valor |
|-------|-------|
| **Categoria** | SQL Ineficiente |
| **Origem** | RELATÓRIO Q5.4 |
| **Impacto** | PDFs com muitos itens geram múltiplas queries. |
| **Esforço** | Pequeno (1h) — eager loading de `category` antes do loop |
| **Arquivos** | `services/quote_pdf.py` |
| **Dependências** | Nenhuma |

---

### P2-10 — Bulk Delete com Loop Individual

| Campo | Valor |
|-------|-------|
| **Categoria** | SQL Ineficiente |
| **Origem** | RELATÓRIO Q5.5 |
| **Impacto** | 100 SELECT + 100 UPDATE para deletar 100 fornecedores. |
| **Esforço** | Pequeno (1h) — `update()` com `in_(ids)` |
| **Arquivos** | `suppliers/routes.py`, `services/routes.py` |
| **Dependências** | Nenhuma |

---

### P2-11 — Loop de `all()` em Cancel (Financial Records)

| Campo | Valor |
|-------|-------|
| **Categoria** | SQL Ineficiente |
| **Origem** | RELATÓRIO Q5.6 |
| **Impacto** | Cancelamento de Order com muitos registros financeiros é lento. |
| **Esforço** | Pequeno (1h) — bulk update |
| **Arquivos** | `services/order_service.py` |
| **Dependências** | Nenhuma |

---

### P2-12 — `db.session.expire()` + Reload Desnecessário

| Campo | Valor |
|-------|-------|
| **Categoria** | SQL Ineficiente |
| **Origem** | RELATÓRIO Q5.7 |
| **Impacto** | Query extra desnecessária para recarregar itens já em memória. |
| **Esforço** | Pequeno (30min) — usar itens em memória |
| **Arquivos** | `services/order_service.py` |
| **Dependências** | Nenhuma |

---

### P2-13 — Query COUNT + Iteração na Mesma Collection

| Campo | Valor |
|-------|-------|
| **Categoria** | SQL Ineficiente |
| **Origem** | RELATÓRIO Q5.8 |
| **Impacto** | Duas queries onde uma bastaria (COUNT + SELECT). |
| **Esforço** | Pequeno (30min) — carregar com `all()` e usar `len()` |
| **Arquivos** | `services/purchase_order_service.py` |
| **Dependências** | Nenhuma |

---

### P2-14 — Paginação em Listagens

| Campo | Valor |
|-------|-------|
| **Categoria** | Performance |
| **Origem** | RELATÓRIO P6.3 |
| **Impacto** | Memory pressure com crescimento de dados. Listagens sem limite. |
| **Esforço** | Médio (3h-5h) — adicionar `.paginate()` em 8+ listagens |
| **Arquivos** | `quotes/routes.py`, `orders/routes.py`, `purchase_orders/routes.py`, `dispatch/routes.py`, `clients/routes.py`, `drivers/routes.py`, `suppliers/routes.py`, `financial/routes.py` |
| **Dependências** | Nenhuma |

---

### P2-15 — Otimizar Dashboard

| Campo | Valor |
|-------|-------|
| **Categoria** | Performance |
| **Origem** | RELATÓRIO P6.4 |
| **Impacto** | Dashboard 2-3x mais rápido após otimização. |
| **Esforço** | Médio (3h-5h) — consolidar queries, eager loading |
| **Arquivos** | `dashboard/routes.py`, `services/dispatch_service.py` |
| **Dependências** | P1-06 (query do gráfico) |

---

### P2-16 — Cache de Catálogo de Serviços

| Campo | Valor |
|-------|-------|
| **Categoria** | Performance |
| **Origem** | RELATÓRIO P6.5 |
| **Impacto** | Redução de queries repetidas em múltiplas páginas. |
| **Esforço** | Médio (2h-3h) — Flask-Caching com invalidação |
| **Arquivos** | `quotes/routes.py`, `orders/routes.py`, `services/routes.py`, `requirements.txt` |
| **Dependências** | Nenhuma |

---

### P2-17 — Mover Lógica de Negócio das Rotas para Serviços

| Campo | Valor |
|-------|-------|
| **Categoria** | Refatoração |
| **Origem** | RELATÓRIO R7.4 |
| **Impacto** | Separação clara de responsabilidades. Rotas orquestram, serviços executam. |
| **Esforço** | Médio (4h-6h) — extrair `save_all()` para serviços |
| **Arquivos** | `orders/routes.py`, `purchase_orders/routes.py`, `services/order_service.py`, `services/purchase_order_service.py` |
| **Dependências** | P0-02, P2-04 |

---

### P2-18 — Unificar Sistema de Autorização

| Campo | Valor |
|-------|-------|
| **Categoria** | Refatoração |
| **Origem** | RELATÓRIO R7.5 |
| **Impacto** | Simplificação. Remoção de ~100 linhas de lógica dual. |
| **Esforço** | Médio (6h-8h) — remover coluna `role`, atualizar `has_role()`, `has_permission()`, `_is_effective_admin` |
| **Arquivos** | `models/user.py`, `utils/permissions.py`, migrations/ |
| **Dependências** | P2-01 (idêntico) |

---

## P3 — REFATORAÇÃO (12 itens)

Itens de melhoria de código, qualidade e manutenibilidade.

---

### P3-01 — Cookie Secure e HSTS Condicionais

| Campo | Valor |
|-------|-------|
| **Categoria** | Segurança |
| **Origem** | RELATÓRIO S4.8 |
| **Impacto** | HSTS desabilitado se `SESSION_COOKIE_SECURE` não estiver ativo. |
| **Esforço** | Pequeno (1h) — separar flags |
| **Arquivos** | `config.py`, `utils/security.py` |
| **Dependências** | Nenhuma |

---

### P3-02 — Ausência de Logging de Acessos Negados

| Campo | Valor |
|-------|-------|
| **Categoria** | Segurança |
| **Origem** | RELATÓRIO S4.9 |
| **Impacto** | Tentativas de acesso não autorizado não são detectáveis. |
| **Esforço** | Pequeno (1h-2h) — adicionar `log_activity` nos decorators |
| **Arquivos** | `utils/decorators.py` |
| **Dependências** | Nenhuma |

---

### P3-03 — Otimizar Geração de PDF

| Campo | Valor |
|-------|-------|
| **Categoria** | Performance |
| **Origem** | RELATÓRIO P6.6 |
| **Impacto** | PDFs gerados mais rápido, menos memória. |
| **Esforço** | Pequeno (2h-3h) — mover queries para fora de loops, cache de logo_url, timeout no translate |
| **Arquivos** | `services/quote_pdf.py`, `services/order_pdf.py`, `services/purchase_order_pdf.py`, `utils/translate.py` |
| **Dependências** | P1-09 (base class facilita) |

---

### P3-04 — Query de Numeração Sequencial

| Campo | Valor |
|-------|-------|
| **Categoria** | Performance |
| **Origem** | RELATÓRIO P6.7 |
| **Impacto** | Performance em PostgreSQL com milhões de registros. |
| **Esforço** | Médio (3h-4h) — tabela de sequência dedicada |
| **Arquivos** | `services/numbering_service.py`, migrations/ |
| **Dependências** | P1-05 (race condition — pode ser resolvido junto) |

---

### P3-05 — Extrair Helpers de Template Duplicados

| Campo | Valor |
|-------|-------|
| **Categoria** | Refatoração |
| **Origem** | RELATÓRIO R7.6 |
| **Impacto** | Consistência de formatação. Menos código nos templates. |
| **Esforço** | Pequeno (1h-2h) — garantir uso de `|currency` em todos os templates |
| **Arquivos** | 10+ templates Jinja2 |
| **Dependências** | Nenhuma |

---

### P3-06 — Remover `__import__("datetime")`

| Campo | Valor |
|-------|-------|
| **Categoria** | Refatoração |
| **Origem** | RELATÓRIO R7.7 |
| **Impacto** | Código mais legível, ferramentas de análise estática funcionam. |
| **Esforço** | Pequeno (30min) — substituir por imports normais |
| **Arquivos** | `dashboard/routes.py` |
| **Dependências** | Nenhuma |

---

### P3-07 — Dead Code: Remover `financial_service.py`

| Campo | Valor |
|-------|-------|
| **Categoria** | Refatoração |
| **Origem** | RELATÓRIO R7.9 |
| **Impacto** | Código morto removido. Confusão eliminada. |
| **Esforço** | Pequeno (30min) — confirmar ausência de callers e remover |
| **Arquivos** | `services/financial_service.py`, `services/booking_service.py` (import não usado) |
| **Dependências** | P2-03 (limpeza de legados) |

---

### P3-08 — Adicionar Type Hints

| Campo | Valor |
|-------|-------|
| **Categoria** | Refatoração |
| **Origem** | RELATÓRIO R7.10 |
| **Impacto** | Melhor autocompletar, detecção de bugs por ferramentas de tipo. |
| **Esforço** | Grande (16h-24h) — adicionar type hints em ~70 arquivos gradualmente |
| **Arquivos** | Todos os `services/`, `utils/`, `models/` |
| **Dependências** | Nenhuma |

---

### P3-09 — Extrair Lógica de Desconto Duplicada

| Campo | Valor |
|-------|-------|
| **Categoria** | Refatoração |
| **Origem** | RELATÓRIO R7.2 |
| **Impacto** | DRY. `computed_total` idêntico em Order e PurchaseOrder. |
| **Esforço** | Pequeno (1h-2h) — criar `compute_total()` compartilhado |
| **Arquivos** | `models/order.py`, `models/purchase_order.py`, `utils/helpers.py` |
| **Dependências** | Nenhuma |

---

### P3-10 — Consolidar Gerenciamento de Transações (Unit of Work)

| Campo | Valor |
|-------|-------|
| **Categoria** | Refatoração |
| **Origem** | RELATÓRIO R7.8 |
| **Impacto** | Padrão uniforme. Menos bugs de transação. |
| **Esforço** | Grande (12h-16h) — revisar todos os serviços, remover `commit()` internos, adicionar context manager |
| **Arquivos** | Todos os serviços e controllers |
| **Dependências** | P0-02 (resolve — são o mesmo item) |

---

### P3-11 — Corrigir Inconsistência de `baixa()` com `commit()` Parcial

| Campo | Valor |
|-------|-------|
| **Categoria** | Dívida Técnica (adicional) |
| **Origem** | Análise de `order_service.baixa()` e `purchase_order_service.baixa()` |
| **Impacto** | Pagamento marcado como pago mas registro financeiro nunca criado se a segunda etapa falhar. |
| **Esforço** | Médio (3h-4h) — reestruturar com savepoint ou transação atômica |
| **Arquivos** | `services/order_service.py`, `services/purchase_order_service.py` |
| **Dependências** | P0-02 |

---

### P3-12 — `_sync_pending_financials` com Rollback Silencioso

| Campo | Valor |
|-------|-------|
| **Categoria** | Dívida Técnica (adicional) |
| **Origem** | Análise de `_sync_order_pending_financials()` e `_sync_po_pending_financials()` |
| **Impacto** | Rollback silencioso descarta alterações legítimas da sessão. |
| **Esforço** | Pequeno (1h-2h) — isolar em savepoint |
| **Arquivos** | `services/order_service.py`, `services/purchase_order_service.py` |
| **Dependências** | P0-02 |

---

## Resumo Estatístico

| Prioridade | Quantidade | % |
|-----------|-----------|-----|
| **P0 — Crítico** | 5 | 10% |
| **P1 — Importante** | 13 | 27% |
| **P2 — Melhoria** | 18 | 38% |
| **P3 — Refatoração** | 12 | 25% |
| **TOTAL** | **48** | **100%** |

| Categoria | P0 | P1 | P2 | P3 | Total |
|-----------|----|----|----|----|-------|
| Arquitetura | 2 | 1 | 3 | 0 | 6 |
| Dívida Técnica | 2 | 2 | 4 | 2 | 10 |
| Segurança | 1 | 3 | 1 | 2 | 7 |
| SQL Ineficiente | 0 | 3 | 5 | 0 | 8 |
| Performance | 0 | 2 | 3 | 2 | 7 |
| Refatoração | 0 | 2 | 2 | 6 | 10 |

| Status | Quantidade |
|--------|-----------|
| ✅ **CONCLUÍDO** | 1 (P0-01: `parse_brl()`) |
| 🔴 **PENDENTE** | 47 |
