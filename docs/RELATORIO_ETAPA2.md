# ETAPA 2 — RELATÓRIO FINAL (Correção da lógica financeira)

**Data**: 28/08/2026 — **Checkpoint pré-alterações**: tag `v3-pre-etapa2-logica-financeira-20260828` (sobre `dcee012`)
**Commit da etapa**: ver `git log -1` após o commit (sem push — deploy segue fluxo normal da branch `v3`)

---

## A. Alterações realizadas

1. **Regra única de reconhecimento de receita** — receita de serviço só é reconhecida com faturamento efetivo (`invoiced_at` preenchido e status faturado/concluído). SO novo/aberto/cancelado/excluído/concluído-sem-fatura = 0.
2. **Regra única de custo direto** — PO em `rascunho`/`cancelado`/`excluído` **não** é custo realizado (eliminou a inconsistência `margin_service` × Dashboard); PO sem SO não é atribuída a nenhum serviço (futura despesa geral).
3. **Margem única** — funções centrais em `margin_service` (receita reconhecida − custo direto), usadas pelo Dashboard, pela property `Order.margin_pct` (cálculo ao vivo, sem ler denormalização) e pelos eventos naturais que recalcula a denormalização.
4. **Dashboard** — `_so_revenue` (por `invoiced_at`, só faturados) e `_po_cost` (PO válida + vinculada a SO ativo); margem derivada das duas; gráfico 12 meses usa as mesmas funções.
5. **Funil corrigido** — conversão com numerador e denominador no mesmo horizonte (340% → valor ≤100%); valores de SO do funil passam a usar `computed_total` (desconto aplicado).
6. **Cards com período** — dashboard (recebimentos/pagamentos pendentes, ancorados no vencimento) e painel financeiro ("A Receber/A Pagar", ancorados na data contábil).
7. **Proteção de registros pagos** — `void_payment_financial_records` não soft-deleta mais FinancialRecords com status `pago` (histórico preservado na exclusão futura de SO/PO).
8. **Baixa atômica no painel financeiro** — `baixa_record` agora commit única transação (FR + parcela + status) com rollback total em falha (antes: dois commits com estado parcial possível).
9. **Relatórios** — somas de receita/custo por `paid_date` agora exigem `status = "pago"`.

## B. Arquivos modificados

- `app/services/margin_service.py` (funções centrais)
- `app/blueprints/dashboard/routes.py` (receita/custo/funil/cards)
- `app/blueprints/financial/routes.py` (cards com período + baixa atômica)
- `app/blueprints/reports/routes.py` (filtro status pago)
- `app/services/financial_service.py` (void preserva pagos)
- `app/models/order.py` (`margin_pct` ao vivo)
- `app/models/purchase_order.py` (constante `PO_INVALID_COST_STATUSES`)
- **Novos**: `tests/test_financial_logic_etapa2.py` (7 testes), `docs/RECONCILIACAO_FINANCEIRA.md` (Etapa 1)

## C. Funções financeiras alteradas

| Função | Mudança |
|---|---|
| `margin_service.recognized_service_revenue(order)` | NOVA — regra única de reconhecimento |
| `margin_service.direct_costs_for_order / direct_cost_total` | NOVAS — custo direto válido |
| `margin_service.gross_margin / gross_margin_pct` | NOVAS — margem única |
| `margin_service.calculate_order_margin / recalculate_order` | custo agora exclui rascunho (mesma regra) |
| `Order.margin_pct` (property) | cálculo ao vivo, ignora denormalização |
| `dashboard._so_revenue / _po_cost` | receita por faturamento; custo válido + pareado |
| `financial_service.void_payment_financial_records` | preserva FRs pagos |
| `financial.baixa_record` | transação única com rollback |
| `reports.index` | status `pago` obrigatório |

## D. Receita antes/depois da correção (R$)

| Período | Antes (emissão, ≠excluido) | Depois (faturamento efetivo) |
|---|---|---|
| mai/2026 | 13.500,00 | 0,00 |
| jun/2026 | 24.006,00 | 15.500,00 |
| jul/2026 | 19.471,00 | 1.771,00 |
| ago/2026 | 0,00 | 8.675,00 |
| **Acumulado** | **56.977,00** | **25.946,00** |

Diferença = SOs não faturados (abertos/concluídos sem fatura) e o SO cancelado — antes contavam, agora não.

## E. Custos antes/depois (R$)

| Período | Antes (≠excl/rasc) | Depois (válido + vinculado a SO ativo) |
|---|---|---|
| jun/2026 | 38.880,00 | 25.325,00 |
| jul/2026 | 14.595,00 | 14.595,00 |
| **Acumulado** | **53.475,00** | **39.920,00** |

Diferença = PO sem SO (13.500, fica para a futura Despesa Geral) + PO de SO excluído (55). O status `aberto` permanece como custo válido conforme regra da etapa (apenas rascunho/cancelado/excluído saem).

## F. Margem antes/depois (R$)

