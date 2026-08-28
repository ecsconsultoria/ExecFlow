# AUDITORIA FINANCEIRA — ExecFlow ERP (V3)

**Data**: 28/08/2026
**Escopo**: `ExecFlow_ERP/ExecFlow_ERP_V3` (Flask + SQLAlchemy + Alembic + SQLite dev / PostgreSQL prod)
**Método**: auditoria 100% somente-leitura — código lido, banco consultado com `mode=ro`. **Nenhum arquivo, modelo, rota, migration ou banco foi alterado.**
**Referências**: relatórios detalhados dos agentes de auditoria (banco/modelos, SO, PO, FinancialRecord, Dashboard) disponíveis na sessão.

---

## A. Arquitetura atual

**Stack**: Flask + Flask-SQLAlchemy + Flask-Migrate/Alembic ([ExecFlow.py](../ExecFlow.py)), servido por gunicorn (Procfile, Render). Banco: **SQLite em dev** (`sqlite:///DB_V2.db` → resolve para `instance/DB_V2.db`, que é o arquivo com dados; o `DB_V2.db` da raiz está com 0 bytes e é sobra) e **PostgreSQL em produção** via `DATABASE_URL` ([config.py:73-75](../config.py)). Boot roda `db.create_all()` + `flask db upgrade` + `_ensure_schema_columns()` (ALTER TABLE ad-hoc em runtime, [app/__init__.py:151-300](../app/__init__.py)).

**Dois sistemas financeiros coexistem — só um está vivo:**

| Sistema | Tabelas | Dados reais | Status |
|---|---|---|---|
| **Legado (VIVO)** | `orders` + `order_payments` (SO/parcelas), `purchase_orders` + `po_payments` (PO/parcelas), `financial_records` (espelho/ledger), `payment_receipts` (documento) | 40 SOs, 32 POs, 55 FRs, 7 recibos | Alimenta dashboard, painel financeiro e relatórios |
| **"V4" (MORTO)** | `service_orders` (OS), `revenue_entries`, `operation_costs`, `supplier_payments`, `financial_entries`, `accounts_receivable` | **Todas com 0 linhas** | `FinancialEntry` nunca é instanciada em nenhum lugar; `RevenueEntry` é criada mas nunca baixada/lida |

**Mapa simplificado (Tabela → finalidade → relacionamentos):**

| Tabela | Finalidade | Relacionamentos |
|---|---|---|
| `companies` | Tenant (multi-empresa) | tudo aponta para ela |
| `quotes` / `quote_items` / `quote_inclusions` | RFQ (orçamento) | Order.quote_id, PurchaseOrder.quote_id, ServiceOrder.quote_id |
| `orders` / `order_items` / `order_payments` | **Sales Order** + itens + **parcelas (contas a receber de facto)** | orders→purchase_orders; payments CASCADE |
| `purchase_orders` / `po_items` / `po_payments` | **Purchase Order** + itens + **parcelas (contas a pagar de facto)** | order_id→orders, supplier_id, quote_id, service_order_id |
| `financial_records` | **Ledger único legado** — espelho de receita/custo + lançamentos manuais | FK só companies/quotes; vínculo a SO/PO **por string** `reference` (`order_payment:N` / `po_payment:N`) |
| `payment_receipts` | Recibo imutável (documento, não lançamento), 1 por parcela | order_id, payment_id UNIQUE |
| `accounts_receivable` | Contas a receber legado (Booking) | **0 linhas** — morta |
| `service_orders` + derivados | OS operacional + financeiro V4 | **0 linhas** — morta |
| `financial_entries` | Ledger V4 ("substitui FinancialRecord" segundo docstring) | **0 linhas** — nunca instanciada |

**Modelos-chave**:
- [order.py](../app/models/order.py) (SO: `total_amount`, `usd_rate`, `discount_*`, `freight_amount`, `other_costs_*`, `emission_date`, `invoice_number`, `invoiced_at`, `total_po_cost`, `margin_amount`; status `novo/aberto/faturado/concluido/cancelado/excluido`)
- [purchase_order.py](../app/models/purchase_order.py) (PO: `amount`, `payment_terms`, `payment_due_date`, `paid_at`, `discount_*`, `freight_amount`, `invoiced_at`; status `rascunho/aberto/enviado/aprovado/em_execucao/concluido/faturado/pago/cancelado/excluido`)
- [financial.py](../app/models/financial.py) (FR: `type` revenue/cost, `category`, `amount`, `status`, `emission_date`, `due_date`, `paid_date`, `reference`, soft-delete)

