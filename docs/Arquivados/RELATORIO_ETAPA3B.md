# ETAPA 3B — RELATÓRIO FINAL (Módulo de Despesas Gerais)

**Data**: 28/08/2026 — **Commit**: ver `git log -1` (sem push — deploy segue o fluxo normal da branch `v3`)

---

## A. Backup

`backup/DB_V2_pre-etapa3b-20260828.db` — criado antes de qualquer alteração com a API nativa de backup do SQLite. Backups anteriores (Etapas 0 e 3A) **não sobrescritos**.

## B. Checkpoint

Branch `v3`, commit de entrada `a9a4958` (Etapa 3A), working tree limpo, alembic head `a3c1f8d2e6b4`, `integrity_check` ok — verificado antes de iniciar. Tag: **`v3-pre-etapa3b-despesas-20260828`**.

## C. Migration

`c4d2e9f0a1b5_add_expense_link_columns_to_financial_records.py`
- **UP**: 3 colunas nullable em `financial_records` — `supplier_id` (FK suppliers), `order_id` (FK orders), `purchase_order_id` (FK purchase_orders). SQLite via `batch_alter_table`; PostgreSQL via ADD COLUMN. Guardas de coluna existente.
- **DOWN**: remove somente as 3 colunas novas (validado em cópia isolada).
- **Aplicada no banco dev** (head `c4d2e9f0a1b5`); produção migra no próximo deploy.

## D. Schema antes/depois

- Antes: `financial_records` com 21 colunas.
- Depois: `financial_records` com 24 colunas (3 novas, **0 registros históricos preenchidos**).

## E. Model criado/alterado

**Nenhum model novo** — decisão de arquitetura: a despesa **É o próprio `FinancialRecord`** (`type='expense'`, `reference='expense:{id}'`), evitando duplicar descrição/valor/datas/status em uma tabela paralela. Alterado: `FinancialRecord` ganhou `supplier_id`, `order_id`, `purchase_order_id` + relationships (`supplier`, `order`, `purchase_order`).

## F. Rotas

| Rota | Acesso | Função |
|---|---|---|
| `GET /financial/expenses` | login | Lista + KPIs + filtros (período/status/categoria/centro de custo/fornecedor) |
| `GET/POST /financial/expenses/new` | `financial.manage` | Criar despesa |
| `GET/POST /financial/expenses/<id>/edit` | `financial.manage` | Editar (somente pendente; paga bloqueada) |
| `POST /financial/expenses/<id>/cancel` | `financial.manage` | Cancelar (somente pendente; paga bloqueada) |
| `POST /financial/record/<id>/baixa` (existente) | `financial.manage` | Pagar despesa (transação atômica da Etapa 2) |
| `edit_record`/`delete_record` (genéricos) | `financial.manage` | **Bloqueados para `type='expense'`** (redirecionam para a tela de Despesas) |

## G. Templates/componentes

- `financial/expenses.html` (lista + KPIs + filtros), `financial/expense_form.html` (formulário)
- Link "Despesas" no painel Financeiro
- Dashboard principal: faixa "Despesas Gerais" (No Período / Pendentes / Vencidas / Pagas no Período) — **separada** de Receita de Serviços e Custos Diretos; KPIs existentes intactos; fórmula de margem da Etapa 2 inalterada.

## H. Regras implementadas

1. Despesa **não exige SO/PO** (campos opcionais no formulário; NULL válido).
2. **Categoria obrigatória**, somente `type='expense'`, da mesma company (revenue/direct_cost rejeitadas).
3. **Centro de custo obrigatório**, da mesma company.
4. Fornecedor **opcional**, da mesma company.
5. Emissão e vencimento obrigatórios; valor > 0.
6. Status: pendente / paga / cancelada (+ "Vencida" computada quando pendente com vencimento vencido).
7. Referência única `expense:{id}`; índice parcial UNIQUE protege contra duplicidade ativa.
8. Pagamento transacional (FR + status + datas no mesmo commit; falha → rollback completo).
9. Despesa paga: **não edita, não cancela, não exclui** — histórico preservado (sem soft-delete).
10. Despesa pendente: cancelamento por status (nunca DELETE físico).
11. Isolamento multiempresa em todas as queries e validações.
12. Recorrência e anexos: **não implementados** (arquitetura permite no futuro; sem sistema de arquivos novo).

