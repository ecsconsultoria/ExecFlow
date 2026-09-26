# RELATÓRIO — LANÇAMENTOS IPVA E EMPRÉSTIMO BANCO B (PRODUÇÃO)

**Data**: 31/08/2026 — **Modo**: lançamentos reais autorizados via interface normal do ExecFlow (sessão admin, UTF-8 correto), incluindo baixas nas datas indicadas. Nenhuma escrita direta no banco; nenhum registro existente alterado.

---

## Resumo executivo

Duas despesas lançadas e pagas em produção:

| Despesa | ID | Valor | Categoria | Pago em |
|---|---|---|---|---|
| Honorários IPVA — competência 07/2026 | **1003** | R$ 500,00 | Impostos e Tributos (raiz) | **31/08/2026** |
| Empréstimo Banco B — competência 07/2026 | **1004** | R$ 2.000,00 | Despesas Financeiras → Empréstimo Banco B (nova) | **25/08/2026** |

Sem duplicidade (1 registro de cada). Reflexos conferidos: DRE julho (Impostos e Tributos R$ 1.300,00 · nova linha Despesas Financeiras R$ 2.000,00), Caixa agosto realizado +R$ 2.500,00, AP pendente inalterado.

---

## 1. Decisões confirmadas com o usuário

- 1ª despesa = **uma única despesa IPVA**, descrição "Honorários IPVA" (R$ 500,00).
- IPVA: categoria existente (raiz "Impostos e Tributos").
- Empréstimo: **criar** raiz "Despesas Financeiras" → filha "Empréstimo Banco B" (opção recomendada aceita).
- Pagamentos: IPVA pago 31/08 · Empréstimo pago 25/08 (vencimento = data do pagamento em cada).

## 2. Estruturas criadas (catálogo)

| Categoria | ID | Tipo | Observação |
|---|---|---|---|
| Despesas Financeiras (raiz) | 5 | Despesa | nova — linha própria e correta da DRE (grupo já previsto no sistema) |
| Empréstimo Banco B (filha) | 6 | Despesa | pai = Despesas Financeiras |

## 3. Lançamentos criados

**Despesa 1003 — IPVA**

| Campo | Valor |
|---|---|
| Descrição | Honorários IPVA — competência 07/2026 |
| Valor | R$ 500,00 |
| Categoria | Impostos e Tributos (raiz, id 3) |
| Centro de custo | Administrativo |
| Fornecedor | — |
| Emissão | 31/07/2026 |
| Vencimento | 31/08/2026 |
| Observação | — |
| Baixa | **Paga em 31/08/2026** (sem método informado, sem valor parcial — valor exato) |

**Despesa 1004 — Empréstimo Banco B**

| Campo | Valor |
|---|---|
| Descrição | Empréstimo Banco B — competência 07/2026 |
| Valor | R$ 2.000,00 |
| Categoria | Empréstimo Banco B (id 6, raiz Despesas Financeiras) |
| Centro de custo | Administrativo |
| Fornecedor | Banco B |
| Emissão | 31/07/2026 |
| Vencimento | 25/08/2026 |
| Observação | — |
| Baixa | **Paga em 25/08/2026** (sem método informado, valor exato) |

## 4. Reflexos validados (somente leitura)

| Indicador | Valor | Check |
|---|---|---|
| Despesas Pendentes | R$ 800,00 (só DAS) | ✅ |
| Despesas Pagas no Período | **R$ 7.500,00** (5.000 pró-labore + 500 + 2.000) | ✅ |
| DRE julho — Impostos e Tributos | **R$ 1.300,00** (800,00 DAS + 500 IPVA) | ✅ |
| DRE julho — Despesas Financeiras | **R$ 2.000,00** (linha nova) | ✅ |
| DRE julho — Pessoal | R$ 5.000,00 (inalterado) | ✅ |
| AP — A Pagar | R$ 8.800,00 · 8 pendentes (inalterado — as duas já pagas) | ✅ |
| Caixa agosto — Saídas Realizadas | **R$ 47.500,00** (45.000,00 + 500 + 2.000) | ✅ |
| Caixa agosto — Saídas Previstas | R$ 8.800,00 (8.000 + DAS 800,00) | ✅ |
| Auditoria | "Despesa 'Empréstimo Banco B — competência 07/2026' R$ 2000.00 criada · financial:1004" (31/08 12:01) · "Baixa registrada R$ 2000.00 (-) · financial:1004" (31/08 12:05) + entradas do IPVA | ✅ |

## 5. Duplicidade

- Pré-checks idempotentes; **exatamente 1 registro** de cada despesa (1003 e 1004); 1 linha de cada no Lançamentos/Despesas; baixas únicas (auditoria). ✅

## 6. Observações

- Acentos preservados corretamente ("Empréstimo", "competência", "Honorários") — envio via UTF-8 explícito.
- Método de pagamento ficou vazio nas baixas (campo opcional; consistente com a prática anterior).
- O IPVA aparece na DRE sob a linha da raiz "Impostos e Tributos" (escolha do usuário de usar categoria existente); o empréstimo, na nova linha "Despesas Financeiras".

---

**Nenhum outro registro criado ou alterado. Nenhum commit/push/deploy. PARADO.**
