# PLANO ETAPA 12E-A1 — RELATÓRIOS / PDF / XLSX (ANÁLISE E PLANEJAMENTO)

**Data**: 29/08/2026 — **Modo**: SOMENTE ANÁLISE + PLANO. **Nenhum código alterado, nenhum banco alterado, nenhuma migration, endpoint, PDF, XLSX, commit, push ou deploy.**

---

## 1. Estado atual

- O ExecFlow já possui: PDFs transacionais (RFQ/SO/PO/Recibo) via **ReportLab**; exportação **CSV** (Excel-compatível) em RFQ/SO/PO/Serviços; tela de Relatórios básica (`/reports/`, métricas mensais); serviços financeiros com **fonte única de dados** (AR/AP, Caixa, DRE).
- **Não existe**: PDF ou XLSX para as telas financeiras novas (Lançamentos, Despesas, DRE, Caixa, AR, AP, Categorias, Centros de Custo); nenhum XLSX real (as exportações atuais são CSV, apesar do botão dizer "Exportar Excel").
- Código ativo: `a9950b0` (branch `v3`, produção deployada e validada).

## 2. Relatórios existentes

- Blueprint `reports` (`app/blueprints/reports/routes.py`): única rota `/reports/` (permissão `reports.view`) — dashboard mensal com totais de RFQs, estatísticas de OS e Receitas/Custos **pagos** do mês (caixa por `paid_date`). Template: `app/templates/reports/index.html`.

## 3. PDFs existentes

- 4 serviços ReportLab em `app/services/`: `quote_pdf.py`, `order_pdf.py`, `purchase_order_pdf.py`, `receipt_pdf.py`.
- Padrões consolidados nesses arquivos (reaproveitar): `SimpleDocTemplate` A4; `ParagraphStyle`/`TableStyle`; formatação BRL (`_fmt_brl`); cabeçalho com **logo da empresa** (`company.logo_url`, resolvendo `/uploads/`); rodapé com paginação (`canvas.draw…` + estilo de footer); suporte a idioma (pt/en) nos PDFs transacionais.

## 4. XLSX existentes

- **CSV** (não XLSX): `app/utils/export.py` — `csv_response()` com UTF-8 BOM, separador `;`, pronto para Excel. Usado em `/quotes/export`, `/orders/export`, `/po/export` (e serviços).
- **openpyxl** já é usado em `app/blueprints/services/routes.py` (importação e exportação de tabela de serviços com `Workbook`, `Font`, `PatternFill`, `Alignment`) — padrão de formatação existente para reaproveitar.

## 5. Componentes reutilizáveis

`app/templates/components/`: `page_header.html` (título + ações), `button.html` (macro `btn` com variants primary/success/danger/warning/neutral/ghost/outline e sizes xs–icon), `badge.html`, `card.html`, `input.html`, `modal.html`, `table.html`, `timeline.html`, `status_badge_style.html`, `payment_summary.html`.

## 6. Telas que receberão PDF

| Tela | PDF | Justificativa |
|---|---|---|
| DRE | ✅ | documento executivo por competência (seções do item "Relatórios Financeiros" do pedido) |
| Fluxo de Caixa | ✅ | resumo executivo (saldo inicial, realizado, previsto, projetado) |
| Contas a Receber | ✅ | posição de cobrança por cliente |
| Contas a Pagar | ✅ | posição de obrigações por fornecedor |
| Despesas | ✅ | extrato de despesas |
| Lançamentos | ✅ | relatório consolidado do ledger |
| Categorias Financeiras | ❌ | lista de catálogo — XLSX basta |
| Centros de Custo | ❌ | idem |
| SO/PO/RFQ | — | já têm PDFs transacionais próprios (por documento); relatório consolidado fica para fase futura |

## 7. Telas que receberão XLSX

