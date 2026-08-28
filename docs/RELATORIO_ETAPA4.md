# ETAPA 4 — RELATÓRIO FINAL (Fluxo de Caixa Realizado)

**Data**: 28/08/2026 — **Commit**: ver `git log -1` (sem push — deploy segue o fluxo normal da branch `v3`)

---

## A. Backup

`backup/DB_V2_pre-etapa4-20260828.db` — criado antes de qualquer alteração (API nativa do SQLite). Backups anteriores (Etapas 0, 3A, 3B) **não sobrescritos**.

## B. Checkpoint

Branch `v3`, commit de entrada `929de99`, working tree limpo, alembic head `c4d2e9f0a1b5`, `integrity_check` ok. Tag: **`v3-pre-etapa4-fluxo-caixa-20260828`**.

## C. Migration

**NENHUMA** — nenhuma tabela/coluna nova foi necessária. O Fluxo de Caixa é 100% leitura sobre o ledger existente. (Nenhuma migration destrutiva; head permanece `c4d2e9f0a1b5`.)

## D. Schema

Inalterado.

## E. Fonte oficial dos movimentos

**`FinancialRecord` (ledger único)** — `status='pago'` + `paid_date` preenchido.
- Cada movimento aparece **exatamente uma vez**: o FR é o espelho 1:1 do pagamento (reference única + índice parcial UNIQUE da Etapa 3A) — `OrderPayment`/`POPayment`/despesa **não** geram linha duplicada.
- Nenhuma tabela paralela de movimentos foi criada (evita duplicar FinancialRecords).

## F. Entradas

FR `type='revenue'`, `status='pago'`, `paid_date` no período. Origem: `SO` (reference `order_payment:N`), `OUTRA` (lançamento manual). Detalhes por movimento: data (pagamento), valor, descrição, categoria, centro de custo, origem, referência, cliente e SO quando existir.

## G. Saídas

FR `type='cost'` (PO — reference `po_payment:N`) e `type='expense'` (Despesa Geral — reference `expense:N`), `status='pago'`, `paid_date` no período. Origem: `PO`, `DESPESA`, `OUTRA`. Agrupadas na tela por categoria-raiz (Custos Diretos / Despesas Operacionais / Administrativas / Pessoal / Impostos / Financeiras). Detalhes: fornecedor, PO, categoria, centro de custo, referência.

## H. Caixa Realizado

Tela **Financeiro → Fluxo de Caixa** (`/financial/cash-flow`): Total de Entradas, Total de Saídas, Saldo do Período, Saldo Final + blocos ENTRADAS/SAÍDAS com detalhe expansível por movimento (somente leitura).

Regras aplicadas (testadas):
- SO faturado e **não recebido** → caixa 0; recebido → entra o **valor recebido**, uma única vez. Evento de caixa = RECEBIMENTO.
- PO não paga → 0; paga → valor pago, uma única vez. Rascunho/cancelada → fora.
- Despesa pendente/vencida/cancelada → 0; paga → valor pago, uma única vez (sem segunda despesa no pagamento).
- Período pela **data real do movimento** (`paid_date`) — nunca `created_at`.

## I. Caixa Previsto

Implementado apenas como **informação separada** (cards "PREVISTO · A receber / A pagar — não realizado"), somando FRs pendentes de receita e de custo+despesa. Nunca misturado com o realizado. Projeção completa (por vencimento, linha do tempo) fica para etapa futura.

## J. Saldo Inicial

**NÃO inventado.** Sem configuração, a tela exibe "Saldo inicial não configurado" e o Saldo Final é rotulado como resultado líquido do período (nunca como saldo bancário real). Configuração futura via settings da empresa.

## K. Saldo Final

Saldo Final = Saldo Inicial (0, não configurado) + Entradas − Saídas. Exibido com a ressalva visual.

## L. Categorias

Reutiliza as categorias da Etapa 3A (`financial_category_id`); fallback para a categoria legada quando o vínculo novo não existe. Nenhuma categoria nova/duplicada.

## M. Centros de Custo

Reutiliza os centros da Etapa 3A (`cost_center_id`), exibidos no detalhe de cada movimento. Respeita `company_id`.

## N. Multiempresa

Todas as queries filtram por `company_id` do usuário logado; teste confirma que a tela não vaza movimentos de outra empresa.

## O. RBAC

Tela de **somente leitura** para qualquer usuário logado (visão financeira); nenhuma rota de mutação criada (`POST /financial/cash-flow` → 405). Modificações de dados continuam exigindo `financial.manage` nas telas de origem (SO/PO/Despesas). Testado.

## P. Testes

`tests/test_cash_flow_etapa4.py` — 7 testes: receita só com recebimento (parcial 600/1000 entra 600); PO só paga (não paga/rascunho fora); despesa só paga (pendente/vencida/cancelada fora) + categoria/centro corretos; período por `paid_date`; previsto separado do realizado; multiempresa + tela read-only (sem vazamento, sem forms, 405 no POST); viewer (sem `financial.manage`) vê a tela e não modifica nada.

## Q. Regressão

- Etapa 2 (7 testes): passando · Etapa 3A (8): passando · Etapa 3B (12): passando · Etapa 4 (7): passando.
- Suíte completa: **mesmas 6 falhas pré-existentes** (`test_decorators_and_audit.py`) — nenhuma falha nova.

## R. Integridade

`PRAGMA integrity_check` = ok. Alembic head inalterado (`c4d2e9f0a1b5`). Sem migration nesta etapa → sem necessidade de rollback.

## S. Dados históricos

Comparação atual × backup pré-Etapa 4: **todas as tabelas protegidas IDÊNTICAS** (quotes, orders, order_items, order_payments, purchase_orders, po_items, po_payments, financial_records, payment_receipts, clients, suppliers, companies, services, vehicles, audit_logs, financial_categories, cost_centers).

- SO alterados: **ZERO** · POs alterados: **ZERO** · Pagamentos alterados: **ZERO** · FinancialRecords históricos alterados: **ZERO**
- Registros de teste no banco real: **ZERO** (testes em `sqlite :memory:`) · PO-260602-005, FR id45 e 27 soft-deletados: **não tocados** · V4: **não tocado** · DRE e margem: **não tocados**

## T. Problemas encontrados

Nenhum.

## U. Pendências

1. Configuração de **saldo inicial** (futuro, via settings da empresa).
2. **Caixa Previsto** completo (projeção por vencimento, linha do tempo) — etapa futura.
3. Dump do PostgreSQL de produção (pendente desde a Etapa 0 — obrigatório antes do próximo deploy).
4. DRE; restauração dos 27 FRs; classificação do PO-260602-005/FR id45; aposentadoria do V4 — etapas futuras.

## V. Recomendação para Etapa 5

1. **DRE** (Receita Bruta → Custos Diretos → Margem Bruta → Despesas Gerais → Resultado) sobre categorias/centros de custo — agora com todas as fontes existentes.
2. Configuração de saldo inicial + Caixa Previsto completo.
3. Deploy com validação (dump de produção antes).
4. Decisões: restauração dos 27 FRs e classificação dos registros históricos órfãos (com autorização explícita — alteram dados).

**Nada disso foi implementado nesta etapa.**

🟢 **ETAPA 4 CONCLUÍDA — FLUXO DE CAIXA VALIDADO**