**Migrações**: 14 versões, todas aplicadas (head `b5c6d7e8f9a0`). Drift real: colunas órfãs do Booking removido (`booking_id` em 3 tabelas), tabelas sem migração (só `create_all`: `po_payments`, `order_payments`, `financial_records`, etc.), colunas criadas por patch runtime. Multi-tenant por `company_id`; company 1 ("Executive Car SP") é a única com dados.

---

## B. Fluxo atual de Receita

```
RFQ → [approve] aprovado → POST /orders/create/<qid> → SO "novo" (quote→reserva_confirmada)
  → [open] "aberto" → [generate-payments] OrderPayment (parcelas = contas a receber de facto)
  → [faturar] "faturado": invoice_number, invoiced_at, invoice_due_date
              + cria FinancialRecord PENDENTE por parcela (type=revenue, receita_servico)
  → [baixa da parcela] paid_amount/paid_at na parcela + FR → "pago" (paid_date)
              + auto-conclui o SO se faturado e tudo pago
  → [receipt] PaymentReceipt (documento imutável, só SO concluído + parcela paga)
Estorno: parcela zerada + FR pago→pendente (paid_date=None; amount NÃO revertido)
```

- **Faturamento** = transição de status + campos; **não existe nota fiscal** (sem tabela/rota). A rota de faturar individual não exige parcelas ([order_service.py:191-212](../app/services/order_service.py)).
- **Receita real** = `FinancialRecord type='revenue'`, criado **no faturamento (pendente)** e **na baixa (pago)** via `_sync_order_pending_financials` / `_sync_payment_financial_record` ([order_service.py:503-570](../app/services/order_service.py)). O FR usa `emission_date = order.emission_date` — que é a **data de criação do SO**, não a de faturamento.
- **Contas a Receber**: não existe tabela funcional — o papel é das `order_payments` pendentes (R$ 3.640) + FR pendente (R$ 3.640). Consistentes entre si hoje.
- **3 definições de receita, 3 números diferentes por mês**: dashboard soma SOs por `emission_date` (qualquer status ≠ excluido); painel financeiro usa FR por `coalesce(emission_date, paid_date, created_at)` só `status='pago'`; relatórios usam FR por `paid_date` sem filtro de status. Ex.: agosto = 0 (dashboard) vs 0 (financeiro) vs **R$ 7.906** (relatórios).
- **Receita reconhecida antes do faturamento — CONFIRMADO**: `_so_revenue` ([dashboard/routes.py:85-102](../app/blueprints/dashboard/routes.py)) soma SOs `novo/aberto/cancelado` inclusive. YTD: dashboard R$ 56.977 vs FRs R$ 46.416 (42.776 pago + 3.640 pendente) → **R$ 14.201 de receita sem lançamento financeiro** (5 SOs sem parcela alguma: R$ 10.561; 2 SOs `aberto`: R$ 2.926).
- **Pagamento não muda o KPI de receita**: o dashboard lê `orders`, não FRs — baixar parcela não altera o número.

---

## C. Fluxo atual de Custos

```
PO criado de 3 formas: manual (rascunho) | a partir do SO (create_from_order / POST
/orders/<oid>/create-po — copia itens com price_cost) | create_from_service_order (NUNCA chamada)
  → [save] "aberto" → [generate-payments] POPayment (parcelas; due_date = hoje + payment_terms)
  → [faturar PO] (exige fornecedor + parcelas) "faturado" + FR PENDENTE por parcela
                 (type=cost, custo_fornecedor, emission_date = po.created_at.date())
  → [baixa] parcela paga + FR → "pago"; PO faturado→pago (service) ou →concluido (rota)
Custo NÃO tem OperationCost no fluxo PO — OperationCost só existe no fluxo OS (morto)
```

