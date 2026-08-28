# ETAPA 9A — RELATÓRIO DE ANÁLISE (Caixa Previsto + Saldo Inicial — SOMENTE ANÁLISE)

**Data**: 28/08/2026 — **Modo**: 100% somente leitura. **NENHUM dado alterado.** **Commit**: ver `git log -1` (documentação).

---

## A. Caixa atual (preservado — Etapa 4)

Tela `/financial/cash-flow`: entradas = FR `revenue` **pago**; saídas = FR `cost`/`expense` **pago**; âncora = `paid_date`; cards Entradas/Saídas/Saldo do Período/Saldo Final (com aviso "saldo inicial não configurado"). Previsto atual = 2 cards informativos (A receber / A pagar).

## B. Fonte do realizado

`FinancialRecord` (`status='pago'` + `paid_date`) — `cash_flow_service.realized_entries`. Valor atual: R$ 275.606,00 pagos totais (230.076 entradas + 45.530 saídas).

## C. Fonte do previsto (proposta — estrutura JÁ EXISTE)

**`ar_ap_service` da Etapa 8B** (fonte única de obrigações):
- Entradas previstas = `receivable_rows` (parcela válida não recebida).
- Saídas previstas = `payable_rows` (POPayment válida não paga + FR expense pendente).
- Âncora = **`due_date`** (nunca paid_date para não-realizados).

Valores atuais: AR 3.640,00 · AP 16.150,00 (PO) + 0,00 (despesas) · **previsão líquida de obrigações = −R$ 12.510,00**.

## D. Entradas previstas

Parcelas válidas, não recebidas, não canceladas, SO não excluído, com due_date. Exclui: pagas, canceladas, excluídas.

## E. Saídas previstas

A) POPayment válida não paga (inclui **PO não faturada** — regra 8B preservada); B) FR `expense` pendente. Exclui: pagos, cancelados, soft-deletados.

## F. Transição previsto → realizado

Por construção, sem sobreposição: a obrigação aparece no previsto **enquanto não paga** (parcela/expense pendente) e passa ao realizado **quando paga** (FR pago, espelho 1:1 pela mesma `reference`). Ex.: parcela R$ 10.000 → previsto 10.000/realizado 0 → após baixa: previsto 0/realizado 10.000. A baixa atômica (Etapa 2) garante a troca no mesmo evento.

## G. Duplicidade

Nenhuma: previsto lê parcelas/expenses pendentes; realizado lê FRs pagos — o mesmo evento nunca é somado nas duas visões; `reference` única (índice parcial UNIQUE).

## H. Saldo inicial

**Não existe estrutura** de saldo de abertura. O que existe e é **aproveitável sem migration**: `companies.settings` (coluna JSON, hoje NULL) — recomendação: gravar `{"cash_initial_balance": <valor>, "cash_initial_date": <data>}` por empresa, com tela de configuração (Financeiro → Configurações) e auditoria. **Nunca inferir** o saldo do acumulado atual.

## I. Saldo final

- **Saldo Realizado** = inicial + entradas realizadas − saídas realizadas.
- **Saldo Previsto** = inicial + entradas previstas − saídas previstas (obrigações futuras).
- **Saldo Projetado** = inicial + realizado do período + previsto futuro − saídas previstas futuras.
Interface separa os três conceitos (nunca rotular projeção como saldo bancário real).

## J. Multiempresa

Tudo por `company_id` (services 8B/4 já filtram); saldo inicial por empresa no próprio `settings`.

## K. RBAC

Inalterado: `login_required` para ver; `financial.manage` para configurar o saldo inicial.

## L. Performance

Previsto reusa `ar_ap_service` (2 queries simples por bloco) — **sem N+1 novo**. Visão diária (item 14) recomendada para etapa futura: agregação por dia de `paid_date` (realizado) e `due_date` (previsto) com uma query agrupada por dia — barata, sem mudança de arquitetura.

## M. Estrutura existente aproveitável

`cash_flow_service.realized_entries/split_movements/movement_info` · `ar_ap_service.receivable_rows/payable_rows/totals` · `companies.settings` (JSON) · `_financial_period_bounds` (hoje/7d/30d/mês/mês anterior/trimestre/ano/custom).

## N. Estrutura que eventualmente será necessária

**Nenhuma migration prevista** — saldo inicial cabe no JSON existente. Futuro distante (se precisar de extrato com saldo por dia auditável): tabela de saldo de abertura com histórico de revisões (só com autorização específica).

## O. Impacto

Zero no banco/schema; impacto visual na tela de Caixa (novos cards + configuração de saldo). DRE, AR, AP e Caixa realizado **inalterados**.

## P. Ordem recomendada de implementação (Etapa 9B)

1. Configuração do saldo inicial via `companies.settings` (rota + formulário + auditoria; RBAC financial.manage).
2. Tela de Caixa: cards Saldo Inicial / Entradas e Saídas Realizadas / Saldo Realizado / Entradas e Saídas Previstas / Saldo Projetado — consumindo os serviços existentes.
3. Filtros: adicionar "mês seguinte" ao helper de períodos (extensão pequena).
4. Visão diária (opcional, depois).
5. Testes cobrindo: transição previsto→realizado, sem duplicidade, saldo inicial por empresa, isolamento multiempresa, RBAC.

---

## Regressão

Suíte completa: **mesmas 6 falhas pré-existentes** — nenhuma nova (Etapas 2–8B verdes).

**Nenhum banco, migration, dado, SO, PO, pagamento, FR, AR ou AP foi alterado.**

🟢 **ETAPA 9A CONCLUÍDA — ARQUITETURA DO CAIXA PREVISTO ANALISADA**

PARADO — aguardando autorização explícita para a implementação (Etapa 9B).
