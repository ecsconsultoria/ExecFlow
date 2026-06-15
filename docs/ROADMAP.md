# ROADMAP.md — App_Orcamentos_V2

> **Data:** 05/06/2026 (atualizado)
> **Fonte:** BACKLOG.md (48 itens)
> **Regra de priorização:** 1. Estabilidade → 2. Segurança → 3. Performance → 4. Refatoração
> **Status:** ✅ Sprint 1 CONCLUÍDA (7/7 itens + Booking removido + Menu reestruturado)
> **Duração dos sprints:** Variável por item (esforço estimado em horas)

---

## Sprint 1 — ESTABILIDADE (P0 + Segurança Crítica)

**Objetivo:** Eliminar bugs que causam corrupção de dados, perda financeira ou falha do sistema.
**Duração estimada:** 18h-30h

---

### Item 1.1 — ✅ P0-01: Parsing Monetário (`parse_brl()`)

| Campo | Valor |
|-------|-------|
| **Prioridade** | P0 |
| **Esforço** | CONCLUÍDO |
| **Status** | ✅ DONE |

---

### Item 1.2 — P0-04: Bug `is_deleted` em OperationCost

| Campo | Valor |
|-------|-------|
| **Prioridade** | P0 |
| **Esforço** | 1h |
| **Tarefa** | Adicionar `SoftDeleteMixin` a `OperationCost` ou remover `getattr` do `recalculate_margin()` |
| **Arquivos** | `models/service_order.py`, `models/operation_cost.py` |
| **Validação** | Criar `OperationCost`, soft-deletar, verificar que `recalculate_margin()` não o inclui |

---

### Item 1.3 — P0-05: Reset Destrutivo sem Confirmação

| Campo | Valor |
|-------|-------|
| **Prioridade** | P0 |
| **Esforço** | 3h-4h |
| **Tarefa** | Adicionar modal de confirmação com digitação de "CONFIRMAR", re-autenticação (senha), e registro em `AuditLog` |
| **Arquivos** | `dashboard/routes.py`, `templates/dashboard/settings.html`, `utils/audit.py` |
| **Validação** | Tentar reset sem confirmação → bloqueado. Reset com confirmação → auditado. |

---

### Item 1.4 — P0-02: Inconsistência no Gerenciamento de Transações

| Campo | Valor |
|-------|-------|
| **Prioridade** | P0 |
| **Esforço** | 8h-12h |
| **Tarefa** | Auditar todos os serviços. Mapear quem commita e quem não commita. Definir padrão (recomendado: commit no controller). Corrigir os desvios. |
| **Arquivos** | `booking_service.py`, `order_service.py`, `purchase_order_service.py`, `quote_service.py`, `service_order_service.py` + controllers |
| **Validação** | Todo teste existente passa. Teste de integração: criar Quote → Order → PO → verificar atomicidade. |

---

### Item 1.5 — P0-03: Duplicação de Cascade Financeiro

| Campo | Valor |
|-------|-------|
| **Prioridade** | P0 |
| **Esforço** | 4h-6h |
| **Tarefa** | Extrair lógica de void/cancelamento financeiro para `financial_service.py`. Unificar as 3 implementações. |
| **Arquivos** | `orders/routes.py`, `purchase_orders/routes.py`, `financial/routes.py`, `services/financial_service.py` |
| **Validação** | Cancelar Order → verificar registros financeiros cancelados. Cancelar PO → idem. Excluir FinancialRecord → idem. |

---

### Item 1.6 — P1-11: Mass Assignment em ServiceOrder

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforço** | 1h-2h |
| **Tarefa** | Substituir `hasattr` por allowlist explícita de campos no `create_manual()` |
| **Arquivos** | `services/service_order_service.py` |
| **Validação** | Tentar injetar `revenue_amount` via formulário → valor ignorado. |

---

### Item 1.7 — P1-12: Cross-Tenant Data Exposure (Categories/Roles)

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforço** | 1h-2h |
| **Tarefa** | Confirmar design multi-tenant para `VehicleCategory` e `Role`. Se forem globais, documentar. Se não, adicionar `company_id`. |
| **Arquivos** | `categories/routes.py`, `roles/routes.py` |
| **Validação** | Usuário empresa A não vê categorias/roles exclusivas da empresa B. |

---

### Sprint 1 — Resumo