| Tela | XLSX | Observação |
|---|---|---|
| DRE | ✅ | colunas mensais + competência — ideal para Excel |
| Fluxo de Caixa | ✅ | movimentos realizados + previstos com colunas realiz./prev. |
| Contas a Receber | ✅ | tabular |
| Contas a Pagar | ✅ | tabular |
| Despesas | ✅ | tabular + campos financeiros |
| Lançamentos | ✅ | consolidado (competência, pagamento, referência) |
| Categorias Financeiras | ✅ | catálogo |
| Centros de Custo | ✅ | catálogo |
| SO/PO/RFQ | 🔄 | já possuem CSV com filtros — migração para XLSX real opcional (fase 2, reutilizando o novo builder) |

## 8. Proposta de UX dos botões

- **Cabeçalho de cada tela** (linha `mb-4 flex flex-wrap items-center gap-2` já existente em todas as telas financeiras), alinhados à direita: **`[PDF]`** e **`[XLSX]`** lado a lado, estilo **ghost/outline neutro** (slate) com ícones `fa-file-pdf` e `fa-file-excel` + texto — aparência de **ação de relatório**, distinta de navegação; sem excesso de cor (sem verde/vermelho chamativo; no máximo cor no ícone do PDF).
- Padrão proposto (novo macro `components/export_buttons.html` para consistência):
  ```html
  <a href="{{ url_for('financial.dre_pdf', **filtros) }}" class="btn-ghost btn-sm" title="Gerar PDF">
    <i class="fa-solid fa-file-pdf mr-1.5"></i><span class="hidden sm:inline">PDF</span>
  </a>
  <a href="{{ url_for('financial.dre_xlsx', **filtros) }}" class="btn-ghost btn-sm" title="Exportar XLSX">
    <i class="fa-solid fa-file-excel mr-1.5"></i><span class="hidden sm:inline">XLSX</span>
  </a>
  ```
- Telas só-XLSX (Categorias/CC): apenas o botão `[XLSX]`.
- Sem dropdown "Exportar ▾" na fase 1 (2 botões explícitos atendem a preferência de identificação fácil; dropdown fica documentado como alternativa futura).

## 9. Estrutura dos PDFs

Novo módulo compartilhado **`app/services/report_pdf.py`** (ReportLab, reaproveitando padrões dos PDFs atuais):

1. **Cabeçalho** — logo da empresa (esquerda) + título do relatório (ex.: "DRE Gerencial") + subtítulo com **período e filtros aplicados** (direita).
2. **Corpo** — seções hierárquicas: blocos de resumo (cards simples em tabela) seguidos das tabelas detalhadas (repetindo `Table` + `TableStyle`, zebra sutil, cabeçalho bold com fundo cinza-claro).
3. **Rodapé** — página X de Y + data/hora de geração + "Gerado por <usuário>" + empresa.
4. Formatação: BRL (`R$ 1.234,56`), datas `dd/mm/aaaa`, negativos em vermelho, totais com fundo destacado.
5. Paginação automática (`SimpleDocTemplate` + `RepeatRows=1` no cabeçalho das tabelas longas).
6. Conteúdo por relatório:
   - **DRE**: período, receitas, custos diretos, margem bruta, despesas gerais por grupo, resultado operacional; detalhamento mensal quando o período cobrir mais de um mês.
   - **Caixa**: saldo inicial (+ aviso se não configurado), entradas/saídas realizadas, entradas/saídas previstas, saldo realizado e projetado.
   - **AR**: cliente, referência, vencimento, valor original, recebido, saldo, status.
   - **AP**: fornecedor, descrição, vencimento, valor, pago, saldo, status, categoria, centro de custo.
   - **Despesas**: descrição, categoria, centro de custo, emissão, vencimento, valor, status.
   - **Lançamentos**: consolidado (data, descrição, tipo, categoria, centro, valor, status, referência, competência, pagamento).

## 10. Estrutura dos XLSX

Novo módulo compartilhado **`app/services/report_xlsx.py`** (openpyxl, reutilizando o padrão de `services/routes.py`):

