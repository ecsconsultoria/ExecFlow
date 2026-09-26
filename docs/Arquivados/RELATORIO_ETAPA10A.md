# ETAPA 10A — RELATÓRIO DE AUDITORIA FINAL DO FINANCEIRO GERENCIAL (SOMENTE ANÁLISE)

**Data**: 28/08/2026 — **Modo**: 100% somente leitura. **NENHUM dado alterado.** **Commit**: ver `git log -1` (documentação).

---

## A. Arquitetura gerencial atual

Camadas consolidadas pelas etapas: **fonte de verdade** = Orders/POs/FRs com espelhos 1:1; **serviços centrais** = `margin_service` (regra única de custo válido), `dre_service` (competência), `cash_flow_service` (realizado + saldo inicial), `ar_ap_service` (obrigações), `financial_service` (ledger/void/restore). Dashboard, DRE, Caixa e AR/AP consomem esses serviços — exceto os pontos documentados em R.

## B. Receita

- **DRE e Dashboard "Receita SO"**: mesma regra (Orders faturadas por `invoiced_at`) ✅ — `dre_service.recognized_revenue` e `dashboard._so_revenue`.
- Painel Financeiro: somas de FR por `ref_date` (visão de ledger, não DRE) — rotulada; Relatórios: caixa (`paid_date`, status pago).
- Nenhum local usa parcela ou FR como fonte da DRE; nenhum uso de `paid_date` para competência de receita. ✅

## C. Custos

- **DRE**: `dre_service.direct_costs` — PO válida (fora rascunho/cancelado/excluído) vinculada a SO não excluído; competência com prioridade `service_date → delivery_date → created_at` (fallback sinalizado) ✅.
- **Dashboard "Custo PO"**: PO válida vinculada, por **`created_at`** — ⚠️ **divergência de âncora** com a DRE (documentada desde a Etapa 5; mantida por decisão da Etapa 2).
- PO sem SO: fora do custo direto (CUSTO NÃO CLASSIFICADO na DRE) ✅; PO paga/não paga: ambas podem ser custo direto por competência (regra 8B: obrigação independente do pagamento) ✅.

## D. Despesas

FR `type='expense'` não cancelada, competência `emission_date`, agrupada pelas categorias 3A (Operacionais/Administrativas/Pessoal/Impostos/Financeiras) ✅ — na DRE; **não** entra como custo direto; não duplica; canceladas fora (testado).

## E. Margem

- Margem Bruta = Receita − Custos Diretos (sem despesas) ✅ em `dre_service.gross_margin` e no template da DRE.
- Margem % = margem/receita quando receita > 0 (sem divisão por zero) ✅.
- **Três cálculos de margem coexistem**: `dre_service` (competência) · Dashboard KPI (`so_revenue − po_cost`, custo por created_at) · `Order.margin_pct` (ao vivo, receita total do SO). Números podem divergir por âncora — documentado em R.

## F. Resultado

Resultado Operacional = Margem Bruta − Despesas Gerais ✅ (independente de pagamentos/recebimentos/caixa — testado: baixa não altera DRE).

## G. DRE

Tela Financeiro → DRE com demonstração, visão mensal Jan–Dez (fetch único + bucket), detalhamento por SO/PO/despesa e pendências (não classificados/indeterminados/fallbacks) — tudo consumindo `dre_service`. Somente leitura ✅.

## H. Caixa

Realizado (`cash_flow_service`): FR pago por `paid_date` ✅. Previsto: `ar_ap_service` por `due_date` ✅. Saldo inicial via `companies.settings` (nunca inferido) ✅. Saldo realizado/projetado com fórmulas definidas na 9B ✅. Realizado e previsto nunca misturados (badges + cards separados) ✅.

## I. AR

`ar_ap_service.receivable_rows` — parcela válida não recebida, âncora `due_date`; vencido computado; recebido por `paid_date`. Única fonte para Dashboard/Painel/AR ✅ (divergência da 8A eliminada).

## J. AP

`ar_ap_service.payable_rows` — POPayment válida não paga + FR expense pendente; quebra Custos × Despesas; vencido computado; pago por `paid_date`. Única fonte ✅.

## K. Dashboard

Cards auditados: Receita SO (`invoiced_at` ✅) · Custo PO (`created_at` ⚠️) · Margem (decorrente) · Despesas Gerais (faixa por emission/paid ✅) · DRE resumida (dre_service ✅) · AR/AP (ar_ap_service ✅). **Única inconsistência restante: âncora do Custo PO.**

