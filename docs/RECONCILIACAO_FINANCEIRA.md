# RECONCILIAÇÃO FINANCEIRA — ExecFlow ERP (Etapa 1)

**Data**: 28/08/2026 — **Modo**: 100% somente leitura (SELECTs `mode=ro`; nenhum INSERT/UPDATE/DELETE/ALTER/migration/backfill executado).
**Checkpoint**: branch `v3`, HEAD `dcee012`, tag `v3-pre-financeiro-20260828` (d9cff09), working tree limpo, alembic head `b5c6d7e8f9a0`.

---

## A. Estado atual

| Item | Valor |
|---|---|
| Branch / commit | `v3` / `dcee012` (apenas ajuste documental do BACKUP_INFO.md sobre a tag `v3-pre-financeiro-20260828`) |
| Working tree | limpo — nenhuma alteração desde a Etapa 0 além da documentada |
| Alembic head | `b5c6d7e8f9a0` (banco e migrations) |
| Banco | SQLite `instance/DB_V2.db` (dev); produção PostgreSQL sem acesso local |
| Integridade | `PRAGMA integrity_check` = ok |
| Empresas | 2 (company 1 "Executive Car SP" é a única com dados) |

## B. SOs existentes (40)

| Status | Qtd | Soma `total_amount` |
|---|---|---|
| excluido | 23 | R$ 189.600,00 |
| concluido | 14 | R$ 50.961,00 |
| aberto | 2 | R$ 2.926,00 |
| faturado | 1 | R$ 3.640,00 |

- Parcelas (`order_payments`): 35, somando R$ 235.916,00; **31 pagas** (R$ 230.076,00), 4 em aberto.
- 17 SOs ativos (não excluídos); 7 SOs `concluido` **sem `invoiced_at`** (nunca faturaram); 3 SOs `concluido` **sem parcelas** (SO-260630-001, SO-260703-001, SO-260703-002 — R$ 7.635,00).

## C. POs existentes (32)

| Status | Qtd | Observação |
|---|---|---|
| aberto | 10 | custos em `po_items` (campo `amount` = 0 na maioria) |
| excluido | 9 | R$ 21.650,00 |
| pago | 7 | R$ 20.700,00 |
| rascunho | 4 | — |
| faturado | 1 | R$ 13.200,00 (PO-260615-003) |
| concluido | 1 | PO-260630-001 (sem `invoiced_at`) |

- Parcelas (`po_payments`): 21, somando R$ 74.330,00; **14 pagas** (R$ 45.530,00).
- 29 POs vinculadas a SO (`order_id`); 1 PO paga sem SO (PO-260602-005, R$ 13.500,00); 0 com `service_order_id`.

## D. Contas a Receber (35 parcelas × FinancialRecords)

| Situação | Qtd | Valor pago | Detalhe |
|---|---|---|---|
| **Correto** (FR ativo consistente) | 15 | R$ 46.416,00 (14 pagas 42.776 + 1 pendente 3.640) | espelho 1:1 sem divergência |
| **FR soft-deletado** — SO excluído | 20 | R$ 187.300,00 pagos + R$ 2.200,00 pendentes | todos os FRs existiam e foram soft-deletados junto com o SO |
| FR ausente | 0 | — | nenhuma parcela de AR sem FR |
| Duplicidade ativa | 0 | — | nenhuma |

Lista individual (parcela → SO → cliente → FR → situação) gerada no script de reconciliação (33 linhas verificadas uma a uma); todas as classificações acima vêm dela. Exemplos de inconsistência histórica em FRs deletados: FR id5 (`order_payment:3`) com status `pendente` porém `paid_date` preenchido; FR id8 (`order_payment:4`) com `paid_date` 29/05 e parcela paga em 02/06; FR id12 (`order_payment:7`) com `due_date` NULL.

## E. Contas a Pagar (21 parcelas × FinancialRecords)

