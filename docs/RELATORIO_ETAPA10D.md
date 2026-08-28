# ETAPA 10D — RELATÓRIO FINAL (Correção da Baixa/Recebimento Parcial)

**Data**: 28/08/2026 — **Commit**: ver `git log -1` (sem push — deploy segue o fluxo normal da branch `v3`)

---

## A. Backup

`backup/DB_V2_pre-etapa10d-20260828.db` — criado antes das alterações (API nativa do SQLite). Backups anteriores **não sobrescritos**.

## B. Checkpoint

Branch `v3`, commit de entrada `0898378`, working tree limpo, alembic head `c4d2e9f0a1b5`, `integrity_check` ok. Tag: **`v3-pre-etapa10d-baixa-parcial-20260828`**.

## C. Causa raiz

`order_service.baixa()` tratava `paid_amount` como **valor total** (atribuição direta `payment.paid_amount = paid_amount`), e a rota usava o total da parcela como default. Consequências: (1) segunda baixa **sobrescrevia** o acumulado (1.300 → 800); (2) o FR espelho recebia o último valor (perdendo o histórico); (3) a auto-conclusão do SO nunca disparava (soma das parcelas < total); (4) o AR ignorava a parcela parcial (filtro `paid_at IS NULL`) — o saldo restante sumia do A Receber.

## D. Correção

1. **`order_service.baixa` — semântica INCREMENTAL**: `paid_amount` é **somado** ao já recebido (`new_total = paid_amount_atual + recebido`); nunca sobrescreve.
2. **Validações**: recebimento ≤ 0 rejeitado; exceder o **saldo restante** rejeitado (mensagem com o saldo); parcela **já quitada** rejeitada (protege retry/double-click — idempotência por bloqueio).
3. **Rota** (`/orders/payments/<pid>/baixa`): default sem valor = **`pmt.balance`** (saldo restante, não o total); auditoria agora inclui o valor de cada baixa ("Parcela N baixada R$ X").
4. **`ar_ap_service.receivable_rows`**: parcela **parcialmente paga** entra no AR com o **saldo** (`balance`), não com o total; quitadas ficam fora.
5. **FR espelho**: um por parcela, `amount` = **total acumulado recebido** — o Caixa soma o recebido correto e nunca duplica (reference única + índice parcial UNIQUE preservados).

## E. Regra de recebimento parcial

0 < recebido < parcela → parcela permanece aberta/parcial (`is_paid = balance > 0` — false), saldo exibido no AR · recebido == parcela → **PAGO** (`balance == 0`) · excedente → **bloqueado**.

## F. FinancialRecord

Sem migration; espelho 1:1 preservado com `amount` acumulado; histórico de cada recebimento fica no `audit_logs` (valor + data + usuário). Nenhuma baixa nova destrói a anterior.

## G. OrderPayment

`paid_amount` acumulado; `paid_at` atualizado para a data do último recebimento; `balance`/`is_paid` derivam corretamente.

## H. AR

Antes: 1.300 → após 500: **800** → após 800: **0** (testado por unit e ao vivo).

## I. Caixa

Após 500: +500 · após 800: **+1.300 acumulado** (nunca 800 nem 1.800) — validado ao vivo.

## J. DRE

**Inalterada** em todas as fases (receita por `invoiced_at`) — testado explicitamente antes/depois de cada baixa.

## K. Dashboard

Consistente (consome dre_service/ar_ap_service corrigidos); caixa mostra 1.300 após quitação.

## L. Auditoria

Cada baixa gera "Parcela N baixada R$ X" com usuário/timestamp; retry bloqueado não gera lançamento.

## M. SO

Auto-conclusão voltou a funcionar: parcela quitada + SO faturado → `concluido` (validado ao vivo). Regra existente preservada (sem status novo).

## N. Testes

`tests/test_baixa_parcial_etapa10d.py` — 7 testes: cenário principal 500+800; três parciais 300/400/600; excesso bloqueado sem alterar nada; retry/duplicidade bloqueado; integral + zero bloqueado; rollback em erro; RBAC (403) e multiempresa (403, sem vazamento). Dois testes antigos atualizados para a nova semântica (Etapa 2 re-baixa agora bloqueada; Etapa 9B usa parcela pendente).

## O. Idempotência

Re-baixa de parcela quitada → **bloqueada** com mensagem ("já quitada"); nenhuma alteração de estado; 1 FR apenas.

## P. Rollback

Falha no recálculo de margem → transação revertida (parcela 0, sem FR) — testado.

## Q. Multiempresa / R. RBAC

Parcela de outra empresa: acesso negado (403 — sem vazamento) · operador sem `financial.manage`: 403 · testado.

## S. Regressão

Suíte completa: **mesmas 6 falhas pré-existentes** (`test_decorators_and_audit.py`) — nenhuma nova (Etapas 2, 3A, 3B, 4, 5, 6, 6C, 6E, 7E, 8B, 9B, 10B, 10C, 10D verdes).

## T. Integridade

`integrity_check` = ok · sem migration · **19 tabelas IDÊNTICAS ao backup pré-10D** (incluindo `audit_logs` — limpeza cirúrgica dos registros de teste, que reutilizaram ids do autoincrement).

## U. Dados históricos

**ZERO alterações**: SOs, POs, OrderPayments, POPayments, FinancialRecords, pagamentos, parcelas históricos intactos (contagens 40/32/55/36/17). FR28/Pronampe, FR45 e os 6 soft-deletados: **não tocados**. A correção afeta apenas o comportamento **futuro**.

## V. Resultado

🟢 **ETAPA 10D CONCLUÍDA — BAIXA PARCIAL CORRIGIDA**

Critérios de aprovação verificados (unit + validação ao vivo no servidor):
✓ 1.300 = 500 + 800 corretamente · ✓ nenhum valor sobrescrito · ✓ saldo/AR corretos · ✓ Caixa 1.300 acumulado · ✓ DRE inalterada · ✓ Dashboard consistente · ✓ sem duplicidade · ✓ excesso bloqueado · ✓ retry bloqueado · ✓ auditoria · ✓ rollback · ✓ multiempresa · ✓ RBAC · ✓ histórico intacto · ✓ suíte sem novas falhas.

*Observação documentada (fora do escopo): a rota `financial.baixa_record` (painel) mantém a semântica antiga para FRs; e `purchase_order_service.baixa` idem — especificamente preservados pela Etapa 10D (seção 18 do pedido). Corrigir esses dois pontos exigiria etapa própria com autorização.*

PARADO — aguardando autorização explícita para a próxima etapa.
