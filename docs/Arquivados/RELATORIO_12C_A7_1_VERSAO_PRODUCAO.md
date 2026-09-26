# RELATÓRIO ETAPA 12C-A7.1 — INVESTIGAÇÃO DE VERSÃO REAL EM PRODUÇÃO

**Data**: 29/08/2026 — **Modo**: SOMENTE investigação (leitura). **Nenhum commit, push, deploy, migration, alteração de código, banco, Render, env vars ou configuração foi realizada.**

---

## Resumo executivo

A produção **NÃO contém a evolução financeira** (Etapas 2 a 11B). O código publicado é o último commit enviado ao GitHub antes do início das Etapas: **`91d6c12` (27/08/2026 19:24)**. Toda a evolução financeira foi committada **localmente depois disso** (28/08 a 29/08) e **nunca foi enviada ao GitHub** (`git push` não executado) — portanto o Render nunca a recebeu.

**Classificação: C — PRODUÇÃO ESTÁ EM COMMIT DIFERENTE/ANTIGO.**

Não é problema de menu, template, RBAC, nem de deploy corrompido: o Render está servindo exatamente o último commit que foi enviado para a branch. A funcionalidade "falta" porque o código dela nunca chegou ao GitHub.

---

## 1. Branch local

`v3`

## 2. HEAD local

`a9950b0d03f37295f65f86e480d95fd1b72c6f0a`

## 3. Commit local

`a9950b0` — **29/08/2026 02:05** — `feat: UX de parcelas e baixas (Etapa 11B fase 2)`

Status: `## v3...origin/v3 [ahead 28]` — **28 commits locais à frente do remote**, mais 13 docs de relatório não commitados (12A/12B/12C — mantidos sem commit por instrução).

## 4. Repository local

`https://github.com/ecsconsultoria/ExecFlow.git` (remote `origin`)

- `origin/v3` (HEAD do GitHub): **`91d6c12`** — 27/08/2026 19:24 — `feat: badge de status premium (compartilhado) nas listas de SO e PO` ← **último commit enviado**
- `origin/main`: `e8fdd46` — 28/06/2026 — 282 commits atrás da `v3` (subset estrito; nada em `main` que não exista em `v3`)
- `git fetch --dry-run origin`: nenhuma novidade no remote → o GitHub está com `91d6c12` na `v3`, confirmado.

## 5. Branch do Render

⚠️ **Não confirmável diretamente deste ambiente** (sem acesso ao Dashboard do Render). Evidência indireta (seção 17) indica que a produção executa a **linha da branch `v3`**, não `main`. **Pendência: confirmar visualmente no Dashboard (Settings → Build & Deploy → Branch).**

## 6. Commit do Render (deployado)

⚠️ **Deploy ID/data/hora não acessíveis deste ambiente.** O commit efetivamente publicado foi determinado por **fingerprint HTTP** (seção 17): a produção responde de forma **consistente com `91d6c12`** (último commit pushed) — e, em todo caso, **necessariamente anterior à Etapa 0** (`d9cff09`, 28/08/2026 14:54), pois nenhum commit da evolução financeira está no GitHub.

## 7. Último deploy

- Último código enviado ao GitHub: `91d6c12`, **27/08/2026 19:24** (horário local).
- Se o auto-deploy do Render está ligado, o último deploy corresponde a esse push.
- **Confirmar no Dashboard**: Data/Commit do último deploy e status.

## 8. Comparação local × produção

| | Local (HEAD) | Produção |
|---|---|---|
| Commit | `a9950b0` (29/08 02:05) | `91d6c12` (27/08 19:24) — último pushed |
| Diferença | — | **28 commits atrás** (= toda a evolução financeira) |
| Etapas 2–11B | ✅ presentes | ❌ ausentes |
| Migrations | 16 arquivos (head `c4d2e9f0a1b5`) | 14 arquivos (head `f8a9c1e2d3b4`) |
| Templates financeiros | 13 | 4 |
| Rotas financeiras | 15 | 8 |