- Linha 1: **título** (bold, 12–14pt) · Linha 2: **período** · Linha 3: **filtros utilizados** (ex.: "Categoria: Todas · Centro: Todos · Status: Pendente") · linha em branco.
- **Cabeçalho** de colunas (bold, fundo cinza, borda fina) · **dados** · linha de **TOTAIS** (bold).
- **Autofiltro** (`ws.auto_filter`) · **congelamento** do cabeçalho (`freeze_panes`) · **larguras de coluna** adequadas · **formato monetário** (`R$ #,##0.00` — ou numérico + coluna, decidir na implementação; float é a fonte) · datas `dd/mm/yyyy`.
- 1 planilha por relatório; nomes de arquivo: `dre_2026-07-01_2026-07-31.xlsx` etc.
- **Codificação**: conteúdo sempre UTF-8 explícito (lição do incidente de acentos desta sessão — ver seção 19).
- Sanitização de células iniciadas por `=`/`+`/`-`/`@` (injeção de fórmula em Excel) nas colunas de texto.

## 11. Filtros (como cada relatório os recebe)

Os botões exportarão a **URL atual com os mesmos query args** da tela (padrão já usado pelo CSV de RFQ/SO/PO: `url_for('...export', status=status, q=q)`):

| Relatório | Filtros repassados |
|---|---|
| DRE | `period` (ou `date_from`/`date_to` custom) |
| Caixa | `period` / `date_from` / `date_to` |
| AR | `period`, `date_from`, `date_to` (telas atuais têm período; ampliar com cliente se a tela ganhar filtro — fase futura) |
| AP | `period`, `date_from`, `date_to`, `supplier` |
| Despesas | `period`, `status`, `category`, `cost_center`, `supplier` |
| Lançamentos | `period`, `type`, `status`, `client`, `supplier` |
| Categorias / CC | sem filtros (catálogo completo) |

Regra: **o relatório nunca ignora filtro ativo** — os endpoints export recebem os mesmos parâmetros e aplicam as mesmas regras de período (`_financial_period_bounds` / `_cash_period_bounds`).

## 12. Segurança / RBAC

- Todo endpoint de export: `@login_required` + `@require_permission("financial.view")` (exportação de **dados que o usuário já pode ver**; não exigir `financial.manage` — que é para mutação).
- Todas as consultas filtram por `company_id=current_user.company_id` (os services `dre_service`, `cash_flow_service`, `ar_ap_service` já recebem `cid` — reutilizá-los é a própria garantia de isolamento).
- Nenhum endpoint contorna permissão; mesmos decorators das telas.

## 13. Multiempresa

- Isolamento herdado dos services existentes (todos recebem `cid` da sessão). Os exportadores não farão consulta sem filtro de empresa. Cabeçalho do PDF/XLSX inclui o **nome da empresa** (`current_user.company`).

## 14. Responsividade

- **Desktop**: ícone + texto (`PDF` / `XLSX`).
- **Tablet**: ícone + texto quando houver espaço (flex-wrap já existente).
- **Mobile (≤639px)**: só ícone (`hidden sm:inline` no texto), com `title`/`aria-label` — mesmo padrão do botão CSV atual (`w-9 h-9`) e do header mobile aprovado (RFQ). Sem overflow horizontal.

## 15. Acessibilidade

- Todo botão é `<a>` com texto visível (desktop) ou `aria-label`/`title` (mobile), ícone + texto (não depende de cor), foco visível (`focus:ring` já no padrão do projeto).

## 16. Arquivos que precisarão ser alterados (fase de implementação)

