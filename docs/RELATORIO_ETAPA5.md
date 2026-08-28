# ETAPA 5 — RELATÓRIO FINAL (DRE Gerencial por Competência)

**Data**: 28/08/2026 — **Commit**: ver `git log -1` (sem push — deploy segue o fluxo normal da branch `v3`)

---

## A. Backup

`backup/DB_V2_pre-etapa5-20260828.db` — criado antes de qualquer alteração (API nativa do SQLite). Backups anteriores (Etapas 0, 3A, 3B, 4) **não sobrescritos**.

## B. Checkpoint

Branch `v3`, commit de entrada `9b67f42`, working tree limpo, alembic head `c4d2e9f0a1b5`, `integrity_check` ok. Tag: **`v3-pre-etapa5-dre-20260828`**.

## C. Migration

**NENHUMA** — a DRE é 100% leitura/consulta sobre as estruturas existentes. Schema inalterado; sem rollback necessário.

## D. Schema

Inalterado.

## E. Arquivos modificados

- **Novo**: `app/services/dre_service.py` (funções centrais), `app/templates/financial/dre.html`, `tests/test_dre_etapa5.py`, `docs/RELATORIO_ETAPA5.md`
- **Alterados**: `app/blueprints/financial/routes.py` (rota `/financial/dre` + visão mensal), `app/templates/financial/index.html` (link DRE), `app/blueprints/dashboard/routes.py` + `app/templates/dashboard/index.html` (faixa DRE resumida)

## F. Fonte da Receita

`Orders` efetivamente faturadas (regra da Etapa 2: status faturado/concluído **com** `invoiced_at`), competência = **data do faturamento**. Recebimento NÃO altera a receita (testado). Receitas manuais sem `order_payment:` aparecem como "Outras Receitas / Não Classificadas" (hoje: 0 registros).

## G. Fonte dos Custos

`PurchaseOrder` válida (fora rascunho/cancelado/excluído) **vinculada a SO não excluído**, valor `computed_total`. PO sem SO = **CUSTO NÃO CLASSIFICADO** (fora da margem bruta, listado em pendências — ex.: PO-260602-005, não alterada).

## H. Fonte das Despesas

`FinancialRecord type='expense'` não cancelada (pendente E paga entram — DRE ≠ Caixa), competência = `emission_date`, agrupada pela categoria-raiz do catálogo 3A (Despesas Operacionais / Administrativas / Pessoal / Impostos / Financeiras / Não Classificadas).

## I. Regra de competência (ponto crítico — seção 7)

Prioridade implementada em `po_competence_date()`:
1. `service_date` dos itens da PO (data real de execução);
2. `delivery_date` da PO (data operacional confiável);
3. somente se não houver informação melhor: `created_at` (marcado como **fallback** e listado na tela, sem alterar nada).

`created_at` NUNCA é usado automaticamente quando existe data melhor. Despesa sem `emission_date` = **COMPETÊNCIA INDETERMINADA** (fora da DRE, listada). Nenhuma data é inventada.

## J. Receita

Testado: faturado + não recebido → entra (R$ 1.500 em 2 SOs faturados de agosto); aberto/concluído-sem-fatura → fora; pagamento não muda o valor.

## K. Custos Diretos

Testado: PO julho com `service_date` agosto → custo de **agosto**; PO sem datas operacionais → julho (fallback sinalizado); rascunho/cancelada/sem-SO → fora; PO sem SO listada como não classificada (R$ 13.500,00 do caso real).

## L. Margem Bruta

Receita − Custos Diretos (Despesas Gerais **fora** — regra da Etapa 2 preservada). Testado: 1000 − 0 = 1000.

## M. Despesas Gerais

Por competência (emissão), agrupadas por categoria-raiz; cancelada fora; pendente entra (testado: 200 paga + 100 pendente = 300 no grupo Administrativas).

## N. Resultado Operacional

Margem Bruta − Despesas Gerais. Testado: 1000 − 300 = 700.

## O. Centros de Custo

Exibidos no detalhamento das despesas (via `cost_center_id`); isolados por `company_id`.

## P. Filtros

Este mês / mês anterior / trimestre / ano / personalizado — sempre pela **competência** (invoiced_at, service_date/delivery/created_at, emission_date). Visão mensal Jan–Dez com totais (bucket em Python, sem N+1).

## Q. Detalhamento

Somente leitura, expansível: Receita → SO (+data faturamento +valor); Custos → PO (+SO +competência +fornecedor +valor); Despesas → descrição (+categoria +centro +fornecedor +valor). Nenhuma edição de origem pela DRE.

## R. Testes

`tests/test_dre_etapa5.py` — 4 testes: receita (regra + pagamento não altera); custos + competência (prioridade + fallback + não classificados); despesas/margem/resultado; multiempresa + tela somente leitura (sem vazamento, POST 405).

## S. Regressão

Etapa 2 (7): ✓ · Etapa 3A (8): ✓ · Etapa 3B (12): ✓ · Etapa 4 (7): ✓ · Etapa 5 (4): ✓ — suíte completa com **as mesmas 6 falhas pré-existentes** (`test_decorators_and_audit.py`), nenhuma nova.

## T. Performance

Queries únicas por bloco (sem N+1): receita em 1 query; custos em 1 query (POs do período por competência); despesas em 1 query; visão mensal com fetch único do ano + bucket em Python; zero cálculo no template (tudo nas funções centrais).

## U. Integridade

`PRAGMA integrity_check` = ok. Alembic head inalterado (`c4d2e9f0a1b5`). Sem migration nesta etapa.

## V. Dados históricos

Comparação atual × backup pré-Etapa 5: **todas as tabelas protegidas IDÊNTICAS**.
- SO alterados: **ZERO** · POs alterados: **ZERO** · Pagamentos alterados: **ZERO** · FinancialRecords históricos alterados: **ZERO**
- PO-260602-005 e FR id45: **não tocados** · 27 FRs soft-deletados: **não tocados** (fora da DRE, informado na tela) · V4: **não tocado** · Registros de teste no banco real: **ZERO**

## W. Pendências

1. PO-260602-005 (R$ 13.500,00) — classificação como despesa geral (decisão com autorização explícita — altera dado).
2. 27 FRs soft-deletados — restauração decidida em etapa futura.
3. FR id45 (R$ 200,00 custo_operacional manual) — vínculo com catálogo.
4. Dump do PostgreSQL de produção — pendente desde a Etapa 0 (obrigatório antes do próximo deploy).
5. Unificar a faixa de KPIs do Dashboard (regra Etapa 2 por `created_at` para custo) com a competência da DRE — decisão de produto; hoje coexistem rotuladas de forma distinta.
6. Saldo inicial configurável + Caixa Previsto completo (Etapa 4).
7. Aposentadoria do V4.

## X. Recomendação para Etapa 6

1. **Deploy** do conjunto Etapas 2–5 (com dump de produção antes) e validação em produção.
2. **Reconciliação final autorizada**: restauração dos 27 FRs (decisão de negócio), classificação do PO-260602-005 e do FR id45.
3. **Aposentadoria do V4** (tabelas vazias) com migration de remoção ou marcação deprecated.
4. Configuração de saldo inicial + Caixa Previsto completo.

**Nada disso foi implementado nesta etapa.**

🟢 **ETAPA 5 CONCLUÍDA — DRE VALIDADA**
