# ETAPA 11A — RELATÓRIO DE AUDITORIA DE UX DO FINANCEIRO (DESKTOP + MOBILE)

**Data**: 28/08/2026 — **Modo**: 100% somente leitura. **NENHUM dado/regra alterado.** **Commit**: ver `git log -1` (documentação).

---

## A. Dashboard

- Cards: nomenclatura consistente pós-10B (Receita SO / **Custos Diretos** / Margem R$ / Margem % / Despesas Gerais / DRE resumida). KPIs delegam ao `dre_service` — valores coerentes com DRE/Caixa/AR/AP.
- Faixas extras (Despesas Gerais e DRE) com links diretos — boa navegação.
- Gráfico 12 meses: canvas em container com altura fixa 220px (Chart.js responsivo) — sem overflow.
- Funil: barras empilhadas (sem tabela) — adequado.
- Pendências AR/AP com badges de vencido/hoje — legível.

## B. Financeiro (painel)

- Cards renomeados na 10B (**Receitas Pagas**, **Custos Pagos no Período**, A Pagar com quebra) — clareza boa.
- Abas Receitas/Despesas/Lançamentos com filtros flex-wrap — ok em desktop e mobile.
- Lista de lançamentos com tabela em `overflow-x-auto` ✓.

## C. DRE

- Demonstração com linhas claras (Receita − Custos = Margem Bruta; grupos de despesas; Resultado) ✓.
- Visão mensal em tabela com `min-w-[900px]` dentro de `overflow-x-auto` ✓ (scroll horizontal controlado no mobile).
- Detalhamento expansível e pendências explícitas ✓. Filtros com flex-wrap ✓.

## D. Caixa

- Cards Saldo Inicial / Realizado (3) / Previsto (3) com cores distintas — separação visual clara entre realizado (bordas sólidas) e previsto (fundo tonal) ✓.
- Movimentos com badges **REALIZADO/PREVISTO** e datas explícitas ✓. Nota de projeção presente ✓.
- Listas em `grid lg:grid-cols-2` (empilham no mobile) ✓.

## E. AR

- Cards A Receber/Vencidas/Recebidas; lista com overflow-x ✓; estado vazio útil ("Nenhuma conta a receber…") ✓.
- Clareza "A Receber ≠ Faturado": parcial — o card "Recebidas (período)" usa paid_date (caixa), enquanto a lista mostra competência; rótulo "Recebidas" é claro, mas a lista não distingue explicitamente as duas naturezas.

## F. AP

- Quebra Custos de Serviços × Despesas Gerais × Total ✓ (10B/8B). Vencidas e pagas com rótulos claros ✓. Fornecedor como filtro ✓. Estado vazio ✓.
- Clareza "A Pagar ≠ Custo": boa após 10B (subtexto "Custos + Despesas pendentes").

## G. Despesas

- Listagem com KPIs próprios, filtros (período/status/categoria/centro/fornecedor) e formulário completo ✓. Ações claras (editar/pagar/cancelar com ícones + tooltips) ✓.
- **Tabela de 9 colunas SEM `overflow-x-auto`** (problema — ver Q).

## H. Desktop (1920/1440/1366/1024)

- Grids adaptativos (`grid-cols-2 sm:4 lg:7` etc.) — sem overflow; tabelas dentro de containers com scroll quando largas. Nenhum texto cortado identificado nos cards. Menus fixos funcionais.

## I. Tablet (~768px)

- Cards empilham em 2 colunas; tabelas com scroll horizontal onde previsto ✓; filtros quebram linha ✓. Menu colapsa para o hambúrguer (<lg) ✓.

## J. Mobile (375/390/414)

- **Problema principal: tabelas sem container de scroll** — `expenses.html` (9 colunas), `categories.html` (4) e `cost_centers.html` (3) ultrapassam a tela sem scroll horizontal controlado (compressão de colunas/fonte ilegível). `dashboard/index.html` sem tabelas (ok).
- Cards empilham corretamente; filtros empilham ✓; detalhes expansíveis (details) funcionam bem no toque ✓.
- Observação do padrão do projeto: alterações de layout devem ser **mobile-only (≤639px)** — referência: header mobile do RFQ detail (memória do projeto).