| Situação | Qtd | Valor | Detalhe |
|---|---|---|---|
| **Correto** (FR ativo consistente) | 12 | pagos 28.480 + pendentes 13.200 | 10 pagas + 2 pendentes (PO-260615-003) |
| **FR ausente** | 3 | 7.000 + 2.500 + 2.950 | POs **nunca faturadas**: PO-260602-001 (excluída, parcelas não pagas) e PO-260716-001 (aberta, parcela 2.950 vencida em 20/07) — FR só nasce no faturamento |
| **FR soft-deletado** | 6 | 17.050 pagos + 3.150 pendentes | POs excluídas junto com seus SOs |
| Duplicidade ativa | 0 | — | nenhuma |

## F. FinancialRecords (55 = 28 ativos + 27 soft-deletados)

| Grupo (por `reference`) | Ativos | Soft-deletados |
|---|---|---|
| Receita de serviço (`order_payment:N`) | 15 — R$ 46.416,00 (14 pago + 1 pendente) | 21 — R$ 198.250,00 (16 pago 173.800 + 5 pendente 24.450) |
| Custo direto (`po_payment:N`) | 12 — R$ 41.680,00 (10 pago 28.480 + 2 pendente 13.200) | 6 — R$ 20.200,00 (4 pago 17.050 + 2 pendente 3.150) |
| Lançamento manual (sem reference) | 1 — R$ 200,00 pendente (custo_operacional) | 0 |
| Outros | 0 | 0 |

## G. Pagamentos sem FinancialRecord

3 parcelas de **PO** (todas **não pagas** e de POs **nunca faturadas**): `po_payment:5` (7.000), `po_payment:6` (2.500) — PO-260602-001 excluída; `po_payment:18` (2.950) — PO-260716-001 aberta, vencida. Nenhuma parcela de SO sem FR. **Causa (lógica)**: FR de AP só é criado em `faturar()`/`baixa()`; parcela gerada em PO não faturada fica invisível no ledger.

## H. FinancialRecords sem pagamento

Nenhum **ativo**. 1 caso histórico: FR id34 (`order_payment:22`, pendente 8.750, soft-deletado) — a parcela 22 não existe mais (parcelas de SO-260603-001 foram regeneradas; a parcela 2 atual é a 25, com FR ativo id37). Ou seja: **dupla geração histórica**, sem impacto no ledger atual.

## I. R$ 187.300 investigados (individualmente)

**17 parcelas pagas de 16 SOs `excluido`**, total exato **R$ 187.300,00**. Para cada uma: o FR correspondente **existe e está soft-deletado** (16 `pago` + 1 `pendente`-com-`paid_date` — FR id5). **Nenhum FR foi perdido fisicamente — todos foram apagados logicamente** pela rota de exclusão do SO → `void_payment_financial_records` ([financial_service.py:22-41](../app/services/financial_service.py)) → `soft_delete()` sem distinguir status pago de pendente.

| Origem | Valor | Data pago | FR | Situação | Ação recomendada |
|---|---|---|---|---|---|
| 17 parcelas (SO-260601-001 a SO-260602-017) | 187.300,00 | 29/05 a 03/06 | 17 FRs deletados | pago permanece em `order_payments`; ledger apagado | **NÃO restaurar agora.** Decisão de negócio futura (restaurar FRs pagos é tecnicamente simples — upsert por `reference`) |

Observação: excluir SO pago também deveria exigir estorno — a lógica atual não exige.

## J. R$ 17.050 investigados (individualmente)

**4 parcelas pagas de 3 POs `excluido`**, total exato **R$ 17.050,00**: PO-260601-002 (550, 01/06), PO-260601-004 (7.000, 01/06), PO-260602-004 (7.000 + 2.500, 29/05 e 01/06). FRs existem e estão soft-deletados (exclusão da PO/SO). Parcelas seguem pagas em `po_payments` (14 pagas = 45.530) enquanto o ledger ativo registra só 28.480 de custo pago.

## K. SO × PO (17 SOs ativos — visão analítica)