- **Vínculo com SO**: `purchase_orders.order_id → orders.id` (backref `order.purchase_orders`). Na prática: 29 de 32 POs têm `order_id`; 0 com `service_order_id`/`quote_id`. **PO pode nascer solta** (PO 9 = R$ 13.500 sem order).
- **O custo entra no Dashboard na criação do PO** — `_po_cost` soma `computed_total` de POs por `created_at`, excluindo **apenas** `excluido` e `rascunho` ([dashboard/routes.py:105-124](../app/blueprints/dashboard/routes.py)): PO `aberto` (não faturado) e PO `cancelado` contam como custo. 9 POs abertas = R$ 10.345 de custo sem nenhuma parcela/FR.
- **Conta a Pagar**: o PO gera, de facto, contas a pagar — via `po_payments` **e** via FR `pendente`. Mas o FR só nasce no **faturamento**: PO aberta com parcela gerada fica **invisível no painel de Contas a Pagar** (PO 16: parcela de R$ 2.950 vencida em 20/07, sem FR).
- **Baixa**: `pos.baixa()` atualiza parcela + FR + avança status. Bug: a rota força `concluido` em PO `aberto` quando quitada (PO 15 concluído sem nunca faturar, [purchase_orders/routes.py:752-755](../app/blueprints/purchase_orders/routes.py)).
- **Margem por SO**: `margin_service.calculate_order_margin` grava `orders.total_po_cost/margin_amount` (denormalizado) **incluindo PO `rascunho`** e **não exibido em template nenhum** — está obsoleto (order 30 guarda custo 5.900, PO atual = 2.950).

---

## D. Fluxo atual de Contas a Pagar

**Não existe tabela "conta a pagar". Duas fontes divergentes:**

| Fonte | Código | Valor | Filtros |
|---|---|---|---|
| Dashboard "Pagamentos Pendentes" | [dashboard/routes.py:257-262](../app/blueprints/dashboard/routes.py) | **R$ 16.150** (3 parcelas) | `po_payments.paid_at IS NULL` |
| Painel financeiro "A Pagar" | [financial/routes.py:622-624](../app/blueprints/financial/routes.py) | **R$ 13.400** (3 FRs) | FR `type=cost`, `pendente` |

Diferença de R$ 2.750 = PO 16 (parcela 2.950 sem FR, pois nunca faturou) − FR manual id 45 (200, sem parcela). Ou seja: **o painel está incompleto** e as duas telas têm semânticas diferentes de vencido (contagem de parcelas vs soma de FRs).

- Caminhos de baixa concorrentes: `purchase_order_service.baixa()` (atômico, correto) vs `financial/routes.baixa_record` (commit do FR primeiro, sincronização best-effort — risco de divergência parcial).
- **Exclusão/cancelamento de PO soft-deleta TODOS os FRs das parcelas, inclusive os pagos** (`void_payment_financial_records`, [financial_service.py:22-41](../app/services/financial_service.py)): 14 parcelas de PO pagas somam R$ 45.530, mas só R$ 28.480 existem como FR de custo pago — **R$ 17.050 de custo pago sumiu do livro**.
- "Conta paga ainda aparecendo como aberta": **não encontrado** no painel (filtro por `paid_at` está correto). O problema real é o inverso — pagamento existente sem lançamento contábil (FR soft-deletado).

---

## E. Fluxo atual de Contas a Receber

- `AccountReceivable` é legado e **vazia** (0 linhas). AR de facto = `order_payments` pendentes + FR `revenue` pendente — **ambos R$ 3.640 hoje, consistentes** (1 parcela `order_payment:36`, vencida 10/08).
- Dashboard "Recebimentos Pendentes" ([dashboard/routes.py:247-254](../app/blueprints/dashboard/routes.py)) = painel "A Receber" ([financial/routes.py:778-780](../app/blueprints/financial/routes.py)) ✅.
- Bug de UI: os cards "A Receber/A Pagar" do painel financeiro **ignoram o filtro de período** ([financial/routes.py:166-179](../app/blueprints/financial/routes.py)).
- Baixa = `order_service.baixa()` (parcela + FR no mesmo commit — atômico e correto); auto-conclui o SO.
- **Perda de caixa real**: 16 SOs excluídos têm 17 parcelas pagas totalizando **R$ 187.300** — os FRs correspondentes foram soft-deletados na exclusão; o dinheiro recebido só existe na tabela `order_payments` e **não aparece em nenhum relatório**.

---

