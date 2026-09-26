# Biblioteca de Componentes — ExecFlow ERP

> **Local:** `app/templates/components/`
> **Tecnologia:** Macros Jinja2 + 1 componente CSS incluído via `{% include %}` (zero dependências externas)

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
| Export Buttons | `export_buttons.html` | Macro |
| Payment Summary | `payment_summary.html` | Macro |
| Status Badge CSS | `status_badge_style.html` | CSS (include) |
| Timeline de Baixas | `timeline.html` | Macro |

---

## 1. Button (`button.html`)

Botão unificado que substitui 16 padrões diferentes de cores.

### Parâmetros

| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `label` | str | — | Texto do botão |
| `href` | str | None | Se fornecido, renderiza `<a>` em vez de `<button>` |
| `variant` | str | `'primary'` | `primary` `success` `danger` `warning` `neutral` `ghost` `outline` |
| `size` | str | `'sm'` | `xs` `sm` `md` `lg` `icon` |
| `icon` | str | None | Classe Font Awesome (ex: `'fa-plus'`) |
| `type` | str | `'button'` | Tipo HTML (submit, button, reset) |
| `title` | str | None | Tooltip HTML (atributo `title`) |
| `onclick` | str | None | Handler inline |
| `form` | str | None | ID do form para submit externo |

> **Nota:** a classe CSS `.btn-icon-sm` existe e é usada diretamente (ex.: botão de fechar do `modal.html`), mas **não** é um `size` da macro — os sizes suportados são apenas `xs`, `sm`, `md`, `lg` e `icon`.

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

**`input(name, label=None, type='text', value='', placeholder='', required=False, class='', id=None)`:**

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

**`select(name, label=None, options=[], selected='', class='', id=None)`:**

| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `name` | str | — | Nome do campo |
| `label` | str | None | Label (se None, não renderiza label) |
| `options` | list | `[]` | Pares `(valor, rótulo)` das opções |
| `selected` | str | `''` | Valor pré-selecionado |
| `class` | str | `''` | Classes extras no wrapper |
| `id` | str | None | ID (default: name) |

### Exemplos

```jinja2
{% from "components/input.html" import input, select, textarea with context %}

{{ input('email', label='E-mail', type='email', required=True) }}
{{ input('amount', label='Valor', placeholder='0,00') }}  {# auto input-mono #}
{{ select('status', label='Status', options=[('pago','Pago'),('pendente','Pendente')]) }}
{{ textarea('obs', label='Observações', rows=3) }}
```

> **Nota:** `textarea` aceita `rows` (default `3`), `value`, `placeholder`, `class` e `id`.

---

## 5. Table + EmptyState (`table.html`)

Wrapper de tabela com scroll horizontal e estado vazio.

### Parâmetros

`table_card` e `empty_state` são **duas macros separadas**.

**`table_card(class='')`** — wrapper da tabela com scroll horizontal:

| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `class` | str | `''` | Classes extras no table-card |

**`empty_state(message='Nenhum registro encontrado.', icon='fa-inbox')`** — estado vazio; `message` e `icon` pertencem a **esta** macro, não ao `table_card`:

| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `message` | str | `'Nenhum registro encontrado.'` | Mensagem do empty state |
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

## 8. Export Buttons (`export_buttons.html`)

Botões de exportação PDF/XLSX das telas financeiras (Etapa 12E).

### Assinatura

```jinja2
{% from "components/export_buttons.html" import export_buttons with context %}

{{ export_buttons(pdf_url=url_for('financial.dre_export_pdf', **filtros),
                  xlsx_url=url_for('financial.dre_export_xlsx', **filtros)) }}
```

### Parâmetros

| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `pdf_url` | str | None | URL do PDF. **Opcional** — o botão PDF só aparece se a URL existir |
| `xlsx_url` | str | None | URL do XLSX. **Opcional** — o botão XLSX só aparece se a URL existir |

### Comportamento

- **Desktop:** ícone + texto (`PDF` / `XLSX`).
- **Mobile:** somente ícone (aria-label/tooltip).
- Estilo ghost/neutro — ação de exportação, não navegação.
- Uso atual nas 8 telas financeiras: `financial/index.html`, `dre.html`, `cash_flow.html`, `receivables.html`, `payables.html`, `expenses.html`, `categories.html` (só XLSX) e `cost_centers.html` (só XLSX).

---

## 9. Payment Summary (`payment_summary.html`)

Resumo financeiro de parcela (Etapa 11B) — Valor → Recebido → Saldo → Status.

> ⚠️ **Somente apresentação.** A macro consome dados já calculados pelo backend. Ela **NÃO** cria regra financeira, **NÃO** altera valores financeiros e **NÃO** substitui serviços financeiros.

### Assinatura