| Item | Descrição | Esforço | Status |
|------|-----------|--------|--------|
| 1.1 | `parse_brl()` | — | ✅ DONE 04/06 |
| 1.2 | `is_deleted` dead code | 1h | ✅ DONE 05/06 |
| 1.3 | Reset confirmação | 3h-4h | ✅ DONE 05/06 |
| 1.4 | Transações uniformes | 8h-12h | ✅ DONE 05/06 |
| 1.5 | Cascade financeiro | 4h-6h | ✅ DONE 05/06 |
| 1.6 | Mass assignment | 1h-2h | ✅ DONE 05/06 |
| 1.7 | Cross-tenant | 1h-2h | ✅ DONE 05/06 |
| — | Remoção do Booking | — | ✅ DONE 05/06 |
| — | Menu reestruturado | — | ✅ DONE 05/06 |
| **Total** | | **18h-27h** | ✅ CONCLUÍDO | |

---

## Sprint 2 — SEGURANÇA (P1)

**Objetivo:** Fechar brechas de segurança e compliance.
**Duração estimada:** 19h-31h

---

### Item 2.1 — P1-01: LGPD — Google Translate

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforço** | 4h-8h |
| **Tarefa** | Opção A: Implementar tradução offline (dicionário estático) para termos de serviço. Opção B: Adicionar consentimento explícito + documentar transferência. |
| **Arquivos** | `utils/translate.py`, `services/quote_pdf.py`, `services/order_pdf.py`, `services/purchase_order_pdf.py` |
| **Validação** | PDFs em inglês gerados sem chamada HTTP. Ou consentimento registrado. |

---

### Item 2.2 — P1-02: Rate Limiter Multi-Worker

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforço** | 4h-6h |
| **Tarefa** | Migrar de `LoginRateLimiter` in-memory para Flask-Limiter com backend Redis (produção) ou filesystem (dev). |
| **Arquivos** | `utils/security.py`, `auth/routes.py`, `requirements.txt`, `config.py` |
| **Validação** | 5 tentativas → bloqueio em todos os workers. |

---

### Item 2.3 — P1-10: Content-Security-Policy (CSP)

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforço** | 3h-5h |
| **Tarefa** | Definir diretivas CSP. Ajustar templates para usar nonces em inline scripts. Testar em todos os templates. |
| **Arquivos** | `utils/security.py`, 32 templates Jinja2 |
| **Validação** | DevTools → sem erros CSP. XSS de prova de conceito bloqueado. |

---

### Item 2.4 — P2-08: Log de Auditoria Forense

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 (promovido por ser pré-requisito de compliance) |
| **Esforço** | 4h-6h |
| **Tarefa** | Adicionar `ip_address`, `user_agent`, `old_data`, `new_data` (JSON) ao `AuditLog`. Atualizar `log_activity()`. Criar migração. |
| **Arquivos** | `models/audit.py`, `utils/audit.py`, migrations/ |
| **Validação** | Operação de edição registra valores antes/depois. IP e user-agent capturados. |

---

### Item 2.5 — P3-02: Logging de Acessos Negados

| Campo | Valor |
|-------|-------|
| **Prioridade** | P3 (promovido por ser complemento de segurança) |
| **Esforço** | 1h-2h |
| **Tarefa** | Adicionar `log_activity()` nos decorators `require_permission` e `require_role` quando retornam 401/403. |
| **Arquivos** | `utils/decorators.py` |
| **Validação** | Tentar acessar rota sem permissão → registrado no AuditLog. |

---

### Item 2.6 — P3-01: Separar HSTS de Cookie Secure

| Campo | Valor |
|-------|-------|
| **Prioridade** | P3 (promovido por ser segurança) |
| **Esforço** | 1h |
| **Tarefa** | Separar flags de configuração: `ENABLE_HSTS` independente de `SESSION_COOKIE_SECURE`. |
| **Arquivos** | `config.py`, `utils/security.py` |
| **Validação** | HSTS ativo em produção mesmo sem cookie secure (embora ambos devam estar ativos). |

---

### Sprint 2 — Resumo

