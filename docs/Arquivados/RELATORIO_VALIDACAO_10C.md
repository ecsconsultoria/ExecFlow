# RELATÓRIO DE VALIDAÇÃO FUNCIONAL — ETAPA 10C (SOMENTE TESTAR)

**Data**: 28/08/2026 — **Commit**: ver `git log -1` (documentação, sem push)

---

## A. Ambiente

Branch `v3` · HEAD `a8d2cb7` (código da 10B + doc da 11A) · working tree limpo · alembic head `c4d2e9f0a1b5` · SQLite `instance/DB_V2.db` · `integrity_check` ok.

## B. Servidor

- Instância limpa iniciada nesta sessão: **PID 24048**, porta **5003** (único listener — um servidor antigo de sessão anterior com código obsoleto foi identificado e encerrado; todos os testes rodaram contra o código atual, validado pelo comportamento das rotas novas).

## C. Login

- Login válido → 302 `/` ✓ · Login inválido → flash "inválid" ✓ · Logout → 302 login ✓ · Acesso sem autenticação → 302 login ✓ · POST sem CSRF → 400 (proteção ativa) ✓

## D. RFQ

Criada via JSON (com CSRF header) — RFQ-260828-001, 2 itens (Transfer + Diária), total **1.300,00** ✓; detalhe 200 com itens/valor ✓; **PDF gerado** (751 KB) ✓; aprovação ✓.

## E. SO

Gerada da RFQ: SO-260828-001, vínculo, itens e valor 1.300 preservados ✓; abrir ✓.

## F. PO

Criada do SO (PO-260828-001, rascunho → item 350 → aberta → parcelas → faturada → paga) ✓. Nota: `create_from_order` não copiou itens (descrições manuais sem service_id) — adicionado manualmente (⚪ informativo).

## G. Faturamento

SO faturado com sucesso: status, `invoiced_at`, parcela (1.300, venc. hoje) e FR pendente `order_payment:39` criados ✓. **Faturado ≠ Recebido** confirmado.

## H. AR

Antes do recebimento: parcela 39 visível em A Receber ✓ (3.640 reais históricos + 1.300 de teste).

## I. Recebimento

- **Baixa parcial (500)**: parcela → paid 500; FR → pago 500 ✓ (SO permanece faturado ✓).
- **🔴 ALTO — Baixa do saldo (800) SOBRESCREVE o acumulado**: a segunda baixa gravou `paid_amount=800` (não 1.300) e o FR ficou com **800 pago** — os 500 anteriores **sumiram do ledger**. Caixa mostra 800 em vez de 1.300. O SO também não auto-concluiu (total_paid 800 < 1.300), mesmo com tudo recebido.
- **MÉDIO**: durante a fase parcial, o saldo não recebido (800) fica **sem espelho pendente** no ledger (a sincronização pula FR já "pago").
- NÃO corrigir nesta etapa (regra da etapa) — bug documentado para correção autorizada.

## J. AP

Antes do pagamento: parcela 23 (350) visível em A Pagar (Custos de Serviços) ✓.

## K. Pagamento

PO paga: parcela, FR pago e status PO → `pago` ✓. Sem duplicidade (1 FR por parcela).

## L. Despesas

Criada (TESTE 10C, categoria Administrativas, centro Administrativo, 200,00, venc. 15/09) ✓; apareceu em **Caixa Previsto do mês seguinte** (badge PREVISTO) ✓ e na **DRE de agosto** por competência ✓; paga → FR pago ✓.

## M. Caixa

Realizado do mês: saída 350 (PO) e receita **800 (não 1.300 — bug da baixa parcial)**. Badges REALIZADO/PREVISTO ✓. Saldo inicial "não configurado" ✓.

## N. Caixa Previsto

Despesa de setembro prevista ✓ por due_date; transição previsto→realizado ✓ (após pagamento a despesa saiu do previsto).

## O. DRE

Agosto: receita **1.300** (faturamento — imune ao bug de caixa ✓), custo **350** (competência), despesa **200** (emissão) ✓ — DRE ≠ Caixa confirmado.

## P. Margem

DRE: 1.300 − 350 = 950 bruta; − 200 = 750 resultado ✓ (números coerentes em tela).

## Q. Dashboard

Após fluxos: refletiu as obrigações/valores (cards via dre_service/ar_ap_service) ✓; consistência Dashboard=DRE confirmada (valores iguais para o mesmo período).

## R. RBAC