| Período | Antes | Depois | % antes | % depois |
|---|---|---|---|---|
| jun/2026 | 24.006 − 38.880 = −14.874 | 15.500 − 25.325 = −9.825 | −62,0% | −63,4% |
| jul/2026 | 19.471 − 14.595 = +4.876 | 1.771 − 14.595 = −12.824 | +25,0% | −724,1% |
| ago/2026 | 0 − 0 = 0 | 8.675 − 0 = +8.675 | 0% | +100,0% |
| **Acumulado** | **+3.502** | **−13.974** | +6,1% | −53,9% |

A margem agora reflete apenas receita faturada × custo válido. Observação honesta: julho ficou fortemente negativo porque custos de julho pertencem a serviços faturados em agosto (base de custo = `created_at` × base de receita = `invoiced_at`) — artefato de competência conhecido, pendência para etapa futura.

## G. Dashboard

- KPIs Receita/Custo/Margem e gráfico 12 meses: usam as funções centrais (regra única).
- Funil: conversão corrigida (agora ≈81% = 17 aprovadas / 21 enviadas; antes 340%); valores de SO usam `computed_total`.
- Cards AR/AP: respeitam o período selecionado (vencimento no período).

## H. AP/AR

- Arquitetura mantida (parcela operacional + FR de ledger); sem novo módulo.
- Painel financeiro: cards "A Receber/A Pagar" agora respeitam o período.
- Dashboard: pendentes ancorados no vencimento do período.

## I. FinancialRecord

- Nenhum registro alterado, criado ou apagado nesta etapa.
- Proteção futura: void não apaga lançamentos pagos (27 soft-deletados históricos permanecem como estão — restauração é decisão de etapa futura).
- Deduplicação por `reference` garantida em nível de aplicação (query→update→insert); UNIQUE em banco fica documentado para a Etapa 3 (requer migration — não executada).

## J. Proteções adicionadas

1. FR pago não é mais apagado por exclusão/cancelamento de SO/PO.
2. Baixa do painel financeiro é atômica (rollback total em falha).
3. Não-duplicação lógica por `reference` validada por teste.
4. Receita não é reconhecida sem faturamento (nenhuma tela).

## K. Testes executados

- `tests/test_financial_logic_etapa2.py` — 7 testes novos (receita, custo, margem única, dashboard por período, void preserva pagos, não-duplicação, rollback de baixa).
- Suíte completa (`pytest -q`).

## L. Resultado dos testes

- **7/7 novos testes: PASSARAM.**
- Suíte completa: **mesmas 6 falhas pré-existentes** em `tests/test_decorators_and_audit.py` (DetachedInstanceError em `User.roles` — idênticas ao baseline capturado antes das alterações). Nenhuma falha nova.

## M. Confirmação de integridade dos dados

- `PRAGMA integrity_check` = `ok`.
- Comparação tabela a tabela (atual × backup Etapa 0): **todas as tabelas financeiras IDÊNTICAS** (quotes, quote_items, orders, order_items, order_payments, purchase_orders, po_items, po_payments, financial_records, payment_receipts, clients, suppliers, companies, services, vehicles, audit_logs).
- Única diferença em `users`: `updated_at` de 3 usuários, re-gravado pelo `tests/conftest.py` (RBAC) em toda execução da suíte — comportamento pré-existente, presente também no baseline antes das alterações. Não é dado financeiro.

## N. Migrations executadas

**ZERO** — nenhuma migration criada ou aplicada (alembic head continua `b5c6d7e8f9a0`; nenhum arquivo novo em `migrations/versions/`).

## O. Dados históricos alterados

**ZERO** — nenhum SO, PO, parcela, pagamento, FinancialRecord, cliente, fornecedor ou registro financeiro foi modificado.

## P. Problemas ainda pendentes

1. **Competência custo × receita**: custo ancora em `created_at`, receita em `invoiced_at` — meses de transição podem distorcer a margem (julho). Requer definição de data de competência do custo (etapa futura).
2. **PO sem SO (R$ 13.500,00)** sai do custo direto e ainda não tem tela própria — será a Despesa Geral (Etapa 3+).
3. **UNIQUE em `reference`** (proteção contra race em POST duplo) precisa de migration — documentado para Etapa 3.
4. **27 FinancialRecords soft-deletados históricos** seguem como estão (decisão de restauração pendente).
5. **SOs concluídos sem faturamento** (7 SOs) seguem fora da receita — decisão de negócio sobre faturamento obrigatório.
6. 6 falhas RBAC pré-existentes em testes (fora do escopo financeiro).
7. SO sem parcelas (3 SOs) sem indicador de pendência operacional (etapa futura).

## Q. Recomendação para Etapa 3

1. Definir data de competência do custo direto (recomendo: faturamento/vencimento da PO, para casar com a receita).
2. Migration com guardas idempotentes: `financial_categories`, `cost_centers`, FKs em `financial_records`, UNIQUE em `reference` (pós-limpeza).
3. Classificar PO sem SO como Despesa Geral (type `expense`) com categoria + centro de custo.
4. Decidir restauração dos 27 FRs soft-deletados pagos.
5. Aposentar V4 (tabelas vazias) — decisão à parte.

**Nada foi feito da Etapa 3 nesta etapa.**

🟢 **ETAPA 2 CONCLUÍDA — DADOS HISTÓRICOS PRESERVADOS**
