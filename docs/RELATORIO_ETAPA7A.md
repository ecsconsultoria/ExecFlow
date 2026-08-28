# ETAPA 7A — RELATÓRIO DE ANÁLISE DO PO-260602-005 E FR ID45 (SOMENTE LEITURA)

**Data**: 28/08/2026 — **Modo**: 100% somente leitura. **NENHUM dado alterado.** **Commit**: ver `git log -1` (documentação).

---

## A. PO-260602-005 — completo

| Campo | Valor |
|---|---|
| ID / número | 9 / PO-260602-005 |
| company_id | 1 |
| Fornecedor | **Banco do Brasil** (id 11) |
| **Item** | **"Pronampe"** — qtd 1 × R$ 13.500,00 |
| Valor total | R$ 13.500,00 (computed_total = item) |
| Status | **pago** (faturada em 02/06 23:53; paga via parcela em 29/05) |
| SO / ServiceOrder / Quote | **todos NULL** (sem vínculo) |
| Datas | criada 02/06 23:52 · sent_at 02/06 · invoiced_at 02/06 · paid_at 02/06 23:54 |
| Observações | vazias (sem notas) |
| Auditoria | Criada → Item adicionado → Parcelas geradas → PO aberta → Faturada (tudo em 02/06, user 1). **Nunca excluída/cancelada.** |

## B. FR id45 — completo

| Campo | Valor |
|---|---|
| ID / type / category | 45 / cost / custo_operacional |
| Descrição | "Transfer GRU Airport x Itaim" |
| Valor / status | R$ 200,00 / **pendente** |
| Vencimento | 29/07/2026 · payment_method TRANSFERÊNCIA |
| reference | **NULL** (lançamento manual — sem vínculo) |
| emission / due / paid | NULL / 29/07 / NULL |
| supplier / order / PO / categoria / centro | **todos NULL** |
| deleted_at | NULL (ativo) |
| Auditoria | "Lançamento cost R$ 200.00 criado" (28/07 19:42, user 1) |

## C. Fornecedor

Banco do Brasil (para o PO). O FR45 não tem fornecedor.

## D. Valor

PO: R$ 13.500,00 pago · FR45: R$ 200,00 pendente. **Não são o mesmo lançamento** (o PO tem seu espelho próprio — FR id28, `po_payment:10`, ativo e pago 29/05).

## E. Pagamento

- PO: parcela `po_payment:10` **paga** (29/05, R$ 13.500,00) ↔ FR id28 ativo 1:1 (sem duplicata).
- FR45: **sem pagamento** (pendente, vencido desde 29/07).

## F. Datas

PO: criada/faturada 02/06; pagamento 29/05 (data retroativa na baixa — padrão observado nos registros históricos da época). FR45: criado 28/07, vencimento 29/07, sem pagamento.

## G. Evidências da natureza do gasto

- **Item "Pronampe" + fornecedor Banco do Brasil**: PRONAMPE é o programa nacional de crédito a micro/pequenas empresas — este lançamento é uma **amortização/parcela de financiamento bancário**, não um serviço de transporte (sem pickup/delivery, sem SO, sem veículo).
- FR45: descrição "Transfer GRU Airport x Itaim" **sugere serviço de transporte**, mas não há nenhum vínculo no sistema (sem SO/PO/parcela) — lançamento manual solto.

## H. Ausência de SO

**Confirmado**: PO-260602-005 tem `order_id = NULL`, `service_order_id = NULL`, `quote_id = NULL`. Nenhum vínculo será criado.

## I. Natureza econômica

- PO-260602-005: **pagamento de financiamento bancário (Pronampe)** — não é custo de serviço.
- FR id45: **indeterminada** (manual, sem vínculo; descrição sugere custo de serviço, mas sem evidência sistêmica).

## J. Classificação recomendada

- **PO-260602-005 → B — DESPESA GERAL** (subgrupo **Despesas Financeiras**, categoria-raiz já existente no catálogo 3A: "Despesas Financeiras" → sugestão "Amortização de Empréstimos"). Justificativa: item + fornecedor + ausência total de vínculo operacional.
- **FR id45 → D — INDETERMINADO** (revisão manual): ou vincular ao SO do serviço (se o usuário identificar qual — nesse caso seria custo direto), ou classificar como despesa. Sem evidência, não classificar.

## K. Impacto potencial na DRE (simulação — nada alterado)

- Hoje: PO está **fora da DRE** (não é custo direto por não ter SO; não é despesa por ser PO/FR cost). FR45 também fora (não é expense).
- Se o PO fosse classificado como despesa geral: **DRE + R$ 13.500,00 em despesas** na competência da emissão (junho) — Resultado Operacional reduziria em R$ 13.500,00 naquele mês.
- Se o FR45 fosse classificado como despesa (com emissão): **DRE + R$ 200,00** no mês da emissão escolhida.

## L. Impacto potencial no Caixa

- **Caixa atual: o PO JÁ está refletido** — FR id28 (R$ 13.500,00, pago 29/05) aparece como saída de maio. Nenhuma alteração seria necessária.
- FR45: **fora do caixa** (não pago); quando pago, entra como saída de R$ 200,00 no dia do pagamento.

## M. Impacto potencial no AP

- PO: pago — **não gera AP pendente**.
- FR45: **já conta no AP pendente** hoje (R$ 13.400,00 total inclui os R$ 200,00). Ao pagar, baixa normalmente (rota existente).

## N. Duplicidade

- FR id28 (po_payment:10): ativo, 1:1, valor correto — **sem duplicata**.
- FR45: sem reference — não duplica nenhum movimento; aparece uma única vez (AP).

## O. Auditoria

Ambos têm trilha em `audit_logs` (criação do PO com sequência completa; criação manual do FR45). Nenhuma ação será registrada nesta etapa.

## P. Conclusão

1. **PO-260602-005**: empréstimo PRONAMPE pago (Banco do Brasil) — recomenda-se, em etapa futura autorizada, tratá-lo como **Despesa Geral / Despesas Financeiras** (via classificação no catálogo), sem alterar o PO.
2. **FR id45**: lançamento manual pendente de natureza indeterminada — requer **revisão manual do usuário** (vincular ao serviço ou classificar como despesa), sem alteração automática.
3. **Nada foi alterado**: PO alterado = ZERO · FR45 alterado = ZERO · Pagamento alterado = ZERO · SO alterado = ZERO.

---

🟢 **ETAPA 7A CONCLUÍDA — PO-260602-005 / FR45 ANALISADOS**

**Nenhum dado alterado.** Aguardando autorização explícita para qualquer alteração (classificação do PO/FR45, correções etc.).