| SO | Status | Valor SO | Recebido | POs vinculadas (status, custo) | Custo (regra serviço) | Margem (regra serviço) | Margem (regra dashboard) |
|---|---|---|---|---|---|---|---|
| SO-260602-003 | concluido | 900,00 | 900,00 | excluída 900; paga 550 | 550,00 | +350,00 | +350,00 |
| SO-260602-018 | concluido | 13.500,00 | 13.500,00 | excluída 9.500; paga 9.500 | 9.500,00 | +4.000,00 | +4.000,00 |
| SO-260603-001 | concluido* | 17.500,00 | 17.500,00 | faturada 13.200 (pendente) | 13.200,00 | +4.300,00 | +4.300,00 |
| SO-260603-003 | concluido | 1.100,00 | 1.100,00 | paga 800 | 800,00 | +300,00 | +300,00 |
| SO-260630-001 | concluido* | 2.735,00 | **0,00** | concluída 1.275 (paga) | 1.275,00 | +1.460,00 | +1.460,00 |
| SO-260703-001 | concluido* | 3.300,00 | **0,00** | nenhuma | 0,00 | +3.300,00 | +3.300,00 |
| SO-260703-002 | concluido* | 1.600,00 | **0,00** | nenhuma | 0,00 | +1.600,00 | +1.600,00 |
| SO-260703-003 | concluido | 1.771,00 | 1.771,00 | excluída 1.025; aberta 1.025; **rascunho 1.025** | 2.050,00 | **−279,00** | +746,00 |
| SO-260706-001 | concluido | 3.355,00 | 3.355,00 | aberta 2.950; **rascunho 2.950** | 5.900,00 | **−2.545,00** | +405,00 |
| SO-260720-001 | concluido* | 750,00 | 750,00 | nenhuma | 0,00 | +750,00 | +750,00 |
| SO-260720-002 | concluido* | 1.120,00 | 1.120,00 | nenhuma | 0,00 | +1.120,00 | +1.120,00 |
| SO-260729-001 | concluido | 700,00 | 700,00 | aberta 500 | 500,00 | +200,00 | +200,00 |
| SO-260729-002 | faturado | 3.640,00 | 0,00 | aberta 2.800 | 2.800,00 | +840,00 | +840,00 |
| SO-260729-003 | aberto | 2.156,00 | 0,00 | aberta 1.400 | 1.400,00 | +756,00 | +756,00 |
| SO-260729-004 | aberto | 770,00 | 0,00 | 2 abertas 500+500 | 1.000,00 | **−230,00** | −230,00 |
| SO-260729-005 | concluido* | 1.100,00 | 1.100,00 | 2 abertas 710+710 | 1.420,00 | **−320,00** | −320,00 |
| SO-260729-006 | concluido | 980,00 | 980,00 | aberta 700; paga 700; paga 2.100; **rascunho 700** | 4.200,00 | **−3.220,00** | **−2.520,00** |

\* concluído sem faturamento (`invoiced_at` NULL).

Achados: (1) 3 SOs concluídos sem recebimento e 2 sem parcelas; (2) margens negativas reais em 4 SOs; (3) possíveis POs duplicadas (aberta+rascunho do mesmo valor: SO-260703-003, SO-260706-001, SO-260729-006); (4) 7 SOs concluídos sem fatura.

## L. Margens (armazenada × recalculada)

Campos `orders.total_po_cost` / `margin_amount` são denormalizações gravadas por `margin_service.calculate_order_margin` (exclui `cancelado`/`excluido`, **inclui `rascunho`**).

| SO | Valor SO | Custo armazenado | Custo recalculado | Margem armazenada | Margem calculada | Diferença |
|---|---|---|---|---|---|---|
| SO-260601-003 (excluido) | 13.500,00 | 9.500,00 | 0,00 (POs excluídas) | +4.000,00 | +13.500,00 | +9.500,00 |
| SO-260615-001 (excluido) | 1.100,00 | 1.360,00 | 0,00 (POs excluídas) | −260,00 | +1.100,00 | +1.360,00 |

