# ETAPA 8A — RELATÓRIO DE AUDITORIA AR/AP (SOMENTE ANÁLISE)

**Data**: 28/08/2026 — **Modo**: 100% somente leitura. **NENHUM dado alterado.** **Commit**: ver `git log -1` (documentação).

---

## A. Arquitetura atual

**Duas camadas coexistem** (definição das Etapas 1–2, preservada):
1. **Parcela operacional**: `OrderPayment` (SO) / `POPayment` (PO) — obrigação, vencimento, baixa.
2. **Ledger**: `FinancialRecord` — espelho 1:1 por `reference` (`order_payment:N` / `po_payment:N`), + `type='expense'` (despesas, sem parcela) + manuais. Índice parcial UNIQUE garante referência única entre ativos.

## B. AR atual — três visões

| Tela | Fonte | Regra | Valor atual (ago/2026) |
|---|---|---|---|
| Dashboard "Recebimentos Pendentes" | `OrderPayment` não paga, SO não excluído/cancelado, **due_date no período** | parcela | R$ 3.640,00 (parcela 36, venc. 10/08) |
| Painel Financeiro "A Receber" | FR `revenue` `pendente` por **ref_date** (coalesce emission/paid/created) no período | ledger | **R$ 0,00** em agosto (FR 53 tem emission 29/07 → julho) |
| Painel "Recebimentos" (receivables.html) | FR `revenue` pendente (sem período p/ total pendente) + recebidos por `paid_date` | ledger | pendente total 3.640 |
| Relatórios | FR `revenue` **pago** por `paid_date` | caixa | — |

**Divergência concreta**: em "Este mês", o Dashboard mostra **A Receber R$ 3.640** e o painel financeiro mostra **R$ 0** — o primeiro ancora no **vencimento** (10/08), o segundo na **competência** (emission 29/07). Mesma divergência existe em AP (ver C).

Regras atuais (corretas por etapa): faturado ≠ recebido; parcela paga = `paid_at` preenchido; vencida = `due_date < hoje` e não paga; cancelada/excluída fora das listas.

## C. AP atual — três fontes, três números

| Fonte | Regra | Valor atual |
|---|---|---|
| Dashboard "Pagamentos Pendentes" | `POPayment` não paga, PO não excluída/cancelada, due_date no período | R$ 6.600,00 (parcela 20, venc. 27/08) |
| Painel Financeiro "A Pagar" | FR `type='cost'` pendente por ref_date no período (**exclui expense**) | **R$ 0,00** em agosto (FRs 54/55 com emission 15/06) |
| Tela de Despesas | FR `type='expense'` pendente | R$ 0,00 (nenhuma despesa cadastrada) |

**Lacunas conhecidas**:
1. **PO aberta não faturada com parcela** (po_payment:18, R$ 2.950, venc. 20/07) não tem FR → aparece no Dashboard (se no período), **nunca** no painel financeiro (FR só nasce no faturamento).
2. **Despesas pendentes** não entram no card "A Pagar" do painel (por design da Etapa 3B — separadas), então AP não é unificado.
3. Parcelas de ordens excluídas (ids 24/33/34 e 4/5/6/12) ficam de fora das visões (correto — ordens excluídas).

## D. Fontes de dados (matriz)

| Indicador | Fonte oficial | Data usada | Status considerado |
|---|---|---|---|
| Receita | `Order` faturada | `invoiced_at` | faturado/concluído c/ fatura |
| Recebimento | FR revenue pago | `paid_date` | pago |
| **AR** | parcela + FR espelho | vencimento (dashboard) × ref_date (painel) | pendente |
| Custo | PO válida vinculada a SO | competência (service_date→delivery→created) | ≠ rascunho/cancelado/excluído |
| **AP** | parcela + FR espelho; despesa = FR expense | vencimento × ref_date × emissão | pendente |
| Despesa | FR `expense` | `emission_date` | ≠ cancelado |
| Caixa | FR pago | `paid_date` | pago |
| DRE | Orders + POs + expenses | competência | conforme Etapa 5 |

## E. Regras atuais (consolidadas e preservadas)

- Receita só com faturamento efetivo (Etapa 2) · DRE por competência (Etapa 5) · Caixa só realizado (`status=pago` + `paid_date`, Etapa 4) · custo = PO válida vinculada (Etapa 2/5) · despesa = `expense` (3B) · cancelados/soft-deletados fora dos indicadores · void preserva pagos (Etapa 2).

## F. Divergências encontradas