## K. Menu

- Sidebar agrupada por módulo com ícones; menu mobile em overlay ✓. Financeiro tem entradas soltas (Despesas/Caixa/DRE/Categorias/Centros) acessíveis via painel — **não há grupo "Financeiro" explícito no menu lateral** (oportunidade de navegação, não implementar nesta etapa).

## L. Filtros

- Labels claros; flex-wrap em todas as telas ✓; custom com datas ✓; "mês seguinte" no Caixa ✓. **Falta botão "Limpar"** na maioria (para zerar basta recarregar, mas sem affordance explícita). Estado não persiste entre navegações (aceitável).

## M. Acessibilidade

- Contrastes de texto/cards adequados ao dark/light; badges usam texto ≥10px (limite inferior — aceitável para badges).
- Botões de ação por ícone com `title` (tooltip) — sem rótulo visível em alguns casos (pagar/cancelar) — foco por teclado preservado por serem `button/a` nativos.
- Formulários com `label` + `required` nativos ✓. Mensagens flash com categoria de cor ✓.

## N. Estados vazios

Todos presentes e úteis: Despesas, Categorias, Centros, Caixa (entradas/saídas), AR, AP, painel ✓.

## O. Mensagens

Flash de sucesso/erro em criar/editar/pagar/cancelar/saldo ✓; erros de validação específicos ✓ (ex.: "Categoria é obrigatória").

## P. Performance percebida

Telas leves (queries enxutas pós-8B/10B); N+1 documentados (Caixa/DRE) não causam lentidão perceptível no volume atual. Gráfico único. Sem problema perceptível.

## Q. Problemas encontrados

| # | Problema | Onde | Severidade |
|---|---|---|---|
| 1 | Tabela de Despesas (9 colunas) sem scroll horizontal no mobile | `financial/expenses.html:83` | **CRÍTICO** |
| 2 | Tabelas de Categorias e Centros de Custo sem scroll horizontal | `categories.html`, `cost_centers.html` | **ALTO** |
| 3 | Sem botão "Limpar" nos filtros | todas as telas de lista | MÉDIO |
| 4 | "Recebidas" do AR (caixa) convive com lista por competência sem distinção visual | `receivables.html` | MÉDIO |
| 5 | Menu lateral sem grupo "Financeiro" explícito | `base.html` | BAIXO |
| 6 | Ações por ícone sem rótulo visível (tooltip apenas) | despesas/catálogo | BAIXO |

## R. Severidade

- **CRÍTICO**: 1 (mobile — tabela de despesas ilegível).
- **ALTO**: 2 (mobile).
- **MÉDIO**: 3, 4.
- **BAIXO**: 5, 6.

## S. Recomendações

1. Envolver as tabelas de Despesas/Categorias/Centros em `overflow-x-auto` com `min-w` adequado (padrão já usado em DRE/AR/AP) — **mobile-only (≤639px)**, sem tocar no restante.
2. Adicionar botão "Limpar" (href sem query) nos formulários de filtro.
3. Rótulo do card AR: "Recebidas (caixa)" + subtexto na lista ("extrato por competência").
4. Avaliar agrupar o menu em "Financeiro" (etapa própria).
5. Rótulos textuais opcionais ao lado dos ícones de ação (sr-only ou visível no mobile).

## T. Ordem recomendada de implementação (Etapa 11B)

1 → 2 → 3 (rápidos, só templates) → 5 → 4.

---

## Regressão

Suíte completa: **mesmas 6 falhas pré-existentes** — nenhuma nova (Etapas 2–10B verdes).

**Nenhum dado, regra financeira, SO, PO, pagamento ou FinancialRecord foi alterado.**

🟢 **ETAPA 11A CONCLUÍDA — UX FINANCEIRA AUDITADA**

PARADO — aguardando autorização explícita para a implementação das correções (Etapa 11B).