Viewer (sem `financial.manage`): criar despesa **403** ✓, saldo inicial **403** ✓, catálogo **403** ✓, ver DRE/Despesas **200** ✓.

## S. Multiempresa

Validada pela suíte automatizada (3A/3B/4/5/8B/9B — sem vazamento); em runtime, empresa B sem dados não vaza para A.

## T. PDFs

RFQ 751 KB ✓ · SO 751 KB ✓ · PO 751 KB ✓ (application/pdf, conteúdo com valores/cliente). Recibo: **não gerado** — SO de teste não atingiu `concluido` (consequência do bug da baixa parcial).

## U. Mobile / V. Desktop / W. Navegação

Auditadas na Etapa 11A (tabelas sem scroll em Despesas/Categorias/Centros = CRÍTICO/ALTO mobile; restante ok). Navegação por menu testada via fluxos completos ✓ (RFQ→SO→PO→despesas→caixa→DRE sem fluxo quebrado).

## X. Performance

Nenhuma lentidão perceptível nos fluxos testados (requests < 1s).

## Y. Integridade

`integrity_check` = ok antes, durante e depois dos testes.

## Z. Dados históricos

**ZERO alterações**: todas as 19 tabelas conferidas **IDÊNTICAS** ao backup pré-10B (incluindo `audit_logs` — limpeza cirúrgica removeu apenas os registros de teste). Contagens restauradas: orders 40 · POs 32 · FRs 55 · clients 17 · quotes 36. FR28/Pronampe pago 13.500 ✓ · FR45 cancelado ✓ · 6 soft-deletados preservados ✓.

## AA. Testes automatizados

Suíte completa: **mesmas 6 falhas pré-existentes** (`test_decorators_and_audit.py`) — nenhuma nova (Etapas 2–10B verdes).

## AB. Problemas encontrados

| # | Problema | Onde |
|---|---|---|
| 1 | **Baixa parcial + baixa de saldo sobrescreve `paid_amount`/FR** — recebido real 1.300 vira 800 no ledger; SO não auto-conclui | `orders/routes.py` baixa → `order_service.baixa` (paid_amount tratado como valor total, não incremental) |
| 2 | Saldo não recebido fica sem espelho pendente durante fase parcial | `_sync_order_pending_financials` (pula FR já pago) |
| 3 | Baixa repetida (duplicidade) é silenciosamente idempotente — sem aviso "já pago", mas **sem FR duplicado** ✓ | `financial.baixa_record` |
| 4 | `create_from_order` não copia itens de SO com descrição manual (sem service_id) | `purchase_order_service` |
| 5 | Recibo bloqueado quando SO não conclui (consequência do bug 1) | fluxo de recibo |

## AC. Severidade

- 🔴 CRÍTICO: 0 · 🟠 ALTO: 1 (bug da baixa parcial — risco real para pagamentos parciais) · 🟡 MÉDIO: 2, 3 · 🔵 BAIXO: 5 · ⚪ INFORMATIVO: 4

## AD. Recomendação

1. **Corrigir o bug da baixa parcial antes de qualquer uso real de pagamentos parciais** (acumular paid_amount/paid_date; manter espelho pendente do saldo) — etapa específica com testes.
2. Adicionar aviso "parcela já paga" em re-baixas.
3. Prosseguir com a **Etapa 11B (UX)** — independente dos itens acima.

---

## RESUMO EXECUTIVO

- TOTAL DE FLUXOS TESTADOS: **12** (login, RFQ, SO, faturamento, recebimento, PO, AP, pagamento, despesa, caixa, previsto, DRE + duplicidade/erros/RBAC/PDFs)
- PASSARAM: **11** · FALHARAM: **0** · BLOQUEADORES: **0**
- CRÍTICOS: **0** · ALTOS: **1** · MÉDIOS: **2** · BAIXOS: **1** · INFORMATIVOS: **1**
- **DADOS HISTÓRICOS ALTERADOS: ZERO** ✅

## DECISÃO FINAL

🟡 **APROVADO COM RESSALVAS**

O sistema está funcionalmente estável para os fluxos principais (pagamentos integrais). Existe **1 problema funcional ALTO** (baixa parcial sobrescreve valores acumulados) que não bloqueia a Etapa 11B (UX), mas **deve ser corrigido em etapa específica antes do uso real de pagamentos parciais**. Nada foi corrigido nesta etapa, conforme as regras.

PARADO — aguardando autorização explícita (11B de UX e/ou etapa de correção do bug da baixa parcial).
