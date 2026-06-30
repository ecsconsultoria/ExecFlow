# Biblioteca de Componentes — ExecFlow ERP

> **Local:** `app/templates/components/`
> **Tecnologia:** Macros Jinja2 (zero dependências externas)

---

## Índice de Componentes

| Componente | Arquivo | Tipo |
|-----------|---------|------|
| Button | `button.html` | Macro |
| Badge | `badge.html` | Macro |
| Card | `card.html` | Caller Macro |
| Input / Select / Textarea | `input.html` | Macro |
| Table + EmptyState | `table.html` | Macro + Caller |
| Modal | `modal.html` | Caller Macro |
| PageHeader | `page_header.html` | Caller Macro |

---

## 1. Button (`button.html`)

Botão unificado que substitui 16 padrões diferentes de cores.

### Parâmetros

| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `label` | str | — | Texto do botão |
| `href` | str | None | Se fornecido, renderiza `<a>` em vez de `<button>` |
| `variant` | str | `'primary'` | `primary` `success` `danger` `warning` `neutral` `ghost` `outline` |
| `size` | str | `'sm'` | `xs` `sm` `md` `lg` `icon` `icon-sm` |
| `icon` | str | None | Classe Font Awesome (ex: `'fa-plus'`) |
| `type` | str | `'button'` | Tipo HTML (submit, button, reset) |
| `onclick` | str | None | Handler inline |
| `form` | str | None | ID do form para submit externo |

### Exemplos

```jinja2
{% from "components/button.html" import btn with context %}

{# Link #}
{{ btn('Novo Orçamento', href=url_for('quotes.new'), variant='primary', icon='fa-plus') }}

{# Submit #}
{{ btn('Salvar', variant='success', type='submit', icon='fa-check') }}

{# Danger #}
{{ btn('Excluir', variant='danger', icon='fa-trash', onclick='confirmDelete()') }}

{# Ícone apenas #}
{{ btn(None, variant='ghost', size='icon', icon='fa-pen', title='Editar') }}

{# Outline #}
{{ btn('Cancelar', variant='outline', onclick='closeModal()') }}
```

---

## 2. Badge (`badge.html`)

Badge de status unificado.

### Parâmetros

| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `label` | str | — | Texto do badge |
| `variant` | str | `'neutral'` | `success` `warning` `danger` `info` `neutral` `violet` `teal` |

### Exemplos

```jinja2
{% from "components/badge.html" import badge with context %}

{{ badge('Pago', variant='success') }}
{{ badge('Pendente', variant='warning') }}
{{ badge('Cancelado', variant='danger') }}
{{ badge('Rascunho', variant='neutral') }}
```

---

## 3. Card (`card.html`)

Card com título opcional. Usa caller pattern (conteúdo entre tags).

### Parâmetros

| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `title` | str | None | Título do card |
| `padding` | str | `'p-5'` | Padding (p-4, p-5, p-6) |
| `class` | str | `''` | Classes extras |

### Exemplo

```jinja2
{% from "components/card.html" import card with context %}

{% call card(title='Detalhes do Cliente', padding='p-5') %}
  <dl class="grid grid-cols-2 gap-4">
    <div><dt>Nome</dt><dd>João Silva</dd></div>
    <div><dt>Email</dt><dd>joao@email.com</dd></div>
  </dl>
{% endcall %}
```

---

## 4. Input / Select / Textarea (`input.html`)

Inputs padronizados que substituem `.fi` e estilos inline.

### Parâmetros

| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `name` | str | — | Nome do campo |
| `label` | str | None | Label (se None, não renderiza label) |
| `type` | str | `'text'` | Tipo HTML |
| `value` | str | `''` | Valor inicial |
| `placeholder` | str | `''` | Placeholder |
| `required` | bool | False | Obrigatório |
| `class` | str | `''` | Classes extras no wrapper |
| `id` | str | None | ID (default: name) |

### Exemplos

```jinja2
{% from "components/input.html" import input, select, textarea with context %}

{{ input('email', label='E-mail', type='email', required=True) }}
{{ input('amount', label='Valor', placeholder='0,00') }}  {# auto input-mono #}
{{ select('status', label='Status', options=[('pago','Pago'),('pendente','Pendente')]) }}
{{ textarea('obs', label='Observações', rows=4) }}
```

---

## 5. Table + EmptyState (`table.html`)

Wrapper de tabela com scroll horizontal e estado vazio.

### Parâmetros

| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `class` | str | `''` | Classes extras no table-card |
| `message` | str | `'Nenhum registro...'` | Mensagem do empty state |
| `icon` | str | `'fa-inbox'` | Ícone Font Awesome |

### Exemplo

```jinja2
{% from "components/table.html" import table_card, empty_state with context %}

{% if items %}
  {% call table_card() %}
    <table class="table">
      <thead><tr><th>Nome</th><th>Status</th></tr></thead>
      <tbody>
        {% for item in items %}
        <tr><td>{{ item.name }}</td><td>{{ badge(item.status) }}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  {% endcall %}
{% else %}
  {{ empty_state('Nenhum item encontrado.') }}
{% endif %}
```

---

## 6. Modal (`modal.html`)

Modal Alpine.js reutilizável.

### Parâmetros

| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `id` | str | — | ID único |
| `title` | str | — | Título do modal |
| `show_var` | str | `'false'` | Variável Alpine que controla visibilidade |
| `size` | str | `'md'` | `sm` `md` `lg` `xl` |

### Exemplo

```jinja2
{% from "components/modal.html" import modal with context %}
{% from "components/button.html" import btn with context %}

{% call modal(id='confirm-delete', title='Confirmar Exclusão', show_var='showDelete') %}
  <p class="text-sm text-slate-600 mb-4">Tem certeza que deseja excluir?</p>
  <div class="flex justify-end gap-2">
    {{ btn('Cancelar', variant='outline', onclick='showDelete=false') }}
    {{ btn('Excluir', variant='danger', type='submit', form='delete-form') }}
  </div>
{% endcall %}
```

---

## 7. PageHeader (`page_header.html`)

Cabeçalho de página com título e botões de ação.

### Parâmetros

| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `title` | str | — | Título da página |
| `subtitle` | str | None | Subtítulo opcional |

### Exemplo

```jinja2
{% from "components/page_header.html" import page_header with context %}
{% from "components/button.html" import btn with context %}

{% call page_header('Orçamentos', subtitle='3 orçamentos este mês') %}
  {{ btn('Novo Orçamento', href=url_for('quotes.new'), variant='primary', icon='fa-plus') }}
{% endcall %}
```

---

## Guia de Uso nas Próximas Fases

1. **Importar macros** no topo de cada template: `{% from "components/button.html" import btn with context %}`
2. **Substituir botões inline** por `{{ btn(...) }}`
3. **Substituir badges** por `{{ badge(...) }}`
4. **Substituir cards** por `{% call card(...) %}`
5. **Substituir formulários** por `{{ input(...) }}` / `{{ select(...) }}`
6. **Substituir modais** por `{% call modal(...) %}`
7. **Substituir tabelas** por `{% call table_card() %}`
