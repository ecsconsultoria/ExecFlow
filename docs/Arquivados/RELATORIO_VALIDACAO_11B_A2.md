# RELATÓRIO 11B-A2 — VALIDAÇÃO DA DIVERGÊNCIA SO × RECEBIMENTOS × DASHBOARD (SOMENTE INVESTIGAÇÃO)

**Data**: 29/08/2026 — **Modo**: 100% somente leitura. **NENHUM código, banco, migration ou commit.** Banco aberto em `mode=ro`.

---

## 1. Origem dos R$ 28.000 (SERVIÇOS VENDIDOS)

- **Fonte**: visão de Pedidos (SO) — `orders` (ativos, `deleted_at IS NULL`), **todos os status exceto `excluido`** (17 SOs).
- **Campo**: `computed_total` = total − desconto + frete + outros custos.
- **Período**: **sem filtro de período** (acumulado histórico).
- **Data de referência**: nenhuma (soma integral).
- Não é receita: é **valor vendido** — inclui SOs abertos e concluídos sem faturamento.

## 2. Origem dos R$ 21.200 (RECEBIDO)

- **Fonte**: `order_payments` dos **mesmos 17 SOs ativos** — `paid_amount` somado (parcelas pagas).
- **Data**: `paid_at` (caixa).
- **Período**: sem filtro (acumulado).
- Nota: o total geral de recebimentos é R$ 115.000; **R$ 93.800 são de SOs excluídos** (restaurados na Etapa 6C) e ficam fora dessa visão (a visão filtra `excluido`).

## 3. Origem dos R$ 6.800 (PENDENTE)

- **Aritmético da visão**: 28.000 − 21.200 = 6.800. **Não é o Contas a Receber real** (que é R$ 1.800,00 via `ar_ap_service`).
- O "pendente" da visão mistura duas coisas: (a) vendido porém **não faturado** e (b) faturado porém não recebido (R$ 1.800 — SO-260729-002).

## 4. Origem dos R$ 12.500 (DASHBOARD/DRE "Este Ano")

- **Fonte**: `dre_service.recognized_revenue` → `orders` com `invoiced_at` preenchido e status `faturado/concluido` (regra da Etapa 2/5 — **receita reconhecida**).
- **Data de referência**: `invoiced_at` (competência).
- **Período**: "Este Ano" = **01/01/2026 → hoje** (`_period_bounds('ytd')`, confirmado no código — é o ano civil, não 12 meses rolantes).
- Empresa: company_id 1.

## 5. Reconciliação Order por Order (17 SOs ativos)

| SO | valor | status | invoiced_at | recebido | entra na DRE? | motivo |
|---|---:|---|---:|---:|---|---|
| SO-260602-003 | 500,00 | concluido | 02/06 | 500,00 | SIM | faturada |
| SO-260602-018 | 6.500,00 | concluido | 02/06 | 6.500,00 | SIM | faturada |
| SO-260603-001 | 8.800,00 | concluido | **–** | 8.800,00 | **não** | SEM FATURA |
| SO-260603-003 | 550,00 | concluido | 15/06 | 550,00 | SIM | faturada |
| SO-260630-001 | 1.300,00 | concluido | **–** | 0,00 | **não** | SEM FATURA |
| SO-260703-001 | 1.600,00 | concluido | **–** | 0,00 | **não** | SEM FATURA |
| SO-260703-002 | 600,00 | concluido | **–** | 0,00 | **não** | SEM FATURA |
| SO-260703-003 | 900,00 | concluido | 28/07 | 900,00 | SIM | faturada |
| SO-260706-001 | 1.400,00 | concluido | 10/08 | 1.400,00 | SIM | faturada |
| SO-260720-001 | 500,00 | concluido | **–** | 500,00 | **não** | SEM FATURA |
| SO-260720-002 | 650,00 | concluido | **–** | 650,00 | **não** | SEM FATURA |
| SO-260729-001 | 350,00 | concluido | 10/08 | 350,00 | SIM | faturada |
| SO-260729-002 | 1.800,00 | faturado | 25/08 | 0,00 | SIM | faturada (não recebida) |
| SO-260729-003 | 900,00 | aberto | **–** | 0,00 | **não** | aberta |
| SO-260729-004 | 600,00 | aberto | **–** | 0,00 | **não** | aberta |
| SO-260729-005 | 550,00 | concluido | **–** | 550,00 | **não** | SEM FATURA |
| SO-260729-006 | 500,00 | concluido | 10/08 | 500,00 | SIM | faturada |

