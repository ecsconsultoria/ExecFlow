# PLANO — ETAPA 11B (FASE 1: ANÁLISE + PROPOSTA) — UX Financeira de Baixas, Recebimentos, Saldos e Histórico

**Data**: 28/08/2026 — **Commit de referência**: `6b70e2f` (Etapa 10D) — **NENHUM código alterado, NENHUM commit realizado nesta fase.**

---

## 1. Estado atual da UX

**Onde parcelas/baixas são exibidas hoje:**

| Tela | Arquivo | Como exibe |
|---|---|---|
| Detalhe do SO (painel direito "parcelas") | `app/templates/orders/detail.html` (linhas ~818–936) | Tabela: nº, vencimento (editável se aberta), nota, **valor** (editável se aberta), botão baixa (ícone ✓), data pagamento, excluir. Parcela **paga**: valor PAGO + badge "PAGO" + data. Parcela **parcial** (pós-10D, `is_paid == False`): cai no ramo "aberta" com inputs editáveis e **não mostra nada do recebido/saldo**. |
| Detalhe da PO | `app/templates/purchase_orders/detail.html` (linhas ~821–935) | Idêntica em estrutura. |
| Painel Financeiro / AR / AP | `financial/index.html`, `receivables.html`, `payables.html` | Cards de totais + listas de FR com status — sem visão por parcela com recebido/saldo. |
| Dashboard (pendências) | `dashboard/index.html` | Linhas compactas: descrição, vencimento, valor — sem recebido/saldo (o AR agora já vem com o SALDO via `ar_ap_service`, mas o rótulo não distingue "parcial" de "aberta"). |
| Caixa | `financial/cash_flow.html` | Movimentos realizados (FR acumulado) e previstos com badges REALIZADO/PREVISTO — sem referência ao saldo da parcela de origem. |

**Componentes reutilizáveis JÁ EXISTENTES** (`app/templates/components/`): `badge.html` (macro `badge(label, variant)`), `button.html`, `card.html`, `modal.html`, `table.html`, `status_badge_style.html`, `input.html`, `page_header.html`. Não existe componente de **timeline/histórico** nem de **resumo de pagamento**.

**Histórico de baixas**: hoje NÃO aparece em nenhuma tela — os dados existem apenas em `audit_logs` (ação "Parcela N baixada R$ X" com usuário/timestamp, adicionada na 10D) e em `order_payments.paid_at/paid_amount` (apenas o último estado).

## 2. Problemas encontrados

| # | Problema | Onde | Severidade |
|---|---|---|---|
| 1 | **Parcela parcialmente paga é invisível**: usuário não vê quanto já recebeu nem quanto falta (ramo "aberta" mostra só inputs) | orders/purchase_orders detail | 🟠 ALTO (UX) |
| 2 | **Modal de baixa do SO pré-preenche o TOTAL da parcela**, não o saldo — após a 10D, repetir a baixa com esse valor é bloqueada por exceder o saldo (a PO já pré-preenche o saldo — inconsistência) | `orders/detail.html` (`data-amount` + JS `openBaixaO`) | 🟡 MÉDIO |
| 3 | Sem distinção visual entre parcela ABERTA e PARCIAL em nenhuma tela (dashboard/AR mostram o saldo, mas sem rótulo "parcial") | dashboard, receivables | 🟡 MÉDIO |
| 4 | Sem histórico de baixas visível (500 + 800 = 1.300 não é contável na tela) | orders detail | 🟡 MÉDIO |
| 5 | Botão de baixa somente ícone (sem rótulo) e sem confirmação | orders/purchase_orders detail | 🔵 BAIXO |
| 6 | Tabelas sem scroll horizontal no mobile (Despesas/Categorias/Centros — da auditoria 11A) | expenses/categories/cost_centers | 🔴/🟠 (da 11A, fora deste foco) |

## 3. Componentes envolvidos

- **Novos (propostos)**: `components/payment_summary.html` (resumo valor → recebido → saldo → status) e `components/timeline.html` (histórico de baixas). Reusados no SO e na PO.
- **Existentes (reutilizar)**: `badge.html`, `modal.html`, `table.html` (para o histórico).
- **Telas afetadas**: detalhe do SO e da PO (painel de parcelas), modal de baixa (prefill), Dashboard pendências (badge "PARCIAL" quando `0 < recebido < valor`), AR/AP (linha com recebido/saldo no detalhe expansível, se existir).

## 4. Arquivos envolvidos (previsão de alteração)

