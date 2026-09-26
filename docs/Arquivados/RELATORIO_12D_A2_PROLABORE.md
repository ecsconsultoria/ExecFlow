# RELATÓRIO 12D-A2 — LANÇAMENTO DO PRIMEIRO PRÓ-LABORE

**Data**: 29/08/2026 — **Modo**: criação AUTORIZADA de UMA despesa geral via interface normal do ExecFlow (sessão admin). **Nenhuma outra escrita**: sem pagamento/baixa, sem alteração de SO/PO/AR/FR existentes, sem migration, sem UPDATE/DELETE manual. Lançamento permanece **PENDENTE**.

---

## Resumo executivo

Pró-labore criado com sucesso: **despesa id 1001**, R$ 5.000,00, pendente, categoria Pró-Labore (raiz Pessoal), centro de custo Administrativo, fornecedor Colaborador A, emissão 31/07/2026, vencimento 10/08/2026. Todos os reflexos bateram exatamente com o esperado: **DRE julho linha "Pessoal" +R$ 5.000,00** (fora dos custos diretos), **AP +R$ 5.000,00** (origem DESPESA, vencida), **Caixa saída PREVISTA +R$ 5.000,00** (realizado inalterado). Sem duplicidade.

---

## 1. Dados utilizados

| Campo | Valor |
|---|---|
| Valor | R$ 5.000,00 |
| Competência/Emissão | 31/07/2026 |
| Vencimento | 10/08/2026 |
| Descrição | Pró-Labore — competência 07/2026 |
| Categoria | Pessoal → Pró-Labore (id 2) |
| Centro de custo | Administrativo (id 1) |
| Fornecedor | Colaborador A (id 9) |
| Observação | vazia |
| Tipo | Despesa Geral (`expense`) |

## 2. Pré-checagem (antes de criar)

- ✅ Categoria "Pró-Labore" (id 2) ativa e vinculada à raiz "Pessoal" (id 1) — confirmado no select do formulário ("Pessoal → Pró-Labore") e no catálogo (12D-A3).
- ✅ Centro "Administrativo" (id 1) ativo.
- ✅ **Nenhuma duplicidade**: lista de Despesas com "Nenhuma despesa encontrada" (0 despesas antes).

## 3. Baseline (antes) — registrado

| Indicador | Antes |
|---|---|
| Despesas (registros) | 0 (R$ 0,00 em todos os cards) |
| AP A Pagar (Total) | R$ 8.000,00 — 7 pendente(s) (Custos R$ 8.000,00 · Despesas R$ 0,00) |
| AP Vencidos | R$ 5.500,00 — 5 vencido(s) |
| Caixa saídas PREVISTAS (mês) | R$ 8.000,00 |
| Caixa saídas REALIZADAS (mês) | R$ 40.000,00 |
| DRE julho/2026 — linha Pessoal | R$ 0,00 |
| DRE julho/2026 — Despesas Gerais | R$ 0,00 |
| DRE julho/2026 — Custos Diretos | R$ 25.000,00 (coluna julho) |

> **Observação (ação externa ao trabalho deste agente):** entre a validação 12C-A8 (~13:00) e esta etapa, as saídas realizadas do mês caíram de R$ 45.000,00 para R$ 40.000,00 (e "Pagos no Período" do AP de R$ 80.000,00 para R$ 75.000,00) — indicando que um lançamento pago de R$ 5.000,00 foi removido/estornado em produção pelo usuário nesse intervalo. Apenas registrado; nada feito a respeito.

## 4. Resultado da criação

- POST `/financial/expenses/new` (formulário normal do sistema) → 302 → flash **"Despesa criada."**

## 5. ID da despesa

**1001** (`financial_records.id = 1001`; `reference = expense:1001`)

## 6. Campos gravados (verificados no form de edição do id 1001)

