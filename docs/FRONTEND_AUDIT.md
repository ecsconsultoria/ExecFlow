# Auditoria de Front-End — ExecFlow ERP V3

**Data:** 29/06/2026
**Escopo:** 34 templates, 2 arquivos CSS, 1 arquivo JS, Tailwind config
**Método:** Análise estática completa — nenhum arquivo modificado

---

## 1. Estrutura

### 1.1 Templates (34 arquivos)

```
templates/
├── base.html                     # Shell principal (424 linhas)
├── auth/                         # 2 templates (login, change_password)
├── dashboard/                    # 2 templates (index, settings)
├── quotes/                       # 3 templates (index, detail, new)
├── orders/                       # 2 templates (index, detail — 1633 linhas)
├── purchase_orders/              # 2 templates (index, detail — 1659 linhas)
├── dispatch/                     # 2 templates (index, _os_card partial)
├── financial/                    # 3 templates (index, payables, form)
├── clients/                      # 2 templates (index, form)
├── suppliers/                    # 2 templates (index, form)
├── drivers/                      # 2 templates (index, form)
├── vehicles/                     # 2 templates (index, form)
├── users/                        # 2 templates (index, form)
├── services/                     # 1 template (index — 523 linhas)
├── categories/                   # 1 template (index)
├── reports/                      # 1 template (index)
├── roles/                        # 1 template (index)
├── audit/                        # 1 template (index)
└── bookings/                     # vazio
```

### 1.2 CSS

| Arquivo | Tamanho | Status |
|---------|---------|--------|
| `css/tailwind.src.css` | 62 B | Fonte Tailwind (3 diretivas `@tailwind`) |
| `css/tailwind.css` | 674 KB | Build minificado (carregado pelo base.html) |
| `css/main.css` | 81 B | **Arquivo morto** — apenas um comentário |
| `vendor/tailwind.js` | 407 KB | **Arquivo morto** — nenhuma referência |

### 1.3 JavaScript

| Arquivo | Tamanho | Status |
|---------|---------|--------|
| `js/main.js` | 44 B | **Arquivo morto** — apenas um comentário |
| `vendor/alpine.min.js` | 46 KB | Ativo (base.html) |
| `vendor/chartjs.min.js` | 206 KB | Ativo (dashboard) |

**Problema crítico:** Todo JavaScript (~1500 linhas) está inline em tags `<script>` nos templates. `main.js` está vazio. Zero code sharing entre páginas.

---

## 2. Duplicação de Código

### 🔴 Nível Crítico — CSS Duplicado

| Arquivo | Linhas | Conteúdo Duplicado |
|---------|--------|--------------------|
| `orders/detail.html` | 5-24 | `.fi`, `.lbl`, `.card-divider` |
| `purchase_orders/detail.html` | 5-21 | `.fi`, `.lbl`, `.card-divider` (idêntico, difere apenas cor do focus) |

### 🔴 Nível Crítico — Componentes Duplicados

| Componente | Onde aparece | Vezes |
|-----------|-------------|-------|
| PDF/Email/WhatsApp dropdown | quotes, orders, purchase_orders detail | 3× |
| History timeline dropdown | quotes, orders, purchase_orders detail | 3× |
| Baixa (payment) modal | orders, purchase_orders detail, financial index, financial payables | 4× |
| Delete confirmation modal | quotes, orders, purchase_orders detail | 3× |
| Period filter + date picker (Alpine) | financial index, financial payables | 2× |
| `CAT_LABELS`/`ST_LABELS` dicts | financial index, payables, form | 3× |

### 🟡 Nível Médio — Templates Quase Idênticos

| Grupo | Templates | Similaridade |
|-------|-----------|-------------|
| List pages | quotes, orders, purchase_orders index | 90% |
| CRUD forms | clients, drivers, vehicles, suppliers form | 80% |
| Detail pages | orders, purchase_orders detail | 70% |

---

## 3. Responsividade

### 🔴 9 Tabelas sem `overflow-x-auto`

Estas quebrarão horizontalmente em mobile (< 375px):

- `categories/index.html`
- `clients/index.html`
- `drivers/index.html`
- `vehicles/index.html`
- `suppliers/index.html`
- `quotes/detail.html` (tabela de itens)
- `quotes/index.html`
- `orders/index.html`
- `purchase_orders/index.html`

### 🟡 Zero breakpoints `xl:`

Nenhum template usa `xl:` — layouts acima de 1280px usam `lg:` como último breakpoint.

### 🟡 11 Templates sem breakpoints