Apenas 2 divergências — ambas em SOs excluídos (POs vinculadas foram excluídas depois do último recálculo). Para os 17 SOs ativos, o armazenado **bate com a regra do serviço** (por isso rascunho entra no custo denormalizado, mas não no dashboard — duas regras convivendo: −279 vs +746, −2.545 vs +405, −3.220 vs −2.520).

## M. Receita (modelo atual × recomendado)

| Período | Atual (emissão, ≠excluido) | Recomendado A (só `faturado`, por `invoiced_at`) | Recomendado B (`faturado`+`concluido`) |
|---|---|---|---|
| mai/2026 | 13.500,00 | 0,00 | 0,00 |
| jun/2026 | 24.006,00 | 0,00 | 35.735,00 |
| jul/2026 | 19.471,00 | 0,00 | 9.641,00 |
| ago/2026 | 0,00 | 3.640,00 | 8.675,00 |
| **Total** | **56.977,00** | **3.640,00** | **54.051,00** |

- Modelo atual inclui SOs `aberto` e `concluido` sem fatura; R$ 10.561,00 (2 abertos 2.926 + 3 concluídos sem parcelas 7.635) nunca tiveram lançamento contábil.
- Recomendado A é excessivamente restritivo (só 1 SO está `faturado` — os demais foram fechados por bulk sem marcar fatura).
- Recomendado B ainda inclui 7 SOs concluídos sem fatura (R$ 28.105,00). Regra final depende da decisão de negócio (faturamento obrigatório?).

## N. Custos (modelo atual × recomendado)

| Período | Atual (criação, ≠excluido/rascunho) | Recomendado (faturado/pago/concluido + SO ativo) |
|---|---|---|
| mai/2026 | 0,00 | 0,00 |
| jun/2026 | 38.880,00 | 25.325,00 |
| jul/2026 | 14.595,00 | 2.800,00 |
| ago/2026 | 0,00 | 0,00 |
| **Total** | **53.475,00** | **28.125,00** |

Modelo atual inclui POs `aberto` (R$ 10.345,00 não faturadas) e PO de SO excluído. Recomendado exclui a PO paga sem SO (PO-260602-005, R$ 13.500,00) — que não é "custo direto do serviço", e sim **despesa geral** (futuro grupo próprio).

## O. Problemas de lógica encontrados

1. Receita do dashboard inclui SO `novo/aberto/cancelado` — reconhecimento antes do faturamento ([dashboard/routes.py:85-102](../app/blueprints/dashboard/routes.py)).
2. Custo do dashboard inclui PO `aberto` e `cancelado` (exclui só `excluido`/`rascunho`) ([dashboard/routes.py:105-124](../app/blueprints/dashboard/routes.py)).
3. Duas regras de custo por SO: `margin_service` inclui `rascunho`; dashboard exclui — margem do detalhe ≠ margem agregada.
4. Três definições de receita (dashboard por `emission_date`; financeiro por `coalesce(emission,paid,created)`; relatórios por `paid_date` sem filtro de status).
5. Exclusão de SO/PO soft-deleta FRs **pagos** (`void_payment_financial_records` sem distinção de status) — causa dos R$ 187.300 + R$ 17.050.
6. FR de AP só nasce no faturamento — parcela de PO não faturada fica fora do ledger (PO-260716-001).
7. Dois caminhos de baixa (service atômico × `baixa_record` não-atômico com commit em dois tempos).
8. Rota de baixa de PO força `concluido` em PO `aberto` sem fatura (PO-260630-001; PO-260729-009/010).
9. Faturamento do SO não é obrigatório: `fechar()` permite `aberto→concluido` sem parcelas/fatura (7 SOs; 3 sem parcelas).
10. Funil: conversão 340% (numerador histórico, denominador 30 dias); usa `total_amount` (ignora desconto).
11. Cards "A Receber/A Pagar" ignoram o filtro de período; "Previsto" zerado para ordens faturadas.
12. Estorno reverte status/data do FR mas **não** o `amount`; regeneração de parcelas pode deixar FR pendente órfão (caso id34).
13. Edição manual do painel pode alterar `type`/`amount`/`reference` de espelhos sem guarda.
14. Receita por `emission_date` × custo por `created_at` — mismatch de competência (artefato de margem negativa em junho).