1. **Âncora de data diferente entre telas para o mesmo indicador**: AR/AP do Dashboard usam **vencimento**; painel financeiro usa **ref_date (competência)** — mesmo mês exibe valores diferentes (ex.: agosto A Receber 3.640 × 0; A Pagar 6.600 × 0).
2. **PO aberta com parcela vencida fora do ledger** (po_payment:18, R$ 2.950) — invisível no painel financeiro.
3. **AP não unificado**: custos de PO (FR cost) e despesas (FR expense) em telas separadas, sem total único.
4. Relatórios mostram caixa (paid_date) rotulados como receita/custos do mês — semântica distinta do painel.
5. Card "A Pagar" do painel exclui expense por design — documentar no futuro rótulo ("Custos de PO a pagar").

## G. Duplicidades potenciais

- **Nenhuma duplicidade ativa** (índice parcial UNIQUE + espelho 1:1). Risco residual apenas em race de POST duplo — mitigado pelo índice no banco.
- Nenhuma tela soma parcela + FR ao mesmo tempo para o MESMO indicador (dashboard usa parcela; painel usa FR) — por isso os números divergem, mas **não somam em dobro**.

## H. Multiempresa

Todas as queries filtram `company_id` (testado nas Etapas 3A/3B/4/5: 404 e listas sem vazamento). Ordem/pagamento/FR/expense: ok.

## I. RBAC

- Mutações (criar/editar/pagar/cancelar FR e despesas; catálogo): `@require_permission("financial.manage")`.
- Visões (painel financeiro, AR, AP, caixa, DRE): `@login_required` (leitura aberta a usuários logados).
- Relatórios: `reports.view`. Sem novo mecanismo (padrão preservado).

## J. Performance

- Dashboard/painéis: poucas queries por rota — ok.
- **N+1 identificado (não otimizar agora)**: `cash_flow_service.movement_info` resolve ordem/PO por entrada (uma query por movimento); `dre_service.direct_cost_rows` acessa `po.order` e `po.items` lazy. Volumes atuais pequenos; documentado para etapa de otimização.
- Sem cálculos pesados em template (cálculos nas funções centrais desde a Etapa 2).

## K. Arquitetura recomendada (única, sem tabela paralela)

```
AR:  Receita faturada (Order, invoiced_at)
       → Parcela (OrderPayment = obrigação operacional)
       → FR espelho (reference única = ledger)
       → Recebimento (baixa: parcela + FR, atômico)
       → Caixa (FR pago, paid_date)

AP:  Custos de serviços (PO válida vinculada a SO)
       → POPayment (obrigação)
       → FR cost espelho
       → Pagamento (baixa atômica)
       → Caixa
     +
     Despesas Gerais (FR expense, categoria+centro, sem parcela)
       → AP próprio (FR pendente)
       → Pagamento (baixa_record atômico)
       → Caixa
```

- **Fonte oficial única por indicador**: obrigação = parcela (espelhada no FR); caixa = FR pago. Um movimento = uma origem (`reference`).
- **Unificar âncoras de período**: AR/AP por **vencimento** em todas as telas de obrigação; recebido/pago por **paid_date**; DRE por competência. (Decisão de produto: dashboard já usa vencimento; alinhar o painel.)
- **AP unificado**: apresentar AP = Custos de PO (FR cost pendente) + Despesas (FR expense pendente) com quebra por origem, sem misturar telas.

## L. Mudanças necessárias (para etapa de implementação)

1. Padronizar âncora de período do painel financeiro (ref_date → due_date) para AR/AP — alinha com o dashboard (baixo risco, sem migration).
2. Incluir `type='expense'` no total de AP do painel (com quebra "Custos" × "Despesas") — sem migration.
3. Nascer o FR pendente de PO **no vencimento/geração de parcela** (não só no faturamento) — corrige a lacuna do po_payment:18 (mudança de lógica; requer decisão de negócio).
4. Rotular relatórios como "Caixa do mês (recebido/pago)" — cosmético.
5. (Futuro) eliminar N+1 do caixa/DRE.

## M. Risco de cada mudança

| Mudança | Risco |
|---|---|
| 1. Âncora due_date no painel | Baixo — só leitura; números mudam de tela, sem dado alterado |
| 2. Expense no AP | Baixo — agregação; sem dado alterado |
| 3. FR na geração de parcela | Médio — cria FRs novos em fluxos existentes; exige teste com PO não faturada |
| 4. Rótulos | Nulo |
| 5. Performance | Baixo (join/selectinload) |

## N. Ordem recomendada de implementação

1 → 2 → 4 (cosméticos e alinhamento, sem migration) → 5 (performance) → 3 (regra de negócio, com aprovação específica).

---

## Regressão

Suíte completa executada: **mesmas 6 falhas pré-existentes** — nenhuma nova (Etapas 2, 3A, 3B, 4, 5, 6, 6C, 6E, 7E verdes).

**Nenhum dado, model, rota, template ou migration foi alterado.**

🟢 **ETAPA 8A CONCLUÍDA — AR/AP AUDITADOS**

PARADO — aguardando autorização explícita para a implementação da próxima etapa.