| Arquivo | Tipo de mudança |
|---|---|
| `app/templates/components/payment_summary.html` | NOVO — macro de resumo |
| `app/templates/components/timeline.html` | NOVO — macro de timeline |
| `app/templates/orders/detail.html` | tabela de parcelas + modal (data-balance/prefill) + resumo/timeline |
| `app/templates/purchase_orders/detail.html` | idem (espelho) |
| `app/blueprints/orders/routes.py` (detail) | **leitura** de `audit_logs` (ação "baixada") do SO e repasse ao template — somente leitura, sem regra |
| `app/blueprints/purchase_orders/routes.py` (detail) | idem (se aplicável — PO baixa fora do escopo da 10D; histórico existe via audit) |
| `app/templates/dashboard/index.html` | badge "PARCIAL" nas pendências (dado já vem do `ar_ap_service`) |
| `app/templates/financial/receivables.html` / `payables.html` | rótulo de parcial/balance se aplicável |

## 5. Proposta de novo layout (painel de parcelas — SO/PO)

Substituir a linha confusa da tabela por um **bloco de resumo por parcela** (expandível em mobile):

```
┌───────────────────────────────────────────────────────────┐
│ Parcela 1/1        Vencimento 28/08/2026        [PAGO]    │
│                                                           │
│ Valor      R$ 1.300,00                                    │
│ Recebido   R$ 1.300,00   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ 100%           │
│ Saldo      R$ 0,00                                       │
│                                                           │
│ ▾ Histórico de baixas (2)                                 │
│   28/08/2026 · Baixa · R$ 500,00 · saldo após: R$ 800,00  │
│   28/08/2026 · Baixa · R$ 800,00 · saldo após: R$ 0,00    │
│   ─────────────────────────────────                       │
│   TOTAL RECEBIDO  R$ 1.300,00                             │
└───────────────────────────────────────────────────────────┘
```

- Ações (dar baixa/editar/excluir) ficam numa linha discreta à direita (ícones atuais + rótulo "Baixar" visível no hover/mobile).
- A barra de progresso (discreta, 4px) dá a leitura imediata de quitação.
- Em telas menores o bloco empilha: valor/recebido/saldo em uma coluna; histórico em `details` nativo.

## 6. Proposta de componentes

- `payment_summary(pmt)` → renderiza valor/recebido/saldo/barra/status consumindo **apenas** `pmt.amount`, `pmt.paid_amount`, `pmt.balance`, `pmt.is_paid` (dados já existentes; zero registros novos).
- `timeline(entries)` → recebe lista de dicts `{date, label, amount, balance_after}` montada **pelo backend a partir do `audit_logs`** (ações "Parcela N baixada R$ X"). Sem dados artificiais; a ordem vem do timestamp do log; o "saldo após" é derivado da sequência (acumulado) — **derivação de exibição, não gravação**.
- Status via `badge()` existente com novas variantes discretas: `aberta` (slate), `parcial` (amber), `quitada` (emerald), `faturado` (sky), `cancelado` (rose/slate) — cores semânticas suaves, texto ~10–11px, sem aparência de botão.

## 7. Proposta de estados visuais

| Estado | Critério (dados atuais) | Badge |
|---|---|---|
| ABERTA | `paid_amount == 0` e não quitada | neutro (slate) |
| PARCIAL | `0 < paid_amount < amount` | âmbar discreto |
| QUITADA/PAGO | `balance <= 0` | esmeralda discreto |
| CANCELADO | status da SO/PO cancelado/excluído | rosa/cinza |
| FATURADO | contexto da SO | azul-céu (mantém badge existente) |

Nenhum valor de status do banco será alterado — apenas apresentação derivada.

## 8. Proposta para histórico de baixas

- **Fonte única**: `audit_logs` (ação `LIKE 'Parcela % baixada%'`, entidade `order`, `entity_id = order.id`). A 10D já registra o valor de cada baixa — suficiente para reconstruir 500 + 800 = 1.300.
- **Fallback** (parcelas pagas antes da 10D, sem valor no log): exibir a linha com o valor da baixa quando presente; quando ausente, mostrar apenas a data e o total acumulado final — nunca inventar valores.
- Sem INSERT/UPDATE — a timeline é 100% leitura.

## 9. Proposta para visualização de saldo

- Três números com hierarquia: **Valor** (secundário) → **Recebido** (primário, cor da moeda) → **Saldo** (destaque quando > 0).
- Barra de progresso fina (recebido/valor) com tooltip de percentual.
- No Dashboard/AR: linha pendente ganha o badge "PARCIAL" quando `0 < recebido < valor` (o saldo já é o valor exibido — sem mudança de cálculo).

## 10. Responsividade