## P. Problemas de integridade encontrados (dados como estão — NÃO corrigidos)

1. FR id5 (`order_payment:3`, deletado): status `pendente` com `paid_date` 29/05 preenchido.
2. FR id8 (`order_payment:4`, deletado): `paid_date` 29/05, parcela paga em 02/06 (data anterior ao pagamento).
3. FR id12 (`order_payment:7`, deletado): `due_date` NULL.
4. FR id28 (`po_payment:10`, ativo): `emission_date` (02/06) **posterior** a `paid_date` (29/05) — pagamento antes da emissão.
5. FR id35 (`po_payment:14`, ativo): `emission_date` (15/06) posterior a `paid_date` (02/06).
6. FR id34 (`order_payment:22`, deletado): órfão de parcela regenerada.
7. 3 parcelas AP sem FR (POs não faturadas).
8. 27 FRs soft-deletados (R$ 218.450,00) enquanto as parcelas correspondentes permanecem no sistema.
9. `quotes.payment_status` NULL em 100% dos registros (campos de pagamento da RFQ nunca gravados).
10. Denormalização defasada em 2 SOs excluídos (total_po_cost/margin_amount).

## Q. Dados corretos e que devem ser preservados

- **Todos os 40 SOs e 32 POs** com itens, valores, descontos, datas, status e vínculos (regra absoluta desta etapa).
- **Todas as 35+21 parcelas** e seus pagamentos (31 recebimentos R$ 230.076,00 + 14 pagamentos R$ 45.530,00).
- **28 FinancialRecords ativos** (R$ 88.496,00): 15 de receita + 12 de custo + 1 manual — 27 pares parcela↔FR verificados como **corretos** (valor e status batem 1:1).
- Padrão de dedup por `reference` (0 duplicatas ativas), numeração única, recibos imutáveis (7).

## R. Dados que exigem revisão manual (NÃO ALTERAR)

1. 17 FRs de receita pagos soft-deletados (R$ 187.300,00) — confirmar se a exclusão dos 16 SOs foi intencional e decidir sobre restauração futura.
2. 4 FRs de custo pagos soft-deletados (R$ 17.050,00) — idem.
3. FRs id5, id8, id12, id28, id35 — inconsistências históricas de status/data.
4. FR id34 — órfão de parcela regenerada (geração antiga).
5. 7 SOs `concluido` sem faturamento — confirmar se fatura deve ser obrigatória.
6. 3 SOs `concluido` sem parcelas (R$ 7.635,00 recebidos? não — recebido 0).
7. PO-260602-005 (R$ 13.500,00 paga, sem SO) — classificar como despesa geral.
8. PO-260716-001 (parcela 2.950 vencida, sem FR) — faturar ou cancelar.
9. FR manual id45 (R$ 200,00, custo_operacional, sem reference) — vincular a categoria/centro de custo futuros.
10. Possíveis POs duplicadas (aberta + rascunho mesmo valor): PO-260718-002/003, PO-260716-001/PO-260718-004, PO-260729-008/011.
11. PO-260630-001 `concluido` sem `invoiced_at`.

## S. Alterações de lógica recomendadas (para etapa futura, após aprovação)

1. Regra única de reconhecimento de receita e custo, aplicada a dashboard, financeiro e relatórios.
2. Filtros de status corretos no dashboard (receita só faturado/concluído-com-fatura; custo excluir aberto/cancelado/rascunho).
3. Parear SO↔PO na margem agregada; unificar regra do `margin_service` com a do dashboard.
4. Fonte única de AP/AR (parcela operacional + FR de ledger sempre sincronizados, inclusive PO não faturada com parcela vencida).
5. `void_payment_financial_records` não apagar FRs pagos (exigir estorno antes de excluir SO/PO).
6. Tornar `baixa_record` atômico (mesmo commit parcela+FR).
7. UNIQUE em `reference` (com limpeza prévia) + bloqueio de edição manual de espelhos.
8. Faturamento obrigatório para fechar SO/PO com valores (elimina concluído sem fatura).
9. Corrigir funil (período consistente + `computed_total`), cards com período, "Previsto".
10. Regeneração de parcelas deve reconciliar FRs pendentes (evitar órfãos).
11. Fluxo de caixa novo (entradas−saídas por `paid_date`).
12. Categorias financeiras + centros de custo; `type` novo para despesa geral.