## I. Testes

`tests/test_expenses_etapa3b.py` — 12 testes: criação válida; categoria revenue/direct_cost rejeitadas; centro de custo obrigatório e de outra empresa rejeitado; fornecedor opcional; SO/PO opcionais; pagamento cria 1 FR; índice único de reference; rollback em falha de pagamento; cancelamento (pendente ok, paga bloqueada, histórico preservado); edição de paga bloqueada; isolamento multiempresa (404 + lista sem vazamento); RBAC (sem `financial.manage` → 403); regressão de dados transacionais.

## J. Resultado dos testes

- **12/12 novos: PASSARAM.**
- Etapa 2 e Etapa 3A: continuam passando (7 + 8).
- Suíte completa: **mesmas 6 falhas pré-existentes** (`test_decorators_and_audit.py`) — nenhuma falha nova.
- Rollback validado em **cópia isolada**: downgrade 3B remove só as 3 colunas novas (estruturas 3A e dados intactos); re-upgrade reconstrói.

## K. Multiempresa

Todas as queries filtram por `company_id` do usuário logado; validações de categoria/centro/fornecedor/SO/PO conferem a company; empresa A recebe **404** ao acessar despesas da empresa B e a listagem não vaza dados.

## L. RBAC

Reutiliza o mecanismo existente (`@require_permission("financial.manage")` para criar/editar/cancelar/pagar; `@login_required` para listar). Usuário sem permissão recebe 403 — testado.

## M. FinancialRecord

Despesa registrada no ledger com `type='expense'`, `reference='expense:{id}'`, `category='outro'` (legado) + `financial_category_id` (novo catálogo). Pagamento reusa `baixa_record` (atômico). Nenhum registro histórico alterado; nenhuma duplicidade possível (índice parcial UNIQUE + convenção de id próprio).

## N. Contas a Pagar

A despesa pendente É a obrigação (ledger), exibida nas telas de Despesas (KPIs Pendentes/Vencidas) e no dashboard; o painel AP existente (PO) permanece intacto para não misturar PO com Expense — consolidar AP unificado fica como evolução futura.

## O. Dados históricos

Comparação atual × backup pré-3B (todas as tabelas protegidas): **IDÊNTICAS** — orders, order_items, order_payments, purchase_orders, po_items, po_payments, financial_records (dados), quotes, payment_receipts, clients, suppliers, companies, services, vehicles, audit_logs, financial_categories, cost_centers.

- SO alterados: **ZERO**
- POs alterados: **ZERO**
- Pagamentos alterados: **ZERO**
- FinancialRecords históricos alterados: **ZERO**
- Novos campos 3B preenchidos em históricos: **0** · Despesas de teste no banco real: **0**
- `PO-260602-005` e FR `id45`: **não tocados** · 27 FRs soft-deletados: **não tocados**

## P. Problemas encontrados

1. O app de testes usa `create_all` (sem migrations) — o índice parcial UNIQUE não existe no banco em memória; o teste que valida a proteção cria o índice localmente para espelhar o schema de produção. Sem impacto em dev/prod (migration aplica o índice).
2. Nenhum outro problema.

## Q. Limitações

- Recorrência: não implementada (futuro).
- Anexos: não implementados (futuro).
- AP unificado (PO + Despesa numa única visão): ainda separado por design ("não misturar PO com Expense").
- Estorno/ajuste de despesa paga: não implementado (correção futura com fluxo próprio).

## R. Próxima etapa recomendada

1. **Fluxo de Caixa** (entradas−saídas por `paid_date` sobre o ledger: revenue + cost + expense).
2. **DRE** (agregar categorias: Receita Bruta → Custos Diretos → Margem Bruta → Despesas Gerais → Resultado).
3. Classificação do PO-260602-005 e do FR id45 no catálogo (com autorização explícita — altera dados).
4. Restauração decidida dos 27 FRs soft-deletados.
5. Aposentadoria do V4.

**Nada disso foi implementado nesta etapa.**

🟢 **ETAPA 3B CONCLUÍDA — DADOS HISTÓRICOS PRESERVADOS**