| Campo | Valor gravado |
|---|---|
| Descrição | Pró-Labore — competência 07/2026 |
| Valor | 5000.00 |
| Categoria | id 2 — "Pessoal → Pró-Labore" (selected) |
| Centro de custo | id 1 — "Administrativo" (selected) |
| Fornecedor | id 9 — "Colaborador A" (selected) |
| Emissão | 2026-07-31 |
| Vencimento | 2026-08-10 |
| Observação | vazia |
| Status | **pendente** (lista: Pendentes R$ 5.000,00 · Vencidas R$ 5.000,00) |

## 7. Reflexo na DRE

DRE custom 01/07/2026–31/07/2026 (pós):

- Linha **"Pessoal": R$ 5.000,00** ✓ (era R$ 0,00)
- **Despesas Gerais (coluna julho): R$ 5.000,00** ✓ (era R$ 0,00)
- **Custos Diretos: inalterados** (julho R$ 25.000,00) → pró-labore **não** virou custo direto ✓
- Margem Bruta inalterada (despesa só afeta o resultado operacional) ✓

## 8. Reflexo no AP

| Indicador | Antes | Depois |
|---|---|---|
| A Pagar (Total) | R$ 8.000,00 (7) | **R$ 13.000,00 (8)** ✓ |
| Custos de Serviços | R$ 8.000,00 | R$ 8.000,00 (inalterado) |
| Despesas Gerais | R$ 0,00 | **R$ 5.000,00** ✓ |
| Vencidos | R$ 5.500,00 (5) | **R$ 10.500,00 (6)** ✓ |

Linha da obrigação presente: `31/07/2026 · 10/08/2026 · R$ 5.000,00 · Pendente` (origem DESPESA — vencida, pois 10/08 < hoje).

## 9. Reflexo no Caixa

| Indicador | Antes | Depois |
|---|---|---|
| Saídas PREVISTAS (due_date) | R$ 8.000,00 | **R$ 13.000,00** ✓ |
| Saídas REALIZADAS | R$ 40.000,00 | R$ 40.000,00 (**inalterado** — não pago) ✓ |
| Saldo Projetado | −R$ 800,00 | −R$ 5.800,00 |

## 10. Financial Record (espelho)

- O sistema criou **exatamente 1** FinancialRecord (id 1001, `type='expense'`, `reference='expense:1001'`) — o espelho 1:1 da despesa, criado pelo fluxo normal. **Nenhum FR manual, nenhuma duplicação.**
- Visível no Lançamentos (período "Todos"): `– · 31/07/2026 · 10/08/2026 · – · R$ 5.000,00 · – · Pendente`.

## 11. Comparação antes/depois — resumo

| Item | Antes | Depois | Δ |
|---|---|---|---|
| Despesas | 0 | 1 (id 1001) | +1 ✓ |
| AP pendente | 8.000,00 (7) | 13.000,00 (8) | +5.000,00 ✓ |
| DRE Pessoal (julho) | 0,00 | 5.000,00 | +5.000,00 ✓ |
| Caixa previsto (saídas) | 8.000,00 | 13.000,00 | +5.000,00 ✓ |
| Caixa realizado (saídas) | 40.000,00 | 40.000,00 | 0 ✓ |
| SO/PO/AR | — | — | 0 (intocados) ✓ |

## 12. Duplicidade

**Nenhuma.** Única linha na tela de Despesas; único R$ 5.000,00 em AP/Caixa/DRE; um único FR (1001). Pré-checagem confirmou 0 despesas antes.

## 13. Alterações realizadas (escopo exato)

1. `POST /financial/expenses/new` → 1 despesa (FinancialRecord id 1001).
2. Nada mais. Sem baixa, sem pagamento, sem edição/cancelamento, sem migration, sem tocar em dados históricos.

## 14. Eventuais problemas

- Nenhum. (Única ressalva documental: valores de caixa realizado/Pagos no Período já estavam R$ 5.000,00 menores do que na 12C-A8 — movimento externo do usuário entre as etapas, registrado na seção 3.)
- Despesa vencida (10/08) — esperado, dada a competência retroativa de julho; resolve-se com a baixa na próxima etapa autorizada.

---

**PAGAMENTO NÃO EXECUTADO — lançamento permanece PENDENTE. Nenhum commit feito. PARADO, aguardando a próxima etapa.**