| Item | Descrição | Esforço | Status |
|------|-----------|--------|--------|
| 2.1 | LGPD Google Translate | 4h-8h | 🔴 TODO |
| 2.2 | Rate limiter Redis | 4h-6h | 🔴 TODO |
| 2.3 | Content-Security-Policy | 3h-5h | 🔴 TODO |
| 2.4 | Auditoria forense | 4h-6h | 🔴 TODO |
| 2.5 | Logging acessos negados | 1h-2h | 🔴 TODO |
| 2.6 | HSTS independente | 1h | 🔴 TODO |
| **Total** | | **17h-28h** | |

---

## Sprint 3 — PERFORMANCE (P1 + P2)

**Objetivo:** Reduzir queries, otimizar dashboard, preparar para PostgreSQL.
**Duração estimada:** 26h-42h

---

### Item 3.1 — P1-03: Reduzir `lazy="joined"` para `lazy="select"`

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforço** | 8h-12h |
| **Tarefa** | Alterar 9 modelos. Adicionar `joinedload()` explícito nas queries de detalhe. Testar todas as listagens e detalhes. |
| **Arquivos** | `models/order.py`, `models/purchase_order.py`, `models/service_order.py`, `models/quote.py`, `models/audit.py`, `models/revenue_entry.py`, `models/supplier_payment.py`, `models/service_order_assignment.py`, `models/service_order_event.py` |
| **Validação** | `pytest tests/ -v` passa. Listagens não quebram. Detalhes carregam dados corretamente. |

---

### Item 3.2 — P1-04: Índices em FKs para PostgreSQL

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforço** | 8h-12h |
| **Tarefa** | Adicionar `index=True` em 30+ FKs. Criar migração. Testar em staging PostgreSQL. |
| **Arquivos** | 20+ arquivos de modelo, migrations/ |
| **Validação** | `EXPLAIN ANALYZE` mostra index scan, não seq scan. Tempo de query reduzido. |

---

### Item 3.3 — P1-05: Numeração com Race Condition

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforço** | 4h-6h |
| **Tarefa** | Implementar tabela `sequence_numbers` com `SELECT ... FOR UPDATE` (SQLite) ou usar PostgreSQL `SEQUENCE`. |
| **Arquivos** | `services/numbering_service.py`, migrations/ |
| **Validação** | Teste de concorrência: 2 threads criando registros simultaneamente sem `IntegrityError`. |

---

### Item 3.4 — P1-06: Dashboard 24+ Queries → 2 Queries

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforço** | 3h-4h |
| **Tarefa** | Consolidar `_so_revenue()` e `_po_cost()` em query única com `GROUP BY` mensal dos últimos 12 meses. |
| **Arquivos** | `dashboard/routes.py` |
| **Validação** | Dashboard carrega. Gráfico mostra dados corretos. Redução de 24+ para 2 queries. |

---

### Item 3.5 — P1-07: N+1 em `_catalog_json()`

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforço** | 1h-2h |
| **Tarefa** | Adicionar `joinedload(ServicePricing.service).joinedload(Service.state)` e `joinedload(ServicePricing.category)`. |
| **Arquivos** | `quotes/routes.py` |
| **Validação** | Página de novo orçamento carrega em 1-2 queries (não 50+). |

---

### Item 3.6 — P1-08: N+1 Seller Name em Order Detail

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforço** | 1h |
| **Tarefa** | Usar `joinedload` na query de detail para carregar `created_by`. |
| **Arquivos** | `orders/routes.py`, `models/order.py` |
| **Validação** | Detalhe de Order carrega seller name sem query extra. |

---

### Item 3.7 — P2-14: Paginação em Listagens

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 |
| **Esforço** | 3h-5h |
| **Tarefa** | Adicionar `.paginate(page=page, per_page=25)` em 8+ listagens. Atualizar templates com controles de página. |
| **Arquivos** | 8+ blueprints de listagem |
| **Validação** | Listagens mostram 25 itens por página. Navegação entre páginas funciona. |

---

### Sprint 3 — Resumo

| Item | Descrição | Esforço | Status |
|------|-----------|--------|--------|
| 3.1 | `lazy="joined"` → `lazy="select"` | 8h-12h | 🔴 TODO |
| 3.2 | Índices FK PostgreSQL | 8h-12h | 🔴 TODO |
| 3.3 | Numeração race condition | 4h-6h | 🔴 TODO |
| 3.4 | Dashboard queries | 3h-4h | 🔴 TODO |
| 3.5 | N+1 catalog_json | 1h-2h | 🔴 TODO |
| 3.6 | N+1 seller name | 1h | 🔴 TODO |
| 3.7 | Paginação | 3h-5h | 🔴 TODO |
| **Total** | | **28h-42h** | |