Totais conferidos: VENDIDO 28.000 ✓ · RECEBIDO (ativos) 21.200 ✓ · DRE 12.500 ✓.

## 6. Diferenças de período

Nenhuma para a receita: "Este Ano" é o ano civil (01/01→hoje) e as 8 SOs faturadas estão todas dentro dele. O gráfico de 12 meses (Ago/25–Ago/26) que aparece no Dashboard é o **rolling chart** (visão móvel de 12 meses) — **não é o filtro de período**; não afeta os KPIs.

## 7. Diferenças de competência

Receita: competência = `invoiced_at` ✓ em todas as telas (DRE e Dashboard usam o mesmo `dre_service`). Sem divergência de competência.

## 8. Diferenças de faturamento — CAUSA PRINCIPAL

**R$ 15.500 = 28.000 − 12.500** é composto EXATAMENTE por:

| Grupo | SOs | Valor |
|---|---:|---:|
| Concluídos **SEM faturamento** (7) | SO-260603-001 (8.800) · SO-260630-001 (1.300) · SO-260703-001 (1.600) · SO-260703-002 (600) · SO-260720-001 (500) · SO-260720-002 (650) · SO-260729-005 (550) | **R$ 14.000,00** |
| **Abertos** (2) | SO-260729-003 (900) · SO-260729-004 (600) | **R$ 1.500,00** |
| **Total** | | **R$ 15.500,00** ✅ |

12.500 + 14.000 + 1.500 = 28.000 ✅ — matemática exata, sem resíduo.

## 9. Diferenças de recebimento

**R$ 8.700 = 21.200 − 12.500** é composto por dois efeitos opostos:

- **Recebidos SEM faturamento** (+): SO-260603-001 (8.800) + SO-260720-001 (500) + SO-260720-002 (650) + SO-260729-005 (550) = **+R$ 10.500,00**
- **Faturado NÃO recebido** (−): SO-260729-002 (1.800) = **−R$ 1.800,00**
- Resultado: 10.500 − 1.800 = **R$ 8.700,00** ✅

## 10. Verificação de duplicidade

**Zero duplicidade.** Fontes distintas por design: vendidos/recebidos da visão SO usam `orders`/`order_payments`; a DRE usa `dre_service` sobre `orders` (faturadas); o Caixa usa `financial_records` (espelho 1:1, índice UNIQUE). Nenhum indicador soma parcela + FR simultaneamente.

## 11. Verificação do filtro "Este Ano"

- Código (`_period_bounds`, `period='ytd'`): início = **01/01/2026**, fim = hoje. ✔ Ano civil.
- O gráfico "12 meses" (Ago/25–Ago/26) é o **rolling chart** independente — rótulo correto, mas não é o período dos KPIs. Não há bug de intervalo.

## 12. Conclusão objetiva

**"Os R$ 12.500 do Dashboard estão CORRETOS e representam uma visão diferente dos R$ 28.000 de serviços vendidos."**

- **28.000** = valor **vendido** (17 SOs ativos, qualquer status, sem período) — visão comercial da tela de Pedidos.
- **21.200** = **recebido** desses SOs (caixa, sem período).
- **6.800** = vendido − recebido (aritmético da visão; **não** é o AR real — AR = 1.800).
- **12.500** = **receita reconhecida** (regra Etapa 2/5: faturamento efetivo, competência `invoiced_at`, ano civil) — visão gerencial da DRE/Dashboard, aplicada consistentemente.

A diferença de 15.500 é **100% explicada** por 7 SOs concluídos sem faturamento (14.000) + 2 abertos (1.500) — nenhum erro de cálculo. A diferença de 8.700 é **100% explicada** por recebidos sem fatura (10.500) menos faturado não recebido (1.800).

**Verificação adicional (custos):** DRE YTD custos = 19.000 ✓ (jun 12.500 + jul 5.000 + ago 1.500). As POs 001/003 não entram no acumulado porque seus itens têm `service_date` **futuro** (30/08 e 01–03/09/2026) — competência correta (fora do período até hoje). Margem −6.500 = 12.500 − 19.000 ✓.

---

**Nenhum dado foi alterado.** Sem commit, sem código, sem migration.

PARADO — aguardando autorização explícita.