## F. FinancialRecord

- **Modelo**: [financial.py:16-36](../app/models/financial.py) — `company_id`, `quote_id` (nunca preenchido), `type` (revenue/cost — **string livre, sem validação server-side**), `category` (receita_servico, custo_fornecedor, custo_operacional em uso), `amount`, `status` (pendente/aprovado/pago/parcial/cancelado/vencido — só pago/pendente em uso; `vencido` nunca é setado por código), `emission_date`, `due_date`, `paid_date`, `payment_method`, `reference` (chave de dedup **de facto**, não é UNIQUE), `notes`, `deleted_at` (soft-delete).
- **Relacionamentos**: apenas FK `companies` e `quote_id`; **não há FK para Order/PO/Client/Supplier** — o vínculo é a string `reference`.
- **Quem cria / quando** (8 call sites): faturamento de SO (FR pendente por parcela), baixa de parcela SO (FR pago), faturamento/baixa de PO (idem, `type=cost`), lançamento manual no painel (`/financial/record/new`, sem reference), e testes.
- **Quem atualiza**: re-baixa (idempotente), sync de pendentes, estorno (pago→pendente, **amount não revertido**), edição manual (**sem guarda** — pode corromper type/amount/reference de espelhos), baixa pelo painel (permite valor ≠ parcela), cancelamento (→cancelado) e void (soft-delete).
- **O que representa**: ledger único — receita (espelho de AR), custo (espelho de AP) e despesa manual. Híbrido caixa/competência.
- **Duplicidade**: 0 duplicatas por `reference` hoje ✅ — mas a proteção é só o padrão query→update→insert (race em POST duplo), há **lag** (parcela criada após faturamento fica sem FR até a próxima baixa) e a edição manual pode quebrar o espelho.

---

## G. Dashboard

| Métrica | Fórmula atual (código) | Dados reais | Problema |
|---|---|---|---|
| **Receita SO** | Σ `Order.computed_total`, status ≠ `excluido`, por `emission_date` (fallback created_at) | YTD R$ 56.977 · jul R$ 19.471 · **ago R$ 0** | Inclui SO `novo/aberto/cancelado` — receita antes do faturamento; difere dos FRs em R$ 14.201 |
| **Custo PO** | Σ `PO.computed_total`, status ∉ {excluido, rascunho}, por `created_at` | YTD R$ 53.475 · jul R$ 14.595 | Inclui PO `aberto` (não faturado) e `cancelado`; PO de SO excluída conta sem receita pareada |
| **Margem R$ / %** | `so_revenue − po_cost`; % = margem/receita (div por 0 tratada) | jul +R$ 4.876 (25%) · YTD +R$ 3.502 (6,1%) · jun **−62%** | **Soma não pareada** (receita por emissão × custo por criação) — junho negativo é artefato da fórmula, não do negócio |
| **Receitas / Despesas** (painel) | Σ FR `pago` por `coalesce(emission_date, paid_date, created_at)` | Receita 42.776 · Custo 28.480 · "Margem" 14.296 | FR manual sem `emission_date` cai no created_at; diverge dos relatórios (paid_date) |
| **Contas a Pagar** | dashboard: Σ `po_payments` pendentes (**16.150**) / painel: Σ FR cost pendente (**13.400**) | — | **Duas verdades** — PO 16 (2.950) invisível no painel |
| **Contas a Receber** | dashboard = painel = R$ 3.640 | — | Consistentes ✅; card ignora período |
| **Fluxo de Caixa** | **NÃO EXISTE** em lugar nenhum | — | Nada computa entradas−saídas por data de pagamento |
| Bônus: funil | `conversion_rate = 17/5 = 340%` | — | Bug: numerador histórico, denominador 30 dias; funil usa `total_amount` (ignora desconto) |

---

## H. Problemas encontrados