---

## Sprint 4 — REFATORAÇÃO (P1 + P2 + P3)

**Objetivo:** Reduzir dívida técnica, melhorar manutenibilidade, padronizar código.
**Duração estimada:** 32h-56h

---

### Item 4.1 — P1-09: Extrair PDF Base Class

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforço** | 8h-12h |
| **Tarefa** | Criar `BasePDFGenerator` com header, footer, estilos, logo. Migrar 3 geradores. Testar output visualmente. |
| **Arquivos** | `services/quote_pdf.py`, `services/order_pdf.py`, `services/purchase_order_pdf.py`, novo `services/base_pdf.py` |
| **Validação** | PDFs gerados são idênticos aos da versão anterior. |

---

### Item 4.2 — P1-13: Testes Insuficientes

| Campo | Valor |
|-------|-------|
| **Prioridade** | P1 |
| **Esforço** | 16h-24h |
| **Tarefa** | Criar testes unitários para 12 serviços. Criar testes de integração para fluxo Quote→Order→PO→Financeiro. Criar testes de PDF. |
| **Arquivos** | `tests/` (novos arquivos) |
| **Validação** | Cobertura > 70%. Testes de regressão capturam bugs dos Sprints 1-3. |

---

### Item 4.3 — P2-01 / P2-18: Unificar RBAC (Remover Role Legada)

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 |
| **Esforço** | 6h-8h |
| **Tarefa** | Remover coluna `role` string. Simplificar `has_role()`, `has_permission()`, `_is_effective_admin`. Migrar dados. |
| **Arquivos** | `models/user.py`, `utils/permissions.py`, `auth/routes.py`, `users/routes.py`, migrations/ |
| **Validação** | Todos os 85 testes passam. Login com usuários migrados funciona. |

---

### Item 4.4 — P2-02: Denormalização com Event Listeners

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 |
| **Esforço** | 3h-5h |
| **Tarefa** | Adicionar `after_insert`, `after_update`, `after_delete` listeners no SQLAlchemy para `OperationCost`, `RevenueEntry`, `SupplierPayment` → auto `recalculate_margin()`. |
| **Arquivos** | `models/service_order.py`, `models/operation_cost.py`, `models/revenue_entry.py`, `models/supplier_payment.py` |
| **Validação** | Criar custo → margem recalculada automaticamente. Deletar custo → idem. |

---

### Item 4.5 — P2-04 / P2-17: Mover Lógica para Serviços

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 |
| **Esforço** | 4h-6h |
| **Tarefa** | Extrair `save_all()` das rotas para `order_service.update_full()` e `purchase_order_service.update_full()`. |
| **Arquivos** | `orders/routes.py`, `purchase_orders/routes.py`, `services/order_service.py`, `services/purchase_order_service.py` |
| **Validação** | Funcionalidade `save_all()` preservada. Rotas mais enxutas. |

---

### Item 4.6 — P2-10 a P2-13: Micro-Otimizações SQL

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 |
| **Esforço** | 3h (todos juntos) |
| **Tarefa** | P2-10: Bulk delete. P2-11: Bulk update no cancel. P2-12: Remover `db.session.expire()`. P2-13: `len()` em vez de `.count()`. |
| **Arquivos** | `suppliers/routes.py`, `services/routes.py`, `services/order_service.py`, `services/purchase_order_service.py` |
| **Validação** | Comportamento preservado. Performance melhorada. |

---

### Item 4.7 — P2-05: Renomear Coluna `"metadata"`

| Campo | Valor |
|-------|-------|
| **Prioridade** | P2 |
| **Esforço** | 1h-2h |
| **Tarefa** | Renomear para `event_metadata`. Criar migração. Atualizar referências. |
| **Arquivos** | `models/service_order_event.py`, migrations/ |
| **Validação** | Events continuam funcionando. Coluna renomeada. |

---

### Item 4.8 — P3-06, P3-07, P3-09: Refatorações Rápidas