| Arquivo | Mudança |
|---|---|
| `app/services/report_pdf.py` | **novo** — wrapper ReportLab (cabeçalho/rodapé/tabelas/estilos BRL) |
| `app/services/report_xlsx.py` | **novo** — wrapper openpyxl (título/filtros/cabeçalho/totais/autofiltro/freeze) |
| `app/blueprints/financial/routes.py` | + 12 rotas de export (`dre_pdf/xlsx`, `cash_flow_pdf/xlsx`, `receivables_pdf/xlsx`, `payables_pdf/xlsx`, `expenses_pdf/xlsx`, `index_pdf/xlsx`, `categories_xlsx`, `cost_centers_xlsx`) |
| `app/templates/components/export_buttons.html` | **novo** — macro de botões `[PDF] [XLSX]` |
| `app/templates/financial/{index,expenses,dre,cash_flow,payables,receivables,categories,cost_centers}.html` | inclusão dos botões no cabeçalho (passando filtros atuais) |
| `tests/` | testes novos (ver seção 21) |

## 17. Dependências existentes

- ✅ **reportlab** (PDF) — já em `requirements.txt` e em uso.
- ✅ **openpyxl** (XLSX) — já em `requirements.txt` e em uso (`services/routes.py`).

## 18. Dependências novas

**Nenhuma.** As duas bibliotecas necessárias já estão instaladas em produção (requirements do Render).

## 19. Riscos

| Risco | Mitigação |
|---|---|
| Acentos/codificação (incidente real de 29/08: textos %-codificados) | Gerar PDF/XLSX sempre em UTF-8 explícito; testes com strings acentuadas (ó, —, ê, à) em todos os builders |
| Float para moeda (débito técnico conhecido) | Arredondar com `round(..., 2)` na borda de saída; totais = soma das linhas exibidas (não recalcular por outra via) |
| Relatório divergir da tela (filtros/cálculos) | Reutilizar os **mesmos services** das telas (fonte única) — proibido reimplementar soma paralela |
| PDF longo (AR/AP com muitas parcelas) | `RepeatRows` no cabeçalho de tabela + limite de linhas igual ao da tela (500) com aviso no rodapé se truncado |
| Injeção de fórmula no XLSX (células `=cmd()`) | Sanitizar texto iniciando com `= + - @` nas colunas de texto |
| Permissão/isolamento | Decorators + `cid` nos services; teste de empresa cruzada |
| Volume de rotas duplicadas | Centralizar em funções auxiliares `_export_*` dentro do blueprint financial |

## 20. Plano de implementação (pequenos passos)

1. **Wrappers**: `report_pdf.py` e `report_xlsx.py` (com testes unitários de formatação/accentos/totais).
2. **Piloto DRE**: rotas `dre_pdf`/`dre_xlsx` + botões na tela DRE (valida o padrão completo de ponta a ponta).
3. **Caixa**: `cash_flow_pdf/xlsx` + botões.
4. **AR e AP**: `receivables_pdf/xlsx`, `payables_pdf/xlsx` + botões.
5. **Despesas e Lançamentos**: `expenses_pdf/xlsx`, `index_pdf/xlsx` + botões.
6. **Catálogos**: `categories_xlsx`, `cost_centers_xlsx`.
7. **Macro unificado**: `export_buttons.html` aplicado nas 8 telas (refatorar os botões adicionados nos passos 2–6).
8. **SO/PO/RFQ (fase 2, opcional)**: trocar CSV por XLSX real usando `report_xlsx.py`.
9. Testes completos + smoke em produção com validação de filtros (read-only).

## 21. Testes recomendados

- **Unitários** (builders): formatação BRL/datas; acentos em PDF/XLSX; totais corretos; freeze/autofilter presentes; sanitização de `=`.
- **Rotas**: sem login → 302; sem `financial.view` → 403; filtros repassados (period/status/category) refletem nos dados; empresa cruzada → vazio (não vaza).
- **Integração**: export com período custom (DRE julho contém Pessoal R$ 10.000,00 — caso real já existente em produção); Caixa previsto×realizado sem duplicação.
- **Visual/UX**: botões no header (desktop/mobile), acessibilidade (aria/title), sem overflow.

---

**NENHUMA alteração foi feita. Somente o plano foi criado. PARADO — aguardando autorização explícita para a implementação (passo a passo da seção 20).**
