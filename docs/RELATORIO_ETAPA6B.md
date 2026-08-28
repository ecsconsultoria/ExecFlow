# ETAPA 6B — RELATÓRIO DE INVESTIGAÇÃO DE NEGÓCIO DOS 21 FRs EM REVISÃO

**Data**: 28/08/2026 — **Modo**: 100% somente leitura (nenhum UPDATE/DELETE/INSERT/restore/backfill/migration). **Commit**: ver `git log -1` (apenas documentação).

---

## A. 21 registros analisados

21/21 analisados individualmente com evidências de: pagamento, SO/PO, faturamento, itens, datas de serviço/entrega, recibos, auditoria completa (quem/quando/sequência) e alterações posteriores.

## B. Tabela individual

| FR | Tipo | Valor | Reference | Pago | SO/PO | Faturado | Serviço evidenciado | Cancelado? | Estornado? | Exclusão explicada? | Classificação | Recomendação |
|---|---|---:|---|---|---|---|---|---|---|---|---|
| 1 | rev | 450,00 | order_payment:1 | 01/06 | SO-260601-001 | sim | delivery 02/06 + closed + invoice | não | não | sim (audit, user 1, 02/06) | **A** | restaurar |
| 2 | rev | 450,00 | order_payment:2 | 01/06 | SO-260601-001 | sim | idem | não | não | sim | **A** | restaurar |
| 3 | cost | 550,00 | po_payment:1 | 01/06 | PO-260601-002 → SO-260601-001 | sim (PO) | SO delivery + closed | não | não | sim | **A** | restaurar |
| 5 | rev | 13.500,00 | order_payment:3 | 29/05 | SO-260601-003 | sim | closed + invoice | não | não | sim | **A*** | restaurar (com correção de status) |
| 6 | cost | 7.000,00 | po_payment:3 | 01/06 | PO-260601-004 → SO-260601-003 | sim (PO) | SO closed | não | não | sim | **A** | restaurar |
| 8 | rev | 13.500,00 | order_payment:4 | 02/06 | SO-260602-001 | sim | delivery 10/05 + closed + invoice | não | não | sim | **A** | restaurar (data a revisar) |
| 12 | rev | 13.500,00 | order_payment:7 | 02/06 | SO-260602-005 | **não** | delivery 15/05 + closed | não | não | sim | **A** | restaurar (sem fatura formal) |
| 13 | rev | 13.500,00 | order_payment:8 | 29/05 | SO-260602-006 | sim | delivery 14/05 + closed + invoice | não | não | sim | **A** | restaurar |
| 14 | rev | 13.500,00 | order_payment:9 | 29/05 | SO-260602-007 | sim | delivery + closed + invoice | não | não | sim | **A** | restaurar |
| 15 | rev | 13.500,00 | order_payment:10 | 29/05 | SO-260602-008 | **não** | closed | não | não | sim | **A** | restaurar (sem fatura formal) |
| 16 | rev | 13.500,00 | order_payment:11 | 02/06 | SO-260602-009 | sim | delivery 02/05 + closed + invoice | não | não | sim | **A** | restaurar |
| 17 | rev | 13.500,00 | order_payment:12 | 29/05 | SO-260602-010 | sim | closed + invoice | não | não | sim | **A** | restaurar |
| 18 | rev | 13.500,00 | order_payment:13 | 29/05 | SO-260602-011 | sim | closed + invoice | não | não | sim | **A** | restaurar |
| 19 | rev | 13.500,00 | order_payment:14 | 29/05 | SO-260602-012 | sim | delivery 29/05 + closed + invoice | não | não | sim | **A** | restaurar |
| 20 | rev | 10.000,00 | order_payment:15 | 03/06 | SO-260602-013 | sim | closed + invoice | não | não | sim | **A** | restaurar |
| 21 | rev | 900,00 | order_payment:16 | 03/06 | SO-260602-014 | sim | closed + invoice | não | não | sim | **A** | restaurar |
| 22 | rev | 13.500,00 | order_payment:17 | 29/05 | SO-260602-015 | sim | delivery + closed + invoice | não | não | sim | **A** | restaurar |
| 23 | rev | 13.500,00 | order_payment:18 | 03/06 | SO-260602-016 | sim | delivery + closed + invoice | não | não | sim | **A** | restaurar |
| 24 | rev | 13.500,00 | order_payment:19 | 29/05 | SO-260602-017 | sim | delivery 14/05 + closed + invoice | não | não | sim (via painel financeiro) | **A** | restaurar |
| 26 | cost | 7.000,00 | po_payment:8 | 29/05 | PO-260602-004 → SO-260602-018 (concluído) | sim (PO) | SO closed | não | não | sim | **A** | restaurar |
| 27 | cost | 2.500,00 | po_payment:9 | 01/06 | PO-260602-004 → SO-260602-018 (concluído) | sim (PO) | SO closed | não | não | sim | **A** | restaurar |

\* id 5: FR com status "pendente" apesar da parcela paga (anomalia do fluxo antigo).

## C. Evidências encontradas

- **Auditoria completa de todos**: sequência Criado → Parcelas geradas → Aberto → Faturado → Parcela baixada → Excluído, sempre pelo usuário 1, em datas 01–02/06/2026 (uma em 15/06).
- **16 de 17 SOs com faturamento** (`invoiced_at`) e `closed_at` preenchido em todos.
- **9 SOs com `delivery_datetime`** (data de serviço) e itens de serviço registrados em todos.
- **Nenhum `cancelled_at`** em qualquer SO/PO dos 21. **Nenhum estorno** em auditoria. **Nenhuma alteração após a exclusão** (updated_at ≤ momento da exclusão).

