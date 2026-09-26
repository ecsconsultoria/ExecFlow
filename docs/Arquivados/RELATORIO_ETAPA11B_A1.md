# RELATÓRIO 11B-A1 — VALIDAÇÃO DA FONTE DO HISTÓRICO DE BAIXAS (SOMENTE INVESTIGAÇÃO)

**Data**: 28/08/2026 — **Modo**: 100% somente leitura. **NENHUM dado, código, migration ou commit.** Banco aberto em `mode=ro`.

---

## 1. Objetivo

Determinar se a futura timeline de baixas da Etapa 11B pode ser construída de forma confiável com os dados já existentes.

## 2. Fonte(s) de dados encontradas

| Fonte | O que registra | Valor individual da baixa? |
|---|---|---|
| `audit_logs` (ação "Parcela N baixada", entidade `order`/`po`) | cada baixa de parcela via tela de SO/PO | **somente pós-10D** (formato "Parcela N baixada R$ X") |
| `audit_logs` (ação "Baixa registrada R$ X", entidade `financial`) | baixas via **painel financeiro** (`baixa_record` — fluxo fora do escopo) | sim, mas refere-se ao FR, não à parcela |
| `order_payments`/`po_payments` | estado atual: `paid_amount`, `paid_at` | **não** — apenas o acumulado final |
| `financial_records` | espelho 1:1 por parcela (`reference`) | não — apenas o acumulado final |

**Não existe tabela estruturada de baixas** (sem payment_events/history). O audit_logs é a única fonte de eventos individuais.

## 3. Estrutura dos registros de baixa

- **Tela de SO/PO (rota `orders.baixa` / `purchase_orders.baixa`)**:
  - Pré-10D: `action = "Parcela {n} baixada"` — **sem valor**.
  - Pós-10D: `action = "Parcela {n} baixada R$ {valor}"` — **com valor** (formato livre, não estruturado — parse por regex necessário).
  - Campos: `user_id` (responsável), `created_at` (timestamp), `entity_id` (id do SO/PO), `company_id`.
- **Painel financeiro** (`baixa_record`): `action = "Baixa registrada R$ X (MÉTODO)"`, `entity_id` = id do FR — **outro fluxo**; misturá-lo na timeline de parcela causaria duplicidade de exibição.

## 4. Análise dos audit_logs

- 48 entradas relacionadas a baixa: **26** "Parcela N baixada" (pré-10D, sem valor) + **22** "Baixa registrada R$ X" (painel financeiro, com valor, entidade `financial`).
- Exemplos reais:
  - `id 13, entity=order, entity_id=1, "Parcela 1 baixada", 2026-06-01 16:09:46` (sem valor)
  - `id 45, entity=po, entity_id=2, "Parcela 1 baixada", 2026-06-01 18:52:47` (sem valor)
  - `id 43, entity=financial, entity_id=3, "Baixa registrada R$ 550.00 (PIX)"` (painel)
- **Não há nenhum exemplo pós-10D persistido** (as baixas de teste da 10D foram removidas na limpeza — o formato com valor está garantido pelo código da 10D, confirmado por leitura).

## 5. Quantidade de baixas

- Baixas de parcela registradas em audit (tela SO/PO): **26** (todas pré-10D, sem valor individual).
- Baixas via painel financeiro: **22** (com valor, entidade financial — fora do escopo da timeline de parcelas).
- Parcelas pagas hoje: **31** de SO (R$ 230.076,00) e **14** de PO (R$ 45.530,00).
- **Parcelas com mais de uma baixa: 0** no banco atual (`paid_amount>0 AND paid_amount<amount` → 0 parciais) — todos os pagamentos históricos foram integrais.
- Pós-10D: 0 registros persistidos (testes limpos).

## 6. Baixas anteriores à 10D

- Todas as **26** entradas "Parcela N baixada" têm: usuário ✓, timestamp ✓, parcela identificável (pelo `installment_no` no texto + entity_id) ✓, ordem cronológica ✓.
- **Valor individual da baixa: NÃO registrado** em nenhuma delas.
- Consequência: para o passado, é impossível reconstruir 500 + 800 = 1.300; só o acumulado final (`paid_amount`) é comprovável.

## 7. Baixas posteriores à 10D

