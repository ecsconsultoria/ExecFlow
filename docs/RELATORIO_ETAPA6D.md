# ETAPA 6D — RELATÓRIO DE ANÁLISE DAS DATAS DOS FRs 8 E 12 (SOMENTE ANÁLISE)

**Data**: 28/08/2026 — **Modo**: somente leitura. **NENHUM dado alterado.** **Commit**: ver `git log -1` (documentação).

---

## 1. Checkpoint

Branch `v3`, commit `a066523`, working tree limpo, alembic head `c4d2e9f0a1b5`, `integrity_check` ok. Tag: **`v3-pre-etapa6d-datas-fr8-fr12-20260828`**. Backup de banco **não foi necessário** — nenhuma alteração executada nesta etapa.

## 2. Situação atual

| | FR 8 | FR 12 |
|---|---|---|
| paid_date atual | **29/05/2026** | **29/05/2026** |
| Data real da parcela (paid_at) | **02/06/2026 20:08** | **02/06/2026 20:53** |
| Valor | R$ 13.500,00 | R$ 13.500,00 |
| Reference | order_payment:4 | order_payment:7 |
| SO | SO-260602-001 (faturado em 02/06) | SO-260602-005 (sem faturamento formal) |
| Data recomendada | **02/06/2026** | **02/06/2026** |

## 3. Impacto no Caixa (paid_date é a data do movimento)

| Período | Entradas atuais | Entradas simuladas | Diferença |
|---|---:|---:|---:|
| maio/2026 | R$ 162.000,00 | R$ 135.000,00 | **−R$ 27.000,00** |
| junho/2026 | R$ 57.200,00 | R$ 84.200,00 | **+R$ 27.000,00** |
| **Acumulado mai+jun** | **R$ 219.200,00** | **R$ 219.200,00** | **R$ 0,00** |

- Líquido maio: R$ 141.500,00 → R$ 114.500,00 · Líquido junho: R$ 37.045,00 → R$ 64.045,00
- Saídas não são afetadas (os dois FRs são entradas).
- **Total acumulado inalterado** — a correção move caixa entre meses, não muda o resultado.

## 4. Impacto em relatórios (tela Relatórios usa paid_date)

- maio: R$ 162.000,00 → R$ 135.000,00 · junho: R$ 57.200,00 → R$ 84.200,00 (mesma movimentação de R$ 27.000,00).

## 5. DRE — SEM impacto (explicação)

A DRE (Etapa 5) **não utiliza paid_date**: receita = Orders por `invoiced_at`; custos = POs por competência; despesas = emissão.
- FR 8 (SO-260602-001): SO faturado em 02/06 → a receita da DRE já está em **junho**, independente do paid_date do FR.
- FR 12 (SO-260602-005): SO sem faturamento → **fora da DRE**, independente do paid_date.
- **Impacto na DRE: R$ 0,00.**

## 6. AR — SEM impacto

Os dois FRs estão pagos; a correção de paid_date não altera saldo pendente (AR permanece R$ 3.640,00).

## 7. AP — SEM impacto

Nenhum dos dois é custo; AP permanece R$ 13.400,00.

## 8. Auditoria — mecanismo existe

`log_activity` (audit_logs) já é o padrão do projeto. Uma correção autorizada registraria: FR id, reference da parcela, valor anterior (29/05), valor novo (02/06), motivo ("correção de data de caixa para a data real da baixa — Etapa 6D"), data da alteração, usuário responsável. A tela de relatórios/caixa refletiria automaticamente.

## 9. RECOMENDAÇÃO

**"Recomenda-se corrigir"** — alterar `paid_date` de 29/05 → 02/06 nos FRs 8 e 12.

Motivos:
1. A parcela (`order_payments.paid_at` — fonte primária do recebimento) registra 02/06; o 29/05 foi data manual retroativa no FR.
2. `paid_date` é a data do movimento de caixa — a correção alinha o Caixa mensal e os relatórios com o evento real.
3. Total acumulado, DRE, AR e AP permanecem inalterados (impacto = apenas troca de mês, R$ 27.000 de maio para junho).
4. Reversível e auditável (mecanismo pronto).

Ressalvas (não bloqueiam): FR 12 pertence a SO sem faturamento formal — a correção de data não muda essa situação; e a correção deve ser executada **somente após autorização explícita**, preservando todos os demais campos.

---

## Status

🟢 **ETAPA 6D — ANÁLISE DE DATAS CONCLUÍDA**

**NENHUM DADO ALTERADO.** (SOs, POs, pagamentos, parcelas e FinancialRecords permanecem exatamente como na Etapa 6C.) Aguardando autorização explícita para corrigir as datas.