## D. Motivo da exclusão

Padrão consistente: as exclusões foram **administrativas** (executadas minutos/horas após o registro do pagamento, pelo mesmo usuário administrador) — compatível com limpeza/reescrita do ambiente de teste, **não** com cancelamento de serviço: não há eventos de cancelamento, estorno ou devolução em nenhum dos 21. Dois casos via painel financeiro (cascade, ex. FR 24 → SO-260602-017). As RFQs vinculadas também foram excluídas (limpeza em cadeia).

## E. Classificação de negócio

- **Grupo A (SERVIÇO REALIZADO / PAGAMENTO REAL): 21/21 — R$ 204.350,00**
- Grupo B (cancelado/estornado): **0**
- Grupo C (incerto): **0**
- Grupo D (outra): **0**

## F. Candidatos fortes à restauração

**Todos os 21** — pagamento real registrado, serviço evidenciado (fatura/delivery/closed), nenhum cancelamento ou estorno.

## G. Casos cancelados

Nenhum.

## H. Casos incertos

Nenhum. (Observações menores: ids 12 e 15 não têm faturamento formal — baixa direta; id 5 tem status divergente; ids 8/12 têm data do FR divergente da parcela.)

## I. Valores por grupo

| Grupo | Qtd | Valor |
|---|---|---|
| A | 21 | R$ 204.350,00 (receita 187.300,00 + custo 17.050,00) |
| B | 0 | R$ 0,00 |
| C | 0 | R$ 0,00 |
| D | 0 | R$ 0,00 |
| **Total** | **21** | **R$ 204.350,00** |

## J. Impacto hipotético no Caixa (se Grupo A fosse restaurado)

Entradas **+R$ 187.300,00** e saídas **+R$ 17.050,00** no Caixa Realizado (movimentos reais hoje ausentes). Sem duplicação (references únicas). **NÃO executado.**

## K. Impacto hipotético na DRE

**R$ 0,00** — as fontes da DRE são Orders/POs (excluídas permanecem fora); os FRs restaurados não alteram competência. **NÃO executado.**

## L. Impacto hipotético no AR

**R$ 0,00** — todos os 21 são pagos. **NÃO executado.**

## M. Impacto hipotético no AP

**R$ 0,00** — os custos são pagos. **NÃO executado.**

## N. ID 5

- FR: `revenue`, R$ 13.500,00, status **pendente**, `paid_date` 29/05, soft-deletado.
- Parcela `order_payment:3`: **paga** (29/05, R$ 13.500,00) — pagamento real.
- Não há FR ativo para a parcela; não há duplicata.
- Conclusão: o fluxo antigo gravou `paid_date` mas não atualizou o status para "pago" (anomalia pontual). Recomendação: restauração **com correção de status para "pago"** — altera campo histórico e requer sua autorização específica (o script de restauração atual preserva o status; a correção seria uma ação explícita à parte).

## O. IDs 8/12 (divergência de data)

- id 8: FR `paid_date` 29/05; parcela paga em **02/06 20:08**. id 12: FR 29/05; parcela **02/06 20:53**.
- O evento real (baixa) é a data da parcela (02/06) — o FR foi criado com data manual retroativa informada no formulário.
- Recomendação: se restaurados, considerar a data da parcela como referência de caixa (a DRE/Caixa usam `paid_date` do FR — divergência de 4 dias; decisão sua sobre qual data prevalece; nenhuma data será alterada sem autorização).

## P. IDs 12/15 (SO sem faturamento)

- id 12: SO-260602-005 — `invoiced_at` NULL, porém `delivery_datetime` 15/05 + `closed_at` + baixa em 02/06 → **evidência de serviço realizado** (baixa direta sem faturar).
- id 15: SO-260602-008 — sem fatura e sem delivery, apenas `closed_at` + item de serviço + baixa → evidência mais fraca, mas pagamento real e sem cancelamento.
- Recomendação: restauráveis como recebimento (Grupo A), mantendo a observação de que o faturamento formal não ocorreu (decisão sua se isso impede a restauração — recomendação: não impede, pois o recebimento é fato).

## Q. Pendências

1. **Sua decisão sobre a restauração do Grupo A** (21 registros, R$ 204.350,00) — com as ressalvas pontuais dos ids 5, 8, 12 e 15.
2. Correção de status do id 5 (se autorizada).
3. Os 6 NÃO RESTAURAR permanecem como estão.
4. PO-260602-005 e FR id45: pendência separada (não tocados).
5. Dump do PostgreSQL de produção antes de qualquer deploy.

---

## Dados alterados

- SO alterados: **ZERO** · POs alterados: **ZERO** · Pagamentos alterados: **ZERO** · FinancialRecords alterados: **ZERO** · Banco alterado: **ZERO** · Restaurações executadas: **ZERO**

🟢 **ETAPA 6B CONCLUÍDA — ANÁLISE DE NEGÓCIO DOS 21 REGISTROS**

Nenhuma restauração executada. Aguardando sua análise do relatório — não prosseguirei para a Etapa 7 sem sua autorização explícita.