Todos os form templates (`suppliers/form`, `drivers/form`, `vehicles/form`, `auth/*`, etc.) usam apenas `max-w-lg` container fixo — sem adaptação para telas maiores.

### 🟢 O que funciona bem

- Dashboard: `grid-cols-2 sm:grid-cols-4 lg:grid-cols-7`
- Financial: `grid-cols-2 lg:grid-cols-5`
- Mobile drawer: `w-[85%] max-w-sm` + backdrop blur
- Flash messages: auto-dismiss com Alpine

---

## 4. CSS — Inline Styles e Cores Hardcoded

### 50 ocorrências de `style=""`

| Arquivo | Ocorrências |
|---------|------------|
| `orders/detail.html` | 17 |
| `purchase_orders/detail.html` | 17 |
| `quotes/detail.html` | 6 |
| Demais | 10 |

**Padrões mais comuns:**
- `style="display:grid;grid-template-columns:1fr 1fr"` → deveria ser `grid grid-cols-2`
- `style="min-width:200px"` → deveria ser `min-w-[200px]`
- `style="{{ status|status_badge_style }}"` → filtro Jinja gera CSS inline para badges

### Hex colors hardcoded (fora do Tailwind)

- `#e2e8f0`, `#334155`, `#94a3b8`, `#0d9488`, `#7c3aed` nos `<style>` dos detail pages
- `#16a34a`, `#dc2626`, `#d97706` no JS do purchase_orders/detail

---

## 5. Sistema de Componentes — Situação Atual

### Botões: 16 padrões de cores diferentes

| Cor | Uso | Vezes |
|-----|-----|-------|
| `bg-blue-600` | Salvar, Novo, Criar SO, Criar PO, Abrir | 21 |
| `bg-emerald-600` | Aprovar, Faturar, Concluir | 7 |
| `bg-red-600` | Rejeitar, Cancelar, Excluir | 5 |
| `bg-red-500` | Cancelar variante, Limpar Financeiro | 4 |
| `bg-violet-600` | Novo Orçamento, Nova PO, Adicionar Item | 6 |
| `bg-teal-600` | Novo SO, Gerar Contas | 5 |
| `bg-amber-500/600` | Reabrir, Iniciar PO | 5 |
| `bg-slate-400/600` | PDF, Ver Pedido | 7 |
| `bg-sky-600` | Salvar (edit item — usado 1 única vez!) | 1 |

### Cards: Bem padronizado

`rounded-xl shadow-sm` é usado em ~45 cards. Padrão consistente.

### Formulários: 2 sistemas diferentes

1. **Tailwind puro:** `w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500` — 90% dos forms
2. **CSS custom (`.fi`):** definido inline em orders/detail e purchase_orders/detail com hex colors hardcoded

### Labels: 3 padrões diferentes

1. `text-sm font-medium` — forms comuns
2. `.lbl` class (10px, uppercase) — orders/PO detail
3. `text-xs font-medium` — services/index

### Badges de Status: 3 sistemas paralelos

1. `status_badge_style` filter — gera CSS inline (quotes, orders, PO)
2. `ST_CLS` dict — classes Tailwind (financial)
3. Classes inline simples — (drivers, vehicles)

### Grids: gaps inconsistentes

| Contexto | Gap | Deveria ser |
|----------|-----|------------|
| Dashboard KPIs | `gap-3` | `gap-4` |
| Financial summary | `gap-4` | `gap-4` |
| Reports | `gap-4` | `gap-4` |
| Financial form | `gap-3` | `gap-4` |
| Clients form | `gap-x-8 gap-y-4` | `gap-4` |

---

## 6. Design System Proposto

### 6.1 Cores Semânticas

```
Primary (ações principais):  blue-600
Success (positivo):          emerald-600
Danger (negativo/destrutivo): red-600
Warning (atenção):           amber-500
Info (neutro):               slate-600
```

### 6.2 Tipografia

```
Heading XL (KPI):    text-2xl font-bold
Heading LG (página): text-lg font-bold
Heading MD (seção):  text-sm font-semibold
Body:                text-sm
Small:               text-xs
Caption:             text-[11px]
Mono (valores):      font-mono
```

### 6.3 Espaçamento

```
Seção:         mb-6
Card padding:  p-4 (KPI), p-5 (detail), p-6 (form)
Grid gap:      gap-4 (padrão único)
Botão gap:     gap-1.5
```

### 6.4 Componentes Padronizados