1. **Pagamento de SO não atualiza receita** — CONFIRMADO, em dois sentidos: (a) o KPI de receita do dashboard lê `orders`, não pagamentos — baixar parcela não muda o número; (b) `RevenueEntry`/`ServiceOrder.revenue_amount` (V4) nunca são atualizados por nada.
2. **Baixa não atualiza Dashboard** — CONFIRMADO: `_so_revenue`/`_po_cost` não leem FRs; baixar parcela só muda o painel financeiro.
3. **Duplicidade financeira** — hoje **0 duplicatas por `reference`**, mas riscos reais: sem UNIQUE (race), lag de espelho pós-geração de parcelas, edição manual sem guarda, e duplicação **por design** no fluxo OS morto (mesma despesa vira `SupplierPayment` + `OperationCost`).
4. **PO contabilizado mais de uma vez** — não duplica dentro de um mesmo painel, mas o mesmo custo aparece em dois mundos com valores diferentes (dashboard soma POs; financeiro soma FRs por parcela) e a margem denormalizada (`orders.total_po_cost`) está obsoleta.
5. **Receita reconhecida antes do faturamento** — CONFIRMADO (R$ 14.201 YTD sem lançamento; inclui SOs `novo/aberto`).
6. **Custos como despesas gerais** — FR manual sem vínculo misturado no mesmo painel; PO aberto conta como custo; PO solta (R$ 13.500) entra na margem agregada sem SO pareado.
7. **Despesas sem vínculo com SO** — SIM: PO solta, FR manual (1 registro) e todo o fluxo OS (morto) permitem.
8. **Contas pagas ainda abertas** — não confirmado no painel AP; o grave é o inverso: **pagamentos existentes sem lançamento contábil** (R$ 187.300 de receita e R$ 17.050 de custo soft-deletados com as ordens) e PO concluído sem fatura.
9. Extras: conversão de funil 340%; relatórios vs financeiro divergem por data/status; cards sem filtro de período; "Previsto" sempre 0 para ordens faturadas; margem por SO inclui PO rascunho; `_ensure_schema_columns` faz DDL em runtime em todo boot; V4 inteiro é risco latente de duplicidade.

---

## I. O que deve ser preservado

1. **Padrão espelho parcela↔FR com `reference`** (`order_payment:N` / `po_payment:N`) — é a base certa; só precisa de UNIQUE + reconciliação.
2. **Fluxo atômico de baixa** via services (`order_service.baixa` / `purchase_order_service.baixa`) — commit único parcela+FR; usar como referência e unificar.
3. Máquinas de status de SO/PO (faturado, pago, concluído), auto-conclusão do SO, estorno.
4. `PaymentReceipt` imutável com numeração única (documento separado de lançamento — conceito correto).
5. Numeração única (SO/PO/RFQ/REC), multi-tenant `company_id`, SoftDeleteMixin, auditoria (`audit_logs`, rastreamento `*_by`).
6. `payment_terms` gerando parcelas com vencimento.
7. Seed existente de categorias de despesa (`category_type` em `vehicle_categories` — migração a2b3c4d5e6f7 já criou 12 categorias) — reaproveitável para as categorias financeiras.
8. Testes existentes (atenção: há 6 testes RBAC falhando pré-existentes na base — não confundir com regressão).

---

## J. O que precisa ser alterado

1. **Definição única de reconhecimento** de receita e custo (regra + data) aplicada igualmente em dashboard, painel financeiro e relatórios (hoje são 3 critérios).
2. **Filtros de status do dashboard**: receita não pode incluir `novo/aberto/cancelado`; custo não pode incluir `aberto/cancelado`; parear SO↔PO na margem; corrigir `margin_service` (rascunho fora) e sincronizá-lo com o dashboard.
3. **Contas a Pagar com fonte única** (parcela ↔ FR sempre sincronizados, inclusive PO não faturada) e cards respeitando o período.
4. **Categorias financeiras + Centros de custo** (novas tabelas, seções 8–9 abaixo).
5. **Vínculo/classificação obrigatória**: custo direto = PO vinculado a SO; despesa geral = FR manual com categoria + centro de custo (sem SO, por design).
6. **Proteções de integridade**: UNIQUE em `reference` (com limpeza prévia), bloquear edição manual de espelhos, `void_payment_financial_records` **não apagar FRs pagos** (exigir estorno), regeneração de parcelas reconciliando FRs pendentes, unificar o caminho não-atômico `baixa_record`.
7. **Decidir o destino do V4**: adotar de verdade ou aposentar (hoje é só risco latente de duplicidade — `RevenueEntry` órfã).
8. **Corrigir bugs**: funil 340%, `total_amount` vs `computed_total`, "Previsto", relatórios por `paid_date` sem status.
9. **Fluxo de caixa** (novo — hoje inexistente).
10. **Reconciliação histórica** (decisão de negócio): FRs pagos soft-deletados, espelhos de custo ausentes, denormalização obsoleta.

