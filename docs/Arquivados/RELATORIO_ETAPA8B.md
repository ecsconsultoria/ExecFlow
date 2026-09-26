# ETAPA 8B — RELATÓRIO FINAL (AP/AR Unificados)

**Data**: 28/08/2026 — **Commit**: ver `git log -1` (sem push — deploy segue o fluxo normal da branch `v3`)

---

## A. Backup

`backup/DB_V2_pre-etapa8b-20260828.db` — criado antes das alterações (API nativa do SQLite). Backups anteriores **não sobrescritos**.

## B. Checkpoint

Branch `v3`, commit de entrada `d336400`, working tree limpo, alembic head `c4d2e9f0a1b5`, `integrity_check` ok.

## C. Tag

**`v3-pre-etapa8b-ap-ar-20260828`**

## D. Regra final do AR

**A Receber = OrderPayment válida (SO não excluído/cancelado) NÃO recebida, organizada por `due_date`.** Faturado ≠ A Receber ≠ Recebido. Recebido = pagamento efetivo (caixa por `paid_date`). Vencido = `due_date < hoje` e não recebido.

## E. Regra final do AP

**A Pagar = (A) Custos de Serviços (POPayment válida não paga) + (B) Despesas Gerais (FR `expense` pendente), organizadas por `due_date`.** Canceladas fora; pagas fora do saldo (histórico/caixa). Total = Custos + Despesas, sem duplicação.

## F. Custos de Serviços

Regra da Etapa 2 preservada (PO válida vinculada a SO); a obrigação usa a parcela (`POPayment.due_date`). PO/pagamentos/status **não alterados**.

## G. Despesas Gerais

FR `type='expense'` pendente entra no AP (por `due_date`); cancelada fora; paga fora do saldo. Nenhum FR novo é gerado nesta etapa (regra 13 preservada).

## H. Dashboard

Cards de AR/AP agora consomem **`ar_ap_service`** (mesma função central das telas) — nenhuma regra paralela. Ex.: agosto/2026 → A Receber R$ 3.640 (venc. 10/08), A Pagar R$ 6.600 (venc. 27/08), com origem "PO"/"Despesa" exibida.

## I. Painel Financeiro

Cards "A Receber"/"A Pagar" passam a usar **due_date** (antes ref_date) — **divergência da Etapa 8A eliminada**: mesmo período e empresa agora mostram os mesmos valores em Dashboard e Painel. Tela AP com quebra **Custos de Serviços × Despesas Gerais × Total**; tela AR com pendente por parcela (due_date) e recebido por paid_date.

## J. Filtros

Período = **período de vencimento** (`due_date` entre início/fim) para A Receber/A Pagar/Vencido; recebido/pago do período = **paid_date** (caixa). Competência continua exclusiva da DRE.

## K. Duplicidade

Cada obrigação aparece uma única vez (parcela ou despesa); POPayment e FR **não** são somados juntos; índice parcial UNIQUE preservado. Testado.

## L. Multiempresa

Todas as funções filtram `company_id`; teste confirma zero vazamento (Empresa A não vê obrigações da B).

## M. RBAC

Inalterado: `financial.manage` (mutações), `financial.view` (telas AR/AP), `reports.view`, `login_required`.

## N. Testes

`tests/test_ar_ap_etapa8b.py` — 5 testes cobrindo os 14 casos obrigatórios: AR por due_date; AP por due_date; vencido; recebido/pago por paid_date; despesa no AP; despesa cancelada fora; custo de PO no AP; zero duplicidade; Dashboard = Painel (mesma função); multiempresa; Caixa inalterado; DRE inalterada.

## O. Regressão

Suíte completa: **mesmas 6 falhas pré-existentes** (`test_decorators_and_audit.py`) — nenhuma nova (Etapas 2, 3A, 3B, 4, 5, 6, 6C, 6E, 7E, 8B verdes).

## P. Integridade

`integrity_check` ok · sem migration (schema inalterado) · **banco IDÊNTICO ao backup pré-8B** (todas as 17 tabelas conferidas, incluindo `financial_records`).

## Q. Dados históricos

SO: **ZERO** · PO: **ZERO** · pagamentos: **ZERO** · parcelas: **ZERO** · FinancialRecords: **ZERO** — somente código/interface alterados.

## R. Pendências

1. **FR de AP para PO não faturada** (parcela po_payment:18, R$ 2.950, venc. 20/07): agora visível no AP unificado (via parcela), mas ainda **sem espelho no ledger** — geração de FR na criação da parcela fica para etapa específica (regra 13 desta etapa).
2. N+1 documentados no Caixa/DRE (não expandidos).
3. Dump do PostgreSQL de produção antes do deploy.
4. PO-260602-005 (Pronampe): fora da DRE — decisão pendente (Etapa 7C).

---

🟢 **ETAPA 8B CONCLUÍDA — AP/AR UNIFICADOS**

Caixa inalterado · DRE inalterada · dados históricos preservados. PARADO — aguardando autorização explícita para a próxima etapa.
