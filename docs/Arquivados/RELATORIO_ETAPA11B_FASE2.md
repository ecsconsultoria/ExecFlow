# RELATÓRIO — ETAPA 11B FASE 2 (Implementação da UX de Parcelas e Baixas)

**Data**: 29/08/2026 — **Commit**: ver `git log -1` (sem push — deploy segue o fluxo normal da branch `v3`)

---

## 1. Implementação realizada

1. **Resumo da parcela** (componente `payment_summary`): Valor → Recebido (com barra de progresso) → Saldo → Status — dados 100% derivados de `amount`/`paid_amount`/`balance`/`is_paid` (sem regra nova).
2. **Timeline de baixas** (componente `baixa_timeline` + `payment_history_service`): fonte exclusiva `audit_logs` (ações "Parcela N baixada..."), ignorando "Baixa registrada" (painel). Saldo após derivado em Python apenas para exibição.
3. **Tabela de parcelas do SO/PO reformulada** em 3 estados (ABERTA / PARCIAL / QUITADA) com colunas Pago/Saldo/Status e linha expansível (resumo + histórico).
4. **Modal de baixa** agora pré-preenche o **saldo restante** (`data-balance`), rótulo "Valor a receber nesta baixa" — SO e PO consistentes.
5. **Dashboard/AR**: badge PARCIAL quando `0 < recebido < valor` (dado já vinha do `ar_ap_service`).

## 2. Componentes criados

- `app/templates/components/payment_summary.html` (macro `payment_summary`)
- `app/templates/components/timeline.html` (macro `baixa_timeline`)
- `app/services/payment_history_service.py` (`build_baixa_history` — somente leitura)

## 3. Arquivos alterados

- `app/services/payment_history_service.py` (novo)
- `app/templates/components/payment_summary.html`, `timeline.html` (novos)
- `app/templates/orders/detail.html` (tabela de parcelas, modal, JS `togglePmtExtra`, prefill saldo)
- `app/templates/purchase_orders/detail.html` (mesmo padrão; lógica de baixa da PO intocada)
- `app/blueprints/orders/routes.py` (detalhe: monta `baixa_history` — leitura)
- `app/blueprints/purchase_orders/routes.py` (idem)
- `app/templates/dashboard/index.html` (badge PARCIAL)
- `tests/test_ux_parcelas_etapa11b.py` (novo — 7 testes)

## 4. Fluxo visual

Linha da parcela mostra: `# | Vencimento | Obs | Valor | Baixa | Pago/Saldo/Status | ações`. Clicar no chevron expande resumo completo (4 blocos) + timeline + TOTAL RECEBIDO. Estados com fundo sutil: quitada (esmeralda), parcial (âmbar), aberta (neutro).

## 5. Histórico pré-10D

Eventos sem valor individual mostram a data e "valor individual não disponível" + aviso "Detalhamento individual das baixas não disponível para este período" — **nenhum valor inventado**; o TOTAL RECEBIDO exibe o valor comprovado da parcela.

## 6. Histórico pós-10D

Linhas completas: data/hora · usuário · Baixa R$ X · saldo após. TOTAL RECEBIDO = acumulado real. Validado ao vivo: 500 → saldo após 800,00; total 1.300 (na validação, após a segunda baixa).

## 7. Modal de baixa

Pré-preenche `balance` (nunca o total); teste de render confirma `data-balance="800,00"` para parcela 1.300 com 500 recebidos.

## 8. Responsividade

Bloco de resumo em `grid-cols-2 sm:grid-cols-4` (empilha no mobile); tabelas dentro de `overflow-x-auto` existente; badges `text-[10px]` sem quebra; linha expansível funciona por toque.

## 9. Acessibilidade

`aria-label` em todos os botões de ação (baixa/estornar/excluir/detalhes); badges com texto além da cor; contraste do padrão do projeto (dark/light); foco nativo.

## 10. Testes

7 testes novos: histórico pós-10D completo (valores/saldos/total/consistência); pré-10D sem invenção; "Baixa registrada" ignorada + inconsistência sinalizada sem corrigir; render de ABERTA/PARCIAL/QUITADA; `data-balance` correto; timeline renderizada; multiempresa sem vazamento.

## 11. Regressão

Suíte completa: **mesmas 6 falhas pré-existentes** (`test_decorators_and_audit.py`) — nenhuma nova (Etapas 2–11B verdes).

## 12. Integridade do banco

`integrity_check` ok · sem migration · **19 tabelas IDÊNTICAS ao backup pré-11B** (incluindo `audit_logs` — limpeza cirúrgica dos dados de teste).

## 13. Dados históricos

**ZERO alterações**: SOs, POs, parcelas, pagamentos, FinancialRecords, audit_logs, FR28/Pronampe, FR45, 6 soft-deletados — contagens 40/32/55/36/17 intactas.

## 14. Limitações

- Timeline detalhada apenas pós-10D (pré-10D exibe aviso + acumulado comprovado) — classificação B da 11B-A1.
- `financial.baixa_record` e `purchase_order_service.baixa` **continuam fora do escopo** (lógica preservada; a PO ganhou apenas a exibição).
- Parcela parcial não permite editar vencimento/nota/valor (read-only) — preservação dos valores já recebidos; edição de parcelas parciais pode ser tema de etapa futura.

## 15. Problemas encontrados

- Nenhum bloqueador. Durante o desenvolvimento: parse de valor do log corrigido (formato "500.00" decimal vs "1.300,00" milhar); `currency` filter adiciona "R$" (testes ajustados ao formato real).

## 16. Validação visual (ao vivo, servidor local)

Fluxo real executado: RFQ/SO de teste → parcela 1.300 → baixa parcial 500 → detail renderizado com: badge **PARCIAL** (×2: linha + resumo), "saldo R$ 800,00", `data-balance="800,00"`, timeline "Baixa R$ 500.00 · saldo após 800.00", TOTAL RECEBIDO. PO/ABERTA/QUITADA validadas nos testes de render. Dados de teste removidos; banco idêntico ao pré-11B.

---

🟢 **ETAPA 11B FASE 2 CONCLUÍDA — UX DE PARCELAS E BAIXAS IMPLEMENTADA**

PARADO — aguardando autorização explícita para a próxima etapa.