- Formato com valor ("Parcela N baixada R$ X") implementado e validado (testes 10D + validação ao vivo 500/800 — auditou "Parcela 1 baixada R$ 500.00" e "R$ 800.00" antes da limpeza).
- Daqui para frente, cada baixa terá: valor ✓, data/hora ✓, usuário ✓, parcela ✓ (nº no texto + entity_id do SO), ordem ✓.
- **Saldo após a baixa**: não gravado — será **derivado** em Python pela sequência cronológica (valor da parcela − somatório das baixas anteriores). Derivação de exibição, sem gravação.

## 8. Parcelas com múltiplas baixas

Atualmente: **zero** (nenhuma parcela parcial no banco). A primeira parcela com múltiplas baixas surgirá no uso futuro pós-10D, e terá seu histórico completo no audit_logs.

## 9. Capacidade de reconstrução do histórico

| Período | Valor individual | Data | Usuário | Parcela | Saldo após | Reconstrução |
|---|---|---|---|---|---|---|
| Pré-10D | ❌ ausente | ✓ | ✓ | ✓ | ❌ (derivável só do final) | parcial |
| Pós-10D | ✓ (formato livre) | ✓ | ✓ | ✓ | derivável | completa |

## 10. Exemplos reais encontrados

- SO 1 (histórico): "Parcela 1 baixada" (01/06 16:09) → `paid_amount` final = 450,00. Valor individual **indisponível**.
- Painel: FR 3 "Baixa registrada R$ 550.00 (PIX)" — pertence a `po_payment:1`, mas é registro do FR (outro fluxo).
- 10D (validação ao vivo, já limpa): "Parcela 1 baixada R$ 500.00" e "Parcela 1 baixada R$ 800.00" — formato futuro confirmado.

## 11. Limitações

1. Baixas pré-10D sem valor individual — a timeline histórica mostrará apenas o acumulado final (sem inventar).
2. Formato do log é texto livre — parse por regex com **fallback seguro** (linha sem valor quando não parseável).
3. "Baixa registrada R$ X" (painel financeiro) NÃO deve ser misturada à timeline de parcela (é outro fluxo; o FR já espelha).
4. `paid_at`/`paid_amount` guardam somente o último evento — impossível recuperar eventos antigos fora do audit.
5. `baixa_record` e `purchase_order_service.baixa` seguem fora do escopo (não possuem valor individual auditado por baixa no formato de parcela).

## 12. Classificação A/B/C de confiabilidade

**B — CONFIÁVEL COM LIMITAÇÕES**

- **Pós-10D**: timeline completa e confiável (valor/data/usuário/parcela; saldo derivado).
- **Pré-10D**: apenas o acumulado final é confiável — a timeline histórica exibirá uma linha única ("recebido R$ X em <data>") sem decomposição inventada.

## 13. Recomendação para a UX 11B

1. Implementar a **timeline pós-10D completa** (dados do audit_logs, saldo após derivado em Python).
2. Para parcelas pré-10D: exibir **resumo** (Original / Recebido / Saldo / Último recebimento) **sem timeline decomposta** — nenhum valor inventado.
3. Filtrar timeline por `entity='order'`/`entity='po'` + `entity_id` + ação `LIKE 'Parcela % baixada%'`; ignorar "Baixa registrada" (painel).
4. Documentar na própria UI (tooltip/legenda) que o histórico detalhado existe a partir da data de implantação da 10D.

## 14. Confirmação da semântica da 10D

Verificada no código e no banco (somente leitura):
- `order_service.baixa`: `new_total = paid_amount_atual + recebido` (linha 486) ✓ — acumula, nunca sobrescreve; bloqueia excesso ("saldo restante") e retry ("já quitada") ✓.
- **FinancialRecord = acumulado**: FR revenue pago (31 registros) soma **R$ 230.076,00** = soma de `paid_amount` das 31 parcelas pagas ✓; FR cost pago (14) soma R$ 45.530,00 = soma das 14 po_payments pagas ✓ — espelho 1:1 consistente.
- **AccountReceivable (função) = saldo restante**: `ar_ap_service.receivable_rows` usa `balance = amount − paid_amount` e exclui quitadas ✓ (o modelo legado `AccountReceivable` segue vazio/fora de uso — nada alterado).

## 15. Confirmação de que nenhum dado foi alterado

- Banco aberto somente em `mode=ro` durante toda a investigação.
- Nenhum INSERT/UPDATE/DELETE, nenhuma migration, nenhuma alteração de código/commit.
- Contagens de referência intactas (orders 40 · POs 32 · FRs 55 · audit_logs sem novos registros).

---

✅ Critérios de sucesso cumpridos. **PARADO — aguardando autorização explícita para a implementação da 11B (fase 2).** Nenhum commit foi realizado.
