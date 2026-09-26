# RELATÓRIO 12D-A3 — LANÇAMENTO DO DAS / SIMPLES NACIONAL

**Data**: 29/08/2026 — **Modo**: lançamento REAL autorizado, criado via interface normal do ExecFlow (sessão admin). **Nenhuma outra escrita**: nenhum pagamento/baixa, nenhum INSERT/UPDATE/DELETE direto, nenhuma alteração em categorias, centros, DRE, Caixa, AP ou lançamentos existentes. O lançamento permanece **PENDENTE**.

---

## Resumo executivo

Lançamento do DAS criado com sucesso: **despesa id 1002**, R$ 800,00, **pendente** (imposto em aberto, sem pagamento), categoria "DAS / Simples Nacional" (raiz "Impostos e Tributos"), centro de custo "Administrativo", emissão 31/07/2026, vencimento 31/08/2026. Reflexos automáticos confirmados: **AP +R$ 800,00** (8 pendências), **Caixa saída PREVISTA +R$ 800,00** (realizado inalterado), **DRE julho/2026** com a linha da raiz "Impostos e Tributos" em R$ 800,00. Sem duplicidade.

---

## 1. Dados do lançamento

| Campo | Valor |
|---|---|
| Tipo | Despesa Geral (`expense`) |
| Descrição | DAS / Simples Nacional — competência 07/2026 |
| Valor | R$ 800,00 |
| Competência / Emissão | 07/2026 · 31/07/2026 |
| Vencimento | 31/08/2026 |
| Categoria | DAS / Simples Nacional (id 4) — raiz "Impostos e Tributos" (id 3) |
| Centro de custo | Administrativo (id 1) |
| Fornecedor | em branco (não obrigatório) ✓ |
| Observação | DAS / Simples Nacional referente à competência 07/2026 ✓ |
| Status | **Pendente** (em aberto — sem baixa, sem data de pagamento) ✓ |

## 2. ID criado

**1002** (`financial_records.id = 1002`; referência `expense:1002`)

Campos verificados no formulário de edição do id 1002: descrição, valor 800.00, categoria selecionada "Impostos e Tributos → DAS / Simples Nacional", centro "Administrativo", fornecedor sem seleção, emissão 2026-07-31, vencimento 2026-08-31, observação gravada. ✓

## 3. FinancialRecord

- **Exatamente 1** FinancialRecord — a própria despesa (espelho 1:1, `reference='expense:1002'`), criado pelo fluxo normal (nenhum FR manual).
- Visível no Lançamentos (período "Todos"): `31/07/2026 · 31/08/2026 · R$ 800,00 · Pendente` — **1 única linha** ✓
- Nenhum FR adicional criado, nenhum pagamento, nenhuma baixa.

## 4. Reflexo no AP

| Indicador | Antes | Depois | Δ | OK |
|---|---|---|---|---|
| A Pagar (Total) | R$ 8.000,00 — 7 pend. | **R$ 8.800,00 — 8 pend.** | +800,00 | ✅ |
| Custos de Serviços | R$ 8.000,00 | R$ 8.000,00 | 0 | ✅ |
| Despesas Gerais | R$ 0,00 | **R$ 800,00** | +800,00 | ✅ |
| Vencidos | R$ 5.500,00 — 5 | R$ 5.500,00 — 5 | 0 | ✅ (vencimento 31/08 > hoje — não está vencido) |
| Pago no Período | R$ 80.000,00 | R$ 80.000,00 | 0 | ✅ |

## 5. Reflexo no Caixa

| Indicador | Antes | Depois | Δ | OK |
|---|---|---|---|---|
| Saídas PREVISTAS (due_date) | R$ 8.000,00 | **R$ 8.800,00** | +800,00 | ✅ |
| Saídas REALIZADAS | R$ 45.000,00 | R$ 45.000,00 | 0 (não pago) | ✅ |
| Saldo Projetado | −R$ 5.800,00 | −R$ 6.600,00 | −800,00 | ✅ |

O DAS entrou como **saída PREVISTA** (31/08/2026) — **não** como realizada. ✓

## 6. Reflexo na DRE (competência 07/2026)

- Nova linha **"Impostos e Tributos: R$ 800,00"** na seção de Despesas Gerais da DRE de julho ✓ (a DRE agrupa despesas pela **categoria-raiz**; como a raiz criada se chama "Impostos e Tributos" — e não "Impostos" —, o sistema a exibe como linha própria, ao lado dos grupos fixos. Comportamento correto do sistema; **nada foi alterado**).
- Linhas existentes preservadas: "Pessoal" R$ 5.000,00 · "Impostos" (grupo fixo) R$ 0,00 ✓
- **Não** entrou em Custos Diretos ✓ (custos diretos julho inalterados).
- Resultado Operacional de julho passou a −R$ 40.000,00 (incluindo Pessoal 5.000 + Impostos e Tributos 800,00) — reflexo esperado por competência.

## 7. Status

**PENDENTE** (em aberto) — cartões da tela Despesas: Pendentes R$ 800,00 · Vencidas R$ 0,00 · Pagas no Período R$ 5.000,00 (pró-labore). Sem data de pagamento, sem baixa. ✓

## 8. Validação de duplicidade

- Pré-check: 0 despesas DAS existentes (lista de Despesas sem registro do DAS antes).
- Pós: **exatamente 1** despesa (id 1002) · **exatamente 1** FinancialRecord · **1 única** linha de R$ 800,00 no Lançamentos · **0 pagamentos** · **0 baixas** ✓
- Auditoria: 1 registro de criação (`Despesa 'DAS / Simples Nacional — competência 07/2026' R$ 800.00 criada · financial:1002 · 29/08/2026 13:49 · admin@example.com`).

## 9. Integridade

- Todas as telas consultadas responderam sem erro (200); valores consistentes entre Despesas/AP/Caixa/DRE/Lançamentos/Auditoria.
- Verificação por SQL direto (FKs/integrity_check): não acessível deste ambiente — nenhum indício de problema nas camadas acessíveis.

## 10. Problemas encontrados

**Nenhum.** (Observação documental apenas: a DRE exibe o grupo sob o nome da raiz "Impostos e Tributos" — linha própria, em vez do grupo fixo "Impostos" — decorrência do nome da raiz criada; comportamento correto do sistema, nada alterado.)

---

**PAGAMENTO NÃO EXECUTADO — o DAS permanece EM ABERTO/PENDENTE. Nenhum commit/push/deploy. PARADO, aguardando a próxima etapa.**