---

## K. Proposta de nova arquitetura

A separação desejada **é compatível com o legado atual** — a mudança é mais de regra e organização do que de reescrita:

**Receita de serviços** (`SO → Faturamento → Receita → AR`): o fluxo já existe quase inteiro (faturamento cria FR pendente; baixa cria FR pago). Faltam: regra única de reconhecimento (recomendo **competência por faturamento** para receita/custo, com visão de caixa por `paid_date` em tela separada), remover o reconhecimento prematuro do dashboard, e tratar `invoice_number/invoiced_at` como o evento contábil.

**Custo direto** (`PO → Custo → AP`): já existe via `order_id` + parcelas + FR `custo_fornecedor`. Faltam: exigir vínculo (ou classificar explicitamente PO solta), nascer o FR de AP no vencimento (não só no faturamento), e impedir exclusão de ordens que apaguem lançamentos pagos.

**Despesas gerais** (`Despesa → Categoria → Centro de Custo → AP`): a rota de lançamento manual já existe (`/financial/record/new`). Faltam apenas as duas dimensões (categoria estruturada + centro de custo) e um `type` distinto de custo direto (ex.: `expense`).

**Decisão estrutural recomendada**: manter `FinancialRecord` como **ledger único** (evita migração de dados — as tabelas V4 estão vazias), adicionar por migração `category_id` → `financial_categories`, `cost_center_id` → `cost_centers`, UNIQUE em `reference`, e declarar V4 (`financial_entries`, `revenue_entries`, `operation_costs`, `supplier_payments`, `service_orders`+) como **deprecated** para remoção futura (ou removê-las por migração quando seguro — lembre-se de que `create_all` nunca dropa).

---

## L. Riscos de migração

1. **Histórico muda de número**: aplicar a regra correta de reconhecimento vai reescrever os KPIs passados (a margem YTD de R$ 3.502 é provavelmente otimista — pareamento real deve piorá-la). Requer decisão de corte (recalcular tudo ou só dali em diante).
2. **Dados órfãos de hoje**: R$ 187.300 de receita paga e R$ 17.050 de custo pago existem só nas parcelas — decidir se restauram os FRs (recomendado) antes de qualquer soma nova.
3. **SQLite dev × PostgreSQL prod**: migrações testadas em SQLite precisam validação no Postgres (tipos, índices, UNIQUE parcial). O padrão de guardas idempotentes do projeto deve ser mantido.
4. **V4 latente**: enquanto `service_order_service` existir, qualquer uso futuro da OS duplicará receita/custo (`RevenueEntry` órfã + `SupplierPayment`/`OperationCost` duplos). Aposentar antes de evoluir.
5. **Duplo caminho de baixa** (painel financeiro não-atômico) pode divergir parcela↔FR durante a transição — unificar primeiro.
6. **Drift de schema existente** (colunas órfãs `booking_id`, tabelas sem migração, ALTERs runtime) — qualquer nova migração precisa conviver com isso.
7. **`reference` duplicável**: criar UNIQUE exige limpeza prévia e teste de concorrência.
8. **Backup obrigatório antes de qualquer etapa** (seção 11) — sem ele, nenhuma etapa começa.

---

## M. Plano de implementação por etapas (NÃO iniciar sem autorização)