```jinja2
{% from 'components/payment_summary.html' import payment_summary %}

{{ payment_summary(amount, paid_amount, status_label, status_variant,
                   due_date=None, paid_at=None) }}
```

### Parâmetros

| Param | Tipo | Default | Descrição |
|-------|------|---------|-----------|
| `amount` | float | — | Valor da parcela |
| `paid_amount` | float | — | Valor já recebido |
| `status_label` | str | — | Rótulo do status (ex.: `'QUITADA'`) |
| `status_variant` | str | — | Variante do badge (`success`, `warning`, `neutral`) |
| `due_date` | datetime | None | Vencimento (opcional) |
| `paid_at` | datetime | None | Último recebimento (opcional) |

### Estados utilizados atualmente

| Estado | Critério | Variante |
|--------|----------|----------|
| QUITADA | pago = total | `success` |
| PARCIAL | 0 < pago < total | `warning` |
| ABERTA | nada recebido | `neutral` |

### Dependências

- Filtro Jinja `currency` (registrado no app factory).
- Macro `badge` (importada internamente).

Uso atual: `orders/detail.html` e `purchase_orders/detail.html`.

---

## 10. Status Badge CSS (`status_badge_style.html`)

> ⚠️ **Isto NÃO é uma macro.** É um componente CSS incluído via `{% include %}` — não usar `{% from ... import %}`.

### Uso

```jinja2
{% include "components/status_badge_style.html" %}  {# no bloco extra_head #}
```

Depois aplicar as classes:

```html
<span class="status-badge status-badge--<variante>">
  <span class="status-badge__dot"></span>LABEL
</span>
```

### Variantes existentes

| Variante | Significado |
|----------|-------------|
| `open` | Aberto |
| `invoiced` | Faturado |
| `completed` | Concluído |
| `pending` | Pendente |
| `cancelled` | Cancelado |

- Versões para **light e dark mode** (prefixo `.dark`).
- Badge de largura fixa (104px), caixa alta, dot indicativo.
- **Para novos status, adicione apenas uma nova variante CSS** neste arquivo.

Uso atual: `quotes/index.html`, `orders/index.html`, `purchase_orders/index.html`.

---

## 11. Timeline de Baixas (`timeline.html`)

Histórico de baixas de parcelas (Etapa 11B).

> ⚠️ **Atenção:** arquivo `timeline.html`, mas a macro se chama **`baixa_timeline`** — não existe macro chamada `timeline`.

### Assinatura

```jinja2
{% from 'components/timeline.html' import baixa_timeline %}

{{ baixa_timeline(history) }}
```

### Parâmetro `history`

| Param | Tipo | Descrição |
|-------|------|-----------|
| `history` | dict | Estrutura do `payment_history_service` (por parcela); a macro não renderiza nada se vazio |

Estrutura de `history`:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `entries[]` | list | Eventos de baixa |
| `entries[].at` | datetime | Data/hora da baixa |
| `entries[].user` | str | Usuário que executou |
| `entries[].value` | float | Valor da baixa (pode ser `None` em registros pré-10D) |
| `entries[].balance_after` | float | Saldo após a baixa (pode ser `None`) |
| `pre_10d` | bool | Histórico anterior à Etapa 10D |
| `consistent` | bool | Histórico consistente com o total recebido |
| `final_paid` | float | Total recebido comprovado |

### Comportamento

- Eventos **pré-10D sem valor individual** exibem aviso — **nunca inventar valores**.
- Inconsistência entre histórico e total exibe alerta e **preserva os dados originais** (revisão manual).
- Rodapé com `TOTAL RECEBIDO` (valor comprovado da parcela quando `pre_10d`).

Dependência (somente leitura): `app/services/payment_history_service.py` — **não alterar**.

Uso atual: `orders/detail.html` e `purchase_orders/detail.html`.

---

## Guia de Uso nas Próximas Fases

1. **Importar macros** no topo de cada template: `{% from "components/button.html" import btn with context %}`
2. **Substituir botões inline** por `{{ btn(...) }}`
3. **Substituir badges** por `{{ badge(...) }}`
4. **Substituir cards** por `{% call card(...) %}`
5. **Substituir formulários** por `{{ input(...) }}` / `{{ select(...) }}`
6. **Substituir modais** por `{% call modal(...) %}`
7. **Substituir tabelas** por `{% call table_card() %}`
8. **Substituir cabeçalhos de página** por `{% call page_header(...) %}`
9. **Substituir botões de exportação** das telas financeiras por `{{ export_buttons(...) }}`
10. **Substituir resumos de parcela** por `{{ payment_summary(...) }}` (somente apresentação)
11. **Incluir o badge de status premium** via `{% include "components/status_badge_style.html" %}` (CSS — não é macro)
12. **Substituir históricos de baixa** por `{{ baixa_timeline(history) }}` (macro `baixa_timeline`, arquivo `timeline.html`)
