# ANÁLISE — PADRONIZAR A TELA DE RFQ NO LAYOUT DA TELA DE SO

**Data**: 31/08/2026 — **Modo**: SOMENTE ANÁLISE. **Nenhum arquivo foi alterado.**

---

## Resumo executivo

**É possível** padronizar visualmente a RFQ no layout SO **sem quebrar nada**, desde que sejam copiados apenas os elementos visuais genéricos e NÃO os dois blocos exclusivos do fluxo de SO (bulk bar e colunas de pagamento). Os botões atuais da RFQ são mantidos exatamente como estão. A única alteração de rota necessária é trivial (soma do Total para o rodapé). Classificação: **VIÁVEL — com escopo definido abaixo.**

---

## 1. O que as telas já têm em comum (nada a fazer)

| Elemento | RFQ | SO |
|---|---|---|
| `page_title` com ícone + subtítulo | ✅ | ✅ |
| `extra_head` com `status_badge_style.html` | ✅ (recém-feito) | ✅ |
| Barra de filtros colapsável (Alpine `x-data="{open:true}"`, mesmo card) | ✅ | ✅ |
| Select de status + busca + botão exportar + botão novo | ✅ | ✅ |
| Linha "N resultados encontrados" | ✅ | ✅ |
| Tabela em card com `overflow-x-auto`, mesma tipografia de `th/td` | ✅ | ✅ |
| Badge de status padrão (dot + label, light/dark) | ✅ | ✅ |
| Ações de linha (ícone ver + excluir com confirmação) no mesmo estilo `w-8 h-8` | ✅ | ✅ |
| Estado vazio | ✅ | ✅ |

## 2. Diferenças visuais restantes (o que o SO tem e a RFQ não)

| Elemento | No SO | Aplicável à RFQ? |
|---|---|---|
| **Coluna checkbox + Bulk bar** (faturar/concluir em massa, barra fixa inferior) | ✅ | ❌ **NÃO copiar** — é funcionalidade de fluxo (rotas POST `orders.bulk_faturar`/`bulk_concluir`); RFQ não tem equivalente. Copiar só o visual criaria UI morta; criar as rotas seria feature nova fora do pedido. |
| **Colunas "Pagto Parcial" e "Saldo Pendente"** | ✅ | ❌ **NÃO se aplica** — cotações não possuem parcelas/pagamentos (isso nasce no SO/PO). |
| **`tfoot` de totais** (Total / Pago / Pendente somados do filtro) | ✅ | ⚠️ **Aplicável parcialmente** — RFQ pode ter a linha de **Total** (soma de `total_amount`); requer +2 linhas na rota (`total_filtered = sum(...)`) — sem impacto no fluxo. |
| **Opção de filtro "Aberto/Faturado"** | ✅ | ❌ Específica de status de SO; RFQ mantém seus próprios status. |
| **Filtro extra de data/período** no SO? | — | (SO usa status+busca como RFQ — sem diferença relevante) |
| **Coluna "Nº RFQ" com link para a cotação** | ✅ (link `orders.quote`) | RFQ já tem o equivalente inverso ("Nº SO" com link para o pedido). |

## 3. O que "igualar" na prática (escopo proposto)

Apenas 3 ajustes, todos visuais/genéricos, **mantendo os botões e o fluxo intactos**:

1. **`tfoot` de Total** — linha de rodapé somando os valores exibidos (como no SO, sem colunas de pago/pendente). Rota: `total_filtered = sum(q.total_amount or 0 for q in quotes)` + passar ao template.
2. **Harmonização cosmética** — conferir espaçamentos/`px-3 py-3.5` das células e `w-8` do checkbox… (sem checkbox), alinhar classes de data/valor ao SO (`hidden md:table-cell`, `text-center` nos totais).
3. **Nada mais.** Bulk bar, colunas de pagamento e filtros específicos de SO ficam FORA (documentado na seção 2).

## 4. O que NÃO quebraria

- **Fluxo**: todas as ações da RFQ (Novo Orçamento, Exportar CSV, Ver detalhe, Excluir, links para SO) permanecem idênticas — nenhuma rota/endpoint é alterado (só a adição opcional do total na rota `quotes.index`).
- **Botões**: mantidos exatamente como estão (ícone + tooltip, mesmas rotas e permissões `quote.create`/`quote.delete`).
- **Permissões/RBAC**: `quote.view` na tela, inalterado.
- **Mobile**: colunas `hidden md:table-cell` já seguem o padrão SO; sem overflow novo.
- **Testes**: a suíte existente (RBAC routes, export CSV, etc.) não depende da estrutura de células; o acréscimo do tfoot é aditivo.

## 5. Riscos e cuidados

| Risco | Mitigação |
|---|---|
| Tentação de copiar o bulk bar por "igualdade visual" | NÃO copiar — UI morta ou feature incompleta; manter fora (decisão documentada) |
| Soma do Total exibir valores de cotações excluídas | Usar a MESMA query já filtrada (o `quotes` já exclui `excluido` quando sem filtro) |
| Alinhamento das colunas entre telas | Copiar as classes exatas do `th/td` do SO |
| Testes de renderização | Suíte + smoke local (`/quotes/` 200 com tfoot) |

## 6. Conclusão

**VIÁVEL sem quebrar nada**, com escopo enxuto: tfoot de Total + harmonização de células. Elementos de fluxo do SO (bulk, pagamentos) ficam de fora por não se aplicarem — a "igualdade" final será visual e consistente, mantendo todos os botões e funcionalidades da RFQ.

---

**Nenhuma alteração foi feita. Aguardando autorização para aplicar o escopo da seção 3 (se desejado).**