| Etapa | Conteúdo | Risco |
|---|---|---|
| **0 — Backup & checkpoint** | Backup do banco (dev: SQLite; prod: PostgreSQL), zip/bundle do código, commit + tag no Git, registro de versão, procedimento de restauração documentado (detalhes na seção 11) | Nenhum |
| **1 — Decisões de negócio** | Definir: regra de reconhecimento (competência por faturamento vs caixa), destino do V4, categorias/centros de custo, restauração ou não dos FRs soft-deletados pagos | Nenhum (reunião) |
| **2 — Correções sem migração** | Filtros de status do dashboard, pareamento SO↔PO, funil, cards com período, previsto, relatórios | Baixo — só leitura/consulta |
| **3 — Schema** | Migrações novas (com guardas): `financial_categories`, `cost_centers`, FKs em `financial_records`, UNIQUE em `reference` (pós-limpeza), índices | Médio |
| **4 — Backfill/reconciliação** | Script idempotente (com revisão manual): categorizar os 28 FRs ativos, restaurar espelhos pagos ausentes (conforme decisão), corrigir `total_po_cost/margin_amount`, categorizar/ligar POs | Médio — dados históricos |
| **5 — Consolidar AP/AR + fluxo de caixa** | Fonte única de AP/AR, `baixa_record` atômico, tela de fluxo de caixa (entradas−saídas por `paid_date`) | Médio |
| **6 — Aposentar V4 + DRE** | Remover/desativar tabelas V4 mortas; DRE por categoria + centro de custo (seções 8–10) | Médio/Baixo |

### Seções 8–10 (avaliação, sem implementar)

- **Categorias financeiras**: criar tabela `financial_categories` com os 7 grupos sugeridos (Custos Diretos, Despesas Operacionais, Despesas Administrativas, Pessoal, Impostos, Despesas Financeiras, Outras Despesas), mapeando as categorias legadas (`custo_fornecedor` → Custos Diretos, `custo_operacional` → Desp. Operacionais, `imposto` → Impostos, `outro` → Outras). O seed existente em `vehicle_categories` (12 categorias de despesa) pode ser migrado para cá.
- **Centros de custo**: tabela `cost_centers` com Operação, Frota, Administrativo, Comercial, Marketing, Tecnologia, Financeiro — FK opcional em `financial_records` e em `purchase_orders`; default "Operação" para custos vinculados a SO.
- **DRE**: viável futuramente como agregação por período sobre o ledger único — Receita Bruta = Σ FR revenue; Impostos = Σ categoria Impostos (hoje **não existe** lançamento de imposto sobre receita — precisará ser lançado como FR próprio); Custos Diretos = Σ custos de POs vinculadas a SOs; Lucro Bruto; Despesas por categoria; Resultado. **Não implementar agora.**

### 11. Backup — como será feito na próxima etapa (nada feito agora)

1. **Banco** — Dev (SQLite): com o app parado (ou após `PRAGMA wal_checkpoint(TRUNCATE)`), executar `sqlite3 instance/DB_V2.db ".backup backup/DB_V2_pre-financeiro-YYYYMMDD.db"` (usa a API Online Backup do SQLite — segura mesmo com WAL ativo) e guardar também os arquivos `-wal`/`-shm`. Prod (PostgreSQL Render): dump via `pg_dump -Fc` (ou botão de download de DB do Render), armazenado fora do servidor.
2. **Código**: `git bundle create execflow_v3_pre-financeiro.bundle --all` + cópia zip do diretório (excluindo `__pycache__`, `htmlcov`, `.venv`).
3. **Git**: commit limpo na branch `v3` + tag `v3-pre-financeiro-<data>` (sem push automático — seguir o fluxo normal de deploy).
4. **Identificação de versão**: arquivo `BACKUP_INFO.md` com commit hash, tag, alembic head (`b5c6d7e8f9a0`), data/hora e SHA-256 dos backups.
5. **Restauração**: Dev — parar app, substituir `DB_V2.db` pela cópia, apagar `-wal/-shm`, reiniciar. Prod — `pg_restore --clean --if-exists` no banco alvo. **Validar o procedimento restaurando em ambiente de teste antes de iniciar a Etapa 1.**

---

## Resumo executivo

O sistema tem uma **base financeira legada funcional e auditável** (parcelas + espelho `FinancialRecord`), mas com:

1. Reconhecimento prematuro de receita/custo no dashboard;
2. Três definições diferentes de receita entre telas;
3. Lançamentos pagos que somem ao excluir ordens (R$ 187.300 receita + R$ 17.050 custo);
4. Contas a Pagar com duas verdades (dashboard vs painel);
5. Ausência total de fluxo de caixa;
6. Um subsistema "V4" completo porém morto, que é risco latente de duplicidade.

A arquitetura proposta (Receita de Serviços / Custo Direto / Despesas Gerais com categorias e centros de custo) **se encaixa no legado com migrações incrementais**, sem reescrever o ledger.

**Nada foi alterado nesta auditoria.**