| Componente | Classes |
|-----------|---------|
| **Primary Button** | `h-8 px-3 text-xs font-medium rounded-lg inline-flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white transition-colors` |
| **Success Button** | `h-8 px-3 ... bg-emerald-600 hover:bg-emerald-700 text-white` |
| **Danger Button** | `h-8 px-3 ... bg-red-600 hover:bg-red-700 text-white` |
| **Neutral Button** | `h-8 px-3 ... bg-slate-600 hover:bg-slate-700 text-white` |
| **Card** | `bg-white dark:bg-slate-800 rounded-xl shadow-sm` |
| **Table Card** | `bg-white dark:bg-slate-800 rounded-xl shadow-sm overflow-x-auto` |
| **Input** | `w-full border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500` |
| **Label** | `block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1` |
| **Status Badge** | `text-xs px-2 py-0.5 rounded-full font-medium` (success: emerald, warning: amber, danger: red, neutral: slate) |
| **Empty State** | Ícone 3xl em círculo + texto "Nenhum X encontrado" |

---

## 7. Plano de Refatoração

### Fase 1 — Limpeza (2-3h, baixo risco)

| # | Ação | Impacto |
|---|------|---------|
| 1 | Remover `css/main.css` (morto) | Nenhum |
| 2 | Remover `js/main.js` (morto) | Nenhum |
| 3 | Remover `vendor/tailwind.js` (407 KB morto) | Nenhum |
| 4 | Remover `[x-cloak]` duplicado de quotes/orders/PO detail | Nenhum |
| 5 | Extrair `.fi`/`.lbl`/`.card-divider` para `tailwind.src.css` | Baixo |

### Fase 2 — Responsividade (3-4h, baixo risco)

| # | Ação | Arquivos |
|---|------|----------|
| 6 | Adicionar `overflow-x-auto` em 9 tabelas | 9 index/detail |
| 7 | Substituir 50 `style=""` por classes Tailwind | 6 templates |
| 8 | Padronizar `gap-4` em todos os grids | ~8 templates |

### Fase 3 — Componentização (6-8h, médio risco)

| # | Ação | Arquivos |
|---|------|----------|
| 9 | Criar macro Jinja2 `btn(label, url, variant, size)` | Novo: `templates/macros/buttons.html` |
| 10 | Criar macro `card(title, padding)` | Novo: `templates/macros/cards.html` |
| 11 | Criar macro `badge(text, variant)` | Novo: `templates/macros/badges.html` |
| 12 | Criar macro `empty_state(icon, message)` | Novo: `templates/macros/empty.html` |
| 13 | Criar partial `_baixa_modal.html` (compartilhado) | 4 templates |
| 14 | Criar partial `_pdf_dropdown.html` (compartilhado) | 3 templates |
| 15 | Refatorar list pages para layout compartilhado | 3 templates |

### Fase 4 — Unificação JS (4-6h, alto risco)

| # | Ação | Arquivos |
|---|------|----------|
| 16 | Mover Alpine `erp()` para `main.js` | base.html → main.js |
| 17 | Extrair `savePmt`/`deletePmt`/`openBaixa` para módulo JS | orders + PO detail |
| 18 | Substituir `innerHTML` por DOM API para construção de rows | orders + PO detail |
| 19 | Unificar vanilla `onclick` com Alpine `@click` | Vários |

### Fase 5 — Design System (3-4h, baixo risco)

| # | Ação | Arquivos |
|---|------|----------|
| 20 | Criar `@layer components` no `tailwind.src.css` com `.btn-*`, `.card`, `.input`, `.badge-*` | tailwind.src.css |
| 21 | Substituir `status_badge_style` filter por classes CSS | utils/helpers.py + 5 templates |
| 22 | Padronizar heading hierarchy (text-2xl → text-lg → text-sm) | Vários |

---

## 8. Estimativas

| Fase | Horas | Risco | Templates Afetados |
|------|-------|-------|--------------------|
| Fase 1 — Limpeza | 2-3h | Baixo | 5 |
| Fase 2 — Responsividade | 3-4h | Baixo | 15 |
| Fase 3 — Componentização | 6-8h | Médio | 12 |
| Fase 4 — Unificação JS | 4-6h | Alto | 5 |
| Fase 5 — Design System | 3-4h | Baixo | 20+ |
| **Total** | **18-25h** | | **25+** |

---

## 9. Ordem Recomendada

```
Fase 1 (Limpeza) → Fase 2 (Responsividade) → Fase 5 (Design System) → Fase 3 (Componentização) → Fase 4 (JS)
```

As Fases 1-2 são seguras e de alto impacto imediato. As Fases 3-5 exigem mais planejamento e testes, mas são o caminho para um front-end sustentável.

---

*Relatório gerado em 29/06/2026. Nenhum arquivo foi modificado.*