- Desktop: bloco de resumo em 3 colunas (valor/recebido/saldo) + histórico colapsável.
- Tablet/Mobile (≤639px, conforme padrão do projeto — referência: header mobile do RFQ detail): bloco empilha em 1 coluna; histórico em `<details>`; tabela de parcelas com `overflow-x-auto` quando necessário; modal de baixa já é responsivo.
- Nada de fonte menor que 10px; números monetários sempre `font-mono`.

## 11. Acessibilidade

- Badges com contraste AA no dark/light; texto além da cor (rótulo textual).
- Botão de baixa ganha `aria-label`/rótulo visível no mobile.
- Timeline navegável por teclado (lista simples, sem interação obrigatória).
- Foco visível nos botões do modal (padrão atual preservado).

## 12. Compatibilidade com o design atual

- Tailwind + macros de `components/` existentes; dark mode com tokens atuais; sem nova dependência; sem JS framework novo (vanilla JS existente no detail).
- Cores dentro da paleta já usada (emerald/amber/slate/sky/rose).

## 13. Impacto técnico

- **Templates**: ordens/PO detail + 2 macros novos + badge no dashboard/AR.
- **Backend (somente leitura)**: rota de detalhe do SO/PO passa a buscar as linhas de baixa no `audit_logs` (1 query por tela, indexada por entity/entity_id) e derivar `balance_after` em Python. Nenhum endpoint novo, nenhuma regra alterada.
- **Modal de baixa (SO)**: trocar `data-amount` (total) por `data-balance` (saldo) + prefill — alinha com a PO e com a semântica da 10D.
- Sem migration · sem alteração de FR/AR/AP/DRE/Caixa.

## 14. Riscos

1. **Parsing do audit_logs**: histórico depende do formato da ação — mitigar com fallback (linha sem valor quando não parseável) e teste.
2. **Histórico de parcelas pré-10D**: baixas antigas não têm valor no log — a timeline mostrará apenas o acumulado final (documentado, sem invenção).
3. **Performance**: 1 query extra por detail — desprezível; evitar N+1 (buscar todos os logs do pedido de uma vez).
4. **Regressão visual do detail** (tela mais usada do fluxo): alterações contidas no painel de parcelas; testes de render + validação ao vivo como na 10C/10D.
5. **Escopo**: não tocar `financial.baixa_record` nem `purchase_order_service.baixa` (fora do escopo — documentado).

## 15. Dados que NÃO serão alterados

SOs, POs, OrderPayments, POPayments, FinancialRecords, AccountReceivables (legado), audit_logs, pagamentos, parcelas, saldo inicial, FR28/Pronampe, FR45, 6 soft-deletados. Nenhuma migration, nenhum UPDATE/INSERT/DELETE de correção, nenhum recálculo.

## 16. Testes recomendados (para a fase de implementação)

1. Render do bloco de resumo para parcela aberta/parcial/quitada (valores e badges corretos).
2. Timeline montada a partir do audit_logs (500 + 800 → saldo após 800/0; total 1.300).
3. Fallback quando o log não tem valor (linha sem inventar número).
4. Modal de baixa do SO pré-preenche o **saldo** (não o total) — consistente com a PO.
5. Dashboard/AR exibem "PARCIAL" somente quando `0 < recebido < valor`.
6. Multiempresa: timeline/parcelas de outra empresa nunca aparecem (rotas já filtram; teste de render).
7. Regressão: suíte completa (baseline = 6 falhas RBAC pré-existentes).
8. Responsividade: render mobile ≤639px sem overflow de resumo/timeline.

## 17. Plano de implementação em pequenos passos

1. **Macros** `payment_summary.html` e `timeline.html` (sem tocar telas ainda) + testes de render unitário.
2. **SO detail**: integrar resumo + timeline no painel de parcelas; corrigir prefill do modal para saldo (data-balance).
3. **PO detail**: mesmo tratamento (espelho; baixa de PO continua com a semântica atual — apenas exibição).
4. **Dashboard/AR**: badge PARCIAL nas pendências (dado já disponível).
5. **Mobile** (≤639px): empilhamento + overflow da tabela.
6. Validação ao vivo (fluxo 10D 500+800) + suíte completa + relatório da fase 2.

---

## CRITÉRIO DE SUCESSO DA FASE 1

✅ código analisado · ✅ UX documentada · ✅ problemas identificados · ✅ proposta visual documentada · ✅ arquivos afetados identificados · ✅ riscos documentados · ✅ preservação de dados confirmada · ✅ nenhuma regra financeira alterada · ✅ nenhum dado histórico alterado · ✅ nenhum código de produção alterado · ✅ plano criado.

**PARADO — aguardando autorização explícita para a implementação (fase 2).**