## T. Nova arquitetura financeira recomendada (validada com os dados)

**Receita de serviços** — SO → faturamento → receita → contas a receber → recebimento → caixa. Já existe como: `Order` → `faturar()` (FR pendente) → `OrderPayment` (obrigação operacional) + `FinancialRecord` (ledger) → `baixa()` (FR pago). Falta: regra única de reconhecimento e faturamento obrigatório.

**Custo direto** — PO vinculado ao SO → custo do serviço → contas a pagar → pagamento → caixa. Já existe via `order_id` + `po_payments` + FR `custo_fornecedor`. Falta: AP nascer no vencimento (não só no faturamento), impedir exclusão que apague pagos, classificar PO sem SO como despesa geral.

**Despesa geral** — sem SO; com Categoria Financeira + Centro de Custo + Conta a Pagar + Pagamento. A rota de lançamento manual existe (`/financial/record/new`); faltam as dimensões categoria/centro de custo e um `type` próprio (ex.: `expense`), criando a base para o DRE futuro.

**Fontes oficiais recomendadas**: `OrderPayment`/`POPayment` = parcelas operacionais (obrigação, vencimento, baixa); `FinancialRecord` = ledger contábil (receita, custo direto, despesa geral) com `reference` como chave de reconciliação — exatamente o modelo em uso, endurecido com UNIQUE + proteções.

## U. Plano da próxima etapa (NÃO iniciar sem aprovação)

1. **Decisões de negócio** (reunião): regra de reconhecimento (competência por faturamento?); faturamento obrigatório?; destino dos FRs soft-deletados (restaurar pagos?); destino do V4 (aposentar); categorias e centros de custo.
2. **Etapa 2 — correções de lógica sem migração**: filtros do dashboard, pareamento SO↔PO, funil, cards, relatórios, proteção do void (não apagar pagos), baixa atômica.
3. **Etapa 3 — schema**: `financial_categories`, `cost_centers`, UNIQUE em `reference`, FKs novas (migrações com guardas idempotentes).
4. **Etapa 4 — backfill/reconciliação aprovada**: categorizar FRs ativos; restaurar espelhos pagos conforme decisão; corrigir denorm.
5. **Etapa 5 — AP/AR consolidado + fluxo de caixa**. 6. **Etapa 6 — aposentar V4 + DRE**.

## 22. Resumo executivo

| Item | Quantidade | Valor | Situação | Ação |
|---|---|---|---|---|
| SOs | 40 | R$ 247.127,00 | íntegros | PRESERVAR |
| POs | 32 | custos em itens (parcelas R$ 74.330,00) | íntegros | PRESERVAR |
| Recebimentos | 31 parcelas | R$ 230.076,00 | íntegros | PRESERVAR |
| Pagamentos | 14 parcelas | R$ 45.530,00 | íntegros | PRESERVAR |
| FinancialRecords corretos | 28 | R$ 88.496,00 | consistentes 1:1 com parcelas | PRESERVAR |
| FR ausentes | 3 | R$ 12.450,00 | parcelas sem ledger (POs não faturadas) | ANALISAR |
| FR soft-deletados | 27 | R$ 218.450,00 | pagamentos fora do ledger | ANALISAR |
| Possíveis duplicidades | 0 ativas (1 histórica) | — | nenhuma ativa | ANALISAR |
| Dados que exigem revisão | ~11 casos | — | sem correção automática | NÃO ALTERAR |

**Nenhum dado financeiro foi alterado nesta etapa.** Sistema permanece funcional e com exatamente os mesmos dados existentes.

🟢 **RECONCILIAÇÃO CONCLUÍDA — AGUARDANDO APROVAÇÃO**
