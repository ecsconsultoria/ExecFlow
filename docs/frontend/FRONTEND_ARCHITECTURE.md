# Arquitetura do Front-End — ExecFlow ERP V3

> **Data:** 29/06/2026
> **Stack:** Flask + Jinja2 + Tailwind CSS + Alpine.js + Chart.js + Font Awesome 6

---

## 1. Visão Geral

```
┌─────────────────────────────────────────────────────────┐
│                    base.html (shell)                    │
│  ┌──────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ Primary  │ │  Secondary   │ │       Main           │ │
│  │ Sidebar  │ │  Sidebar     │ │  ┌────────────────┐  │ │
│  │ 72px     │ │  240px       │ │  │  page_title    │  │ │
│  │ ícones   │ │  sub-itens   │ │  │  (header)      │  │ │
│  │          │ │              │ │  ├────────────────┤  │ │
│  │          │ │              │ │  │  content       │  │ │
│  │          │ │              │ │  │  (templates)   │  │ │
│  └──────────┘ └──────────────┘ │  └────────────────┘  │ │
│                                └──────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Camadas

### 2.1 CSS

| Camada | Arquivo | Responsabilidade |
|--------|---------|-----------------|
| **Design System** | `tailwind.src.css` → `tailwind.css` | Componentes base (`.btn`, `.card`, `.badge`, `.input`, `.table`, `.modal`) |
| **Tailwind Utils** | Compilado via JIT | Classes utilitárias |
| **Font Awesome** | `vendor/fontawesome/all.min.css` | Ícones |
| **Inline `<style>`** | Templates (a eliminar) | Estilos pontuais — devem migrar para o Design System |

### 2.2 JavaScript

| Camada | Arquivo | Responsabilidade |
|--------|---------|-----------------|
| **Alpine.js** | `vendor/alpine.min.js` | Reatividade: sidebar, dropdowns, modais, drawer mobile |
| **Chart.js** | `vendor/chartjs.min.js` | Gráficos (dashboard) |
| **Inline `<script>`** | Templates (a unificar) | Lógica de negócio: AJAX, CRUD, validação |

### 2.3 Templates

| Camada | Diretório | Responsabilidade |
|--------|-----------|-----------------|
| **Shell** | `base.html` | Layout principal, sidebars, header, footer |
| **Páginas** | `templates/*/` | Conteúdo específico de cada módulo |
| **Componentes** | `templates/components/` | Macros Jinja2 reutilizáveis (NOVO) |
| **Partials** | `templates/*/_*.html` | Fragmentos incluídos via `{% include %}` |

---

## 3. Fluxo de Renderização

```
Request HTTP
  │
  ▼
Flask Route → render_template('modulo/pagina.html')
  │
  ▼
Jinja2: pagina.html extends base.html
  │
  ├── {% block page_title %} → Header
  ├── {% block content %}    → Corpo da página
  └── {% block modals %}     → Modais
  │
  ▼
base.html
  ├── Primary Sidebar (Jinja2 + Alpine.js)
  ├── Secondary Sidebar (Alpine.js x-show)
  ├── Header (page_title block)
  ├── Flash Messages (Alpine.js auto-dismiss)
  ├── Content (content block)
  ├── Footer
  └── Mobile Drawer (Alpine.js)
```

---

## 4. Sistema de Componentes

### 4.1 Macros Jinja2 (Novo — `templates/components/`)

```
components/
├── button.html       → {{ btn(label, href, variant, size) }}
├── badge.html        → {{ badge(label, variant) }}
├── card.html         → {% call card(title) %}...{% endcall %}
├── input.html        → {{ input(name, label) }} / {{ select() }} / {{ textarea() }}
├── table.html        → {% call table_card() %}...{% endcall %} / {{ empty_state() }}
├── modal.html        → {% call modal(id, title) %}...{% endcall %}
└── page_header.html  → {% call page_header(title) %}...{% endcall %}
```

### 4.2 Como usar

```jinja2
{% extends "base.html" %}
{% from "components/button.html" import btn with context %}
{% from "components/badge.html" import badge with context %}
{% from "components/card.html" import card with context %}

{% block content %}
  {% call page_header('Meu Módulo', subtitle='Resumo do mês') %}
    {{ btn('Novo', href=url_for('modulo.new'), variant='primary', icon='fa-plus') }}
  {% endcall %}

  {% call card(title='Lista de Itens', padding='p-4') %}
    <table class="table">...</table>
  {% endcall %}
{% endblock %}
```

---

## 5. Responsividade

| Breakpoint | Largura | Comportamento |
|-----------|---------|---------------|
| Default | < 640px | Mobile: drawer menu, 1 coluna, tabelas com scroll |
| `sm:` | ≥ 640px | 2 colunas, botões com texto |
| `md:` | ≥ 768px | Tabelas mostram mais colunas |
| `lg:` | ≥ 1024px | Dual sidebar visível, grids multi-coluna |
| `xl:` | ≥ 1280px | Layouts largos (a implementar) |

---

## 6. Próximas Fases

| Fase | Escopo | Status |
|------|--------|--------|
| ✅ Fase 1 | Design System + Componentes | Concluída |
| ⬜ Fase 2 | Responsividade (overflow-x-auto, breakpoints) | Pendente |
| ⬜ Fase 3 | Substituir componentes inline por macros | Pendente |
| ⬜ Fase 4 | Unificar JavaScript (mover para main.js) | Pendente |
| ⬜ Fase 5 | Remover CSS duplicado (`.fi`, `.lbl`) | Pendente |
