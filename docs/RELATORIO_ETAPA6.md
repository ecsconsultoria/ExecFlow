# ETAPA 6 — RELATÓRIO FINAL (Reconciliação e Restauração Controlada dos FRs Históricos)

**Data**: 28/08/2026 — **Commit**: ver `git log -1` (sem push — deploy segue o fluxo normal da branch `v3`)

---

## A. Backup

`backup/DB_V2_pre-etapa6-20260828.db` — criado antes de qualquer alteração (API nativa do SQLite). Backups anteriores **não sobrescritos**.

## B. Checkpoint

Branch `v3`, commit de entrada `44bc827`, working tree limpo, alembic head `c4d2e9f0a1b5`, `integrity_check` ok.

## C. Tag

**`v3-pre-etapa6-reconciliacao-financial-records-20260828`**

## D. Quantidade de FR analisados

**27/27** — um a um, somente leitura (FASE A), com verificação de: parcela existente, SO/PO existente, faturamento, valor igual ao pago, pagamento efetivo, data do pagamento, duplicata ativa, status e campos ausentes.

## E. Tabela individual dos 27

| FR | Tipo | Valor | Reference | Pagamento | SO/PO | Dup? | Situação | Ação |
|---|---|---:|---|---|---|---|---|---|
| 1 | revenue | 450,00 | order_payment:1 | pago (450) | SO-260601-001 excluído, faturado | não | origem excluída | REVISÃO |
| 2 | revenue | 450,00 | order_payment:2 | pago (450) | SO-260601-001 excluído, faturado | não | origem excluída | REVISÃO |
| 3 | cost | 550,00 | po_payment:1 | pago (550) | PO-260601-002 excluída | não | origem excluída | REVISÃO |
| 5 | revenue | 13.500,00 | order_payment:3 | **pago (13.500)** | SO-260601-003 excluído, faturado | não | **status FR pendente com parcela paga** | REVISÃO |
| 6 | cost | 7.000,00 | po_payment:3 | pago (7.000) | PO-260601-004 excluída | não | origem excluída | REVISÃO |
| 7 | cost | 2.500,00 | po_payment:4 | **não pago** | PO-260601-004 excluída | não | não pago | NÃO RESTAURAR |
| 8 | revenue | 13.500,00 | order_payment:4 | pago (13.500) | SO-260602-001 excluído, faturado | não | **data FR 29/05 ≠ parcela 02/06** | REVISÃO |
| 12 | revenue | 13.500,00 | order_payment:7 | pago (13.500) | SO-260602-005 excluído, **sem faturamento** | não | sem fatura + **data divergente** + due ausente | REVISÃO |
| 13 | revenue | 13.500,00 | order_payment:8 | pago (13.500) | SO-260602-006 excluído, faturado | não | origem excluída | REVISÃO |
| 14 | revenue | 13.500,00 | order_payment:9 | pago (13.500) | SO-260602-007 excluído, faturado | não | origem excluída | REVISÃO |
| 15 | revenue | 13.500,00 | order_payment:10 | pago (13.500) | SO-260602-008 excluído, **sem faturamento** | não | sem fatura + due ausente | REVISÃO |
| 16 | revenue | 13.500,00 | order_payment:11 | pago (13.500) | SO-260602-009 excluído, faturado | não | origem excluída | REVISÃO |
| 17 | revenue | 13.500,00 | order_payment:12 | pago (13.500) | SO-260602-010 excluído, faturado | não | origem excluída | REVISÃO |
| 18 | revenue | 13.500,00 | order_payment:13 | pago (13.500) | SO-260602-011 excluído, faturado | não | origem excluída | REVISÃO |
| 19 | revenue | 13.500,00 | order_payment:14 | pago (13.500) | SO-260602-012 excluído, faturado | não | origem excluída | REVISÃO |
| 20 | revenue | 10.000,00 | order_payment:15 | pago (10.000) | SO-260602-013 excluído, faturado | não | origem excluída | REVISÃO |
| 21 | revenue | 900,00 | order_payment:16 | pago (900) | SO-260602-014 excluído, faturado | não | origem excluída | REVISÃO |
| 22 | revenue | 13.500,00 | order_payment:17 | pago (13.500) | SO-260602-015 excluído, faturado | não | origem excluída | REVISÃO |
| 23 | revenue | 13.500,00 | order_payment:18 | pago (13.500) | SO-260602-016 excluído, faturado | não | origem excluída | REVISÃO |
| 24 | revenue | 13.500,00 | order_payment:19 | pago (13.500) | SO-260602-017 excluído, faturado | não | origem excluída | REVISÃO |
| 26 | cost | 7.000,00 | po_payment:8 | pago (7.000) | PO-260602-004 excluída | não | origem excluída | REVISÃO |
| 27 | cost | 2.500,00 | po_payment:9 | pago (2.500) | PO-260602-004 excluída | não | origem excluída | REVISÃO |
| 31 | revenue | 1.100,00 | order_payment:24 | **não pago** | SO-260615-001 excluído | não | não pago | NÃO RESTAURAR |
| 32 | cost | 650,00 | po_payment:12 | **não pago** | PO-260615-001 excluída | não | não pago | NÃO RESTAURAR |
| 34 | revenue | 8.750,00 | order_payment:22 | **parcela inexistente** | — | não | parcela regenerada | NÃO RESTAURAR |
| 43 | revenue | 550,00 | order_payment:33 | **não pago** | SO-260728-001 excluído | não | não pago | NÃO RESTAURAR |
| 44 | revenue | 550,00 | order_payment:34 | **não pago** | SO-260728-001 excluído | não | não pago | NÃO RESTAURAR |