## L. Datas/competência — matriz (estado atual)

| Indicador | Data correta (regra) | Estado atual |
|---|---|---|
| Receita DRE | invoiced_at | ✅ |
| Custo DRE | competência operacional | ✅ (DRE) |
| Custo PO (Dashboard KPI) | competência | ⚠️ created_at |
| Despesa DRE | emission_date | ✅ |
| AR | due_date | ✅ |
| AP | due_date | ✅ |
| Caixa realizado | paid_date | ✅ |
| Caixa previsto | due_date | ✅ |

## M. Multiempresa

Todos os serviços filtram `company_id` (testado em 3A/3B/4/5/8B/9B); sem indicador que misture empresas.

## N. RBAC

Auditado, sem mudanças: `financial.manage` (mutações + catálogo + saldo inicial), `financial.view` (telas AR/AP), `reports.view`, `login_required` (painéis/caixa/DRE), `settings.manage` (reset).

## O. Performance

N+1 documentados (não otimizados): `cash_flow_service.movement_info` (1 query por movimento) e `dre_service.direct_cost_rows` (lazy `po.order`/`po.items`). Queries repetidas: receita/custo calculados por mês na visão anual com fetch único (ok). Nenhum cálculo em template (exceto formatação).

## P. Duplicação de lógica

1. **Margem em 3 lugares** (`dre_service`, Dashboard KPI, `Order.margin_pct`) — mesma intenção, âncoras diferentes.
2. **Receita/custo em 2 serviços** (`dre_service` vs `dashboard._so_revenue/_po_cost`) — receita idêntica; custo diverge na âncora.
3. Painel Financeiro mantém somas próprias de FR (ledger) — aceitável como visão de ledger, mas sem rótulo explícito em alguns cards.
4. `margin_service.recalculate_order` grava denorm (total_po_cost/margin_amount) que **nenhuma tela lê** — candidata a remoção em etapa própria.

## Q. Dependências do V4

- `dashboard/routes.py`: `ServiceOrder` apenas na lista "Próximas OS" (0 linhas — exibição vazia).
- `reports/routes.py`: `os_stats` de `ServiceOrder` (0 linhas).
- `orders/quotes/purchase_orders`: rotas `create-os` e services de OS (não usados em produção).
- **Nenhuma dependência do V4 em DRE, Caixa, AR ou AP** ✅ — a aposentadoria do V4 não afeta o financeiro gerencial.

## R. Divergências encontradas

1. **Âncora do Custo PO no Dashboard** (`created_at`) ≠ competência da DRE — única divergência material restante.
2. Rótulos do Painel Financeiro (receita/custos pagos por ref_date) podem ser lidos como competência — semântica de ledger/caixa não explícita.
3. `Order.margin_pct` calcula sobre o total do SO (não sobre reconhecida) — diferença conceitual para SO não faturado.
4. Denorm `total_po_cost/margin_amount` escrita mas não lida (débito técnico).

## S. Riscos

- Mudar a âncora do Custo PO altera números históricos do KPI (decisão de produto) — risco baixo de dados, médio de percepção.
- Unificar margens exige decidir a âncora única (competência) — impacto visual no Dashboard.
- Remover denorm exige verificar callers do `recalculate_order` (baixa/faturar) — médio.

## T. Correções recomendadas (Etapa 10B)

1. **Unificar Custo PO no Dashboard** para a competência do `dre_service` (service_date → delivery → created).
2. **Margem única**: Dashboard KPI e DRE usarem `dre_service` (mesma fonte); `Order.margin_pct` permanece como visão por SO.
3. Rotular explicitamente os cards do Painel Financeiro como "recebido/pago no período" (caixa) para eliminar ambiguidade.
4. (Futuro) remover denorm não lida + eliminar N+1.

## U. Ordem de implementação

1 → 3 (baixo risco, sem migration) → 2 (alinhamento de margem) → 4 (débito técnico).

---

## Regressão

Suíte completa: **mesmas 6 falhas pré-existentes** — nenhuma nova (Etapas 2–9B verdes).

**Nenhum dado, migration, SO, PO, pagamento, FR, AR, AP, DRE, Caixa, saldo inicial, Pronampe, FR45 ou V4 foi alterado.**

🟢 **ETAPA 10A CONCLUÍDA — FINANCEIRO GERENCIAL AUDITADO**

PARADO — aguardando autorização explícita para a implementação (Etapa 10B).
