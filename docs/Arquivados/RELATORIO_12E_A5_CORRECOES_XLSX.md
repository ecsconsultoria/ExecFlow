# RELATÓRIO ETAPA 12E-A5 — CORREÇÕES FINAIS DOS RELATÓRIOS XLSX

**Data**: 29/08/2026 — **Modo**: correções LOCAIS autorizadas (2 itens da 12E-A4). **Nenhuma outra refatoração, nenhuma alteração de dados, banco, migration, commit, push ou deploy.**

---

## Resumo executivo

As duas ressalvas técnicas da 12E-A4 foram corrigidas: (1) largura das colunas monetárias no XLSX agora considera o **valor formatado** ("R$ 5.000,00") com mínimo de 14 caracteres; (2) o total misto do relatório de Lançamentos foi substituído por **totais por tipo + resultado líquido**. Valores continuam numéricos com formato R$. Regressão: **208 passed / 6 failed** (mesmas 6 pré-existentes, zero novas).

**Classificação: A — CORREÇÕES APROVADAS** (permanece pendente, de fora deste escopo, a conferência visual humana com logo — ressalva nº 3 da A4).

---

## 1. Problema da largura

Na A4: a largura das colunas monetárias era calculada pelo **valor bruto** (`5000.0` → 7 caracteres) e não pelo **formato exibido** pelo Excel ("R$ 5.000,00" → 12–13 caracteres), podendo cortar valores grandes (#####).

## 2. Correção

`app/services/report_xlsx.py` → `_auto_widths()`:
- Colunas em `money_cols`: largura calculada por `f"R$ {abs(v):,.2f}"` (comprimento do valor FORMATADO + 2), **mínimo de 14**.
- Colunas em `date_cols`: mínimo de 12 ("dd/mm/aaaa").
- O valor da célula **permanece NUMBER** com `number_format` monetário — apenas a largura mudou.

## 3. Problema dos totais (Lançamentos)

A linha única "TOTAIS" somava Receitas + Custos + Despesas indistintamente — total misto com interpretação financeira ambígua (presente no XLSX e no PDF — documentado na A4).

## 4. Correção

`app/blueprints/financial/routes.py` → novo helper `_index_totals(rows)` (apresentação apenas; mesmos dados do `_index_export_rows`):

- **TOTAL RECEITAS** · **TOTAL CUSTOS** · **TOTAL DESPESAS** (linhas separadas)
- **RESULTADO LÍQUIDO = Receitas − Custos − Despesas**
- Aplicado ao **XLSX** (4 linhas de totais destacadas) e ao **PDF** (mesmas 4 linhas, última destacada) — mantendo TELA/PDF/XLSX consistentes. O builder `build_report_xlsx` passou a aceitar `totals` como lista de linhas (retrocompatível com linha única).

## 5. Arquivos alterados

| Arquivo | Mudança |
|---|---|
| `app/services/report_xlsx.py` | `_auto_widths` (formato visual + mínimos); `_norm_totals` + suporte a múltiplas linhas de totais |
| `app/blueprints/financial/routes.py` | `_index_totals()`; `index_export_pdf`/`index_export_xlsx` com totais por tipo + líquido |
| `tests/test_financial_exports_etapa12e.py` | +2 testes (largura/número/formato; totais por tipo/líquido/sem total misto, PDF e XLSX) |

## 6. Testes

- `test_xlsx_money_column_width_and_numeric`: largura ≥ 14 para valores R$ 5.000,00 / 800,00 / 100.000,00 / 1.000.000,00; células numéricas com formato "R$" ✓
- `test_lancamentos_totals_by_type`: sem "TOTAIS"; TOTAL RECEITAS 5.000 / CUSTOS 2.000 / DESPESAS 1.000 / LÍQUIDO 2.000 (XLSX numérico) e rótulos no PDF ✓

## 7. Regressão

**208 passed / 6 failed** — mesmas 6 falhas pré-existentes (`test_decorators_and_audit.py`), **zero falhas novas** (206 + 2 novos testes).

## 8. Validação dos XLSX regenerados (todos os 6 + amostras)

| XLSX | Larguras money | Células R$ numéricas |
|---|---|---|
| DRE | B: 14,0 | 10 ✓ |
| Caixa | F: 14,0 | 10 ✓ |
| AR | D: 16,0 · E: 14,0 · F: 14,0 | 6 ✓ |
| AP | D/E/F: 14,0 | 12 ✓ |
| Despesas | G: 14,0 | 1 ✓ |
| Lançamentos | F: 15,0 | 53 ✓ |

Lançamentos (dados reais do banco dev): TOTAL RECEITAS **120.000** · TOTAL CUSTOS **30.000** · TOTAL DESPESAS **0** · RESULTADO LÍQUIDO **90.000** (= 120.000 − 30.000 ✓) — **sem "TOTAIS" misto**. Freeze panes, autofilter, datas e formatos inalterados em todos.

## 9. Impacto

- Nenhuma regra financeira alterada — os totais são agregação de apresentação sobre os MESMOS registros já exibidos (mesma fonte `_index_export_rows`).
- Nenhum dado criado/alterado (gerações read-only; banco dev com contagens idênticas).
- Demais relatórios (DRE, Caixa, AR, AP, Despesas) intactos — apenas a largura das colunas monetárias mudou (melhor legibilidade).

## 10. Problemas remanescentes

- **Nenhum** dentro deste escopo. Permanece pendente, de fora do escopo: conferência visual humana das amostras com logo configurado (ressalva nº 3 da A4) e a decisão de commit/push/deploy do pacote 12E completo.

---

# **Classificação: A — CORREÇÕES APROVADAS**

**Nenhum commit, push, deploy, migration ou alteração de dados. PARADO — aguardando autorização.**