**A produção está exatamente onde o GitHub estava no fim do dia 27/08.** A evolução financeira (28 commits, 28–29/08) nunca saiu da máquina local.

## 9. Rotas esperadas (código local)

Blueprint `financial` (`/financial`, arquivo `app/blueprints/financial/routes.py`):

| Recurso | Rota | Endpoint | Introduzida em | Permissão |
|---|---|---|---|---|
| Lançamentos | `/financial/` | `financial.index` | anterior | `financial.view` |
| Contas a Pagar | `/financial/payables` | `financial.payables` | anterior | `financial.view` |
| Contas a Receber | `/financial/receivables` | `financial.receivables` | anterior | `financial.view` |
| Categorias Financeiras | `/financial/categories` (+new/edit/toggle) | `financial.categories` | `a9a4958` (Etapa 3A) | `financial.manage` |
| Centros de Custo | `/financial/cost-centers` (+new/edit/toggle) | `financial.cost_centers` | `a9a4958` (Etapa 3A) | `financial.manage` |
| Despesas | `/financial/expenses` (+new/edit/cancel) | `financial.expenses` | `929de99` (Etapa 3B) | `financial.view` |
| Fluxo de Caixa | `/financial/cash-flow` (+settings) | `financial.cash_flow` | `9b67f42` (Etapa 4) | `financial.view` |
| DRE | `/financial/dre` | `financial.dre` | `44bc827` (Etapa 5) | `financial.view` |

Commits por etapa (todos **não enviados** — commitados entre 28/08 15:31 e 29/08 02:05):

| Etapa | Commit | Data | O que entrega |
|---|---|---|---|
| 0 (checkpoint) | `d9cff09` | 28/08 14:54 | backup pré-evolução |
| 2 | `1fd1e6c` | 28/08 15:31 | unifica lógica financeira (faturamento) |
| 3A | `a9a4958` | 28/08 16:00 | **Categorias Financeiras + Centros de Custo** |
| 3B | `929de99` | 28/08 16:16 | **Despesas Gerais** |
| 4 | `9b67f42` | 28/08 16:25 | **Fluxo de Caixa Realizado** |
| 5 | `44bc827` | 28/08 16:35 | **DRE Gerencial por competência** |
| 8B | `8f8a0f3` | 28/08 18:07 | AP/AR unificados |
| 9B | `dafbc48` | 28/08 18:20 | Caixa completo (realizado+previsto+saldo) |
| 10B | `7ee81cb` | 28/08 18:35 | consolidação financeiro gerencial |
| 10D | `6b70e2f` | 28/08 19:40 | baixa parcial incremental |
| 11B F2 | `a9950b0` | 29/08 02:05 | UX de parcelas e baixas |

## 10. Rotas existentes em produção (probe HTTP GET, 29/08)

Somente leitura — nenhum POST, nenhum login, nenhum dado alterado.

| Rota | Status | Interpretação |
|---|---|---|
| `/` | 302 → `/auth/login?next=%2F` | raiz existe (dashboard protegido) |
| `/auth/login` | 200 | login público ok |
| `/financial/` | 302 → login | ✅ existe na produção |
| `/financial/payables` | 302 → login | ✅ existe |
| `/financial/receivables` | 302 → login | ✅ existe |
| `/financial/dre` | **404** | ❌ NÃO existe na produção |
| `/financial/cash-flow` | **404** | ❌ NÃO existe |
| `/financial/categories` | **404** | ❌ NÃO existe |
| `/financial/cost-centers` | **404** | ❌ NÃO existe |
| `/financial/expenses` | **404** | ❌ NÃO existe |
| `/reports/`, `/po/`, `/orders/`, `/quotes/`, `/dispatch/` | 302 | ✅ existem |

**Interpretação:** 302 = rota registrada no código publicado (exige login); 404 = rota não existe no código publicado. O padrão bate **exatamente** com o commit `91d6c12` (as 5 rotas financeiras novas das Etapas 3A–5 estão ausentes).

## 11. Templates envolvidos

`app/templates/financial/`:

| Template | HEAD local | `91d6c12` (produção) |
|---|---|---|
| `index.html` (Lançamentos) | ✅ com barra de atalhos | ✅ sem barra de atalhos |
| `form.html`, `payables.html`, `receivables.html` | ✅ | ✅ |
| `categories.html`, `category_form.html` | ✅ | ❌ não existe |
| `cost_centers.html`, `cost_center_form.html` | ✅ | ❌ |
| `expenses.html`, `expense_form.html` | ✅ | ❌ |
| `cash_flow.html`, `cash_flow_settings.html` | ✅ | ❌ |
| `dre.html` | ✅ | ❌ |

No `index.html` local (adicionado pelas Etapas 3A/3B/4/5) existe a barra de atalhos:

```html
<div class="mb-4 flex flex-wrap items-center gap-2">
  <a href="{{ url_for('financial.expenses') }}">Despesas</a>
  <a href="{{ url_for('financial.cash_flow') }}">Fluxo de Caixa</a>
  <a href="{{ url_for('financial.dre') }}">DRE</a>
  {% if has_perm('financial.manage') %}
  <a href="{{ url_for('financial.categories') }}">Categorias Financeiras</a>
  <a href="{{ url_for('financial.cost_centers') }}">Centros de Custo</a>
  {% endif %}
</div>
```

No `index.html` do commit publicado essa barra **não existe** — daí a tela de Lançamentos da produção não mostrar os botões, exatamente como o usuário observou.

## 12. Menu

- O menu principal é construído em `app/templates/base.html` (seções desktop e mobile).
- A seção financeira do menu é **idêntica** no commit publicado e no local: Contas a Pagar, Contas a Receber, Receitas, Despesas, Lançamentos — todas atrás de `{% if has_perm('financial.view') %}`.
- **DRE, Fluxo de Caixa, Categorias Financeiras e Centros de Custo nunca fizeram parte do menu principal** (em nenhuma das duas versões): por design, ficam como botões/atalhos na própria tela de Lançamentos (`financial/index.html`). Não há problema de RBAC nem de feature flag no menu.

## 13. Tela de Lançamentos

- Rota: `/financial/` → `financial.index` → template `app/templates/financial/index.html`.
- Blueprint: `financial` registrado com `url_prefix="/financial"` em `app/blueprints/__init__.py` (idêntico nas duas versões).
- **Por que os botões de DRE / Fluxo de Caixa / Categorias Financeiras / Centros de Custo não aparecem em produção:** resposta **A) os links não existem no código publicado** — a barra de atalhos foi adicionada nas Etapas 3A–5, todas em commits não enviados ao GitHub. Não é caso B (template não usado), não é caso C (RBAC), não é caso D (produção antiga *é* o caso — ver classificação), e não há outra causa.

## 14. RBAC

- `financial.view` — protege Lançamentos, AP, AR, Despesas, Caixa, DRE (decorator `@require_permission`).
- `financial.manage` — protege Categorias Financeiras e Centros de Custo (rotas e botões de atalho).
- Nenhum indício de que o RBAC esteja ocultando algo: o admin autenticado vê tudo que o código publicado contém. O problema é de **versão de código**, não de permissão.

## 15. Migrations

| | Produção (`91d6c12`) | Local (HEAD) |
|---|---|---|
| Arquivos em `migrations/versions/` | 14 | 16 |
| Head da cadeia | `f8a9c1e2d3b4` (faturado fields) | `c4d2e9f0a1b5` |
| Migrations da evolução financeira | ❌ ausentes | ✅ `a3c1f8d2e6b4` (financial categories/cost centers) e `c4d2e9f0a1b5` (expense link columns) |

- Migração executada ≠ código correto publicado (per o escopo da etapa): aqui **nem o código nem as migrations novas** estão publicados. O banco de produção não tem as tabelas/colunas financeiras das Etapas 3A/3B.

## 16. Causa provável

**A evolução financeira (Etapas 2–11B) nunca foi enviada ao GitHub.** Sequência verificada:

1. Último push para `origin/v3`: `91d6c12`, 27/08/2026 19:24.
2. Toda a evolução financeira foi committada localmente **depois** (28/08 14:54 → 29/08 02:05) — 28 commits.
3. Nenhum `git push` foi executado desde então (status: `ahead 28`; `git fetch --dry-run` confirma que o GitHub continua em `91d6c12`).
4. O Render (auto-deploy na `v3`) só recebe código via push → continua servindo `91d6c12`.
5. `91d6c12` não contém DRE, Fluxo de Caixa, Categorias Financeiras, Centros de Custo nem Despesas → a produção não os mostra. **Comportamento correto para o código publicado.**

A 11B Fase 2 (UX de parcelas/baixas) também não está em produção pelo mesmo motivo — mas o sintoma visível (telas financeiras ausentes) vem das Etapas 3A–5, anteriores a ela.

## 17. Evidências

1. `git status`: `## v3...origin/v3 [ahead 28]`; `origin/v3 = 91d6c12` (27/08 19:24).
2. `v3~28 == 91d6c12` — a evolução local assenta exatamente sobre o último push.
3. `git fetch --dry-run origin`: remote sem commits novos.
4. `git show 91d6c12:app/templates/financial/index.html` — sem a barra de atalhos.
5. `git show 91d6c12:app/blueprints/financial/routes.py` — apenas `/`, record CRUD, `/payables`, `/receivables`.
6. `git ls-tree 91d6c12 app/templates/financial/` — 4 templates (vs 13 locais).
7. `git ls-tree 91d6c12 migrations/versions/` — 14 arquivos (vs 16 locais).
8. Probe HTTP em `https://execflow-erp.onrender.com` (GET, somente leitura): `/financial/dre|cash-flow|categories|cost-centers|expenses` → **404**; `/financial/|payables|receivables` → 302.
9. Fingerprint de versão via rotas recentes: produção possui `receipt` (`d54cf08`, 13/08), `bulk-faturar`/`bulk-concluir` (`0cb2e95`/`7408763`, 10/08 e 25/08), `duplicate`/`reorder` (`1949fef`, 07/08) → produção está na linha `v3`, em commit ≥ `7408763` (25/08) e ≤ último push `91d6c12` (27/08) → consistente com `91d6c12`.
10. A produção **não** está na `main`: `main` (`e8fdd46`, 28/06) é anterior a `d54cf08`, cuja rota existe na produção.
11. Observação adicional (headers HTTP): o cookie de sessão da produção vem **sem atributo `Secure`** e a resposta sem `Strict-Transport-Security` — o que indica `SESSION_COOKIE_SECURE=1` não definido no Render (coerente com as pendências 12C seções 2–3). **Apenas registrado; nada alterado.**

## 18. O que NÃO foi alterado

Nada. Zero alterações em: código, banco, produção, Render, Environment Variables, Start Command, Procfile, branch. Nenhum commit, push, deploy, migration, restart, rollback. As únicas requisições HTTP feitas foram GET de leitura (páginas/rotas públicas, sem login, sem POST). Único artefato criado: este relatório.

## 19. Próximo passo recomendado (aguardando autorização — NÃO executar)

1. **Confirmar no Dashboard do Render** (visual, sem alterar): Repository, Branch, commit do último deploy, data/status — para fechar as seções 5–7.
2. Quando autorizado o deploy da evolução financeira, a ordem continua a da 12C seção 18: dump do PostgreSQL → env vars (`FLASK_ENV=production`, `SECRET_KEY`, `SESSION_COOKIE_SECURE=1`, uploads) → **push da `v3`** (é o push que faz o código chegar ao Render) → monitorar logs → smoke.
3. Os 13 docs de relatório não commitados podem ser commitados junto quando autorizado (mantidos sem commit por instrução anterior).

---

## CLASSIFICAÇÃO

# **C — PRODUÇÃO ESTÁ EM COMMIT DIFERENTE/ANTIGO**

Produção: `91d6c12` (27/08/2026). Local: `a9950b0` (29/08/2026). A diferença = 28 commits locais não enviados, contendo toda a evolução financeira (Etapas 2–11B). **Nada foi alterado. PARADO — aguardando autorização.**
