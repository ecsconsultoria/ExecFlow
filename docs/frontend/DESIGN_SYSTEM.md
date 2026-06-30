# Design System — ExecFlow ERP

> **Versão:** 1.0 — Fundação
> **Arquivo CSS:** `app/static/css/tailwind.src.css`

---

## 1. Paleta de Cores

### Cores Semânticas

| Token | Tailwind | Uso |
|-------|----------|-----|
| **Primary** | `blue-600` / `blue-700` | Ações principais (Salvar, Criar, Novo) |
| **Success** | `emerald-600` / `emerald-700` | Aprovar, Faturar, Concluir, Pago |
| **Danger** | `red-600` / `red-700` | Excluir, Cancelar, Rejeitar |
| **Warning** | `amber-500` / `amber-600` | Atenção, Reabrir, Pendente |
| **Neutral** | `slate-600` / `slate-700` | PDF, Visualizar, Ações secundárias |
| **Info** | `blue-500` / `blue-600` | Links, informações |

### Cores de Módulo

| Módulo | Cor | Onde usar |
|--------|-----|----------|
| Quotes (RFQ) | `violet-600` | Botões, links, badges |
| Orders (SO) | `teal-600` | Botões, links, badges |
| Purchase Orders (PO) | `violet-600` | Botões, links, badges |
| Dispatch | `cyan-600` | Cards de status |
| Financial | `amber-500` | Ícones, destaques |

### Backgrounds

| Token | Tailwind | Uso |
|-------|----------|-----|
| Page BG | `bg-slate-100` / `dark:bg-slate-900` | Fundo da página |
| Card BG | `bg-white` / `dark:bg-slate-800` | Cards |
| Sidebar BG | `bg-slate-900` | Sidebar primário |
| Sidebar 2 BG | `bg-slate-800` | Sidebar secundário |

---

## 2. Tipografia

| Nível | Classe | Tamanho | Peso | Uso |
|-------|--------|---------|------|-----|
| KPI | `text-2xl font-extrabold` | 24px | 800 | Valores grandes (dashboard) |
| Título Página | `text-lg font-bold` | 18px | 700 | Título no header |
| Título Seção | `text-sm font-semibold` | 14px | 600 | `.section-title` |
| Corpo | `text-sm` | 14px | 400 | Texto padrão |
| Pequeno | `text-xs` | 12px | 400 | Labels, badges, tabelas |
| Caption | `text-[11px]` | 11px | 400 | Metadata, timestamps |
| Mono | `font-mono` | — | — | Valores monetários, códigos |

---

## 3. Espaçamentos

| Token | Valor | Uso |
|-------|-------|-----|
| Page padding | `p-6` (24px) | Padding do `<main>` |
| Section gap | `mb-6` (24px) | Entre seções |
| Card padding (form) | `p-6` (24px) | Formulários |
| Card padding (KPI) | `p-4` (16px) | Cards KPI |
| Card padding (detail) | `p-5` (20px) | Cards de detalhe |
| Grid gap | `gap-4` (16px) | Padrão de grid |
| Button gap | `gap-1.5` (6px) | Ícone + texto |
| Filter bar padding | `px-4 py-2` | Barra de filtros |

---

## 4. Breakpoints

| Nome | Largura | Prefixo |
|------|---------|---------|
| Mobile | < 640px | (default) |
| Tablet pequeno | 640px+ | `sm:` |
| Tablet | 768px+ | `md:` |
| Desktop | 1024px+ | `lg:` |
| Desktop largo | 1280px+ | `xl:` |

---

## 5. Componentes CSS

### Botões

```html
<button class="btn-primary btn-sm">Salvar</button>
<button class="btn-success btn-sm">Aprovar</button>
<button class="btn-danger btn-sm">Excluir</button>
<button class="btn-warning btn-sm">Reabrir</button>
<button class="btn-neutral btn-sm">PDF</button>
<button class="btn-ghost btn-sm">Cancelar</button>
<button class="btn-outline btn-sm">Voltar</button>
```

**Variants:** `primary` `success` `danger` `warning` `neutral` `ghost` `outline`
**Sizes:** `xs` `sm` `md` `lg` `icon` `icon-sm`

### Cards

```html
<div class="card p-5">...</div>
<div class="card-hover p-4">...</div>
```

### Inputs

```html
<input class="input">
<select class="select">
<label class="label">
<label class="label-sm">
```

### Tabelas

```html
<div class="table-card">
  <table class="table">...</table>
</div>
```

### Badges

```html
<span class="badge-success">Pago</span>
<span class="badge-warning">Pendente</span>
<span class="badge-danger">Vencido</span>
<span class="badge-info">Em Andamento</span>
<span class="badge-neutral">Rascunho</span>
```

### Modais

```html
<div class="modal-backdrop">
  <div class="modal-container">
    <div class="modal-header">...</div>
    <div class="modal-body">...</div>
    <div class="modal-footer">...</div>
  </div>
</div>
```

### Empty State

```html
<div class="empty-state">
  <div class="empty-state-icon"><i class="fa-solid fa-inbox"></i></div>
  <p class="empty-state-title">Nenhum registro encontrado</p>
</div>
```

### Timeline

```html
<ol class="timeline">
  <li class="timeline-item">
    <span class="timeline-dot"></span>
    <p class="timeline-title">Ação realizada</p>
    <p class="timeline-meta">01/01/2026 · Admin</p>
  </li>
</ol>
```

### Dropdown

```html
<div class="dropdown-menu">
  <a class="dropdown-item">Opção 1</a>
  <a class="dropdown-item">Opção 2</a>
</div>
```

---

## 6. Status do Sistema

| Status | Variant Badge | Classe |
|--------|--------------|--------|
| Pago / Aprovado / Concluído | `success` | `badge-success` |
| Pendente | `warning` | `badge-warning` |
| Vencido / Cancelado / Rejeitado | `danger` | `badge-danger` |
| Em Andamento / Aberto | `info` | `badge-info` |
| Rascunho / Excluído | `neutral` | `badge-neutral` |
