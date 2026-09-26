# CLAUDE.md — ExecFlow ERP V3

> Contexto canônico para sessões do Claude Code. Fatos verificados em 26/09/2026.
> Regras de conduta obrigatórias: [AGENTS.md](AGENTS.md), [AGENTS_DEV.md](AGENTS_DEV.md), [AGENTS_PROD.md](AGENTS_PROD.md).

## Fatos verificados (NÃO confie nos docs V2-era sem checar contra esta tabela)

| Fato | Valor |
|---|---|
| Entry point dev | `ExecFlow.py` — servidor Flask na **porta 5003** (`app.run(host="0.0.0.0", port=5003, debug=True)`) |
| Entry point prod | `gunicorn ExecFlow:app` no Render (Procfile: `--workers 1 --threads 2 --timeout 60 --max-requests 100 --max-requests-jitter 20`) |
| venv | `AI_Projects/venv` (Python 3.11.9) — **não** é um venv local do projeto |
| Banco dev | SQLite `instance/DB_V2.db` (WAL) · Banco prod: PostgreSQL (Render) |
| Migrações | 18 arquivos em `migrations/versions/` (padrão: guardas idempotentes; SQLite dev × PostgreSQL prod) |
| Testes | 330 coletados — baseline atual: **6 falhas pré-existentes** em `test_decorators_and_audit.py` (DetachedInstanceError em `User.roles`). **Não tratar como regressão** — comparar com este baseline |
| Deploy | **push na branch `v3`** = auto-deploy no Render (NUNCA `main`). Commit local não afeta produção |
| Obs. menor | `config.py` tem fallback `BASE_URL=...:5004`; o servidor real roda em 5003. `qa_test_e2e.py` ainda aponta 5004 (legado) |

## Regras financeiras vigentes (pós-Etapa 2 — 28/08/2026)

- **Receita** reconhecida SÓ com faturamento efetivo (`invoiced_at` preenchido; status faturado/concluído).
- **Custo direto** = PO válida vinculada a SO ativo (PO `rascunho`/`cancelado`/`excluído` NÃO conta).
- **Ledger único = `FinancialRecord`** (`type`: `revenue`/`cost`/`expense`). O subsistema "V4" (`financial_entries`, `revenue_entries`, `operation_costs`, `supplier_payments`, `service_orders`) está **MORTO (0 linhas) — não use, não escreva nele**.
- **Despesa geral** = FR `type='expense'` com categoria financeira + centro de custo obrigatórios.
- `parse_brl()` é OBRIGATÓRIO para todo parsing monetário (nunca `float(str.replace(...))`).
- Histórico financeiro saneado nas Etapas 6–7 (21 FRs restaurados, FR45 cancelado — decisões e evidências em `docs/Arquivados/`).
- Backup do banco antes de qualquer migração (padrão de todas as Etapas; backups em `backup/`).

## Documentação: o que ler

| Doc | Status |
|---|---|
| `AGENTS.md` / `AGENTS_DEV.md` / `AGENTS_PROD.md` | Regras obrigatórias de conduta (atualizadas para V3 em 26/09/2026) |
| `docs/AUDITORIA_FINANCEIRA.md` (28/08) | ✅ **Fonte de verdade** da arquitetura financeira real |
| `docs/RECONCILIACAO_FINANCEIRA.md` (28/08) | ✅ Baseline dos dados (SO/PO/FR) e decisões de restauração |
| `docs/PLANO_ETAPA11B_UX.md`, `docs/PLANO_ETAPA12E_RELATORIOS_EXPORTACOES.md`, `docs/ANALISE_RFQ_PADRAO_SO.md` | ✅ Decisões de design recentes (escopos explícitos) |
| `docs/frontend/DESIGN_SYSTEM.md` + `COMPONENTS.md` | ✅ Padrão visual e macros Jinja2 obrigatórias |
| `docs/architecture.md`, `docs/CODEBASE_INDEX.md`, `docs/business_rules.md`, `docs/development.md`, `docs/deployment.md`, `docs/production.md` | ⚠️ V2-era — úteis como estrutura, mas divergem dos fatos acima (porta, entry point, contagem de testes, "V4 ativo") |
| `docs/Arquivados/` | 🗂️ Trilha de auditoria das Etapas 0→12E (60 relatórios) — consultar sob demanda |
| `docs/BACKLOG.md`, `docs/ROADMAP.md` | ❌ Planejamento V2 abandonado (superado pela sequência real de Etapas) |
| `BACKUP_INFO.md`, `RELATORIO_ARQUITETURA.md`, `RELATORIO_PARSING_MONETARIO.md`, `QA_REPORT.md` (raiz) | ❌ Históricos (maio–junho/2026) |

## Regras rápidas de código

- **Multi-tenant**: toda query de dados de empresa filtra por `company_id` (`current_user.company_id`). Exceções globais: `Permission`, `Role`, `State`, `VehicleCategory`.
- **RBAC**: toda rota sensível usa `@require_permission`/`@require_any_permission`/`@require_role` (server-side). `has_perm()` em template é só UX.
- **Exclusões**: soft delete (`obj.soft_delete()`), nunca `db.session.delete()` em modelos com `SoftDeleteMixin`. Operações sensíveis chamam `log_activity()`.
- **NÃO** adicionar `commit()` dentro de serviços (delegar ao controller). **NÃO** usar `lazy="joined"` em relacionamentos novos. **NÃO** usar raw SQL fora das exceções documentadas.
- Commits em PT, com autorização do usuário; **sem push sem autorização** (push na `v3` = deploy em produção).

## Arquitetura resumida

```
ExecFlow.py (entry) → create_app() [app/__init__.py]
  ├── blueprints/  (18 módulos de rotas)  → services/ (19 módulos de regra)
  │                                          ├── margin_service, dre_service, cash_flow_service,
  │                                          │   ar_ap_service, payment_history_service, financial_service,
  │                                          │   order_service, purchase_order_service, quote_service,
  │                                          │   dispatch_service, numbering_service, recurrence_service,
  │                                          │   service_order_service (OS = fluxo MORTO)
  │                                          └── PDF/XLSX: quote_pdf, order_pdf, purchase_order_pdf,
  │                                              receipt_pdf, report_pdf, report_xlsx
  ├── models/      (SQLAlchemy; TimestampMixin/SoftDeleteMixin em models/base.py)
  ├── utils/       (permissions.py = catálogo RBAC; helpers.py = parse_brl; decorators.py; audit.py; security.py)
  └── templates/   (Jinja2 + macros em templates/components/: btn, badge, card, input, table,
                   modal, page_header, timeline, payment_summary, status_badge_style, export_buttons)
```