## F. Registros restaurados

**ZERO** — nenhum registro atingiu os critérios de RESTAURAÇÃO SEGURA. Todos os 27 dependem de decisão de negócio (origem excluída) ou estão bloqueados por regra.

## G. Registros não restaurados (NÃO RESTAURAR)

**6** — R$ 14.100,00: 5 parcelas não pagas (ids 7, 31, 32, 43, 44) + 1 parcela inexistente/regenerada (id 34).

## H. Registros pendentes (RESTAURAÇÃO COM REVISÃO)

**21** — R$ 204.350,00 (16 receitas pagas + 1 receita com status divergente + 4 custos pagos). Bloqueador comum: **SO/PO de origem está excluído** — a restauração do lançamento não alteraria SO/PO, mas o histórico pertence a ordens removidas; requer confirmação de que as exclusões foram intencionais. Divergências pontuais adicionais: id 5 (status pendente com pagamento realizado), id 8 e 12 (data do FR ≠ data da parcela), id 12 e 15 (SO sem faturamento + due_date ausente).

## I. Motivo de cada decisão

- **REVISÃO**: origem excluída (todos os 21) + divergências pontuais citadas acima.
- **NÃO RESTAURAR**: regra do pagamento (não pago → não restaurar como realizado) e parcela inexistente (reference órfã de regeneração).
- **SEGURA**: nenhum (qualquer um dos 21 dependeria de confirmar as exclusões; os demais têm bloqueio técnico).

## J. Impacto na DRE

**ZERO** (nenhuma restauração). Impacto potencial se os 21 forem restaurados: **nenhum na DRE** — as fontes da DRE são Orders (excluídas permanecem fora) e POs válidas; os FRs restaurados não alteram competência.

## K. Impacto no Caixa

**ZERO** (nada restaurado). Impacto potencial se os 20 pagos (+ id 5, com correção de status) forem restaurados: **entradas +R$ 173.800,00 e saídas +R$ 17.050,00** no Fluxo de Caixa Realizado (movimentos reais hoje ausentes do caixa), sem duplicação (references únicas).

## L. Impacto no AR

**ZERO**. Potencial: nenhum (os candidatos são pagos; AR não muda).

## M. Impacto no AP

**ZERO**. Potencial: nenhum (os candidatos de custo são pagos; AP não muda).

## N. Testes

`tests/test_restore_financial_records_etapa6.py` — 6 testes: restauração segura preservando ID/valor/datas/status/reference/company; bloqueio por duplicata ativa; bloqueio por parcela não paga; bloqueio por valor divergente e por parcela inexistente; bloqueio por company errada; rollback completo em falha de auditoria.

## O. Regressão

Etapa 2 (7) ✓ · 3A (8) ✓ · 3B (12) ✓ · 4 (7) ✓ · 5 (4) ✓ · 6 (6) ✓ — suíte completa com **as mesmas 6 falhas pré-existentes**, nenhuma nova.

## P. Integridade

`PRAGMA integrity_check` = ok. Alembic head inalterado (`c4d2e9f0a1b5`). Sem migration.

## Q. Dados históricos

Comparação atual × backup pré-Etapa 6: **todas as tabelas protegidas IDÊNTICAS, incluindo `financial_records`** (27 continuam soft-deletados; 0 restaurados).

- SO alterados: **ZERO** · POs alterados: **ZERO** · Pagamentos alterados: **ZERO** · Valores históricos alterados: **ZERO**
- PO-260602-005 e FR id45: **não tocados** · V4: **não tocado**

## R. Pendências

1. **Decisão de negócio sobre os 21 REVISÃO**: confirmar se as exclusões dos 16 SOs e 3 POs foram intencionais. Se sim → manter os FRs deletados (histórico de ordens removidas) ou restaurar os pagos para o Caixa completo (+173.800 / +17.050). Se não → tratar exclusões indevidas.
2. **id 5**: corrigir status para "pago" (divergência) — altera campo histórico; requer autorização específica.
3. **id 34**: órfão de parcela regenerada — descartável (manter deletado).
4. PO-260602-005 / FR id45: classificação futura (etapa própria).
5. Dump do PostgreSQL de produção — pendente desde a Etapa 0.

## S. Recomendação para Etapa 7

1. **Decidir** (com o usuário) sobre os 21 REVISÃO e executar a restauração aprovada com `tools/restore_financial_record.py <id>` (um a um, auditado, transacional).
2. **Deploy** do conjunto Etapas 2–6 (dump de produção antes).
3. **Aposentadoria do V4** + classificação do PO-260602-005/FR id45 (com autorização).

---

🟡 **ETAPA 6 PARCIAL — REVISÃO NECESSÁRIA**

Análise dos 27 completa; **0 restaurações executadas** porque nenhum registro atendeu aos critérios de RESTAURAÇÃO SEGURA sem decisão de negócio (origens excluídas) — nenhum dado foi alterado. Ferramenta de restauração individual, testada e auditada, pronta para uso após sua autorização explícita sobre cada decisão.