| Campo | Valor |
|-------|-------|
| **Prioridade** | P3 |
| **Esforço** | 2h (todos juntos) |
| **Tarefa** | Remover `__import__("datetime")`. Remover `financial_service.py`. Extrair `compute_total()` duplicado. |
| **Arquivos** | `dashboard/routes.py`, `services/financial_service.py`, `services/booking_service.py`, `models/order.py`, `models/purchase_order.py`, `utils/helpers.py` |
| **Validação** | Dashboard carrega. Lógica de desconto preservada. |

---

### Sprint 4 — Resumo

| Item | Descrição | Esforço | Status |
|------|-----------|--------|--------|
| 4.1 | PDF base class | 8h-12h | 🔴 TODO |
| 4.2 | Testes (unit + integração) | 16h-24h | 🔴 TODO |
| 4.3 | Unificar RBAC | 6h-8h | 🔴 TODO |
| 4.4 | Event listeners denormalização | 3h-5h | 🔴 TODO |
| 4.5 | Mover lógica para serviços | 4h-6h | 🔴 TODO |
| 4.6 | Micro-otimizações SQL | 3h | 🔴 TODO |
| 4.7 | Renomear coluna metadata | 1h-2h | 🔴 TODO |
| 4.8 | Refatorações rápidas | 2h | 🔴 TODO |
| **Total** | | **43h-62h** | |

---

## Visão Geral do Roadmap

```
SPRINT 1 (18h-27h)          SPRINT 2 (17h-28h)          SPRINT 3 (28h-42h)          SPRINT 4 (43h-62h)
┌────────────────────┐      ┌────────────────────┐      ┌────────────────────┐      ┌────────────────────┐
│ ESTABILIDADE       │      │ SEGURANÇA          │      │ PERFORMANCE        │      │ REFATORAÇÃO        │
│                    │      │                    │      │                    │      │                    │
│ ✅ parse_brl       │      │ LGPD Translate     │      │ lazy=select        │      │ PDF base class     │
│ is_deleted bug     │      │ Rate limiter Redis │      │ Índices FK (PG)    │      │ Testes (70% cov)   │
│ Reset confirmação  │      │ CSP                │      │ Numeração lock     │      │ Unificar RBAC      │
│ Transações uniform │      │ Auditoria forense  │      │ Dashboard 2q       │      │ Event listeners    │
│ Cascade financeiro │      │ Log acessos negados│      │ N+1 catalog_json   │      │ Mover logic p/ svc │
│ Mass assignment    │      │ HSTS independente  │      │ N+1 seller name    │      │ Micro-otimiz SQL   │
│ Cross-tenant       │      │                    │      │ Paginação          │      │ Renomear metadata  │
│                    │      │                    │      │                    │      │ Refatorações rápid │
└────────────────────┘      └────────────────────┘      └────────────────────┘      └────────────────────┘
```

### Estimativa Total

| Sprint | Foco | Itens | Esforço |
|--------|------|-------|---------|
| Sprint 1 | Estabilidade | 7 | 18h-27h |
| Sprint 2 | Segurança | 6 | 17h-28h |
| Sprint 3 | Performance | 7 | 28h-42h |
| Sprint 4 | Refatoração | 8 | 43h-62h |
| **Total** | | **28** | **106h-159h** |

### Itens não incluídos nos Sprints (Backlog Futuro)

Estes itens do BACKLOG.md não foram incluídos nos 4 sprints por serem de menor prioridade ou dependerem de decisões arquiteturais:

| ID | Item | P | Motivo do adiamento |
|----|------|---|---------------------|
| P2-03 | Modelos legados V4 | P2 | Requer plano de depreciação |
| P2-06 | 22 CHECK constraints | P2 | Grande volume, melhor após testes |
| P2-07 | Validação @validates | P2 | Depende de decisão de formato |
| P2-15 | Otimizar dashboard | P2 | Parcialmente coberto por P1-06 |
| P2-16 | Cache catálogo | P2 | Infra (Flask-Caching) |
| P3-03 | Otimizar PDF | P3 | Parcialmente coberto por P1-09 |
| P3-04 | Query numeração | P3 | Parcialmente coberto por P1-05 |
| P3-05 | Helpers template | P3 | Cosmético |
| P3-08 | Type hints | P3 | Grande volume, gradual |
| P3-10 | Unit of Work | P3 | Coberto por P0-02 |
| P3-11 | Baixa commit parcial | P3 | Coberto por P0-02 |
| P3-12 | sync pending rollback | P3 | Coberto por P0-02 |
