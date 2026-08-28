# ETAPA 6C — RELATÓRIO FINAL (Restauração Controlada dos 21 FinancialRecords)

**Data**: 28/08/2026 — **Commit**: ver `git log -1` (sem push — deploy segue o fluxo normal da branch `v3`)
**Autorização**: expressa do usuário — restaurar individualmente os 21 IDs do Grupo A; corrigir status do ID 5.

---

## 1. Backup e Checkpoint

- Backup: `backup/DB_V2_pre-etapa6c-20260828.db` (pré-restauração; anteriores não sobrescritos)
- Branch `v3`, commit de entrada `9f1be02`, working tree limpo, alembic head `c4d2e9f0a1b5`, `integrity_check` ok
- Tag: **`v3-pre-etapa6c-restauracao-20260828`**

## 2. Tabela das restaurações (21/21 executadas, 0 bloqueadas)

| ID | Reference | Tipo | Valor | Status Antes | Status Depois | Restaurado | Observação |
|---|---|---:|---|---|---|---|---|
| 1 | order_payment:1 | revenue | 450,00 | pago | pago | ✅ | normal |
| 2 | order_payment:2 | revenue | 450,00 | pago | pago | ✅ | normal |
| 3 | po_payment:1 | cost | 550,00 | pago | pago | ✅ | normal |
| 5 | order_payment:3 | revenue | 13.500,00 | pendente | **pago** | ✅ | **status corrigido de pendente para pago por autorização explícita na Etapa 6C** |
| 6 | po_payment:3 | cost | 7.000,00 | pago | pago | ✅ | normal |
| 8 | order_payment:4 | revenue | 13.500,00 | pago | pago | ✅ | **datas preservadas** (FR 29/05 × parcela 02/06) |
| 12 | order_payment:7 | revenue | 13.500,00 | pago | pago | ✅ | **datas preservadas** + sem faturamento formal |
| 13 | order_payment:8 | revenue | 13.500,00 | pago | pago | ✅ | normal |
| 14 | order_payment:9 | revenue | 13.500,00 | pago | pago | ✅ | normal |
| 15 | order_payment:10 | revenue | 13.500,00 | pago | pago | ✅ | sem faturamento formal |
| 16 | order_payment:11 | revenue | 13.500,00 | pago | pago | ✅ | normal |
| 17 | order_payment:12 | revenue | 13.500,00 | pago | pago | ✅ | normal |
| 18 | order_payment:13 | revenue | 13.500,00 | pago | pago | ✅ | normal |
| 19 | order_payment:14 | revenue | 13.500,00 | pago | pago | ✅ | normal |
| 20 | order_payment:15 | revenue | 10.000,00 | pago | pago | ✅ | normal |
| 21 | order_payment:16 | revenue | 900,00 | pago | pago | ✅ | normal |
| 22 | order_payment:17 | revenue | 13.500,00 | pago | pago | ✅ | normal |
| 23 | order_payment:18 | revenue | 13.500,00 | pago | pago | ✅ | normal |
| 24 | order_payment:19 | revenue | 13.500,00 | pago | pago | ✅ | normal |
| 26 | po_payment:8 | cost | 7.000,00 | pago | pago | ✅ | normal |
| 27 | po_payment:9 | cost | 2.500,00 | pago | pago | ✅ | normal |

**Total: 21 restaurados — R$ 204.350,00** (receitas R$ 187.300,00 + custos R$ 17.050,00) · Bloqueados: 0.

## 3. Grupos especiais

- **RESTAURO NORMAL**: 17 registros.
- **ID 5 — STATUS CORRIGIDO**: restaurado e status `pendente → pago` (autorização explícita; única alteração além do soft-delete; registrado em auditoria).
- **IDs 8 e 12 — DATAS PRESERVADAS PARA REVISÃO**: datas originais mantidas (FR 29/05 × parcela 02/06 — decisão de correção fica para etapa separada).
- **IDs 12 e 15 — SEM FATURAMENTO FORMAL**: restaurados normalmente (serviço evidenciado + pagamento real; `invoiced_at`/SO **não alterados**).

## 4. Proibidos

**6 permanecem soft-deletados** (não tocados): IDs 7, 31, 32, 34, 43, 44. Nenhuma outra restauração ocorreu (diff do banco confirmado: exatamente os 21 autorizados).

## 5. Impacto financeiro

| Indicador | Antes | Depois | Diferença |
|---|---:|---:|---:|
| Caixa — Entradas (recebimentos) | R$ 42.776,00 | R$ 230.076,00 | **+R$ 187.300,00** ✅ |
| Caixa — Saídas (pagamentos) | R$ 28.480,00 | R$ 45.530,00 | **+R$ 17.050,00** ✅ |
| Caixa — Líquido | R$ 14.296,00 | R$ 184.546,00 | **+R$ 170.250,00** ✅ |
| DRE | inalterada | inalterada | **R$ 0,00** ✅ (fontes = Orders/POs) |
| Contas a Receber | R$ 3.640,00 | R$ 3.640,00 | **R$ 0,00** ✅ |
| Contas a Pagar | R$ 13.400,00 | R$ 13.400,00 | **R$ 0,00** ✅ |

Números conferidos por SQL — batem com o esperado da autorização. Cada reference aparece **uma única vez** no caixa (0 duplicatas ativas).

## 6. Auditoria

Cada restauração gravou entrada em `audit_logs` ("FR RESTAURADO (Etapa 6C) ref=... tipo=... valor=... status_antes=... status_depois=...", usuário 1). Nenhum lançamento novo foi criado — os próprios registros originais foram reativados (IDs preservados).

## 7. Testes e integridade

- **3/3 testes novos 6C** (allowlist só restaura autorizados; bloqueados não interrompem os demais e permanecem deletados; SO/parcela intactos)
- Suíte completa: **mesmas 6 falhas pré-existentes** — nenhuma nova (Etapas 2, 3A, 3B, 4, 5, 6, 6C verdes)
- `integrity_check` = ok
- Diff vs backup pré-6C: `financial_records` difere **somente** nos 21 `deleted_at` (removidos), `updated_at` (timestamps naturais) e `status` do ID 5 (autorizado)

## 8. Dados históricos

- SO alterados: **ZERO** · POs alterados: **ZERO** · OrderPayments: **ZERO** · POPayments: **ZERO** · Valores/datas/references históricos: **ZERO** (exceto status do ID 5, expressamente autorizado)
- orders, order_items, order_payments, purchase_orders, po_items, po_payments, quotes, payment_receipts, clients, suppliers: **IDÊNTICAS** ao backup pré-6C
- PO-260602-005, FR id45: **não tocados**

## 9. Pendências

1. **Decisão sobre as datas dos IDs 8 e 12** (FR 29/05 × parcela 02/06) — etapa separada.
2. Os 6 proibidos (7, 31, 32, 34, 43, 44) seguem soft-deletados — decisão futura (não pagos/órfão).
3. PO-260602-005 / FR id45: classificação futura.
4. Dump do PostgreSQL de produção antes do próximo deploy.

---

🟢 **ETAPA 6C CONCLUÍDA — 21 FINANCIAL RECORDS RESTAURADOS**
